"""Verify distributed file integrity against MANIFEST.json. Does not assert authenticity."""
from pathlib import Path
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]

def main():
    manifest=ROOT/'MANIFEST.json'
    if not manifest.is_file():
        print('No distribution manifest. This check is available in the packaged release.',file=sys.stderr)
        return 2
    data=json.loads(manifest.read_text(encoding='utf-8'));failures=[]
    for item in data['files']:
        p=(ROOT/item['path']).resolve()
        if not p.is_relative_to(ROOT) or not p.is_file():
            failures.append({'path':item['path'],'error':'missing or invalid path'});continue
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        if digest!=item['sha256']:failures.append({'path':item['path'],'error':'hash mismatch'})
    print(json.dumps({'manifest_files':len(data['files']),'passed':not failures,'failures':failures,
                     'note':'Integrity only. This manifest is not cryptographically signed.'},ensure_ascii=False,indent=2))
    return 1 if failures else 0
if __name__=='__main__':raise SystemExit(main())
