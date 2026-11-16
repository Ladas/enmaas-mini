"""Read-only observation failures are retried within a fixed bound, never ignored."""
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import local_probe


class Probe(unittest.TestCase):
    def test_transient_timeout_then_success(self):
        result=SimpleNamespace(stdout=b'actual data')
        with patch.object(local_probe.subprocess,'run',side_effect=[subprocess.TimeoutExpired(['probe'],5),result]) as run,patch.object(local_probe.time,'sleep'):
            self.assertIs(local_probe.read(['probe']),result)
            self.assertEqual(run.call_count,2)
            self.assertEqual(run.call_args.kwargs['timeout'],5)
            self.assertTrue(run.call_args.kwargs['check'])

    def test_persistent_failure_is_bounded_and_private(self):
        for failure in (subprocess.TimeoutExpired(['probe'],5),subprocess.CalledProcessError(1,['probe'],stderr=b'private diagnostic')):
            with patch.object(local_probe.subprocess,'run',side_effect=failure) as run,patch.object(local_probe.time,'sleep'):
                with self.assertRaisesRegex(RuntimeError,'three bounded attempts') as error:local_probe.read(['probe'])
                self.assertEqual(run.call_count,3)
                self.assertNotIn('private diagnostic',str(error.exception))

if __name__=='__main__':unittest.main()
