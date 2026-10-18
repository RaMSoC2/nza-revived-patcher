"""Maintainer: refresh local locks after rebuilding templates; never clears license gates."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def main():
    deps=ROOT/'.dependencies';lock=deps/'manifest.json'
    metadata=json.loads(lock.read_text())
    if not metadata.get('local_only') or metadata.get('public_release_allowed'):
        raise ValueError('Only a private local lock may be refreshed by this tool')
    metadata['files']=[{'path':p.relative_to(deps).as_posix(),'sha256':digest(p)} for p in sorted(deps.rglob('*')) if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts and p.suffix!='.pyc']
    lock.write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf8')
    source=ROOT/'manifests/source-inventory.json'
    previous=json.loads(source.read_text()) if source.exists() else {}
    previous['files']=[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p),'license':'see LICENSE and THIRD_PARTY_NOTICES.txt'} for p in sorted((ROOT/'src').rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
    source.write_text(json.dumps(previous,indent=2)+'\n',encoding='utf8')
    print('Local dependency/source locks refreshed. Publication remains blocked.')
if __name__=='__main__':main()
