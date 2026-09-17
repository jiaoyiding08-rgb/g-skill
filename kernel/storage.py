"""SQLite reference store for one trusted local user. Not a multi-user security boundary."""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any
from .validation import ProtocolError, validate
from runtime.evidence import utcnow, file_digest, check

STATES = {
 'DRAFT': {'READY','PARKED','ABORTED'},
 'READY': {'ACTIVE','PARKED','ABORTED'},
 'ACTIVE': {'WAITING_EVIDENCE','FAILED','PARKED','ABORTED'},
 'WAITING_EVIDENCE': {'ACTIVE','FAILED','PARKED','ABORTED'},
 'VERIFIED': set(), 'FAILED':set(), 'PARKED':{'READY','ABORTED'}, 'ABORTED':set()
}
def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False)
def new_id(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:16]}'

class Store:
    def __init__(self, path: str | Path):
        requested = Path(path).expanduser()
        if requested.is_symlink():
            raise ProtocolError('Database symlinks are not supported.')
        self.path = requested.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(str(self.path), timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA busy_timeout=10000')
        self.db.execute('PRAGMA secure_delete=ON')
        v = self.db.execute('PRAGMA user_version').fetchone()[0]
        if v not in (0,1):
            self.db.close()
            raise ProtocolError(f'Unsupported database schema version: {v}')
        if v == 0:
            self.db.executescript((Path(__file__).parent/'schema.sql').read_text())
            self.db.commit()
        if os.name == 'posix':
            os.chmod(self.path, 0o600)

    def close(self) -> None:
        self.db.close()
    def __enter__(self) -> 'Store': return self
    def __exit__(self, *_: Any) -> None: self.close()

    def _event(self, run_id: str, event_type: str, payload: dict[str,Any]) -> None:
        self.db.execute('INSERT INTO trace_events(event_id,run_id,timestamp,event_type,payload) VALUES (?,?,?,?,?)',
                        (new_id('evt'),run_id,utcnow(),event_type,dumps(payload)))

    def run(self, run_id: str) -> dict[str,Any]:
        row = self.db.execute('SELECT * FROM action_runs WHERE run_id=?',(run_id,)).fetchone()
        if not row: raise ProtocolError(f'Unknown run: {run_id}')
        return dict(row)

    def contract(self, run_id: str) -> dict[str,Any]:
        r = self.run(run_id)
        row = self.db.execute('SELECT payload FROM completion_contracts WHERE contract_id=? AND version=?',
                              (r['contract_id'],r['contract_version'])).fetchone()
        return json.loads(row['payload'])

    def create_run(self, plan: dict[str,Any]) -> str:
        validate('RunPlan',plan)
        fingerprint = hashlib.sha256(dumps(plan).encode()).hexdigest()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            old = self.db.execute('SELECT run_id,request_hash FROM action_runs WHERE idempotency_key=?',
                                  (plan['idempotency_key'],)).fetchone()
            if old:
                if old['request_hash'] != fingerprint:
                    raise ProtocolError('Idempotency key reused with a different request.')
                return old['run_id']
            intent, contract, action = plan['intent'], plan['completion_contract'],plan['next_action']
            old_intent = self.db.execute('SELECT payload FROM intents WHERE intent_id=?',(intent['intent_id'],)).fetchone()
            if old_intent and old_intent['payload'] != dumps(intent):
                raise ProtocolError('Existing intent IDs cannot be overwritten.')
            if not old_intent:
                self.db.execute('INSERT INTO intents VALUES (?,?)',(intent['intent_id'],dumps(intent)))
            old_contract = self.db.execute('SELECT payload FROM completion_contracts WHERE contract_id=? AND version=?',
                                          (contract['contract_id'],contract['version'])).fetchone()
            if old_contract and old_contract['payload'] != dumps(contract):
                raise ProtocolError('A contract revision is immutable; create a new revision/run.')
            if not old_contract:
                self.db.execute('INSERT INTO completion_contracts VALUES (?,?,?)',
                                (contract['contract_id'],contract['version'],dumps(contract)))
            self.db.execute('''INSERT INTO action_runs
              (run_id,episode_id,intent_id,contract_id,contract_version,skill,state,simulated,created_at,started_at,idempotency_key,request_hash)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
              (plan['run_id'],plan['episode_id'],intent['intent_id'],contract['contract_id'],contract['version'],
               plan['skill'],'DRAFT',int(plan['simulated']),utcnow(),None,plan['idempotency_key'],fingerprint))
            self.db.execute('INSERT INTO action_steps VALUES (?,?,?)',(action['action_id'],plan['run_id'],dumps(action)))
            self._event(plan['run_id'],'run_created',{'skill':plan['skill'],'simulated':plan['simulated']})
        return plan['run_id']

    def transition(self, run_id: str, target: str, *, confirmed: bool = False) -> None:
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            r=self.run(run_id)
            if target not in STATES.get(r['state'],set()):
                raise ProtocolError(f'Illegal transition {r["state"]} -> {target}; VERIFIED is verifier-only.')
            if target == 'ACTIVE':
                step=json.loads(self.db.execute('SELECT payload FROM action_steps WHERE run_id=?',(run_id,)).fetchone()[0])
                if step['blocked_by']:
                    raise ProtocolError('Resolve dependencies and create a new plan before starting.')
                if step['requires_confirmation'] and not confirmed:
                    raise ProtocolError('This action requires explicit user confirmation.')
            self.db.execute('UPDATE action_runs SET state=?, started_at=CASE WHEN ?=\'ACTIVE\' THEN COALESCE(started_at,?) ELSE started_at END WHERE run_id=?',
                            (target,target,utcnow(),run_id))
            self._event(run_id,'state_changed',{'from':r['state'],'to':target})

    def snapshot(self, run_id: str, prediction: str, *, confidence: float | None, reasons: list[str],
                 failure_conditions: list[str], observation_window: str) -> dict[str,Any]:
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            r=self.run(run_id)
            if r['started_at'] is not None or r['state'] not in ('DRAFT','READY'):
                raise ProtocolError('A prospective snapshot must be recorded before the action starts.')
            if self.db.execute('SELECT 1 FROM judgment_snapshots WHERE run_id=?',(run_id,)).fetchone():
                raise ProtocolError('Prospective snapshots are immutable; record a separate retrospective note.')
            s={'snapshot_id':new_id('snap'),'run_id':run_id,'recorded_at':utcnow(),'timing':'prospective',
               'prediction':prediction,'confidence':confidence,'reasons':reasons,'failure_conditions':failure_conditions,
               'observation_window':observation_window}
            validate('JudgmentSnapshot',s)
            self.db.execute('INSERT INTO judgment_snapshots VALUES (?,?,?,?)',(s['snapshot_id'],run_id,s['recorded_at'],dumps(s)))
            self._event(run_id,'snapshot_saved',{'snapshot_id':s['snapshot_id']})
        return s

    def attach_file(self, run_id: str, criterion_id: str, path: str | Path, allowed_root: str | Path) -> dict[str,Any]:
        r=self.run(run_id)
        if r['state'] not in ('ACTIVE','WAITING_EVIDENCE'):
            raise ProtocolError('Only active or waiting runs accept new evidence.')
        c=self.contract(run_id)
        criterion=next((x for x in c['criteria'] if x['criterion_id']==criterion_id),None)
        if not criterion: raise ProtocolError('Unknown criterion ID.')
        if 'file' not in criterion['accepted_types']:
            raise ProtocolError('This criterion does not accept a file.')
        target,digest=file_digest(path,allowed_root)
        e={'evidence_id':new_id('ev'),'run_id':run_id,'contract_id':r['contract_id'],
           'contract_version':r['contract_version'],'criterion_id':criterion_id,'type':'file','level':'E1',
           'uri':str(target),'captured_at':utcnow(),'source':'local_verifier','content_sha256':digest,
           'scope_root':str(Path(allowed_root).expanduser().resolve()),'checked_by':'g-local-sha256-v1',
           'revoked_at':None,'simulated':bool(r['simulated'])}
        validate('Evidence',e)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if self.run(run_id)['state'] not in ('ACTIVE','WAITING_EVIDENCE'):
                raise ProtocolError('Run state changed before evidence was attached.')
            self.db.execute('INSERT INTO evidence VALUES (?,?,?,?)',(e['evidence_id'],run_id,criterion_id,dumps(e)))
            self._event(run_id,'evidence_recorded',{'evidence_id':e['evidence_id'],'level':'E1'})
        return e

    def revoke_evidence(self,evidence_id: str) -> None:
        with self.db:
            row=self.db.execute('SELECT run_id,payload FROM evidence WHERE evidence_id=?',(evidence_id,)).fetchone()
            if not row: raise ProtocolError('Unknown evidence.')
            e=json.loads(row['payload']);e['revoked_at']=utcnow()
            self.db.execute('UPDATE evidence SET payload=? WHERE evidence_id=?',(dumps(e),evidence_id))
            self._event(row['run_id'],'note',{'evidence_revoked':evidence_id})
            if self.run(row['run_id'])['state']=='VERIFIED':
                self.db.execute("UPDATE action_runs SET state='WAITING_EVIDENCE' WHERE run_id=?",(row['run_id'],))
                self.db.execute('DELETE FROM outcomes WHERE run_id=?',(row['run_id'],))

    def verify(self,run_id: str) -> dict[str,Any]:
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            r=self.run(run_id)
            if r['state'] not in ('ACTIVE','WAITING_EVIDENCE','VERIFIED'):
                raise ProtocolError('Verification requires an active, waiting, or previously verified run.')
            contract=self.contract(run_id)
            evidence=[json.loads(x[0]) for x in self.db.execute('SELECT payload FROM evidence WHERE run_id=?',(run_id,))]
            checks=[]
            for criterion in contract['criteria']:
                candidates=[e for e in evidence if e['criterion_id']==criterion['criterion_id']]
                passed=False; ev_id=None; reason='尚无满足此条件的证据。'
                for e in candidates:
                    passed,reason=check(criterion,e,r)
                    if passed: ev_id=e['evidence_id'];break
                checks.append({'criterion_id':criterion['criterion_id'],'passed':passed,'reason':reason,'evidence_id':ev_id})
            success=all(x['passed'] for x in checks)
            status='VERIFIED' if success else 'WAITING_EVIDENCE'
            outcome={'run_id':run_id,'status':status,'actual':
                     '已通过本地完成条件核验。此结果只覆盖合同中明确列出的条件。' if success else '完成条件仍有缺项或需要外部核验。',
                     'evidence_ids':list(dict.fromkeys(x['evidence_id'] for x in checks if x['evidence_id'])),
                     'checks':checks,'verified_at':utcnow() if success else None,'simulated':bool(r['simulated'])}
            validate('Outcome',outcome)
            self.db.execute('UPDATE action_runs SET state=? WHERE run_id=?',(status,run_id))
            self.db.execute('INSERT INTO outcomes VALUES (?,?) ON CONFLICT(run_id) DO UPDATE SET payload=excluded.payload',(run_id,dumps(outcome)))
            self._event(run_id,'verification_finished',{'status':status,'checks':checks})
        return outcome

    def add_rule(self,rule: dict[str,Any], *, approved: bool=False) -> None:
        validate('LearnedRule',rule)
        if rule['status'] in ('trial','adopted') and not approved:
            raise ProtocolError('Using a proposed rule requires approval.')
        with self.db:
            for run_id in rule['source_run_ids']: self.run(run_id)
            self.db.execute('INSERT INTO learned_rules VALUES (?,?)',(rule['rule_id'],dumps(rule)))
            self.db.executemany('INSERT INTO rule_sources VALUES (?,?)',[(rule['rule_id'],r) for r in rule['source_run_ids']])

    def add_cluster(self,cluster: dict[str,Any]) -> None:
        validate('RepeatCluster',cluster)
        runs=[self.run(i) for i in cluster['run_ids']]
        if set(cluster['episode_ids']) != {r['episode_id'] for r in runs}:
            raise ProtocolError('Episode counts must match the original runs; repeated edits count once.')
        if len({r['simulated'] for r in runs})>1:
            raise ProtocolError('Do not mix simulated and real episodes.')
        if cluster['maturity'] != 'R0' and any(r['started_at'] is None for r in runs):
            raise ProtocolError('Planned-only runs do not establish repeated action.')
        if cluster['maturity'] == 'R2' and any(r['state'] != 'VERIFIED' for r in runs):
            raise ProtocolError('This reference store requires verified source runs for a template candidate.')
        if cluster['maturity'] not in ('R0','R1','R2'):
            raise ProtocolError('Reference runtime stores observation/template candidates only; R3/R4 require later qualification.')
        with self.db:
            self.db.execute('INSERT INTO repeat_clusters VALUES (?,?)',(cluster['cluster_id'],dumps(cluster)))
            self.db.executemany('INSERT INTO repeat_members VALUES (?,?)',[(cluster['cluster_id'],r['run_id']) for r in runs])

    def export(self,run_id: str | None=None) -> dict[str,Any]:
        if run_id: self.run(run_id)
        runs=[dict(x) for x in self.db.execute('SELECT * FROM action_runs'+(' WHERE run_id=?' if run_id else ''), (run_id,) if run_id else ())]
        ids=[r['run_id'] for r in runs]
        def rows(table: str, column: str, values: list[Any]) -> list[dict[str,Any]]:
            if not values: return []
            q=','.join('?' for _ in values)
            # table and column are hardcoded by this method, never supplied by a caller.
            result=[]
            for row in self.db.execute(f'SELECT * FROM {table} WHERE {column} IN ({q})',values):
                d=dict(row)
                if 'payload' in d: d['payload']=json.loads(d['payload'])
                result.append(d)
            return result
        out={'schema_version':'0.1.0','exported_at':utcnow(),'privacy':'private_export','action_runs':runs}
        for t in ['action_steps','evidence','outcomes','judgment_snapshots','trace_events']:
            out[t]=rows(t,'run_id',ids)
        out['intents']=rows('intents','intent_id',list({r['intent_id'] for r in runs}))
        out['completion_contracts']=[]
        for cid,version in sorted({(r['contract_id'],r['contract_version']) for r in runs}):
            row=self.db.execute('SELECT * FROM completion_contracts WHERE contract_id=? AND version=?',(cid,version)).fetchone()
            out['completion_contracts'].append({'contract_id':cid,'version':version,'payload':json.loads(row['payload'])})
        rules=rows('rule_sources','run_id',ids);clusters=rows('repeat_members','run_id',ids)
        out['learned_rules']=rows('learned_rules','rule_id',list({x['rule_id'] for x in rules}))
        out['repeat_clusters']=rows('repeat_clusters','cluster_id',list({x['cluster_id'] for x in clusters}))
        if not run_id:
            for t in ['skill_versions','eval_cases','eval_runs']:
                out[t]=[]
                for row in self.db.execute(f'SELECT * FROM {t}'):
                    d=dict(row);d['payload']=json.loads(d['payload']);out[t].append(d)
        return out

    def delete_run(self,run_id: str, *, confirmed: bool=False) -> None:
        if not confirmed: raise ProtocolError('Deletion requires explicit confirmation.')
        with self.db:
            r=self.run(run_id)
            # Invalidate derived objects that would retain copied facts from the deleted run.
            self.db.execute('DELETE FROM learned_rules WHERE rule_id IN (SELECT rule_id FROM rule_sources WHERE run_id=?)',(run_id,))
            self.db.execute('DELETE FROM repeat_clusters WHERE cluster_id IN (SELECT cluster_id FROM repeat_members WHERE run_id=?)',(run_id,))
            self.db.execute('DELETE FROM action_runs WHERE run_id=?',(run_id,))
            self.db.execute('DELETE FROM intents WHERE intent_id=? AND NOT EXISTS (SELECT 1 FROM action_runs WHERE intent_id=?)',(r['intent_id'],r['intent_id']))
            self.db.execute('''DELETE FROM completion_contracts WHERE contract_id=? AND version=? AND NOT EXISTS
              (SELECT 1 FROM action_runs WHERE contract_id=? AND contract_version=?)''',
              (r['contract_id'],r['contract_version'],r['contract_id'],r['contract_version']))
        # Original user files and exported backups are intentionally not deleted.
