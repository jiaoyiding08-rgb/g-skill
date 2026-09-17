from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from .storage import Store
from .validation import ProtocolError, validate
from .router import route
from .demo import run_demo

def read_json(path: str):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def main(argv: list[str] | None=None) -> int:
    p=argparse.ArgumentParser(description='G Skill local reference runtime. No background or external actions.')
    p.add_argument('--db',default='.local/gskill.sqlite',help='Explicit local database path')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('init')
    c=sub.add_parser('create');c.add_argument('file')
    c=sub.add_parser('state');c.add_argument('run_id');c.add_argument('target');c.add_argument('--confirm',action='store_true')
    c=sub.add_parser('attach');c.add_argument('run_id');c.add_argument('criterion_id');c.add_argument('file');c.add_argument('--root',required=True)
    c=sub.add_parser('verify');c.add_argument('run_id')
    c=sub.add_parser('show');c.add_argument('run_id')
    c=sub.add_parser('snapshot');c.add_argument('run_id');c.add_argument('--prediction',required=True);c.add_argument('--window',required=True)
    c=sub.add_parser('export');c.add_argument('--out',required=True)
    c=sub.add_parser('delete');c.add_argument('run_id');c.add_argument('--confirm',action='store_true')
    c=sub.add_parser('check');c.add_argument('file');c.add_argument('--kind',default='Envelope')
    c=sub.add_parser('route');c.add_argument('file')
    c=sub.add_parser('demo');c.add_argument('--out',required=True)
    a=p.parse_args(argv)
    try:
        if a.command=='demo': result=run_demo(a.out)
        elif a.command=='check': validate(a.kind,read_json(a.file));result={'schema_valid':True,'kind':a.kind,'behavior_validated':False}
        elif a.command=='route': result=route(read_json(a.file))
        else:
            if a.command!='init' and not Path(a.db).expanduser().exists():
                raise ProtocolError('Database does not exist. Run init first.')
            with Store(a.db) as s:
                if a.command=='init': result={'created_or_opened':str(s.path),'schema_version':1}
                elif a.command=='create': result={'run_id':s.create_run(read_json(a.file))}
                elif a.command=='state': s.transition(a.run_id,a.target,confirmed=a.confirm);result=s.run(a.run_id)
                elif a.command=='attach': result=s.attach_file(a.run_id,a.criterion_id,a.file,a.root)
                elif a.command=='verify': result=s.verify(a.run_id)
                elif a.command=='show': result=s.export(a.run_id)
                elif a.command=='snapshot': result=s.snapshot(a.run_id,a.prediction,confidence=None,reasons=[],failure_conditions=[],observation_window=a.window)
                elif a.command=='export':
                    out=Path(a.out).expanduser()
                    if out.exists(): raise ProtocolError('Export destination exists; choose a new path.')
                    out.parent.mkdir(parents=True,exist_ok=True)
                    with out.open('x',encoding='utf-8') as f:json.dump(s.export(),f,ensure_ascii=False,indent=2)
                    if sys.platform!='win32':out.chmod(0o600)
                    result={'exported_to':str(out),'privacy':'private export; contains local records and paths'}
                elif a.command=='delete':
                    s.delete_run(a.run_id,confirmed=a.confirm);result={'deleted_run':a.run_id,'original_files_deleted':False,'backups_deleted':False}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ProtocolError, OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),file=sys.stderr);return 2
