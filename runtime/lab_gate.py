"""Evaluate submitted comparison evidence; never deploy a candidate."""
from __future__ import annotations
from typing import Any
from kernel.validation import ProtocolError

def release_gate(report: dict[str,Any]) -> dict[str,Any]:
    required={'baseline_hash','candidate_hash','actual_model_runs','sealed_holdout',
              'same_environment','critical_regressions','failure_case_improved','holdout_improved',
              'within_budget','human_approved','rollback_available','sample_count'}
    if set(report) != required:
        raise ProtocolError('A release report must provide every documented field, with no extras.')
    for key in required-{'baseline_hash','candidate_hash','critical_regressions','sample_count'}:
        if type(report[key]) is not bool:
            raise ProtocolError(f'{key} must be a boolean.')
    for key in ('critical_regressions','sample_count'):
        if type(report[key]) is not int or report[key]<0:
            raise ProtocolError(f'{key} must be a nonnegative integer.')
    for key in ('baseline_hash','candidate_hash'):
        if not isinstance(report[key],str) or len(report[key])!=64 or any(c not in '0123456789abcdef' for c in report[key]):
            raise ProtocolError(f'{key} must be a SHA-256 digest.')
    blockers=[]
    if report['baseline_hash']==report['candidate_hash']:blockers.append('没有可识别的候选改动')
    for flag in ('actual_model_runs','sealed_holdout','same_environment','failure_case_improved',
                 'holdout_improved','within_budget','human_approved','rollback_available'):
        if not report[flag]:blockers.append(flag)
    if report['critical_regressions']>0:blockers.append('critical_regressions')
    if report['sample_count']==0:blockers.append('no_samples')
    # A nonempty sample does not establish statistical power; human review owns adequacy.
    return {'decision':'CONTINUE_EXPERIMENT' if blockers else 'CANARY_RECOMMENDED',
            'blockers':blockers,'release_executed':False,
            'limitation':'只检查报告字段与门槛；证据真实性和样本充分性需独立审查。'}
