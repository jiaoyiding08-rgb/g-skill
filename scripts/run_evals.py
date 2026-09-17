"""Run six offline fixture checks, or explicitly authorized text-model tests without Node."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from adapters.promptfoo.offline_provider import call_api as fixture
from adapters.promptfoo.provider import call_api as live
from adapters.promptfoo.assertions import get_assert
from adapters.promptfoo.generate_config import make_config

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['offline','live'],default='offline')
    p.add_argument('--limit',type=int,default=3);p.add_argument('--skill');p.add_argument('--out',required=True)
    a=p.parse_args()
    if not 1<=a.limit<=72:raise SystemExit('--limit must be 1..72')
    out=Path(a.out)
    if out.exists():raise SystemExit('Output exists; choose a new file.')
    rows=[]
    if a.mode=='offline':
        for skill in ['g-ground','g-real','g-ship','g-review','g-repeat','g-lab']:
            response=fixture('',{}, {'vars':{'skill':skill}})
            grade=get_assert(response.get('output'),{})
            rows.append({'case':skill,'mode':'fixture','mechanical_grade':grade,'semantic_grade':'not_run'})
    else:
        for test in make_config('dev',a.limit,a.skill)['tests']:
            response=live(test['vars']['input_json'],{}, {})
            grade=get_assert(response['output'],{'vars':test['vars']}) if 'output' in response else {'pass':False,'score':0,'reason':response.get('error','No output')}
            rows.append({'case':test['description'],'response':response,'mechanical_grade':grade,'semantic_grade':'pending_human'})
            if 'error' in response:break
    report={'mode':a.mode,'model_effectiveness_validated':False,'results':rows}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{len(rows)} checks; see {out}. Semantic/model effectiveness is not established.')
    return 0 if all(r['mechanical_grade']['pass'] for r in rows) else 1
if __name__=='__main__':raise SystemExit(main())
