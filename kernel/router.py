"""Deterministic routing from declared context. No keyword-based mind reading."""
from __future__ import annotations
from typing import Any
from .validation import validate

def route(context: dict[str, Any]) -> dict[str, Any]:
    validate('RouteContext', context)
    c = context
    if c['budget_exhausted']:
        return {'skill': None, 'decision': 'STOP', 'reason': '本轮预算已用完。'}
    if not c['authorized_scope']:
        return {'skill': None, 'decision': 'GET_SCOPE', 'reason': '先确定可读取的材料范围。'}
    if c['task_type'] == 'other' and not c['requested_skill']:
        return {'skill': None, 'decision': 'OUT_OF_SCOPE', 'reason': '普通问答不强制进入执行流程。'}
    target = c['requested_skill']
    if (target == 'g-lab' or c['task_type'] == 'skill_maintenance') and not c['maintainer_authorized']:
        return {'skill': None, 'decision': 'GET_MAINTAINER_APPROVAL', 'reason': '维护任务需要独立授权。'}
    # Explicit selection remains possible; the selected skill still applies its safety gates.
    if target:
        return {'skill': target, 'decision': 'ROUTE', 'reason': '使用用户明确选择的模块；保留风险检查。'}
    if c['hard_risk']:
        target = 'g-ship' if c['task_type'] == 'delivery' else 'g-ground'
        return {'skill': target, 'decision': 'REVIEW_RISK', 'reason': '先检查阻塞风险，暂不执行外部动作。'}
    mapping = {'action':'g-ground', 'validation':'g-real', 'delivery':'g-ship',
               'review':'g-review', 'repetition':'g-repeat', 'skill_maintenance':'g-lab'}
    return {'skill': mapping.get(c['task_type']), 'decision': 'ROUTE',
            'reason': '根据当前请求分配一个主模块，不默认连续调用六个模块。'}
