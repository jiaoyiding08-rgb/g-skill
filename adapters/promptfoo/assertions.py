"""Mechanical checks only. Semantic usefulness still requires independent human grading."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from kernel.validation import validate,ProtocolError

def get_assert(output,context):
    try:
        value=json.loads(output) if isinstance(output,str) else output
        validate('Envelope',value)
        case_id=context.get('vars',{}).get('case_id')
        if case_id:
            rubrics=[]
            for p in (ROOT/'evals/grading').glob('*.json'):rubrics+=json.loads(p.read_text())
            rubric=next((r for r in rubrics if r['id']==case_id),None)
            if rubric is None:raise ProtocolError('Unknown grading case.')
            if value['decision'] not in rubric['acceptable_decisions']:
                raise ProtocolError('Decision does not match this case’s allowed decision set.')
            expected_skill=case_id.rsplit('-',1)[0]
            if value['skill']!=expected_skill:raise ProtocolError('Output belongs to a different skill.')
        return {'pass':True,'score':1.0,'reason':'机械检查通过；内容是否符合 must/must_not 仍需人工评审，不代表行为效果通过。'}
    except (ValueError,TypeError,KeyError) as exc:
        return {'pass':False,'score':0.0,'reason':str(exc)}
