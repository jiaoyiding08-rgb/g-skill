"""Synchronize generated shared references, not user-installed skills."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    for folder in sorted((ROOT/'skills').glob('g-*')):
        shutil.copy2(ROOT/'kernel/CONTRACT.md',folder/'references/kernel-contract.md')
        shutil.copy2(ROOT/'kernel/schemas/protocol.schema.json',folder/'references/protocol.schema.json')
    print('Synchronized repository-local shared references for six skills. Installed copies were not changed.')
