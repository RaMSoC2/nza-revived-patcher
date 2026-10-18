from pathlib import Path
import hashlib,sys,tempfile,unittest,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from patcher.source_runtime import apply_unified_patch,checked_archive,extract_zip


class SourceRuntimeTests(unittest.TestCase):
    def test_exact_patch_and_changed_context(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);file=root/'file.txt';file.write_text('one\ntwo\nthree\n')
            patch=root/'change.patch';patch.write_text('--- a/file.txt\n+++ b/file.txt\n@@ -1,3 +1,3 @@\n one\n-two\n+second\n three\n')
            self.assertEqual(apply_unified_patch(root,patch),['file.txt'])
            self.assertEqual(file.read_text(),'one\nsecond\nthree\n')
            with self.assertRaisesRegex(ValueError,'context mismatch'):apply_unified_patch(root,patch)
            self.assertEqual(file.read_text(),'one\nsecond\nthree\n')

    def test_archive_hash_required(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'archive.zip';p.write_bytes(b'wrong source')
            with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):checked_archive(p,'0'*64)
            checked_archive(p,hashlib.sha256(p.read_bytes()).hexdigest())

    def test_zip_traversal_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive=root/'bad.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('root/../../escaped.txt','bad')
            with self.assertRaises(ValueError):extract_zip(archive,root/'out')
            self.assertFalse((root/'escaped.txt').exists())

    def test_case_collisions_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive=root/'bad.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('root/Readme','one');z.writestr('root/README','two')
            with self.assertRaisesRegex(ValueError,'Duplicate'):extract_zip(archive,root/'out')

    def test_patch_cannot_leave_root(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);patch=root/'bad.patch'
            patch.write_text('--- a/../file\n+++ b/../file\n@@ -1 +1 @@\n-old\n+new\n')
            with self.assertRaisesRegex(ValueError,'Unsafe patch'):apply_unified_patch(root,patch)


if __name__=='__main__':unittest.main()
