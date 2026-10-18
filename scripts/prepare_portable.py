"""Assemble local portable dependencies from explicit, already verified inputs.

Not a downloader or public redistribution authorization. Build local-only ZIPs
until runtime and dependency distribution terms have been resolved.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--python-home',type=Path,required=True)
    p.add_argument('--jdk',type=Path,required=True)
    p.add_argument('--build-tools',type=Path,required=True)
    a=p.parse_args()
    deps=ROOT/'.dependencies';deps.mkdir(exist_ok=True)
    python=deps/'python';python.mkdir()
    for n in ('python.exe','python3.dll','python312.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt'):
        shutil.copy2(a.python_home/n,python/n)
    shutil.copytree(a.python_home/'DLLs',python/'DLLs',ignore=shutil.ignore_patterns('*.pdb','*.lib'))
    with zipfile.ZipFile(python/'python312.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted((a.python_home/'Lib').rglob('*')):
            rel=f.relative_to(a.python_home/'Lib')
            if f.is_file() and not any(n in rel.parts for n in ('site-packages','__pycache__','test','tests','tkinter','idlelib','turtledemo','ensurepip')) and f.suffix not in ('.pyc','.pyo'):
                z.write(f,rel.as_posix())
    site=python/'Lib/site-packages';site.mkdir(parents=True)
    pillow=a.python_home/'Lib/site-packages'
    for f in pillow.iterdir():
        if f.name=='PIL' or f.name.lower().startswith(('pillow-', 'pillow.libs')):
            if f.is_dir():shutil.copytree(f,site/f.name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (python/'python312._pth').write_text('python312.zip\nDLLs\nLib/site-packages\n',encoding='ascii')
    java=deps/'java'
    subprocess.run([str(a.jdk/'bin/jlink.exe'),'--add-modules','java.base,java.logging,java.naming,jdk.crypto.ec',
                    '--strip-debug','--no-header-files','--no-man-pages','--compress=2','--output',str(java)],check=True)
    shutil.copy2(a.jdk/'NOTICE',java/'NOTICE')
    tools=deps/'tools';tools.mkdir()
    for src,n in ((a.build_tools/'lib/apksigner.jar','apksigner.jar'),(a.build_tools/'zipalign.exe','zipalign.exe'),(a.build_tools/'libwinpthread-1.dll','libwinpthread-1.dll'),(a.build_tools/'NOTICE.txt','Android-NOTICE.txt')):
        shutil.copy2(src,tools/n)
    templates=json.loads((deps/'templates/metadata.json').read_text())
    files=[{'path':f.relative_to(deps).as_posix(),'sha256':sha(f)} for f in sorted(deps.rglob('*')) if f.is_file() and f.name!='manifest.json' and '__pycache__' not in f.parts and f.suffix!='.pyc']
    value={'format_version':1,'profile':'revived-0.2','local_only':True,'public_release_allowed':False,
           'icon_entry':templates['icon_entry'],'runtime_commit':templates['runtime_commit'],
           'sources':{'python':'https://www.python.org/','java':'https://adoptium.net/',
                      'android_tools':'https://developer.android.com/tools/releases/build-tools',
                      'runtime':'https://github.com/ZailoxTT/ZettaBridge','pillow':'https://python-pillow.github.io/'},
           'files':files}
    (deps/'manifest.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    print('Portable dependencies ready:',len(files),'verified files; publication blocked.')


if __name__=='__main__':main()
