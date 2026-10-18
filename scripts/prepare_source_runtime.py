"""Prepare a new game-free template using ONLY a completed source build and official GSI.

The input game is used locally to derive the guarded engine recipe; it never enters
the template. The previous .dependencies/templates directory is never read.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from patcher import app
from patcher.ext4 import Ext4
from patcher.source_runtime import checked_archive,sha256


def prepare_execution_tools(portable_base, deps, jdk, build_tools):
    """Use only the downloaded official tools, never bundled Java/Android binaries."""
    shutil.copytree(portable_base/'python',deps/'python',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    subprocess.run([str(jdk/'bin/jlink.exe'),'--add-modules',
        'java.base,java.logging,java.naming,jdk.crypto.ec','--strip-debug',
        '--no-header-files','--no-man-pages','--compress=2','--output',str(deps/'java')],check=True)
    shutil.copy2(jdk/'NOTICE',deps/'java/NOTICE')
    target=deps/'tools';target.mkdir()
    for source,name in ((build_tools/'lib/apksigner.jar','apksigner.jar'),
                        (build_tools/'zipalign.exe','zipalign.exe'),
                        (build_tools/'libwinpthread-1.dll','libwinpthread-1.dll'),
                        (build_tools/'NOTICE.txt','Android-NOTICE.txt')):
        shutil.copy2(source,target/name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-build','gsi','jdk','build-tools','android-jar','hidden-api','ndk','input','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--portable-base',type=Path,default=ROOT/'.dependencies')
    a=parser.parse_args()
    for key,value in vars(a).items():
        if isinstance(value,Path):setattr(a,key,value.resolve())
    source=app.choose_input(a.input)
    manifest=json.loads((ROOT/'manifests/runtime-sources.json').read_text())
    profile=json.loads((ROOT/'manifests/profile.json').read_text())
    checked_archive(a.gsi,manifest['sources']['gsi']['sha256'])
    record=json.loads((a.runtime_build/'build.json').read_text())
    if record['runtime_commit']!=manifest['runtime_commit'] or record['used_prebuilt_runtime']:
        raise ValueError('Expected a completed pinned source build')
    for name,digest in record['files'].items():
        file=(a.runtime_build/name).resolve()
        if not file.is_relative_to(a.runtime_build) or sha256(file)!=digest:raise ValueError('Changed source-build output')
    a.output.mkdir(parents=True,exist_ok=False)
    # Extract a fresh system.img from its verified official archive, not a lab image.
    image=a.output/'system.img'
    with zipfile.ZipFile(a.gsi) as archive:
        info=archive.getinfo('system.img')
        if info.file_size>8*1024**3:raise ValueError('Unexpected GSI image size')
        with archive.open(info) as original,image.open('xb') as out:shutil.copyfileobj(original,out,1048576)
    bundle=a.output/'bundle';assets=bundle/'assets';zb=assets/'zb'
    fs=Ext4(image)
    mapping={'system/bin/linker':'/system/bin/bootstrap/linker'}
    mapping.update({'system/lib/'+n:'/system/lib/bootstrap/'+n for n in ('libc.so','libm.so','libdl.so','libdl_android.so')})
    mapping.update({'system/lib/'+n:'/system/lib/'+n for n in ('ld-android.so','liblog.so','libz.so','libc++.so','libstdc++.so')})
    sysroot_records=[]
    try:
        # Preserve the actual GSI's complete notices alongside its extracted libraries.
        notices=assets/'nza-licenses';notices.mkdir(parents=True)
        (notices/'AOSP-NOTICE.xml.gz').write_bytes(fs.contents(fs.lookup('/system/etc/NOTICE.xml.gz')))
        for relative,original in mapping.items():
            content=fs.contents(fs.lookup(original))
            if content[:6]!=b'\x7fELF\x01\x01' or struct.unpack_from('<H',content,18)[0]!=40:raise ValueError('Expected official ARM32 ELF')
            dest=zb/'sysroot'/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
            sysroot_records.append({'source':original,'path':relative,'sha256':sha256(dest)})
    finally:fs.file.close()
    guest=a.runtime_build/'guest'
    (zb/'guest/lib').mkdir(parents=True)
    shutil.copy2(guest/'zbhost',zb/'guest/zbhost')
    for lib in sorted((guest/'lib').glob('*.so')):shutil.copy2(lib,zb/'guest/lib'/lib.name)
    (zb/'host').mkdir();shutil.copy2(a.runtime_build/'native/core/libzbproxy.so',zb/'host/libzbproxy.so')
    native=bundle/'jniLibs/arm64-v8a';native.mkdir(parents=True)
    shutil.copy2(a.runtime_build/'native/core/libzbridge.so',native/'libzbridge.so')
    files=sorted(p for p in zb.rglob('*') if p.is_file())
    (assets/'zb-files.txt').write_text(''.join(p.relative_to(assets).as_posix()+'\n' for p in files))
    hashes=''.join(sha256(p)+'  '+p.relative_to(assets).as_posix()+'\n' for p in files)
    (assets/'zb-version.txt').write_text(hashlib.sha256(hashes.encode()).hexdigest()+'\n')
    print('Fresh ARM32 sysroot extracted from the official GSI; source-built bundle assembled.',flush=True)
    sys.path.insert(0,str(ROOT/'src/android/patches'))
    from client import build
    build(source,a.output/'client',ROOT)
    engine=a.output/'prepared-engine.so'
    with zipfile.ZipFile(a.output/'client/local-resources-unsigned.apk') as apk:
        engine.write_bytes(apk.read('lib/armeabi/libverde.so'))
    # Execute the pinned upstream import fix, then the same two guarded own fixes
    # as the Android integration. No preserved engine file is an input.
    spec=importlib.util.spec_from_file_location('source_import_fix',a.runtime_build/'source/tools/fix_guest_lib.py')
    upstream=importlib.util.module_from_spec(spec);spec.loader.exec_module(upstream)
    upstream.fix(str(engine))
    if sha256(engine)!='407e82f755501d62403108d2c5e61bc4760bfa9746040dd308aaa9afcc4ca4a0':raise ValueError('Unexpected imported engine')
    data=bytearray(engine.read_bytes());offset=30418896;length=168
    data[offset:offset+length]=data[offset+8:offset+length]+b'\0'*8
    engine.write_bytes(data)
    if sha256(engine)!='4de2a7a34adad6b724b2e69e6b0ceae6568c64a056c7efa3bfd47568c7a87482':raise ValueError('Engine SONAME guard')
    offset=0x1b57194
    if data[offset:offset+4]!=bytes.fromhex('0900001a'):raise ValueError('Engine commit instruction guard')
    data[offset:offset+4]=bytes.fromhex('090000ea');engine.write_bytes(data)
    if sha256(engine)!='5bd39aa97d496e36e3a27f84911ee4298caac74324a0cb38a093d509a18d7d6e':raise ValueError('Engine atomic-save guard')
    deps=a.output/'dependencies';deps.mkdir()
    prepare_execution_tools(a.portable_base,deps,a.jdk,a.build_tools)
    command=[sys.executable,ROOT/'scripts/prepare_templates.py',
        '--host-source',a.runtime_build/'source/android/launcher/app/src/main/java',
        '--host-manifest',ROOT/'src/android/launcher/AndroidManifest.xml','--native-bundle',bundle,
        '--prepared-engine',engine,'--jdk',a.jdk,'--build-tools',a.build_tools,'--android-jar',a.android_jar,
        '--hidden-api',a.hidden_api,'--ndk',a.ndk,'--destination',deps/'templates',
        '--version-code',str(profile['android_version_code']),'--version-name',profile['version']]
    subprocess.run([str(v) for v in command],check=True)
    metadata=json.loads((deps/'templates/metadata.json').read_text())
    metadata.update({'format_version':1,'profile':'revived-0.2','local_only':True,'public_release_allowed':False,
        'version':profile['version'],'runtime_built_from_sources':True,
        'source_build':{'runtime_commit':record['runtime_commit'],'used_prebuilt_runtime':False,
                        'official_inputs':record['official_inputs'],'gsi_sha256':manifest['sources']['gsi']['sha256']}})
    metadata['files']=[{'path':p.relative_to(deps).as_posix(),'sha256':sha256(p)} for p in sorted(deps.rglob('*'))
        if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts and p.suffix!='.pyc']
    (deps/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (a.output/'sysroot-provenance.json').write_text(json.dumps(sysroot_records,indent=2)+'\n')
    print('Source-only preparation complete. Generated dependencies: '+str(deps),flush=True)


if __name__=='__main__':main()
