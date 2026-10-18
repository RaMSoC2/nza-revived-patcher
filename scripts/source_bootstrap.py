"""User entry point for local source assembly; never redistributes a prebuilt runtime."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from patcher import app
from patcher.source_runtime import checked_archive,extract_zip,sha256


def acquire(item,downloads,offline=False):
    target=downloads/item['filename']
    if target.is_file():checked_archive(target,item['sha256']);return target
    if offline:raise ValueError('Arquivo oficial ausente no cache: '+item['filename'])
    if not item['url'].startswith('https://'):raise ValueError('Somente HTTPS e permitido')
    print('Baixando dependencia oficial: '+item['filename'],flush=True)
    temporary=downloads/(item['filename']+'.pending-'+uuid.uuid4().hex[:6])
    try:
        with urllib.request.urlopen(item['url'],timeout=60) as response,temporary.open('xb') as out:
            done=0;last=0
            while block:=response.read(1048576):
                out.write(block);done+=len(block)
                if time.monotonic()-last>10:
                    print('  '+str(done//1048576)+' MiB recebidos',flush=True);last=time.monotonic()
        checked_archive(temporary,item['sha256']);temporary.rename(target)
    finally:temporary.unlink(missing_ok=True)
    return target


def find_runtime_inputs(manifest,folder,downloads):
    folder.mkdir(parents=True,exist_ok=True)
    files=list(folder.glob('*.zip'))
    found={}
    for name in ('zettabridge','dynarmic'):
        item=manifest['sources'][name]
        cached=downloads/item['filename']
        if cached.is_file():checked_archive(cached,item['sha256']);found[name]=cached;continue
        for file in files:
            if sha256(file)==item['sha256']:found[name]=file;break
    missing=[name for name in ('zettabridge','dynarmic') if name not in found]
    if missing:
        links='\n'.join(manifest['sources'][name]['url'] for name in missing)
        raise ValueError('Baixe separadamente as fontes oficiais abaixo e coloque os ZIPs, sem extrair, em '+str(folder)+'\n'+links)
    return found


def prepare_tools(manifest,cache,downloads,offline):
    result={}
    for name,item in manifest['tools'].items():
        target=cache/'tools'/name
        for candidate in [target,*sorted((cache/'tools').glob(name+'-*'))]:
            saved=candidate/'nza-archive.json'
            if saved.is_file() and json.loads(saved.read_text()).get('sha256')==item['sha256']:
                target=candidate;break
        marker=target/'nza-archive.json'
        if marker.is_file() and json.loads(marker.read_text()).get('sha256')==item['sha256']:
            result[name]=target;continue
        if target.exists():
            # Interrupted extraction is preserved; a fresh sibling is used.
            target=cache/'tools'/(name+'-'+uuid.uuid4().hex[:6])
        archive=acquire(item,downloads,offline)
        print('Preparando ferramenta local: '+name,flush=True)
        extract_zip(archive,target,strip_root=item['strip_root'])
        marker=target/'nza-archive.json';marker.write_text(json.dumps({'sha256':item['sha256']})+'\n')
        result[name]=target
    result['android_jar']=result.pop('platform')/'android.jar'
    hidden=result.pop('hidden_api')/'classes.jar'
    if sha256(hidden)!=manifest['tools']['hidden_api']['classes_sha256']:raise ValueError('HiddenApiBypass classes hash')
    result['hidden_api']=hidden
    return result


def fingerprint(paths):
    h=hashlib.sha256()
    for path in sorted(paths):h.update(path.name.encode());h.update(path.read_bytes())
    return h.hexdigest()[:16]


def main(argv=None):
    parser=argparse.ArgumentParser(description='No Zombies Allowed — montagem local a partir das fontes')
    parser.add_argument('--input')
    parser.add_argument('--output',type=Path,default=ROOT/'output')
    parser.add_argument('--signing',type=Path,default=ROOT/'signing')
    parser.add_argument('--runtime-input',type=Path,default=ROOT/'runtime-input')
    parser.add_argument('--cache',type=Path,default=ROOT/'.cache')
    parser.add_argument('--offline',action='store_true',help='Usar somente arquivos oficiais ja presentes no cache')
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--jobs',type=int,default=4)
    parser.add_argument('--tools-config',type=Path,help='Advanced: explicit paths to existing verified build tools')
    parser.add_argument('--runtime-build',type=Path,help='Advanced: reuse a completed, hash-checked local source build')
    args=parser.parse_args(argv)
    try:
        manifest=json.loads((ROOT/'manifests/runtime-sources.json').read_text())
        cache=args.cache.resolve();cache.mkdir(parents=True,exist_ok=True)
        downloads=cache/'downloads';downloads.mkdir(exist_ok=True)
        runtime_inputs=find_runtime_inputs(manifest,args.runtime_input.resolve(),downloads)
        if args.check:
            print('Fontes ZettaBridge/Dynarmic conferidas por SHA-256. Nenhum download ou APK gerado.')
            return 0
        (ROOT/'input').mkdir(exist_ok=True)
        original=app.choose_input(args.input)
        print('Montagem local: nenhum runtime ZettaBridge compilado acompanha este pacote.',flush=True)
        print('A primeira preparacao pode baixar varios GB de ferramentas oficiais; o cache sera reutilizado.',flush=True)
        if args.tools_config:
            tools={key:Path(value).resolve() for key,value in json.loads(args.tools_config.read_text()).items()}
        else:tools=prepare_tools(manifest,cache,downloads,args.offline)
        def run(command):subprocess.run([str(value) for value in command],check=True)
        native_key=fingerprint([ROOT/'manifests/runtime-sources.json',ROOT/'scripts/build_runtime_sources.py',
            ROOT/'src/patcher/source_runtime.py',ROOT/'src/android/runtime/zettabridge-native.patch',
            ROOT/'src/android/runtime/zettabridge-launcher.patch'])
        runtime=args.runtime_build.resolve() if args.runtime_build else cache/('runtime-'+native_key)
        if not (runtime/'build.json').is_file():
            if runtime.exists():runtime=cache/('runtime-'+native_key+'-'+uuid.uuid4().hex[:6])
            boost=acquire(manifest['sources']['boost'],downloads,args.offline)
            run([sys.executable,ROOT/'scripts/build_runtime_sources.py',
                '--zettabridge',runtime_inputs['zettabridge'],'--dynarmic',runtime_inputs['dynarmic'],
                '--boost',boost,'--ndk',tools['ndk'],'--cmake',tools['cmake'],'--output',runtime,'--jobs',args.jobs])
        # Validate provenance before deriving a template or executing the new APK builder.
        record=json.loads((runtime/'build.json').read_text())
        if record['runtime_commit']!=manifest['runtime_commit'] or record['used_prebuilt_runtime']:
            raise ValueError('Cache nao corresponde a uma compilacao local das fontes fixadas')
        for name in ('zettabridge','dynarmic'):
            if record['official_inputs'][name]!=manifest['sources'][name]['sha256']:raise ValueError('Wrong source provenance')
        for name,digest in record['files'].items():
            path=(runtime/name).resolve()
            if not path.is_relative_to(runtime) or sha256(path)!=digest:raise ValueError('Runtime local alterado')
        own_sources=[p for p in (ROOT/'src').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
        key=fingerprint([*own_sources,ROOT/'scripts/prepare_templates.py',ROOT/'scripts/prepare_source_runtime.py',ROOT/'manifests/runtime-sources.json',ROOT/'manifests/profile.json'])
        prepared_index=cache/('prepared-'+key+'.json')
        if prepared_index.is_file():
            deps=Path(json.loads(prepared_index.read_text())['dependencies']).resolve()
            if not deps.is_relative_to(cache):raise ValueError('Invalid prepared cache path')
            app.dependencies(deps)
        else:
            gsi=acquire(manifest['sources']['gsi'],downloads,args.offline)
            prepared=cache/('prepared-'+key+'-'+uuid.uuid4().hex[:6])
            run([sys.executable,ROOT/'scripts/prepare_source_runtime.py',
                '--runtime-build',runtime,'--gsi',gsi,'--jdk',tools['jdk'],
                '--build-tools',tools['build_tools'],'--android-jar',tools['android_jar'],
                '--hidden-api',tools['hidden_api'],'--ndk',tools['ndk'],'--input',original,'--output',prepared])
            deps=prepared/'dependencies'
            prepared_index.write_text(json.dumps({'dependencies':str(deps)})+'\n')
        app.execute(original,args.output.resolve(),deps,args.signing.resolve())
        return 0
    except Exception as failure:
        print('ERRO: '+str(failure),file=sys.stderr,flush=True)
        return 1


if __name__=='__main__':raise SystemExit(main())
