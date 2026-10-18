"""Audit exact Git candidates and a source-mode portable ZIP. No license clearance."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {'.apk', '.ipa', '.aab', '.apks', '.xapk', '.obb', '.dex', '.so',
             '.jks', '.keystore', '.p12', '.pfx', '.pem', '.key', '.log', '.db', '.sqlite'}
PRIVATE = {'signing', 'saves', 'input', 'output', 'work', 'originals', 'decompiled',
           'private', 'backups', '.git', '.cache', 'runtime-input'}
SECRETS = [re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),
           re.compile(rb'gh[pousr]_[A-Za-z0-9]{36,}'),
           re.compile(rb'github_pat_[A-Za-z0-9_]{50,}'),
           re.compile(rb'(?<![A-Za-z0-9])AKIA[0-9A-Z]{16}(?![A-Za-z0-9])'),
           re.compile(rb'AIza[0-9A-Za-z_-]{35}')]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect(name, data, portable=False):
    path = PurePosixPath(name)
    problems = []
    if path.is_absolute() or '..' in path.parts or '\\' in name:
        problems.append('unsafe path')
    if any(part in PRIVATE for part in path.parts) or path.name.startswith('.env'):
        problems.append('private path')
    if path.suffix.lower() in FORBIDDEN:
        problems.append('protected artifact')
    dependency = portable and name.startswith('.dependencies/')
    if dependency:
        if len(path.parts) > 1 and path.parts[1] not in {
                'java', 'python', 'tools', 'manifest.json', 'source-runtime-mode.json'}:
            problems.append('unexpected dependency directory')
    else:
        if path.suffix.lower() in {'.exe', '.dll', '.jar', '.zip', '.7z'}:
            problems.append('binary/archive outside portable tools')
        if data.startswith((b'\x7fELF', b'dex\n', b'MZ', b'PK\x03\x04')):
            problems.append('unexpected executable/archive signature')
    if b'\0' not in data[:4096]:
        if any(pattern.search(data) for pattern in SECRETS):
            problems.append('credential pattern (value withheld)')
        # Split markers so the scanner does not match its own implementation.
        markers = [('D:' + chr(92) + 'Projetos' + chr(92)).encode(),
                   ('C:' + chr(92) + 'Users' + chr(92)).encode(),
                   ('C:' + '/Users/').encode()]
        if any(marker in data for marker in markers):
            problems.append('personal absolute path')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, required=True)
    parser.add_argument('--original', type=Path, action='append', default=[])
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    names = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--cached',
                                    '--others', '--exclude-standard', '-z']).decode().split('\0')
    files = {}
    failures = []
    for name in sorted(filter(None, names)):
        path = ROOT / name
        if path.is_symlink():
            failures.append({'file': name, 'reason': ['symbolic link']})
            continue
        data = path.read_bytes()
        files[name] = data
        reasons = inspect(name, data)
        if reasons:
            failures.append({'file': name, 'reason': reasons})
    resources = json.loads((ROOT / 'manifests/resources.json').read_text())
    resource_paths = set()
    for item in resources:
        name = item['source_file']
        resource_paths.add(name)
        if item['kind'] != 'recreated_experimental' or digest(files.get(name, b'')) != item['sha256']:
            failures.append({'file': name, 'reason': ['resource label/hash mismatch']})
    for name in files:
        if name.startswith('assets/') and name not in resource_paths:
            failures.append({'file': name, 'reason': ['unregistered asset']})
    originals = []
    for original in args.original:
        hashes = {}
        with zipfile.ZipFile(original) as archive:
            for entry in archive.infolist():
                if not entry.is_dir():
                    hashes.setdefault(digest(archive.read(entry)), entry.filename)
        matches = []
        for name, data in files.items():
            if digest(data) in hashes:
                matches.append({'candidate': name, 'original_entry': hashes[digest(data)]})
        originals.append({'sha256': digest(original.read_bytes()), 'entry_count': len(hashes),
                          'exact_payload_matches': matches})
        failures.extend({'file': match['candidate'], 'reason': ['exact original APK payload']}
                        for match in matches)
    zip_files = []
    with zipfile.ZipFile(args.zip) as archive:
        seen = set()
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            name = entry.filename.removeprefix('nza-patcher/')
            if not entry.filename.startswith('nza-patcher/') or name.casefold() in seen:
                failures.append({'file': entry.filename, 'reason': ['root/duplicate ZIP entry']})
            seen.add(name.casefold())
            data = archive.read(entry)
            reasons = inspect(name, data, portable=True)
            if not name.startswith('.dependencies/'):
                if name not in files:
                    reasons.append('ZIP file absent from Git candidates')
                elif data != files[name]:
                    reasons.append('ZIP differs from current source')
            if reasons:
                failures.append({'file': entry.filename, 'reason': reasons})
            zip_files.append({'path': name, 'size': len(data), 'sha256': digest(data)})
        lock = json.loads(archive.read('nza-patcher/.dependencies/manifest.json'))
        marker = json.loads(archive.read('nza-patcher/.dependencies/source-runtime-mode.json'))
        if marker.get('contains_java_or_android_tools') is False:
            if any(f['path'].startswith(('.dependencies/java/', '.dependencies/tools/')) for f in zip_files):
                failures.append({'file': '.dependencies', 'reason': ['unexpected bundled Java/Android tools']})
        if marker.get('contains_prebuilt_runtime') is not False:
            failures.append({'file': 'source-runtime-mode.json', 'reason': ['runtime not excluded']})
        for item in lock['files']:
            data = archive.read('nza-patcher/.dependencies/' + item['path'])
            if digest(data) != item['sha256']:
                failures.append({'file': item['path'], 'reason': ['dependency lock mismatch']})
    report = {'scope': 'content/privacy, not legal clearance', 'passed': not failures,
              'git_candidates': [{'path': n, 'size': len(d), 'sha256': digest(d)}
                                 for n, d in files.items()],
              'experimental_resources': len(resources), 'original_comparisons': originals,
              'zip_sha256': digest(args.zip.read_bytes()), 'zip_files': zip_files,
              'failures': failures,
              'limits': ['Exact-byte comparison does not detect crops, recoloring or partial pixel reuse.',
                         'Experimental provenance labels do not independently prove authorship or rights.',
                         'Secret pattern checks cannot prove absence of every possible secret.']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'git_files': len(files),
                      'zip_files': len(zip_files), 'resources': len(resources),
                      'failures': failures}, indent=2))
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
