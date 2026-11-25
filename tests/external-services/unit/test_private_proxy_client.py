"""Only a denial from the OAuth callback qualifies the proxy's group gate."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest
import urllib.error
from unittest.mock import MagicMock, Mock, patch

spec=importlib.util.spec_from_file_location('private_proxy_client',
    Path(__file__).resolve().parents[1]/'private-proxy-client.py')
p=importlib.util.module_from_spec(spec)
with patch.dict(sys.modules,{'issuer_client':types.SimpleNamespace(Form=Mock(),document=Mock())}):
    # The runtime mounts issuer_client in /run/secrets; do not require that mount
    # or leave its import path in the unit-test process.
    with patch.object(sys,'path',list(sys.path)):
        spec.loader.exec_module(p)


class GroupGate(unittest.TestCase):
    def exercise(self,denial_url,denial_status=403):
        admin=MagicMock()
        admin.open.return_value.__enter__=Mock(return_value=types.SimpleNamespace(
            status=202,url=p.PROXY+'/'))
        admin.open.return_value.__exit__=Mock(return_value=False)
        denied=Mock()
        def deny(*args,**kwargs):
            raise urllib.error.HTTPError(denial_url,denial_status,'denied',{},io.BytesIO())
        denied.open.side_effect=deny
        documents=[urllib.error.HTTPError(p.PROXY+'/oauth2/auth',401,'denied',{},io.BytesIO()),
                   urllib.error.HTTPError(p.PROXY+'/oauth2/auth',401,'denied',{},io.BytesIO()),
                   b'form',b'form',b'form']
        with patch.object(p,'client',side_effect=[Mock(),Mock(),admin,denied,denied]), \
                patch.object(p,'document',side_effect=documents), \
                patch.object(p,'Form',return_value=Mock(action=p.ISSUER+'/login')), \
                patch.object(p.Path,'read_text',return_value=json.dumps(
                    dict.fromkeys(('admin','alice','bob'),'synthetic-test-password'))), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            p.main()
        return out.getvalue()

    def test_callback_denials_qualify_both_non_admins(self):
        output=self.exercise(p.PROXY+'/oauth2/callback?state=fixture')
        self.assertIn('alice denied by administrator-group gate',output)
        self.assertIn('bob denied by administrator-group gate',output)

    def test_issuer_or_wrong_proxy_endpoint_cannot_qualify_group_denial(self):
        for url in (p.ISSUER+'/login',p.PROXY+'/oauth2/auth',
                    p.PROXY+'/oauth2/callback/extra',
                    'http://observability.lab.example.com:19443/oauth2/callback',
                    'https://observability.lab.example.com:443/oauth2/callback',
                    'https://other.example.com:19443/oauth2/callback'):
            with self.subTest(url=url),self.assertRaisesRegex(RuntimeError,'proxy callback'):
                self.exercise(url)

    def test_non_forbidden_callback_is_not_a_group_denial(self):
        with self.assertRaisesRegex(RuntimeError,'unexpected group authorization'):
            self.exercise(p.PROXY+'/oauth2/callback',401)


if __name__=='__main__':unittest.main()
