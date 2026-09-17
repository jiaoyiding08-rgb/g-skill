from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from kernel.validation import validate, ProtocolError, ROOT, MASTER
from kernel.router import route
from runtime.handoff import check_handoff
from runtime.lab_gate import release_gate
from adapters.promptfoo.provider import build_messages, call_api, execution_schema
from adapters.promptfoo.assertions import get_assert
from adapters.promptfoo.offline_provider import call_api as offline
from adapters.promptfoo.generate_config import make_config
from jsonschema import Draft202012Validator
import yaml


def route_context(**kw):
    c={'requested_skill':None,'task_type':'action','missing_critical_fact':False,'hard_risk':False,
       'artifact_ready':False,'has_outcome':False,'has_snapshot':False,'independent_episodes':0,
       'authorized_scope':True,'maintainer_authorized':False,'budget_exhausted':False}
    c.update(kw);return c


def release_report(**kw):
    r={'baseline_hash':'a'*64,'candidate_hash':'b'*64,'actual_model_runs':True,'sealed_holdout':True,
       'same_environment':True,'critical_regressions':0,'failure_case_improved':True,'holdout_improved':True,
       'within_budget':True,'human_approved':True,'rollback_available':True,'sample_count':30}
    r.update(kw);return r


class RoutingTests(unittest.TestCase):
    def test_scope_required(self):self.assertEqual(route(route_context(authorized_scope=False))['decision'],'GET_SCOPE')
    def test_budget_stops(self):self.assertEqual(route(route_context(budget_exhausted=True))['decision'],'STOP')
    def test_ordinary_question_not_coerced(self):self.assertEqual(route(route_context(task_type='other'))['decision'],'OUT_OF_SCOPE')
    def test_maintenance_needs_authorization(self):self.assertEqual(route(route_context(task_type='skill_maintenance'))['decision'],'GET_MAINTAINER_APPROVAL')
    def test_explicit_lab_also_needs_authorization(self):self.assertEqual(route(route_context(requested_skill='g-lab'))['decision'],'GET_MAINTAINER_APPROVAL')
    def test_risk_checked_before_action(self):self.assertEqual(route(route_context(hard_risk=True))['decision'],'REVIEW_RISK')
    def test_explicit_selection_preserved(self):self.assertEqual(route(route_context(requested_skill='g-review'))['skill'],'g-review')
    def test_six_declared_routes(self):
        for kind,name in [('action','ground'),('validation','real'),('delivery','ship'),('review','review'),('repetition','repeat'),('skill_maintenance','lab')]:
            with self.subTest(kind=kind):self.assertEqual(route(route_context(task_type=kind,maintainer_authorized=True))['skill'],'g-'+name)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.p={'target':'g-real','parent_run_id':'run_parent','reason':'test assumption','known_facts':['草稿已生成'],
                'unresolved':['用户是否理解'], 'evidence_ids':['ev_a'],'allowed_scope':'current_project',
                'requires_confirmation':True,'depth':1}
        self.args={'current_scope':'current_project','known_run_ids':{'run_parent'},'known_evidence_ids':{'ev_a'},'history':['g-ground']}
    def test_valid_does_not_execute(self):
        r=check_handoff(self.p,**self.args);self.assertTrue(r['accepted']);self.assertFalse(r['executed'])
    def test_scope_cannot_expand(self):
        self.p['allowed_scope']='whole_computer'
        with self.assertRaises(ProtocolError):check_handoff(self.p,**self.args)
    def test_parent_must_exist(self):
        self.p['parent_run_id']='invented'
        with self.assertRaises(ProtocolError):check_handoff(self.p,**self.args)
    def test_evidence_must_exist(self):
        self.p['evidence_ids']=['invented']
        with self.assertRaises(ProtocolError):check_handoff(self.p,**self.args)
    def test_depth_must_match(self):
        self.p['depth']=0
        with self.assertRaises(ProtocolError):check_handoff(self.p,**self.args)
    def test_cycle_stops(self):
        self.p['target']='g-ground'
        with self.assertRaises(ProtocolError):check_handoff(self.p,**self.args)
    def test_max_three_handoffs(self):
        self.args['history']=['g-ground','g-ship','g-review'];self.p['depth']=3
        with self.assertRaises(ProtocolError):check_handoff(self.p,**self.args)


class LabTests(unittest.TestCase):
    def test_positive_report_only_recommends_canary(self):
        r=release_gate(release_report());self.assertEqual(r['decision'],'CANARY_RECOMMENDED');self.assertFalse(r['release_executed'])
    def test_simulation_cannot_replace_model_runs(self):self.assertEqual(release_gate(release_report(actual_model_runs=False))['decision'],'CONTINUE_EXPERIMENT')
    def test_no_blind_holdout_blocks(self):self.assertIn('sealed_holdout',release_gate(release_report(sealed_holdout=False))['blockers'])
    def test_critical_regression_blocks(self):self.assertIn('critical_regressions',release_gate(release_report(critical_regressions=1))['blockers'])
    def test_missing_approval_blocks(self):self.assertIn('human_approved',release_gate(release_report(human_approved=False))['blockers'])
    def test_same_hash_blocks(self):self.assertEqual(release_gate(release_report(candidate_hash='a'*64))['decision'],'CONTINUE_EXPERIMENT')
    def test_no_samples_blocks(self):self.assertIn('no_samples',release_gate(release_report(sample_count=0))['blockers'])
    def test_missing_field_rejected(self):
        r=release_report();r.pop('sealed_holdout')
        with self.assertRaises(ProtocolError):release_gate(r)
    def test_string_true_is_not_boolean(self):
        with self.assertRaises(ProtocolError):release_gate(release_report(actual_model_runs='true'))
    def test_boolean_is_not_sample_count(self):
        with self.assertRaises(ProtocolError):release_gate(release_report(sample_count=True))
    def test_invalid_hash_rejected(self):
        with self.assertRaises(ProtocolError):release_gate(release_report(candidate_hash='fake'))


class AdapterTests(unittest.TestCase):
    def prompt(self):return json.dumps({'skill':'g-ground','input':'请做一个本地草稿','context':{'capability_mode':'prompt_only'}})
    def test_network_default_off(self):
        with patch.dict(os.environ,{},clear=True),patch('adapters.promptfoo.provider.build_opener') as network:
            self.assertIn('error',call_api(self.prompt(),{},{}));network.assert_not_called()
    def test_invalid_endpoint_does_not_call(self):
        with patch.dict(os.environ,{'G_ALLOW_NETWORK':'1','G_CHAT_COMPLETIONS_URL':'http://example.com/v1','G_MODEL':'unused'},clear=True),patch('adapters.promptfoo.provider.build_opener') as network:
            self.assertIn('error',call_api(self.prompt(),{},{}));network.assert_not_called()
    def test_url_credentials_rejected(self):
        with patch.dict(os.environ,{'G_ALLOW_NETWORK':'1','G_CHAT_COMPLETIONS_URL':'https://secret:pass@example.com/v1','G_MODEL':'unused'},clear=True):
            self.assertIn('error',call_api(self.prompt(),{},{}))
    def test_no_implicit_model(self):
        with patch.dict(os.environ,{'G_ALLOW_NETWORK':'1','G_CHAT_COMPLETIONS_URL':'https://example.com/v1'},clear=True):
            self.assertIn('G_MODEL',call_api(self.prompt(),{}, {})['error'])
    def test_grading_not_in_model_messages(self):
        m=build_messages(self.prompt());self.assertEqual(len(m),2)
        for message in m:
            self.assertNotIn('acceptable_decisions',message['content'])
            self.assertNotIn('evals/grading/g-ground.json',message['content'])
        self.assertEqual(set(json.loads(m[1]['content'])),{'input','context'})
    def test_selected_execution_schema_accepts_each_example(self):
        for skill in ['g-ground','g-real','g-ship','g-review','g-repeat','g-lab']:
            schema=execution_schema(skill)
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(json.loads((ROOT/'examples'/f'{skill}.json').read_text()))
            self.assertNotIn('EvalRubric',schema['$defs'])
            self.assertNotIn('EvalCase',schema['$defs'])
    def test_grading_field_rejected(self):
        d=json.loads(self.prompt());d['expected']='ACT_NOW'
        with self.assertRaises(ValueError):build_messages(json.dumps(d))
    def test_skill_path_traversal_rejected(self):
        d=json.loads(self.prompt());d['skill']='../../secret'
        with self.assertRaises(ValueError):build_messages(json.dumps(d))
    def test_malformed_assertion_fails(self):self.assertFalse(get_assert('not json',{})['pass'])
    def test_wrong_case_decision_fails(self):
        d=json.loads((ROOT/'examples/g-ground.json').read_text());self.assertFalse(get_assert(d,{'vars':{'case_id':'g-ground-04'}})['pass'])
    def test_offline_provider_uses_fixed_examples(self):
        out=offline('ignored',{}, {'vars':{'skill':'g-ground'}})
        self.assertEqual(json.loads(out['output'])['skill'],'g-ground');self.assertTrue(get_assert(out['output'],{})['pass'])
    def test_offline_unknown_skill_fails(self):self.assertIn('error',offline('',{}, {'vars':{'skill':'../secrets'}}))
    def test_live_config_is_bounded(self):
        c=make_config();self.assertEqual(len(c['tests']),3);self.assertEqual(c['prompts'],['{{input_json}}'])
        for t in c['tests']:
            body=json.loads(t['vars']['input_json']);self.assertEqual(set(body),{'skill','input','context'})
    def test_holdout_not_called_sealed(self):
        c=json.loads((ROOT/'evals/registry.json').read_text());self.assertEqual(c['sealed_holdout'],0);self.assertEqual(c['real_behavioral_cases'],0)


class PackageTests(unittest.TestCase):
    def test_schema_itself_valid(self):Draft202012Validator.check_schema(MASTER)
    def test_self_contained_refs_and_frontmatter(self):
        for d in sorted((ROOT/'skills').glob('g-*')):
            with self.subTest(skill=d.name):
                raw=(d/'SKILL.md').read_text();front=yaml.safe_load(raw.split('---',2)[1])
                self.assertEqual(front['name'],d.name);self.assertTrue(front['description']);self.assertLess(len(raw.splitlines()),500)
                self.assertEqual((d/'references/kernel-contract.md').read_bytes(),(ROOT/'kernel/CONTRACT.md').read_bytes())
                self.assertEqual((d/'references/protocol.schema.json').read_bytes(),(ROOT/'kernel/schemas/protocol.schema.json').read_bytes())
                self.assertFalse((d/'evals/grading').exists())
    def test_installer_dryrun_then_install_then_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'skills';cmd=[sys.executable,str(ROOT/'scripts/install_skills.py'),'--target',str(target)]
            dry=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(dry.returncode,0);self.assertFalse(target.exists())
            installed=subprocess.run(cmd+['--apply'],capture_output=True,text=True);self.assertEqual(installed.returncode,0,installed.stderr)
            self.assertEqual(len(list(target.iterdir())),5);self.assertFalse((target/'g-lab').exists())
            for name in ['ground','real','ship','review','repeat']:
                self.assertTrue((target/f'g-{name}'/'references/protocol.schema.json').is_file())
            again=subprocess.run(cmd+['--apply'],capture_output=True,text=True);self.assertEqual(again.returncode,2)
    def test_installer_lab_optin(self):
        with tempfile.TemporaryDirectory() as d:
            r=subprocess.run([sys.executable,str(ROOT/'scripts/install_skills.py'),'--target',d,'--include-lab','--apply'],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr);self.assertTrue((Path(d)/'g-lab/SKILL.md').exists())
    def test_no_original_dbskill_files_vendored(self):
        self.assertFalse(any(p.name.startswith('dbs-') for p in ROOT.rglob('*')))


class CaseSchemaTests(unittest.TestCase):
    """The following generated tests validate test data; they do not run any model."""


def _case_test(kind, data):
    def test(self):validate(kind,data)
    return test

for _path in sorted((ROOT/'evals/inputs').glob('*.json')):
    for _c in json.loads(_path.read_text()):
        setattr(CaseSchemaTests,'test_input_'+_c['id'].replace('-','_'),_case_test('EvalCase',_c))
for _path in sorted((ROOT/'evals/grading').glob('*.json')):
    for _c in json.loads(_path.read_text()):
        setattr(CaseSchemaTests,'test_rubric_'+_c['id'].replace('-','_'),_case_test('EvalRubric',_c))
for _path in sorted((ROOT/'examples').glob('g-*.json')):
    setattr(CaseSchemaTests,'test_example_'+_path.stem.replace('-','_'),_case_test('Envelope',json.loads(_path.read_text())))
