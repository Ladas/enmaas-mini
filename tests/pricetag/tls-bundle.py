#!/usr/bin/env python3
"""Check supplied certificates using real TLS handshakes without opening ports."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/pricetag'))
import tls_bundle


class Bundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        for name in ('issuer', 'unrelated'):
            subprocess.run([str(ROOT / 'scripts/remote-gateway/credentials'),
                'lab-tls', '--directory', str(cls.root / name), '--hostname', '192.0.2.10',
                '--alt-hostname', 'localhost', '--alt-hostname', '127.0.0.1'],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.bundle = Path(temporary.name)
        for source, destination in (('server.pem', 'server.pem'),
                                    ('server-key.pem', 'server.key'), ('ca.pem', 'ca.pem')):
            shutil.copyfile(self.root / 'issuer' / source, self.bundle / destination)
            (self.bundle / destination).chmod(0o600)

    def test_valid_bundle_and_wrong_hostname(self):
        self.assertEqual(set(tls_bundle.validate(self.bundle, '192.0.2.10')),
                         {'server.pem', 'server.key', 'ca.pem'})
        with self.assertRaises(ValueError):
            tls_bundle.validate(self.bundle, '192.0.2.99')

    def test_rejects_unsafe_directory_and_key_permissions(self):
        self.bundle.chmod(0o777)
        with self.assertRaises(ValueError):
            tls_bundle.validate(self.bundle, '192.0.2.10')
        self.bundle.chmod(0o700)
        (self.bundle / 'server.key').chmod(0o644)
        with self.assertRaises(ValueError):
            tls_bundle.validate(self.bundle, '192.0.2.10')

    def test_rejects_unrelated_ca_and_mismatched_key(self):
        for source, destination in (('ca.pem', 'ca.pem'), ('server-key.pem', 'server.key')):
            with self.subTest(file=destination):
                target = self.bundle / destination
                original = target.read_bytes()
                target.write_bytes((self.root / 'unrelated' / source).read_bytes())
                with self.assertRaises(ValueError):
                    tls_bundle.validate(self.bundle, '192.0.2.10')
                target.write_bytes(original)

    def test_rejects_missing_file_and_symlink(self):
        target = self.bundle / 'server.key'
        target.unlink()
        with self.assertRaises(ValueError):
            tls_bundle.validate(self.bundle, '192.0.2.10')
        target.symlink_to(self.root / 'issuer/server-key.pem')
        with self.assertRaises(ValueError):
            tls_bundle.validate(self.bundle, '192.0.2.10')


if __name__ == '__main__':
    unittest.main()
