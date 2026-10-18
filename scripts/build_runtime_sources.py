"""Build runtime components locally from pinned official source archives.

No game, launcher template or previous laboratory bundle is used by this stage.
All tool paths are explicit; no global installations or PATH edits are performed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from patcher.source_runtime import checked_archive,extract_zip,apply_unified_patch,sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('zettabridge','dynarmic','boost','ndk','cmake','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=4)
    a=parser.parse_args()
    for name,value in vars(a).items():
        if isinstance(value,Path):setattr(a,name,value.resolve())
    manifest=json.loads((ROOT/'manifests/runtime-sources.json').read_text())
    for name in ('zettabridge','dynarmic','boost'):checked_archive(getattr(a,name),manifest['sources'][name]['sha256'])
    if not 1<=a.jobs<=32:raise ValueError('Invalid job count')
    a.output.mkdir(parents=True,exist_ok=False)
    source=a.output/'source'
    extract_zip(a.zettabridge,source)
    submodule=source/'third_party/dynarmic'
    if submodule.exists():
        if any(submodule.iterdir()):raise ValueError('Expected empty upstream submodule')
        submodule.rmdir()
    extract_zip(a.dynarmic,submodule)
    boost=a.output/'boost';extract_zip(a.boost,boost,include=('boost/','LICENSE_1_0.txt'))
    # The ARMv8 Thumb-2 changes are shipped by upstream as patch recipes.
    for name in ('dynarmic-0001-thumb32-armv8.patch','dynarmic-0002-asimd-narrowing.patch'):
        apply_unified_patch(submodule,source/'third_party/patches'/name)
    edits=apply_unified_patch(source,ROOT/'src/android/runtime/zettabridge-native.patch')
    launcher=source/'android/launcher/app/src/main/java'
    launcher_edits=apply_unified_patch(launcher,ROOT/'src/android/runtime/zettabridge-launcher.patch')
    print('Verified official sources extracted; exact runtime and launcher patches applied.',flush=True)
    build=a.output/'native'
    cmake=a.cmake/'bin/cmake.exe';ninja=a.cmake/'bin/ninja.exe'
    log=(a.output/'compile.log').open('w',encoding='utf8')
    env=dict(os.environ);env.setdefault('SystemRoot','C:\\Windows')
    def run(command):
        subprocess.run([str(v) for v in command],stdout=log,stderr=subprocess.STDOUT,check=True,env=env)
        log.flush()
    run([cmake,'-S',source,'-B',build,'-G','Ninja',
        '-DCMAKE_MAKE_PROGRAM='+str(ninja),'-DCMAKE_TOOLCHAIN_FILE='+str(a.ndk/'build/cmake/android.toolchain.cmake'),
        '-DANDROID_ABI=arm64-v8a','-DANDROID_PLATFORM=android-26','-DANDROID_STL=c++_static',
        '-DCMAKE_BUILD_TYPE=Release','-DCMAKE_CXX_FLAGS_RELEASE=','-DCMAKE_C_FLAGS_RELEASE=',
        '-DBoost_INCLUDE_DIR='+str(boost),'-DPython3_EXECUTABLE='+sys.executable,'-DZB_BUILD_TESTS=OFF'])
    print('Compiling ARM64 runtime from source; log: '+str(a.output/'compile.log'),flush=True)
    run([cmake,'--build',build,'--target','zbridge','zbproxy','--parallel',str(a.jobs)])
    guest=a.output/'guest';(guest/'lib').mkdir(parents=True);(guest/'asm').mkdir()
    compiler=a.ndk/'toolchains/llvm/prebuilt/windows-x86_64/bin/clang.exe'
    common=[compiler,'--target=armv7a-linux-androideabi21','-O2','-Wall','-I'+str(source/'core/include')]
    def cc(target,sources,flags):run([*common,*flags,'-o',target,*sources])
    cc(guest/'zbhost',[source/'guest/zbhost/zbhost.c'],['-ldl'])
    cc(guest/'lib/libzbjni.so',[source/'guest/zbjni/zbjni.c',source/'guest/zbjni/gen/hostcalls.S'],['-shared','-fPIC','-Wl,-soname,libzbjni.so'])
    cc(guest/'lib/libzbcompat.so',[source/'guest/compat/zbcompat.c'],['-shared','-fPIC','-Wl,-soname,libzbcompat.so'])
    import re
    calls={(lib,name):int(index) for index,lib,name in re.findall(r'\{(\d+), "([^"]+)", "([^"]+)"\}',(source/'core/src/gen/hostcalls.inc').read_text())}
    aliases=['glBindFramebuffer','glBindRenderbuffer','glBlendFuncSeparate','glCheckFramebufferStatus',
        'glDeleteFramebuffers','glFramebufferTexture2D','glGenFramebuffers','glGenerateMipmap','glRenderbufferStorage']
    for assembly in sorted((source/'guest/stubs/gen').glob('*.S')):
        text=assembly.read_text()
        if assembly.stem=='libGLESv1_CM':
            for core in aliases:
                name=core+'OES';index=calls[('libGLESv2.so',core)]
                if name+':' in text:raise ValueError('Unexpected OES alias')
                text+=f'\n.global {name}\n.type {name}, %function\n.p2align 2\n{name}:\n svc #0x{0x5a0000|index:x}\n bx lr\n.size {name}, . - {name}\n'
        generated=guest/'asm'/assembly.name;generated.write_text(text)
        cc(guest/'lib'/(assembly.stem+'.so'),[generated],['-shared','-nostdlib','-Wl,-soname,'+assembly.stem+'.so'])
    log.close()
    record={'runtime_commit':manifest['runtime_commit'],'official_inputs':{name:sha256(getattr(a,name)) for name in ('zettabridge','dynarmic','boost')},
        'native_edits':edits,'launcher_edits':launcher_edits,'used_prebuilt_runtime':False,
        'files':{p.relative_to(a.output).as_posix():sha256(p) for p in [build/'core/libzbridge.so',build/'core/libzbproxy.so',guest/'zbhost',*sorted((guest/'lib').glob('*.so'))]}}
    (a.output/'build.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Source runtime built: '+str(a.output),flush=True)


if __name__=='__main__':main()
