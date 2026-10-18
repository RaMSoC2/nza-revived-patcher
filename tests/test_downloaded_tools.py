import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, script):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bootstrap = load('download_bootstrap', 'source_bootstrap.py')
prepare = load('download_prepare', 'prepare_source_runtime.py')


class DownloadedToolsTests(unittest.TestCase):
    def test_download_verified_then_reused_without_network(self):
        data = b'official archive fixture'
        item = {'filename': 'tool.zip', 'url': 'https://example.invalid/tool.zip',
                'sha256': hashlib.sha256(data).hexdigest()}
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with patch.object(bootstrap.urllib.request, 'urlopen', return_value=io.BytesIO(data)) as request:
                result = bootstrap.acquire(item, folder)
                self.assertEqual(result.read_bytes(), data)
                request.assert_called_once()
            with patch.object(bootstrap.urllib.request, 'urlopen', side_effect=AssertionError('network')):
                self.assertEqual(bootstrap.acquire(item, folder, offline=True), result)
                result.write_bytes(b'corrupt')
                with self.assertRaises(ValueError):
                    bootstrap.acquire(item, folder, offline=True)

    def test_wrong_download_hash_not_committed_to_cache(self):
        item = {'filename': 'tool.zip', 'url': 'https://example.invalid/tool.zip', 'sha256': '0'*64}
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with patch.object(bootstrap.urllib.request, 'urlopen', return_value=io.BytesIO(b'wrong')):
                with self.assertRaises(ValueError):
                    bootstrap.acquire(item, folder)
            self.assertFalse(list(folder.iterdir()))

    def test_execution_tools_work_without_bundled_java_or_android(self):
        with tempfile.TemporaryDirectory(prefix='nza tools with spaces ') as directory:
            root = Path(directory)
            portable = root / 'portable'
            (portable / 'python').mkdir(parents=True)
            (portable / 'python/python.exe').write_bytes(b'python fixture')
            jdk = root / 'downloaded jdk'
            jdk.mkdir()
            (jdk / 'NOTICE').write_bytes(b'jdk notice')
            build = root / 'downloaded build tools'
            (build / 'lib').mkdir(parents=True)
            for name in ('lib/apksigner.jar', 'zipalign.exe', 'libwinpthread-1.dll', 'NOTICE.txt'):
                (build / name).write_bytes(name.encode())
            deps = root / 'prepared'
            deps.mkdir()
            def jlink(command, check):
                self.assertEqual(command[0], str(jdk / 'bin/jlink.exe'))
                self.assertTrue(check)
                Path(command[-1]).mkdir()
            with patch.object(prepare.subprocess, 'run', side_effect=jlink):
                prepare.prepare_execution_tools(portable, deps, jdk, build)
            self.assertEqual((deps / 'java/NOTICE').read_bytes(), b'jdk notice')
            self.assertEqual((deps / 'tools/apksigner.jar').read_bytes(), b'lib/apksigner.jar')


if __name__ == '__main__':
    unittest.main()
