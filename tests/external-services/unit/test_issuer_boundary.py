"""Public issuer checks support reviewed IP/DNS names and fail closed."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('issuer_boundary', HERE/'keycloak-boundary.py')
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)


class Boundary(unittest.TestCase):
    def check(self, hostname, *, poison=False, forbidden_status=404):
        origin = 'https://' + hostname + ':8443'
        issuer = origin + '/realms/enmaas-lab'
        body = json.dumps({'issuer': issuer, **{key: issuer + '/' + key for key in
            ('authorization_endpoint', 'token_endpoint', 'jwks_uri')}}).encode()
        if poison:
            body = body.replace(hostname.encode(), b'attacker.example')
        connection = Mock()
        connection.getresponse.side_effect = [
            SimpleNamespace(status=200, read=lambda size: body),
            *[SimpleNamespace(status=forbidden_status, read=lambda size: b'') for _ in range(9)]]
        with patch.object(boundary.ssl, 'create_default_context') as tls, \
             patch.object(boundary.http.client, 'HTTPSConnection', return_value=connection) as create, \
             contextlib.redirect_stdout(io.StringIO()):
            boundary.check(origin, Path('/reviewed/ca.pem'))
            tls.assert_called_once_with(cafile='/reviewed/ca.pem')
            self.assertTrue(all(call.args[:2]==(hostname, 8443) for call in create.call_args_list))
            self.assertTrue(all(call.kwargs['context'] is tls.return_value for call in create.call_args_list))

    def test_ip_and_dns_origins_preserve_tls_identity(self):
        self.check('192.0.2.10')
        self.check('identity.example.test')

    def test_rejects_poisoned_discovery_and_unexpected_status(self):
        with self.assertRaisesRegex(RuntimeError, 'unexpected issuer'):
            self.check('identity.example.test', poison=True)
        for status in (200, 302, 500, 502):
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, 'boundary failed'):
                self.check('192.0.2.10', forbidden_status=status)

    def test_invalid_origin_is_rejected_before_connecting(self):
        with patch.object(boundary.ssl, 'create_default_context') as tls:
            for origin in ('http://192.0.2.10', 'https://user:secret@192.0.2.10',
                           'https://identity.example/path', 'https://identity.example/?q=1'):
                with self.subTest(origin=origin), self.assertRaises(ValueError):
                    boundary.check(origin, Path('/unused'))
            tls.assert_not_called()


if __name__ == '__main__':
    unittest.main()
