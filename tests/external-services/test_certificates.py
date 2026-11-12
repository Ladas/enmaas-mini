#!/usr/bin/env python3
"""Real OpenSSL verification of lab role bundles and trust separation."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('certificates',Path(__file__).with_name('certificates.py'))
certs=importlib.util.module_from_spec(spec);spec.loader.exec_module(certs)

class Certificates(unittest.TestCase):
    def test_role_bundles_and_eku_isolate_client_trust(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'lab'
            certs.generate(root,{'gateway':['192.0.2.10','10.0.0.10'],
                                 'keycloak':['192.0.2.11','10.0.0.11'],
                                 'observability':['192.0.2.12','10.0.0.12']},7)
            for role in ('gateway','keycloak','observability'):
                bundle=root/role
                result=subprocess.run(['openssl','verify','-CAfile',str(root/'trust/issuer-ca.pem'),
                    '-purpose','sslserver',str(bundle/'server.pem')],capture_output=True)
                self.assertEqual(result.returncode,0)
                self.assertFalse(any(p.name.endswith('ca.key') for p in bundle.rglob('*')))
                self.assertEqual((bundle/'server.key').stat().st_mode&0o777,0o600)
            client=root/'gateway/telemetry-client.pem'
            valid=subprocess.run(['openssl','verify','-CAfile',str(root/'trust/telemetry-ca.pem'),
                '-purpose','sslclient',str(client)],capture_output=True)
            self.assertEqual(valid.returncode,0)
            wrong=subprocess.run(['openssl','verify','-CAfile',str(root/'trust/telemetry-ca.pem'),
                '-purpose','sslclient',str(root/'keycloak/server.pem')],capture_output=True)
            self.assertNotEqual(wrong.returncode,0)
            for path in root.rglob('*'):
                self.assertEqual(path.stat().st_mode&0o077,0)
            with self.assertRaises(FileExistsError):certs.generate(root,{},7)

    def test_invalid_inputs_do_not_create_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'lab'
            for hosts,days in (({'gateway':['bad']},7),({},0),({},365)):
                with self.assertRaises(ValueError):certs.generate(root,hosts,days)
                self.assertFalse(root.exists())

if __name__=='__main__':unittest.main()
