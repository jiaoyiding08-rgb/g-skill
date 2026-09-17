"""Offline package consistency checks. No model calls or behavior-effectiveness claims."""
from pathlib import Path
import json
import re
import sys
import ast
import sqlite3
import yaml
from jsonschema import Draft202012Validator
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from kernel.validation import validate, MASTER, DECISIONS


def check_project():
    failures=[];counts={'skill_files':0,'example_envelopes':0,'eval_inputs':0,'eval_rubrics':0,'python_files':0,'sqlite_user_tables':0,'markdown_relative_links':0}
    def verify(label,fn):
        try:fn()
        except Exception as exc:failures.append(f'{label}: {type(exc).__name__}: {exc}')
    verify('master_schema',lambda:Draft202012Validator.check_schema(MASTER))
    def equal(a,b):
        if a!=b:raise ValueError('Values do not match')
    for directory in sorted((ROOT/'skills').glob('g-*')):
        counts['skill_files']+=1;name=directory.name
        def skill_check(directory=directory,name=name):
            raw=(directory/'SKILL.md').read_text();front=yaml.safe_load(raw.split('---',2)[1])
            equal(front['name'],name)
            if not front['description'] or len(raw.splitlines())>500:raise ValueError('Bad description or excessive length')
            equal((directory/'references/kernel-contract.md').read_bytes(),(ROOT/'kernel/CONTRACT.md').read_bytes())
            equal((directory/'references/protocol.schema.json').read_bytes(),(ROOT/'kernel/schemas/protocol.schema.json').read_bytes())
            for decision in DECISIONS[name]:
                if decision not in raw:raise ValueError('Missing declared decision '+decision)
        verify(name,skill_check)
    input_ids=set();rubric_ids=set()
    for p in sorted((ROOT/'evals/inputs').glob('*.json')):
        for case in json.loads(p.read_text()):
            counts['eval_inputs']+=1
            verify(case['id'],lambda case=case:validate('EvalCase',case))
            if case['id'] in input_ids:failures.append('Duplicate input ID '+case['id'])
            input_ids.add(case['id'])
    for p in sorted((ROOT/'evals/grading').glob('*.json')):
        for case in json.loads(p.read_text()):
            counts['eval_rubrics']+=1
            verify(case['id'],lambda case=case:validate('EvalRubric',case))
            if case['id'] in rubric_ids:failures.append('Duplicate rubric ID '+case['id'])
            rubric_ids.add(case['id'])
    verify('input/rubric pairs',lambda:equal(input_ids,rubric_ids))
    for p in sorted((ROOT/'examples').glob('g-*.json')):
        counts['example_envelopes']+=1
        verify(p.name,lambda p=p:validate('Envelope',json.loads(p.read_text())))
        verify(p.name+' bundled copy',lambda p=p:equal(p.read_bytes(),(ROOT/'skills'/p.stem/'references/example-response.json').read_bytes()))
    verify('RunPlan',lambda:validate('RunPlan',json.loads((ROOT/'examples/run-plan.json').read_text())))
    for p in ROOT.rglob('*.py'):
        if '.venv' in p.parts or 'node_modules' in p.parts:continue
        counts['python_files']+=1;verify(str(p.relative_to(ROOT)),lambda p=p:ast.parse(p.read_text(),filename=str(p)))
    for p in ROOT.rglob('*.md'):
        if any(x in p.parts for x in ['.venv','.local','node_modules','reports']):continue
        # Markdown-link destinations only; inline code paths are examples, not automatically links.
        for match in re.finditer(r'\[[^\]]+\]\(([^)]+)\)',p.read_text()):
            link=match.group(1).split('#',1)[0]
            if not link or '://' in link or link.startswith('mailto:'):continue
            counts['markdown_relative_links']+=1
            if not (p.parent/link).exists():failures.append(f'Broken link: {p.relative_to(ROOT)} -> {link}')
    con=sqlite3.connect(':memory:')
    verify('SQLite schema',lambda:con.executescript((ROOT/'kernel/schema.sql').read_text()))
    counts['sqlite_user_tables']=con.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0];con.close()
    return {'mode':'offline_static_checks','passed':not failures,'counts':counts,'failures':failures,'model_calls':0}

if __name__=='__main__':
    result=check_project();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['passed'] else 1)
