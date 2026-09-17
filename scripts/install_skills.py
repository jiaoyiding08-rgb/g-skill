"""Copy selected self-contained skill folders. Never overwrite existing folders."""
from pathlib import Path
import argparse
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--target',required=True,help='Explicit destination, e.g. ~/.agents/skills')
    p.add_argument('--include-lab',action='store_true',help='Also install the maintainer-only skill')
    p.add_argument('--apply',action='store_true',help='Actually copy; default is a dry-run')
    a=p.parse_args();target=Path(a.target).expanduser()
    names=['g-ground','g-real','g-ship','g-review','g-repeat']+(['g-lab'] if a.include_lab else [])
    if any((target/n).exists() or (target/n).is_symlink() for n in names):
        print('Destination already contains a selected skill. Back it up and select a clean destination; nothing was changed.',file=sys.stderr);return 2
    for n in names:print(f'{"COPY" if a.apply else "DRY RUN"}: {n} -> {target/n}')
    if a.apply:
        target.mkdir(parents=True,exist_ok=True)
        for n in names:shutil.copytree(ROOT/'skills'/n,target/n)
    return 0
if __name__=='__main__':raise SystemExit(main())
