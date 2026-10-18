"""Local, version-locked APK preparation. Never installs or uploads anything."""
from pathlib import Path
import argparse
import contextlib
import datetime
import hashlib
import json
import os
import secrets
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = '167a4ac5d2fe653e3403212d37959b954d5f07dd6505456ea85aeb9d7d222312'


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def choose_input(explicit=None):
    if explicit:
        source = Path(explicit).resolve()
    else:
        candidates = sorted((ROOT / 'input').glob('*.apk'))
        if len(candidates) != 1:
            raise ValueError('Coloque exatamente um APK original em input/ ou use --input CAMINHO.')
        source = candidates[0].resolve()
    if not source.is_file():
        raise ValueError('APK de entrada nao encontrado.')
    if sha(source) != EXPECTED:
        raise ValueError('APK incompativel ou corrompido. A v1 aceita somente o APK 1.6.5 com SHA-256 ' + EXPECTED)
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError('Estrutura ZIP do APK invalida.')
    return source


def dependencies(directory=None):
    base = Path(directory).resolve() if directory is not None else ROOT / '.dependencies'
    manifest = base / 'manifest.json'
    if not manifest.is_file():
        raise ValueError('Dependencias ausentes. Use o ZIP portatil completo; o ZIP de fontes do GitHub nao inclui o runtime.')
    metadata = json.loads(manifest.read_text(encoding='utf8'))
    if metadata.get('profile') != 'revived-0.2':
        raise ValueError('Pacote de dependencias de outra versao.')
    for item in metadata['files']:
        p = (base / item['path']).resolve()
        if not p.is_relative_to(base.resolve()) or not p.is_file() or sha(p) != item['sha256']:
            raise ValueError('Dependencia ausente ou alterada: ' + item['path'])
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError('Pillow ausente. Inicie pelo patch.cmd do pacote completo.') from exc
    return base, metadata


def run(command, log):
    # Argument arrays only: paths and passwords never pass through a shell.
    result = subprocess.run([str(x) for x in command], stdout=log, stderr=subprocess.STDOUT)
    log.flush()
    if result.returncode:
        raise RuntimeError('Uma ferramenta falhou; consulte patch.log na pasta de trabalho.')


def prepare_key(base, log, directory=None):
    directory = Path(directory).resolve() if directory is not None else ROOT / 'signing'
    if not directory.exists():directory.mkdir(parents=True)
    key = directory / 'revived.jks'
    password = directory / 'password.txt'
    if key.exists() != password.exists():
        raise ValueError('Assinatura local incompleta. Preserve a pasta signing/ e restaure seu backup; nao criaremos outra chave silenciosamente.')
    if not key.exists():
        lock = directory / 'creating.lock'
        with lock.open('x'):
            pass
        try:
            password.write_text(secrets.token_urlsafe(32) + '\n', encoding='ascii')
            pending = directory / 'revived.pending.jks'
            run([base/'java/bin/keytool.exe', '-genkeypair', '-keystore', pending,
                 '-storepass:file', password, '-keypass:file', password, '-alias', 'revived',
                 '-keyalg', 'RSA', '-keysize', '3072', '-validity', '36500',
                 '-dname', 'CN=Local NZA Revival', '-storetype', 'JKS', '-noprompt'], log)
            pending.rename(key)
        except Exception:
            # Leave incomplete signing data for explicit recovery; never replace an existing key.
            raise
        finally:
            lock.unlink(missing_ok=True)
    return key, password


def sign(source, target, base, key, password, log, minimum=26):
    aligned = target.with_suffix('.aligned.apk')
    run([base/'tools/zipalign.exe', '-f', '4', source, aligned], log)
    run([base/'java/bin/java.exe', '-jar', base/'tools/apksigner.jar', 'sign',
         '--ks', key, '--ks-key-alias', 'revived', '--ks-pass', 'file:'+str(password),
         '--min-sdk-version', str(minimum), '--v1-signing-enabled', 'true',
         '--v2-signing-enabled', 'true', '--v3-signing-enabled', 'true',
         '--v4-signing-enabled', 'false', '--out', target, aligned], log)
    run([base/'java/bin/java.exe', '-jar', base/'tools/apksigner.jar', 'verify',
         '--min-sdk-version', str(minimum), '--verbose', '--print-certs', target], log)
    run([base/'tools/zipalign.exe', '-c', '4', target], log)
    aligned.unlink()


def assemble(template, target, additions):
    with zipfile.ZipFile(template) as source, zipfile.ZipFile(target, 'w') as out:
        names = set(source.namelist())
        for info in source.infolist():
            if info.filename.upper().startswith('META-INF/'):
                continue
            data = additions.get(info.filename)
            out.writestr(info, source.read(info.filename) if data is None else data)
        for name, data in additions.items():
            if name not in names:
                out.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)


def execute(source, output_root, dependency_root=None, signing_root=None):
    base, dependency_metadata = dependencies(dependency_root)
    profile = json.loads((ROOT/'manifests/profile.json').read_text())
    tag = datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    work = ROOT/'work'/tag
    work.mkdir(parents=True, exist_ok=False)
    destination = output_root/tag
    if destination.resolve().is_relative_to(source) or destination == source.parent:
        raise ValueError('Entrada e saida devem ser separadas.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (work/'patch.log').open('w', encoding='utf8') as log:
        print('1/5 Preparando cliente e 217 texturas experimentais...', flush=True)
        sys.path.insert(0, str(ROOT/'src/android/patches'))
        from client import build
        from nza_offline_analytics_patch import patch
        with contextlib.redirect_stdout(log):
            build(source, work/'client', ROOT)
        report = json.loads((work/'client/patch.json').read_text())
        if report['output_elf_sha256'] != profile['client_engine_sha256'] or report['unresolved_catalog_paths']:
            raise ValueError('O cliente gerado divergiu do checkpoint validado.')
        inner_unsigned = work/'client-clean.apk'
        with zipfile.ZipFile(work/'client/local-resources-unsigned.apk') as original:
            dex, analytics = patch(original.read('classes.dex'))
        assemble(work/'client/local-resources-unsigned.apk', inner_unsigned, {'classes.dex': dex})
        print('2/5 Preparando assinatura local...', flush=True)
        key, password = prepare_key(base, log) if signing_root is None else prepare_key(base, log, signing_root)
        inner = work/'client.apk'
        sign(inner_unsigned, inner, base, key, password, log, minimum=8)
        print('3/5 Montando jogo ARM64 com lugares integrados...', flush=True)
        with zipfile.ZipFile(source) as archive:
            icon = archive.read('res/drawable/icon.png')
        outer_unsigned = work/'game-unsigned.apk'
        from patcher.licensing import apk_notices
        assemble(base/'templates/game.apk', outer_unsigned, {
            **apk_notices(ROOT),
            'assets/nza-probe/trial-67.apk': inner.read_bytes(),
            dependency_metadata['icon_entry']: icon,
        })
        pending = work/'result'
        pending.mkdir()
        game = pending/'no-zombies-allowed-revived.apk'
        print('4/5 Assinando e verificando o APK integrado...', flush=True)
        sign(outer_unsigned, game, base, key, password, log)
        if sha(source) != EXPECTED:
            raise ValueError('A entrada foi alterada durante a execucao.')
        result = {'version': dependency_metadata.get('version',profile['version']), 'input_sha256': EXPECTED,
                  'package': profile['package'], 'places_authority': profile['places_authority'],
                  'game_sha256': sha(game), 'places_integrated': True, 'places_default_enabled': True,
                  'legacy_socket_guard': 'seccomp-tsync',
                  'runtime_built_from_sources': dependency_metadata.get('runtime_built_from_sources',False),
                  'runtime_source_build': dependency_metadata.get('source_build'),
                  'client_engine_sha256': report['output_elf_sha256'],
                  'foundation_sha256': report['foundation_patch']['output_sha256'],
                  'experimental_textures': len(report['resource_overlay']),
                  'aliases_reconstructed_from_input': len(report['resource_aliases']),
                  'offline_analytics': analytics, 'runtime_tested_this_build': False,
                  'public_release_allowed': False,
                  'known_issue': 'Supply-run route selector may be invisible; map/timer workaround remains.',
                  'features': ['offline-client','graphics','heroes','construction-buttons','offline-store',
                               'town-name','loading-credit','arm64','atomic-save','wide-fit','gps',
                               'integrated-places-default-on','legacy-process-network-guard']}
        (pending/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    import shutil
    shutil.copy2(work/'patch.log', pending/'patch.log')
    pending.rename(destination)
    print('5/5 Concluido. APK e relatorio em: ' + str(destination), flush=True)
    print('Guarde signing/ para poder atualizar os APKs mantendo a mesma assinatura.')
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description='No Zombies Allowed Revival — preparacao local de APK')
    parser.add_argument('--input', help='APK original 1.6.5 validado')
    parser.add_argument('--output', type=Path, default=ROOT/'output', help='Diretorio dos resultados')
    parser.add_argument('--check', action='store_true', help='Verificar dependencias sem gerar APKs')
    parser.add_argument('--dependencies', type=Path, help='Dependencias locais preparadas a partir das fontes')
    parser.add_argument('--signing', type=Path, help='Pasta da assinatura existente, para preservar atualizacoes')
    args = parser.parse_args(argv)
    try:
        if args.check:
            dependencies(args.dependencies)
            print('Dependencias verificadas; nenhum APK gerado.')
            return 0
        (ROOT/'input').mkdir(exist_ok=True)
        source = choose_input(args.input)
        execute(source, args.output.resolve(), args.dependencies, args.signing)
        return 0
    except Exception as exc:
        print('ERRO: ' + str(exc), file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
