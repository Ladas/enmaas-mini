#!/usr/bin/env python3
"""Exercise bootc build contracts without a registry."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PIN = "registry.redhat.io/rhel9/rhel-bootc@sha256:" + "a" * 64


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.log = self.directory / "calls"
        podman = self.directory / "podman"
        podman.write_text(
            """#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as output:
    output.write(json.dumps(args) + '\\n')
if args[0] == 'info':
    print('linux/amd64')
elif args[:2] == ['image', 'inspect']:
    print('b' * 64)
elif args[0] == 'build':
    file_index = args.index('-f') + 1
    context = pathlib.Path(args[-1])
    target = args[args.index('-t') + 1].rsplit(':', 1)[-1]
    expected = {
        'praxis': ('bootc/Containerfile.praxis', 'bootc/scripts/praxis'),
        'vllm-cpu': ('bootc/Containerfile.vllm.cpu', 'bootc/scripts/vllm-common'),
        'vllm-gpu': ('bootc/Containerfile.vllm.gpu', 'bootc/install-nvidia'),
    }[target]
    assert args[file_index].endswith(expected[0])
    assert (context / expected[1]).is_file()
    assert not (context / '.git').exists()
    assert not (context / 'rhsm_org').exists()
else:
    sys.exit(3)
"""
        )
        podman.chmod(0o755)
        self.env = {
            **{key: value for key, value in os.environ.items()
               if key not in {"RHSM_ORG_ID", "RHSM_ACTIVATION_KEY"}},
            "PATH": str(self.directory) + ":" + os.environ["PATH"],
            "CALL_LOG": str(self.log),
            "RHEL_BOOTC_IMAGE": PIN,
        }

    def run_build(self, *args):
        return subprocess.run(
            ["bash", str(ROOT / "bootc/build"), *args],
            env=self.env,
            text=True,
            capture_output=True,
        )

    def test_help_documents_only_supported_targets(self):
        result = self.run_build("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("praxis|vllm-cpu|vllm-gpu", result.stdout)
        self.assertNotIn("codex", result.stdout)
        self.assertNotIn("opencode", result.stdout)
        self.assertNotIn("openclaw", result.stdout)

    def test_rejects_removed_targets(self):
        for target in ("base", "codex", "opencode", "openclaw", "all"):
            result = self.run_build(target)
            self.assertNotEqual(result.returncode, 0)

    def test_supported_targets_build_isolated_contexts(self):
        for target in ("praxis", "vllm-cpu", "vllm-gpu"):
            self.log.unlink(missing_ok=True)
            result = self.run_build(target, "localhost/enmaas-mini")
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = [json.loads(line) for line in self.log.read_text().splitlines()]
            self.assertTrue(any(call[:1] == ["build"] for call in calls))


if __name__ == "__main__":
    unittest.main()
