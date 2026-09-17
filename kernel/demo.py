"""Offline demonstration using simulated episodes and real local test files."""
from __future__ import annotations
from pathlib import Path
import json
from .storage import Store, new_id
from .validation import ROOT, validate
from runtime.evidence import utcnow
from runtime.lab_gate import release_gate

def make_plan(index: int) -> dict:
    stamp=utcnow();uid=new_id('demo')
    return {'schema_version':'0.1.0','run_id':f'run_{uid}','episode_id':f'episode_{uid}','skill':'g-ground',
    'intent':{'intent_id':f'intent_{uid}','statement':f'完成第 {index} 份本地说明草稿','scope':'离线模拟目录','deadline':None,'source':'user','created_at':stamp},
    'completion_contract':{'contract_id':f'contract_{uid}','version':1,'scope':'仅确认本地示例文件存在及版本一致',
      'criteria':[{'criterion_id':'file_created','statement':'本轮说明草稿文件存在并与登记哈希一致','accepted_types':['file'],'minimum_level':'E1','verification':'local_artifact_sha256','max_age_seconds':86400}], 'created_at':stamp},
    'next_action':{'action_id':f'action_{uid}','action':'创建本地示例说明文件','actor':'agent','timebox_min':10,'blocked_by':[],
      'stop_when':'文件生成且本地核验通过','side_effect':'local_write','requires_confirmation':True},
    'simulated':True,'idempotency_key':uid}

def run_demo(output: str | Path) -> dict:
    out=Path(output).expanduser().resolve()
    out.mkdir(parents=True,exist_ok=True)
    dbpath=out/'demo.sqlite'
    if dbpath.exists():
        raise ValueError('Demo database already exists. Select a new --out directory; existing data is not overwritten.')
    artifacts=out/'artifacts';artifacts.mkdir(exist_ok=True)
    with Store(dbpath) as store:
        runs=[];episodes=[];outcomes=[]
        for i in range(1,4):
            plan=make_plan(i);rid=store.create_run(plan);runs.append(rid);episodes.append(plan['episode_id'])
            store.transition(rid,'READY')
            store.snapshot(rid,'本轮将生成可核对的本地示例文件',confidence=None,reasons=['这是隔离的机械演示。'],
                           failure_conditions=['写文件失败或文件发生变化'],observation_window='本次演示结束')
            store.transition(rid,'ACTIVE',confirmed=True)
            # A plan alone cannot pass; this checks the waiting state first.
            waiting=store.verify(rid)
            assert waiting['status']=='WAITING_EVIDENCE'
            file=artifacts/f'offer-{i}.md'
            file.write_text(f'# 合成示例 {i}\n\n首日活动：选择一个任务，提交草稿，得到反馈。\n\n本文件未发布、未收款，不能证明需求成立。\n',encoding='utf-8')
            store.attach_file(rid,'file_created',file,artifacts)
            outcomes.append(store.verify(rid))
        store.add_rule({'rule_id':new_id('rule'),'rule':'草稿生成后核对所登记版本，避免提交旧文件。',
          'status':'hypothesis','source_run_ids':[runs[0]],'confidence':'low','applies_when':'需要提交本地文件',
          'does_not_apply_when':'无文件的探索任务','recheck_condition':'在后续独立任务中观察是否减少版本错误',
          'valid_until':None,'counterexamples':[]})
        store.add_cluster({'cluster_id':new_id('cluster'),'task_statement':'创建本地说明草稿','episode_ids':episodes,'run_ids':runs,
          'maturity':'R1','stable_steps':['创建草稿','登记文件版本','核对文件存在'], 'variants':[],
          'near_misses':['同一文件多次修改不计为多次独立任务'],'next_validation':'在真实且授权的新任务中试用清单',
          'automation_authorized':False})
        exported=store.export()
    (out/'private-export.json').write_text(json.dumps(exported,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    gate=release_gate({'baseline_hash':'a'*64,'candidate_hash':'b'*64,'actual_model_runs':False,'sealed_holdout':False,
         'same_environment':True,'critical_regressions':0,'failure_case_improved':False,'holdout_improved':False,
         'within_budget':True,'human_approved':False,'rollback_available':True,'sample_count':0})
    for name in ['g-ground','g-real','g-ship','g-review','g-repeat','g-lab']:
        sample=json.loads((ROOT/'examples'/f'{name}.json').read_text())
        validate('Envelope',sample)
    report={'mode':'offline_simulation','actual_llm_calls':0,'external_actions':0,
      'local_verified_runs':sum(o['status']=='VERIFIED' for o in outcomes),'run_ids':runs,
      'six_example_envelopes_schema_valid':True,'lab_gate':gate,
      'limitations':['六个业务示例是预写样例，未由模型生成。','E1 核验只证明文件存在和版本一致。',
                     '未发布、未收款、未观察真实用户。','没有完成模型效果评估或真正的独立留出测试。']}
    (out/'demo-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report
