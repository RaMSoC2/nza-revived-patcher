"""Build a LOCAL-ONLY portable ZIP using a strict allowlist, never input/saves/keys."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile
import importlib.util

_audit_spec=importlib.util.spec_from_file_location('audit_public',Path(__file__).with_name('audit_public.py'))
_audit=importlib.util.module_from_spec(_audit_spec)
_audit_spec.loader.exec_module(_audit)
inspect=_audit.inspect

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-runtime',action='store_true',help='Exclude runtime templates; build from separately acquired sources')
    a=parser.parse_args()
    if a.output.exists():raise ValueError('Refusing to replace an existing release')
    metadata=json.loads((ROOT/'.dependencies/manifest.json').read_text())
    if not metadata['local_only'] or metadata['public_release_allowed']:
        raise ValueError('This packager is only authorized for the private local test build')
    paths=[ROOT/n for n in ('.gitattributes','README.md','LICENSE','THIRD_PARTY_NOTICES.txt','patch.cmd')]
    for name in ('src','assets','manifests','scripts','tests','licenses'):
        paths.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    for p in (ROOT/'.dependencies').rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
        relative=p.relative_to(ROOT/'.dependencies')
        if a.source_runtime and (len(relative.parts)<2 or relative.parts[0]!='python'):continue
        paths.append(p)
    if a.source_runtime:
        metadata=dict(metadata)
        metadata['profile']='source-bootstrap'
        metadata['version']=json.loads((ROOT/'manifests/profile.json').read_text())['version']
        metadata['contains_prebuilt_runtime']=False
        metadata['build_tools_acquisition']='verified-official-downloads'
        metadata['files']=[item for item in metadata['files'] if item['path'].split('/')[0]=='python']
    included={p.relative_to(ROOT).as_posix() for p in paths}
    for p in paths:
        name=p.relative_to(ROOT).as_posix()
        if p.is_symlink():raise ValueError('Symbolic link excluded: '+name)
        problems=inspect(name,p.read_bytes(),portable=True)
        if problems:raise ValueError('Content audit rejected '+name+': '+', '.join(problems))
    for item in metadata['files']:
        if '.dependencies/'+item['path'] not in included:
            raise ValueError('Dependency lock references a file excluded from ZIP: '+item['path'])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(paths):z.write(p,'nza-patcher/'+p.relative_to(ROOT).as_posix())
        z.writestr('nza-patcher/input/','')
        if a.source_runtime:
            z.writestr('nza-patcher/runtime-input/','')
            z.writestr('nza-patcher/.dependencies/manifest.json',json.dumps(metadata,indent=2)+'\n')
            z.writestr('nza-patcher/.dependencies/source-runtime-mode.json',json.dumps({'contains_prebuilt_runtime':False,'contains_java_or_android_tools':False,'acquisition':'user-supplied-pinned-source-archives','build_tools_acquisition':'verified-official-downloads'})+'\n')
    if a.source_runtime:
        with zipfile.ZipFile(a.output) as z:
            if any('/.dependencies/templates/' in name or name.endswith(('.apk','.so')) for name in z.namelist()):
                raise ValueError('Source-mode package unexpectedly contains a runtime binary')
            if any('/.dependencies/java/' in name or '/.dependencies/tools/' in name for name in z.namelist()):
                raise ValueError('Source-mode package unexpectedly bundles Java or Android tools')
    digest=hashlib.sha256(a.output.read_bytes()).hexdigest()
    a.output.with_suffix('.zip.sha256').write_text(digest+'  '+a.output.name+'\n',encoding='ascii')
    print('LOCAL ONLY:',a.output, 'SHA-256',digest)


if __name__=='__main__':main()
