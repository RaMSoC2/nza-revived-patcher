import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('audit_public', Path(__file__).resolve().parents[1] / 'scripts/audit_public.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PublicAuditTest(unittest.TestCase):
    def test_protected_files(self):
        for name in ('output/game.apk', 'signing/password.txt', 'data/save.sqlite',
                     'runtime/lib.so', '../escape.txt', '.env.local'):
            self.assertTrue(audit.inspect(name, b'test'), name)

    def test_executable_disguised_as_source(self):
        self.assertTrue(audit.inspect('src/innocent.txt', b'\x7fELFpayload'))

    def test_credentials_without_echoing_values(self):
        data = b'ghp_' + b'x' * 40
        result = audit.inspect('src/config.py', data)
        self.assertTrue(result)
        self.assertNotIn(data.decode(), str(result))

    def test_portable_tool_scope(self):
        self.assertFalse(audit.inspect('.dependencies/java/bin/java.exe', b'MZbinary', portable=True))
        self.assertTrue(audit.inspect('.dependencies/templates/game.bin', b'data', portable=True))

    def test_embedded_font_is_not_credential(self):
        self.assertFalse(audit.inspect('font.py', b'AwAaAKIAAQAAAAAABAAHAM0AAQAAAAAAB'))


if __name__ == '__main__':
    unittest.main()
