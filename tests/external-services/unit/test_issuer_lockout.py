"""Lockout-fixture cleanup never skips recorded secrets after one failure."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('lockout',
    Path(__file__).resolve().parents[1]/'issuer-lockout.py')
lockout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lockout)


class Cleanup(unittest.TestCase):
    def test_only_recorded_resources_and_bounded_cleanup(self):
        with patch.object(lockout, 'run') as run:
            lockout.cleanup('fixture', True, ['one', 'two'])
            self.assertEqual([call.args for call in run.call_args_list],
                [('rm', '-f', 'fixture'), ('secret', 'rm', 'one'), ('secret', 'rm', 'two')])
            self.assertTrue(all(call.kwargs == {'timeout': 10} for call in run.call_args_list))
            run.reset_mock()
            lockout.cleanup('fixture', False, [])
            run.assert_not_called()

    def test_failure_continues_remaining_cleanup(self):
        for error in (OSError('private output'), subprocess.TimeoutExpired('podman', 10)):
            with patch.object(lockout, 'run', side_effect=[error, b'', b'']) as run:
                with self.assertRaisesRegex(RuntimeError, 'fixture') as caught:
                    lockout.cleanup('fixture', True, ['one', 'two'])
                self.assertEqual(run.call_count, 3)
                self.assertNotIn('private output', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
