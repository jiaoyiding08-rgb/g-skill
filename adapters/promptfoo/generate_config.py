"""Build a live-evaluation config. Generation makes no model or network calls."""
from pathlib import Path
import json
import argparse
ROOT=Path(__file__).resolve().parents[2]

def make_config(split='dev',limit=3,skill=None):
    cases=[]
    for path in sorted((ROOT/'evals/inputs').glob('*.json')):
        cases+=json.loads(path.read_text(encoding='utf-8'))
    cases=[c for c in cases if c['split']==split and (not skill or c['skill']==skill)][:limit]
    tests=[]
    for c in cases:
        # case_id is only used by the grader. The prompt contains input_json only.
        tests.append({'description':c['id'], 'vars':{'case_id':c['id'],
          'input_json':json.dumps({'skill':c['skill'],'input':c['input'],'context':c['context']},ensure_ascii=False)}})
    return {'description':'G Skill alpha: automated format/decision checks; semantic review required',
      'prompts':['{{input_json}}'],'providers':[{'id':'file://provider.py'}],
      'defaultTest':{'assert':[{'type':'python','value':'file://assertions.py'}]},'tests':tests}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['dev','holdout_candidate'],default='dev')
    p.add_argument('--limit',type=int,default=3);p.add_argument('--skill');a=p.parse_args()
    if not 1<=a.limit<=72:raise SystemExit('--limit must be between 1 and 72')
    config=make_config(a.split,a.limit,a.skill)
    if not config['tests']:raise SystemExit('No matching cases')
    out=Path(__file__).parent/'promptfooconfig.live.json'
    out.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(out)
