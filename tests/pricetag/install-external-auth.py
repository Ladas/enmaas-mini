#!/usr/bin/env python3
"""Exercise the real install orchestrator; replace only host/service boundaries."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('install_orchestration_subject', ROOT/'scripts/pricetag/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class ExternalAuthentication(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.units = self.home/'units'
        self.units.mkdir()
        self.inputs = self.home/'inputs'
        self.inputs.mkdir()
        self.commands = []
        self.output = io.StringIO()
        self.failure = None
        self.volume_status = 1
        self.helper = SimpleNamespace(
            STATE=self.inputs, save_provider=Mock(),
            provider_urls=Mock(return_value={'openai': 'https://provider.example/v1'}),
            collect_credential=Mock(return_value='synthetic-private-credential'),
            provider_settings=Mock(return_value={'models': []}),
        )
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        patches = {
            'preflight': Mock(), 'provider_module': Mock(return_value=self.helper),
            'open_log': Mock(), 'service_prefix': Mock(return_value=['service-user']),
            'acquire_images': Mock(return_value=('maas-image', 'metering-image')),
            'import_image': Mock(side_effect=['sha256:'+'1'*64, 'sha256:'+'2'*64, 'sha256:'+'3'*64]),
            'run': self.run_command, 'INPUTS': self.inputs, 'DEPLOY': self.home/'config',
            'Path': lambda value: self.units if str(value).startswith('/etc/containers/systemd/users/') else Path(value),
        }
        for name, value in patches.items():
            self.stack.enter_context(patch.object(installer, name, value))
        self.stack.enter_context(patch.object(installer.os, 'umask'))
        self.stack.enter_context(patch.object(installer.platform, 'machine', return_value='x86_64'))
        self.stack.enter_context(patch.object(installer.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=995)))
        self.stack.enter_context(patch.object(installer.subprocess, 'run', side_effect=self.host_command))
        self.stack.enter_context(contextlib.redirect_stdout(self.output))


    def run_command(self, command, *args, **kwargs):
        command = list(map(str, command))
        self.commands.append(command)
        if self.failure and self.failure(command):
            raise subprocess.CalledProcessError(1, command)
        return ''


    def host_command(self, command, **kwargs):
        if command == ['service-user', 'podman', 'volume', 'exists', 'pricetag-data']:
            return SimpleNamespace(returncode=self.volume_status)
        if command == ['service-user', 'podman', 'secret', 'create', 'pricetag-mock-ui-v1', '-']:
            self.assertEqual(kwargs['input'], b'synthetic-anthropic')
            self.assertTrue(kwargs['check'])
            return SimpleNamespace(returncode=0)
        self.fail('Unexpected host command: ' + str(command))


    def args(self, *extra):
        args = installer.parse_args(['--hostname', 'gateway.example', '--mode', 'mock',
                                     '--plan', '--yes', *extra])
        args.plan = False
        return args


    def preparation(self):
        return next(c for c in self.commands if str(ROOT/'scripts/pricetag/prepare.py') in c)


    def test_remote_service_inputs_are_validated_and_forwarded(self):
        # Validators have their own contract suites; here test orchestration/order.
        installer.sys.path.insert(0, str(ROOT/'scripts/pricetag'))
        import prepare
        import oidc_config
        import tls_bundle
        args = self.args('--image-mode', 'source', '--no-sample-users')
        args.maas_database_url_file = self.home/'maas.url'
        args.metering_database_url_file = self.home/'metering.url'
        args.external_database_ca_file = self.home/'db-ca.pem'
        args.oidc_config = self.home/'oidc.json'
        args.tls_bundle = self.home/'tls'
        args.maas_database_url_file.write_text('synthetic-maas-db')
        args.metering_database_url_file.write_text('synthetic-metering-db')
        with patch.object(prepare, 'validate_external_database_urls') as db, patch.object(
                oidc_config, 'load') as oidc, patch.object(tls_bundle, 'validate') as tls:
            self.volume_status = 125  # External DB must not query a local data volume.
            installer.install(args)
            db.assert_called_once_with('synthetic-maas-db', 'synthetic-metering-db', args.external_database_ca_file)
            oidc.assert_called_once_with(args.oidc_config, 'https://gateway.example:8443')
            tls.assert_called_once_with(args.tls_bundle, args.hostname)
        command = self.preparation()
        for flag, value in (('--maas-database-url-file', args.maas_database_url_file),
                            ('--metering-database-url-file', args.metering_database_url_file),
                            ('--external-database-ca-file', args.external_database_ca_file),
                            ('--oidc-config', args.oidc_config), ('--tls-bundle', args.tls_bundle)):
            self.assertEqual(command[command.index(flag)+1], str(value))
        self.assertNotIn('synthetic-maas-db', self.output.getvalue()+str(self.commands))

    def test_invalid_auth_inputs_fail_before_host_changes(self):
        installer.sys.path.insert(0, str(ROOT/'scripts/pricetag'))
        import oidc_config
        import tls_bundle
        for module, name, option, value in (
                (oidc_config, 'load', '--oidc-config', self.home/'oidc.json'),
                (tls_bundle, 'validate', '--tls-bundle', self.home/'tls')):
            with self.subTest(option=option), patch.object(module, name,
                    side_effect=ValueError('invalid protected input')):
                with self.assertRaisesRegex(ValueError, 'invalid protected input'):
                    installer.install(self.args('--image-mode', 'source', option, str(value)))
                installer.preflight.assert_not_called()
                installer.acquire_images.assert_not_called()
                self.assertEqual(self.commands, [])

    def test_legacy_published_image_cannot_enable_oidc(self):
        args = self.args('--oidc-config', str(self.home/'oidc.json'))
        args.metering_revision = 'ce9c6c51b8dff178637003945b517255c54fc853'
        with self.assertRaisesRegex(ValueError, 'no OIDC handler'):
            installer.install(args)
        installer.preflight.assert_not_called()
        self.assertEqual(self.commands, [])


if __name__ == '__main__':
    unittest.main()
