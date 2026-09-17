"""Offline JSON Schema checks plus cross-field protocol constraints."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
MASTER = json.loads((ROOT / 'kernel/schemas/protocol.schema.json').read_text(encoding='utf-8'))
DECISIONS = json.loads((ROOT / 'kernel/decisions.json').read_text(encoding='utf-8'))

class ProtocolError(ValueError):
    """An input or operation violates the documented protocol."""

def validate(kind: str, value: Any) -> None:
    if kind not in MASTER['$defs']:
        raise ProtocolError(f'Unknown schema type: {kind}')
    schema = dict(MASTER, **{'$ref': f'#/$defs/{kind}'})
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
                    key=lambda e: str(list(e.path)))
    if errors:
        e = errors[0]
        location = '.'.join(str(x) for x in e.path) or '<root>'
        raise ProtocolError(f'{kind}.{location}: {e.message}')
    if kind in ('CompletionContract', 'RunPlan'):
        contract = value if kind == 'CompletionContract' else value['completion_contract']
        ids = [c['criterion_id'] for c in contract['criteria']]
        if len(ids) != len(set(ids)):
            raise ProtocolError('Criterion IDs must be unique inside a contract.')
        for c in contract['criteria']:
            if c['verification'] == 'local_artifact_sha256' and (
                    c['minimum_level'] != 'E1' or c['accepted_types'] != ['file']):
                raise ProtocolError('Local hash verification only supports E1 file-existence claims.')
    if kind == 'ActionStep':
        if value['side_effect'] in ('external_write', 'payment', 'destructive') and not value['requires_confirmation']:
            raise ProtocolError('External or destructive side effects require explicit confirmation.')
    if kind == 'RunPlan':
        validate('ActionStep', value['next_action'])
    if kind == 'Outcome' and value['status'] == 'VERIFIED':
        ids = {x['evidence_id'] for x in value['checks'] if x['passed'] and x['evidence_id']}
        if not value['verified_at'] or not all(x['passed'] and x['evidence_id'] for x in value['checks']):
            raise ProtocolError('VERIFIED requires timestamp and successful evidence-backed checks.')
        if ids != set(value['evidence_ids']):
            raise ProtocolError('Outcome evidence references must match successful checks.')
    if kind == 'RepeatCluster':
        if value['maturity'] != 'R0' and len(value['episode_ids']) < 2:
            raise ProtocolError('Confirmed repetition requires at least two independent episodes.')
        if value['maturity'] == 'R4' and not value['automation_authorized']:
            raise ProtocolError('R4 requires explicit automation authorization.')
    if kind == 'Envelope':
        if len(value['questions']) > 3:
            raise ProtocolError('Ask at most three material questions in one turn.')
        if value['skill'] == 'g-ground' and value['decision'] == 'GET_ONE_FACT' and len(value['questions']) != 1:
            raise ProtocolError('GET_ONE_FACT requires one material question.')
        if value['skill'] == 'g-ground' and value['decision'] == 'ACT_NOW':
            if value['next_action'] is None or value['completion_contract'] is None:
                raise ProtocolError('ACT_NOW requires an action and a completion contract.')
        if value['skill'] == 'g-ship' and value['decision'] == 'ONE_FIX_THEN_SHIP':
            action = value['next_action']
            if not action or not action['timebox_min']:
                raise ProtocolError('A bounded fix requires an action and time budget.')
        if value['next_action']:
            validate('ActionStep', value['next_action'])
        if value['skill'] == 'g-real' and value['decision'] in ('SUPPORTED', 'REFUTED'):
            d = value['details']
            if not d['observations']:
                raise ProtocolError('A hypothesis decision requires actual observations, with source labels.')
            if d['hypothesis_status'] != value['decision'].lower():
                raise ProtocolError('Hypothesis status and decision must agree.')
        if value['completion_contract']:
            validate('CompletionContract', value['completion_contract'])
        if value['skill'] == 'g-ship' and value['decision'] == 'SHIP_NOW':
            d=value['details']
            if d['hard_gate'] != 'pass' or d['core_gate'] != 'pass' or not d['artifact_ref']:
                raise ProtocolError('SHIP_NOW requires inspected material and both gates to pass.')
        if value['skill'] == 'g-review':
            d=value['details']
            if value['decision'] == 'COMPARE' and not d['snapshot_available']:
                raise ProtocolError('COMPARE cannot claim a prospective comparison without a snapshot.')
        if value['skill'] == 'g-review' and value['decision'] == 'RULE_CANDIDATE':
            if not value['details']['rule'] or value['details']['rule']['status'] != 'hypothesis':
                raise ProtocolError('A new review rule starts as a hypothesis, not an adopted rule.')
        if value['skill'] == 'g-repeat' and value['decision'] in ('PATTERN','TEMPLATE_CANDIDATE','SKILL_CANDIDATE','AUTOMATION_CANDIDATE'):
            if not value['details']['cluster'] or value['details']['independent_count'] < 2:
                raise ProtocolError('Repeat recommendations require an independently supported cluster.')
        if value['skill'] == 'g-repeat' and value['details']['cluster']:
            cluster=value['details']['cluster']
            validate('RepeatCluster',cluster)
            if len(cluster['episode_ids']) != value['details']['independent_count']:
                raise ProtocolError('Independent episode count mismatch.')
        if value['skill'] == 'g-lab' and value['decision'] in ('STABLE_RECOMMENDED','CANARY_RECOMMENDED'):
            if not value['details']['live_evals_run'] or not value['details']['evidence_of_improvement']:
                raise ProtocolError('Release recommendations require real evaluation evidence.')
