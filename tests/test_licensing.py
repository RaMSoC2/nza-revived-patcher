import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from patcher.licensing import apk_notices


class LicensingTests(unittest.TestCase):
    def test_runtime_notices_present_and_verified(self):
        additions = apk_notices(ROOT)
        self.assertIn('assets/nza-licenses/ZettaBridge-LICENSE.txt', additions)
        self.assertIn('assets/nza-licenses/Dynarmic-dependencies.txt', additions)
        self.assertIn('assets/nza-licenses/Apache-2.0.txt', additions)
        self.assertIn('assets/nza-licenses/THIRD_PARTY_NOTICES.txt', additions)

    def test_changed_notice_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'manifests').mkdir()
            (root / 'notice.txt').write_bytes(b'changed')
            ledger = {'runtime_notice_files': [{'path': 'notice.txt', 'sha256': hashlib.sha256(b'original').hexdigest()}]}
            (root / 'manifests/legal-review.json').write_text(json.dumps(ledger))
            with self.assertRaisesRegex(ValueError, 'changed'):
                apk_notices(root)

    def test_all_experimental_payloads_have_provenance(self):
        records = json.loads((ROOT / 'manifests/asset-provenance.json').read_text())['resources']
        manifest = json.loads((ROOT / 'manifests/resources.json').read_text())
        self.assertEqual({r['sha256'] for r in records}, {r['sha256'] for r in manifest})
        self.assertEqual(len(records), 217)
        self.assertTrue(all(r['evidence_record_sha256'] and not r['authentic_recovered_art'] for r in records))


if __name__ == '__main__':
    unittest.main()
