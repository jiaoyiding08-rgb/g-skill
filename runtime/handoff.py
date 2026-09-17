"""Check handoff proposals. Does not launch agents or broaden authorization."""
from __future__ import annotations
from typing import Any
from kernel.validation import validate, ProtocolError

def check_handoff(proposal: dict[str, Any], *, current_scope: str, known_run_ids: set[str], known_evidence_ids: set[str], history: list[str]) -> dict[str, Any]:
    validate('Handoff', proposal)
    if proposal['allowed_scope'] != current_scope:
        raise ProtocolError('Handoff cannot broaden the authorized scope.')
    if proposal['parent_run_id'] not in known_run_ids:
        raise ProtocolError('Unknown parent run.')
    if not set(proposal['evidence_ids']).issubset(known_evidence_ids):
        raise ProtocolError('Handoff references unobserved evidence.')
    if proposal['depth'] != len(history) or len(history) >= 3:
        raise ProtocolError('Handoff depth is inconsistent or the turn budget is exhausted.')
    if proposal['target'] in history:
        raise ProtocolError('Repeated handoff target: stop and resolve the blocking fact.')
    return {'accepted':True,'executed':False,'target':proposal['target'],
            'requires_confirmation':proposal['requires_confirmation']}
