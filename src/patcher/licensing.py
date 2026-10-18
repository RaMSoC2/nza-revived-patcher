"""Carry notices into locally generated APKs; this does not clear release gates."""
import hashlib
import json


def apk_notices(root):
    ledger = json.loads((root / 'manifests/legal-review.json').read_text(encoding='utf-8'))
    additions = {}
    for item in ledger['runtime_notice_files']:
        data = (root / item['path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('License notice missing or changed: ' + item['path'])
        additions['assets/nza-licenses/' + (root / item['path']).name] = data
    additions['assets/nza-licenses/PROJECT-MIT.txt'] = (root / 'LICENSE').read_bytes()
    additions['assets/nza-licenses/THIRD_PARTY_NOTICES.txt'] = (root / 'THIRD_PARTY_NOTICES.txt').read_bytes()
    return additions
