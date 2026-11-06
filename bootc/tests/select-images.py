#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bootc/ci/select-images.py"


class SelectImagesTests(unittest.TestCase):
    def select(self, paths):
        result = subprocess.run(
            ["python3", str(SCRIPT)],
            input="\n".join(paths) + "\n",
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_praxis_only_change_selects_praxis(self):
        self.assertEqual(
            self.select(["bootc/Containerfile.praxis"]),
            {"praxis": True, "vllm_cpu": False, "vllm_gpu": False},
        )

    def test_vllm_cpu_only_change_selects_cpu(self):
        self.assertEqual(
            self.select(["bootc/Containerfile.vllm.cpu"]),
            {"praxis": False, "vllm_cpu": True, "vllm_gpu": False},
        )

    def test_vllm_gpu_only_change_selects_gpu(self):
        self.assertEqual(
            self.select(["bootc/install-nvidia"]),
            {"praxis": False, "vllm_cpu": False, "vllm_gpu": True},
        )

    def test_shared_vllm_change_selects_both_profiles(self):
        self.assertEqual(
            self.select(["bootc/scripts/vllm-common"]),
            {"praxis": False, "vllm_cpu": True, "vllm_gpu": True},
        )

    def test_ci_change_selects_all_image_groups(self):
        self.assertEqual(
            self.select([".github/workflows/bootc-images.yml"]),
            {"praxis": True, "vllm_cpu": True, "vllm_gpu": True},
        )

    def test_ignored_path_selects_nothing(self):
        self.assertEqual(
            self.select(["README.md"]),
            {"praxis": False, "vllm_cpu": False, "vllm_gpu": False},
        )


if __name__ == "__main__":
    unittest.main()
