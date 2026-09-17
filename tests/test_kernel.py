from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from kernel.demo import make_plan, run_demo
from kernel.storage import Store, new_id
from kernel.validation import validate, ProtocolError, ROOT
from runtime.evidence import check, file_digest, scoped_file


def sample(name):
    return json.loads((ROOT/'examples'/f'{name}.json').read_text())


class ProtocolTests(unittest.TestCase):
    def test_unknown_schema(self):
        with self.assertRaises(ProtocolError): validate('Unknown',{})

    def test_unknown_field_rejected(self):
        d=sample('g-ground');d['invented']=True
        with self.assertRaises(ProtocolError):validate('Envelope',d)

    def test_model_cannot_sign_own_writes(self):
        d=sample('g-ground');d['writes_applied']=True
        with self.assertRaises(ProtocolError):validate('Envelope',d)

    def test_action_needs_contract(self):
        d=sample('g-ground');d['completion_contract']=None
        with self.assertRaises(ProtocolError):validate('Envelope',d)

    def test_one_material_question(self):
        d=sample('g-ground');d['decision']='GET_ONE_FACT';d['questions']=[]
        with self.assertRaises(ProtocolError):validate('Envelope',d)
        d['questions']=['具体要交付哪一份文件？'];validate('Envelope',d)

    def test_question_limit(self):
        d=sample('g-ground');d['questions']=['a','b','c','d']
        with self.assertRaises(ProtocolError):validate('Envelope',d)

    def test_unknown_skill_decision(self):
        d=sample('g-ground');d['decision']='VERIFIED'
        with self.assertRaises(ProtocolError):validate('Envelope',d)

    def test_empty_contract(self):
        d=make_plan(1);d['completion_contract']['criteria']=[]
        with self.assertRaises(ProtocolError):validate('RunPlan',d)

    def test_duplicate_criterion(self):
        d=make_plan(1);d['completion_contract']['criteria']*=2
        with self.assertRaises(ProtocolError):validate('RunPlan',d)

    def test_hash_cannot_prove_e2(self):
        d=make_plan(1);d['completion_contract']['criteria'][0]['minimum_level']='E2'
        with self.assertRaises(ProtocolError):validate('RunPlan',d)

    def test_external_action_requires_confirmation(self):
        d=make_plan(1);d['next_action']['side_effect']='payment';d['next_action']['requires_confirmation']=False
        with self.assertRaises(ProtocolError):validate('RunPlan',d)

    def test_naive_datetime_rejected(self):
        d=make_plan(1);d['intent']['created_at']='2026-09-18T01:00:00'
        with self.assertRaises(ProtocolError):validate('RunPlan',d)

    def test_no_prospective_comparison_without_snapshot(self):
        d=sample('g-review');d['decision']='COMPARE'
        with self.assertRaises(ProtocolError):validate('Envelope',d)

    def test_new_rule_cannot_be_adopted_without_trial(self):
        d=sample('g-review');d['decision']='RULE_CANDIDATE'
        with self.assertRaises(ProtocolError):validate('Envelope',d)

    def test_ship_requires_known_artifact_and_gates(self):
        d=sample('g-ship');d['decision']='SHIP_NOW';d['details']['artifact_ref']=None
        with self.assertRaises(ProtocolError):validate('Envelope',d)
        d['details']['artifact_ref']='example://draft';d['details']['hard_gate']='pass';d['details']['core_gate']='pass'
        validate('Envelope',d)

    def test_fix_requires_timebox(self):
        d=sample('g-ship');d['next_action']['timebox_min']=None
        with self.assertRaises(ProtocolError):validate('Envelope',d)

    def test_hypothesis_requires_observation(self):
        d=sample('g-real');d['decision']='SUPPORTED';d['details']['observations']=[]
        with self.assertRaises(ProtocolError):validate('Envelope',d)

    def test_repeat_requires_cluster(self):
        d=sample('g-repeat');d['details']['cluster']=None
        with self.assertRaises(ProtocolError):validate('Envelope',d)

    def test_repeat_count_cannot_be_inflated(self):
        d=sample('g-repeat');d['details']['independent_count']=99
        with self.assertRaises(ProtocolError):validate('Envelope',d)

    def test_confirmed_repeat_two_distinct_episodes(self):
        d=sample('g-repeat')['details']['cluster'];d['episode_ids']=['one']
        with self.assertRaises(ProtocolError):validate('RepeatCluster',d)

    def test_automation_needs_authorization(self):
        d=sample('g-repeat')['details']['cluster'];d['maturity']='R4';d['automation_authorized']=False
        with self.assertRaises(ProtocolError):validate('RepeatCluster',d)

    def test_release_without_eval_rejected(self):
        d=sample('g-lab');d['decision']='STABLE_RECOMMENDED'
        with self.assertRaises(ProtocolError):validate('Envelope',d)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.art=self.root/'artifacts';self.art.mkdir()
        self.store=Store(self.root/'records.sqlite')
        self.plan=make_plan(1);self.rid=self.store.create_run(self.plan)

    def tearDown(self):
        self.store.close();self.tmp.cleanup()

    def activate(self):
        self.store.transition(self.rid,'READY');self.store.transition(self.rid,'ACTIVE',confirmed=True)

    def attach(self):
        f=self.art/'result.md';f.write_text('local test')
        e=self.store.attach_file(self.rid,'file_created',f,self.art)
        return f,e

    def rule(self):
        return {'rule_id':new_id('rule'),'rule':'登记文件版本。','status':'hypothesis','source_run_ids':[self.rid],
                'confidence':'low','applies_when':'交付文件','does_not_apply_when':'无产物探索','recheck_condition':'后续十次检查',
                'valid_until':None,'counterexamples':[]}

    def cluster(self, plans):
        return {'cluster_id':new_id('cluster'),'task_statement':'做本地草稿','episode_ids':[p['episode_id'] for p in plans],
                'run_ids':[p['run_id'] for p in plans],'maturity':'R1','stable_steps':['创建文件'],
                'variants':[],'near_misses':['同一文件重复编辑'],'next_validation':'试一个新实例','automation_authorized':False}

    def test_new_run_is_draft(self):self.assertEqual(self.store.run(self.rid)['state'],'DRAFT')

    def test_idempotent_create(self):
        self.assertEqual(self.store.create_run(self.plan),self.rid)
        self.assertEqual(len(self.store.export()['action_runs']),1)

    def test_idempotency_conflict(self):
        d=deepcopy(self.plan);d['next_action']['action']='other'
        with self.assertRaises(ProtocolError):self.store.create_run(d)

    def test_immutable_contract(self):
        d=make_plan(2);d['completion_contract']=deepcopy(self.plan['completion_contract'])
        d['completion_contract']['scope']='changed'
        with self.assertRaises(ProtocolError):self.store.create_run(d)
        self.assertEqual(len(self.store.export()['action_runs']),1)

    def test_immutable_intent(self):
        d=make_plan(2);d['intent']=deepcopy(self.plan['intent']);d['intent']['statement']='changed'
        with self.assertRaises(ProtocolError):self.store.create_run(d)

    def test_direct_verified_forbidden(self):
        for state in ['VERIFIED','ACTIVE']:
            with self.assertRaises(ProtocolError):self.store.transition(self.rid,state,confirmed=True)

    def test_ready_cannot_verify(self):
        self.store.transition(self.rid,'READY')
        with self.assertRaises(ProtocolError):self.store.verify(self.rid)

    def test_start_confirmation(self):
        self.store.transition(self.rid,'READY')
        with self.assertRaises(ProtocolError):self.store.transition(self.rid,'ACTIVE')

    def test_blocked_plan_cannot_start(self):
        d=make_plan(2);d['next_action']['blocked_by']=['await approval'];rid=self.store.create_run(d)
        self.store.transition(rid,'READY')
        with self.assertRaises(ProtocolError):self.store.transition(rid,'ACTIVE',confirmed=True)

    def test_missing_evidence_waits(self):
        self.activate();self.assertEqual(self.store.verify(self.rid)['status'],'WAITING_EVIDENCE')

    def test_artifact_can_satisfy_narrow_e1_contract(self):
        self.activate();self.attach();o=self.store.verify(self.rid)
        self.assertEqual(o['status'],'VERIFIED');self.assertTrue(o['simulated']);validate('Outcome',o)

    def test_verified_outcome_needs_every_check(self):
        self.activate();self.attach();o=self.store.verify(self.rid);o['checks'][0]['passed']=False
        with self.assertRaises(ProtocolError):validate('Outcome',o)

    def test_file_change_invalidates_on_recheck(self):
        self.activate();f,_=self.attach();self.store.verify(self.rid);f.write_text('changed')
        self.assertEqual(self.store.verify(self.rid)['status'],'WAITING_EVIDENCE')

    def test_removed_file_invalidates_on_recheck(self):
        self.activate();f,_=self.attach();self.store.verify(self.rid);f.unlink()
        self.assertEqual(self.store.verify(self.rid)['status'],'WAITING_EVIDENCE')

    def test_evidence_revocation_invalidates(self):
        self.activate();_,e=self.attach();self.store.verify(self.rid);self.store.revoke_evidence(e['evidence_id'])
        self.assertEqual(self.store.run(self.rid)['state'],'WAITING_EVIDENCE')
        self.assertEqual(self.store.verify(self.rid)['status'],'WAITING_EVIDENCE')

    def test_unknown_criterion(self):
        self.activate();f=self.art/'f';f.write_text('x')
        with self.assertRaises(ProtocolError):self.store.attach_file(self.rid,'unknown',f,self.art)

    def test_draft_cannot_attach(self):
        f=self.art/'f';f.write_text('x')
        with self.assertRaises(ProtocolError):self.store.attach_file(self.rid,'file_created',f,self.art)

    def test_no_manual_or_external_verifier_simulation(self):
        d=make_plan(2);c=d['completion_contract']['criteria'][0]
        c['verification']='external_state';c['minimum_level']='E2';c['accepted_types']=['file','system_record']
        rid=self.store.create_run(d);self.store.transition(rid,'READY');self.store.transition(rid,'ACTIVE',confirmed=True)
        f=self.art/'f';f.write_text('a screenshot is not an order receipt')
        self.store.attach_file(rid,'file_created',f,self.art)
        self.assertEqual(self.store.verify(rid)['status'],'WAITING_EVIDENCE')

    def test_all_criteria_required(self):
        d=make_plan(2);c=deepcopy(d['completion_contract']['criteria'][0]);c['criterion_id']='second';d['completion_contract']['criteria'].append(c)
        rid=self.store.create_run(d);self.store.transition(rid,'READY');self.store.transition(rid,'ACTIVE',confirmed=True)
        f=self.art/'f';f.write_text('x');self.store.attach_file(rid,'file_created',f,self.art)
        self.assertEqual(self.store.verify(rid)['status'],'WAITING_EVIDENCE')
        self.store.attach_file(rid,'second',f,self.art);self.assertEqual(self.store.verify(rid)['status'],'VERIFIED')

    def test_snapshot_is_prospective_and_immutable(self):
        kw={'confidence':None,'reasons':['test'],'failure_conditions':[],'observation_window':'today'}
        s=self.store.snapshot(self.rid,'file exists',**kw);validate('JudgmentSnapshot',s)
        with self.assertRaises(ProtocolError):self.store.snapshot(self.rid,'changed',**kw)

    def test_snapshot_cannot_be_backfilled(self):
        self.activate()
        with self.assertRaises(ProtocolError):self.store.snapshot(self.rid,'predicted',confidence=.9,reasons=[],failure_conditions=[],observation_window='today')

    def test_parking_does_not_reset_snapshot_clock(self):
        self.activate();self.store.transition(self.rid,'PARKED');self.store.transition(self.rid,'READY')
        with self.assertRaises(ProtocolError):self.store.snapshot(self.rid,'predicted',confidence=None,reasons=[],failure_conditions=[],observation_window='today')

    def test_rule_requires_existing_run(self):
        r=self.rule();r['source_run_ids']=['no_such_run']
        with self.assertRaises(ProtocolError):self.store.add_rule(r)

    def test_rule_adoption_needs_approval(self):
        r=self.rule();r['status']='adopted'
        with self.assertRaises(ProtocolError):self.store.add_rule(r)
        self.store.add_rule(r,approved=True)

    def test_real_and_simulated_clusters_separated(self):
        p=make_plan(2);p['simulated']=False;self.store.create_run(p)
        with self.assertRaises(ProtocolError):self.store.add_cluster(self.cluster([self.plan,p]))

    def test_false_episode_ids_rejected(self):
        p=make_plan(2);self.store.create_run(p);c=self.cluster([self.plan,p]);c['episode_ids'][0]='invented'
        with self.assertRaises(ProtocolError):self.store.add_cluster(c)

    def test_same_episode_edits_not_confirmed_repeat(self):
        p=make_plan(2);p['episode_id']=self.plan['episode_id'];self.store.create_run(p)
        c=self.cluster([self.plan,p]);c['episode_ids']=[p['episode_id']]
        with self.assertRaises(ProtocolError):self.store.add_cluster(c)

    def test_plans_alone_do_not_count_as_repeated_action(self):
        p=make_plan(2);self.store.create_run(p)
        with self.assertRaises(ProtocolError):self.store.add_cluster(self.cluster([self.plan,p]))

    def test_template_requires_verified_sources(self):
        self.activate();p=make_plan(2);self.store.create_run(p)
        self.store.transition(p['run_id'],'READY');self.store.transition(p['run_id'],'ACTIVE',confirmed=True)
        c=self.cluster([self.plan,p]);c['maturity']='R2'
        with self.assertRaises(ProtocolError):self.store.add_cluster(c)

    def test_backend_does_not_enable_automation(self):
        p=make_plan(2);self.store.create_run(p);c=self.cluster([self.plan,p]);c['maturity']='R4';c['automation_authorized']=True
        with self.assertRaises(ProtocolError):self.store.add_cluster(c)

    def test_export_has_all_registered_data_classes(self):
        out=self.store.export();self.assertEqual(out['privacy'],'private_export')
        for key in ['action_runs','completion_contracts','skill_versions','eval_cases','eval_runs']:
            self.assertIn(key,out)

    def test_delete_requires_confirmation(self):
        with self.assertRaises(ProtocolError):self.store.delete_run(self.rid)

    def test_delete_cascades_derived_records_but_not_user_file(self):
        self.activate();f,_=self.attach();self.store.verify(self.rid);self.store.add_rule(self.rule())
        p=make_plan(2);self.store.create_run(p);self.store.transition(p['run_id'],'READY');self.store.transition(p['run_id'],'ACTIVE',confirmed=True);self.store.add_cluster(self.cluster([self.plan,p]))
        self.store.delete_run(self.rid,confirmed=True)
        out=self.store.export()
        self.assertEqual(len(out['action_runs']),1)
        for key in ['evidence','outcomes','learned_rules','repeat_clusters']:
            self.assertEqual(out[key],[])
        self.assertTrue(f.exists());self.assertEqual(self.store.db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_database_permission_private(self):
        if os.name=='posix':self.assertEqual(self.store.path.stat().st_mode & 0o777,0o600)

    def test_database_symlink_rejected(self):
        link=self.root/'link.sqlite';link.symlink_to(self.store.path)
        with self.assertRaises(ProtocolError):Store(link)

    def test_sql_foreign_keys_on(self):
        self.assertEqual(self.store.db.execute('PRAGMA foreign_keys').fetchone()[0],1)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.allowed=self.root/'allowed';self.allowed.mkdir()
        self.f=self.allowed/'a';self.f.write_text('a');self.store=Store(self.root/'db.sqlite')
        self.p=make_plan(1);self.rid=self.store.create_run(self.p);self.store.transition(self.rid,'READY');self.store.transition(self.rid,'ACTIVE',confirmed=True)
        self.e=self.store.attach_file(self.rid,'file_created',self.f,self.allowed);self.c=self.p['completion_contract']['criteria'][0];self.r=self.store.run(self.rid)

    def tearDown(self):self.store.close();self.tmp.cleanup()

    def test_scope_escape(self):
        f=self.root/'secret';f.write_text('x')
        with self.assertRaises(ProtocolError):file_digest(f,self.allowed)

    def test_symlink_escape(self):
        f=self.root/'secret';f.write_text('x');link=self.allowed/'link';link.symlink_to(f)
        with self.assertRaises(ProtocolError):file_digest(link,self.allowed)

    def test_size_limit(self):
        with patch('runtime.evidence.MAX_FILE_BYTES',0):
            with self.assertRaises(ProtocolError):file_digest(self.f,self.allowed)

    def test_wrong_run(self):
        self.e['run_id']='wrong';self.assertFalse(check(self.c,self.e,self.r)[0])

    def test_wrong_contract_version(self):
        self.e['contract_version']=2;self.assertFalse(check(self.c,self.e,self.r)[0])

    def test_wrong_criterion(self):
        self.e['criterion_id']='other';self.assertFalse(check(self.c,self.e,self.r)[0])

    def test_simulated_evidence_not_real(self):
        self.e['simulated']=False;self.assertFalse(check(self.c,self.e,self.r)[0])

    def test_stale_evidence(self):
        now=datetime.now(timezone.utc)+timedelta(days=2);self.assertFalse(check(self.c,self.e,self.r,now)[0])

    def test_future_timestamp(self):
        self.e['captured_at']=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat();self.assertFalse(check(self.c,self.e,self.r)[0])

    def test_model_claim_cannot_replace_local_verifier(self):
        self.e['source']='model';self.assertFalse(check(self.c,self.e,self.r)[0])

    def test_hash_mismatch(self):
        self.e['content_sha256']='0'*64;self.assertFalse(check(self.c,self.e,self.r)[0])

    def test_correct_file(self):self.assertTrue(check(self.c,self.e,self.r)[0])


class DemoTests(unittest.TestCase):
    def test_demo_is_local_and_simulated(self):
        with tempfile.TemporaryDirectory() as d:
            r=run_demo(d)
            self.assertEqual(r['actual_llm_calls'],0);self.assertEqual(r['external_actions'],0)
            self.assertEqual(r['local_verified_runs'],3);self.assertEqual(r['lab_gate']['decision'],'CONTINUE_EXPERIMENT')
            with self.assertRaises(ValueError):run_demo(d)
