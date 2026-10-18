from pathlib import Path
import json,sys,tempfile,unittest,zipfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from patcher import app

class PatcherTests(unittest.TestCase):
    def test_unknown_input_is_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.apk';p.write_bytes(b'corrupted')
            before=p.read_bytes()
            with self.assertRaisesRegex(ValueError,'incompativel'):app.choose_input(p)
            self.assertEqual(before,p.read_bytes())

    def test_input_selection_refuses_ambiguity(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'ROOT',Path(d)):
            (Path(d)/'input').mkdir()
            for n in ('one.apk','two.apk'):(Path(d)/'input'/n).write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'exatamente um'):app.choose_input()

    def test_known_hash_still_requires_valid_zip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'broken.apk';p.write_bytes(b'invalid')
            with patch.object(app,'EXPECTED',app.sha(p)):
                with self.assertRaises(zipfile.BadZipFile):app.choose_input(p)

    def test_dependencies_cannot_escape_bundle(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'ROOT',Path(d)):
            base=Path(d)/'.dependencies';base.mkdir();outside=Path(d)/'outside';outside.write_bytes(b'a')
            (base/'manifest.json').write_text(json.dumps({'profile':'revived-0.2','files':[{'path':'../outside','sha256':app.sha(outside)}]}))
            with self.assertRaisesRegex(ValueError,'alterada'):app.dependencies()

    def test_missing_dependencies_explained(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'ROOT',Path(d)):
            with self.assertRaisesRegex(ValueError,'Dependencias ausentes'):app.dependencies()

    def test_packaging_preserves_input_and_replaces_only_requested_entries(self):
        with tempfile.TemporaryDirectory(prefix='nza path with spaces ') as d:
            source=Path(d)/'source.apk';target=Path(d)/'result.apk'
            with zipfile.ZipFile(source,'w') as z:
                z.writestr('classes.dex',b'host');z.writestr('res/icon.png',b'placeholder');z.writestr('META-INF/CERT.RSA',b'old')
            before=app.sha(source)
            app.assemble(source,target,{'res/icon.png':b'local','assets/game.apk':b'game'})
            with zipfile.ZipFile(target) as z:
                self.assertEqual(z.read('classes.dex'),b'host');self.assertEqual(z.read('res/icon.png'),b'local')
                self.assertEqual(z.read('assets/game.apk'),b'game');self.assertNotIn('META-INF/CERT.RSA',z.namelist())
                self.assertIsNone(z.testzip())
            self.assertEqual(before,app.sha(source))

    def test_partial_key_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as d,patch.object(app,'ROOT',Path(d)):
            p=Path(d)/'signing';p.mkdir();(p/'revived.jks').write_bytes(b'preserve')
            with self.assertRaisesRegex(ValueError,'incompleta'):app.prepare_key(Path(d),None)
            self.assertEqual((p/'revived.jks').read_bytes(),b'preserve')

if __name__=='__main__':unittest.main()
