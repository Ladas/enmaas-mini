"""Timeouts must not leave disposable clients holding issuer credentials."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('private_issuer',(Path(__file__).resolve().parents[1] / 'private-issuer-runtime.py'))
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


class Cleanup(unittest.TestCase):
    def test_cleanup_continues_after_failure_and_is_bounded(self):
        with patch.object(p,'command',side_effect=[subprocess.TimeoutExpired('podman',10),Mock(returncode=1),Mock(returncode=0),Mock(returncode=0)]) as run:
            with self.assertRaisesRegex(RuntimeError,'cleanup incomplete'):
                p.cleanup('owned', ['owned-secret'],proxy=True,container=True,network=True)
        self.assertEqual(run.call_count,4)
        self.assertTrue(all(call.kwargs['timeout']==10 for call in run.call_args_list))
        self.assertEqual(run.call_args_list[-1].args,('network','rm','owned'))

    def test_success_failure_and_timeout_remove_the_exact_ephemeral_client(self):
        for outcome in (Mock(returncode=0,stdout='PASS'),Mock(returncode=1),subprocess.TimeoutExpired('podman',60)):
            with patch.object(p.subprocess,'run',side_effect=[outcome,Mock(returncode=0)]) as run:
                if isinstance(outcome,Exception) or outcome.returncode:
                    with self.assertRaises((RuntimeError,subprocess.TimeoutExpired)):
                        p.command('run','--rm','--interactive','image','python3',input='test')
                else:p.command('run','--rm','--interactive','image','python3',input='test')
            invocation=run.call_args_list[0].args[0]
            self.assertIn('--name',invocation)
            name=invocation[invocation.index('--name')+1]
            self.assertTrue(name.startswith('enmaas-issuer-client-'))
            self.assertEqual(run.call_args_list[1].args[0],['podman','rm','--force','--ignore',name])

    def test_server_operations_are_not_removed_and_failed_cleanup_is_visible(self):
        with patch.object(p.subprocess,'run',return_value=Mock(returncode=0)) as run:
            p.command('run','--detach','--name','server','image')
            self.assertEqual(run.call_count,1)
        with patch.object(p.subprocess,'run',side_effect=[Mock(returncode=0),Mock(returncode=1)]):
            with self.assertRaisesRegex(RuntimeError,'cleanup'):
                p.command('run','--rm','image')


if __name__=='__main__':unittest.main()
