"""Real-inference tests against a live oMLX instance + real Aider subprocess.
NOT run in standard CI — requires oMLX running locally (`omlx serve`) with the
.agents/local.json roster downloaded, and the `aider` CLI installed. Run explicitly:
`pytest tests/test_local_agent_hardware.py -m local_hardware -v`"""

import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import pytest

from synlynk.local_agent import (
    _health_check,
    _load_local_config,
    _local_dispatch_model_flags,
    _pinned_model,
)


_LOCAL_CONFIG = {
    "name": "local",
    "endpoint": "http://127.0.0.1:8080",
    "models": [
        {"id": "ornith-1.0-9b", "pinned": True, "edit_format": "whole"},
        {"id": "qwen-coder", "pinned": False, "edit_format": "whole"},
        {"id": "gemma-coder", "pinned": False, "edit_format": "diff"},
    ],
    "hardware_tier": "16gb-default",
}


def _make_local_config() -> tuple:
    tmpdir = tempfile.TemporaryDirectory()
    config_path = os.path.join(tmpdir.name, "local.json")
    with open(config_path, "w") as f:
        json.dump(_LOCAL_CONFIG, f)
    return tmpdir, config_path


class _LocalHardwareBase(unittest.TestCase):
    def setUp(self):
        self._tmpdir, config_path = _make_local_config()
        self.addCleanup(self._tmpdir.cleanup)

        self._config_patcher = patch(
            "synlynk.local_agent._DEFAULT_CONFIG_PATH", config_path
        )
        self._config_patcher.start()
        self.addCleanup(self._config_patcher.stop)

        self.config = _load_local_config()
        result = _health_check(self.config["endpoint"])
        if not result["reachable"]:
            self.skipTest(
                f"oMLX not reachable at {self.config['endpoint']} — start with `omlx serve`"
            )


@pytest.mark.local_hardware
class TestRealOmlxHealthCheck(_LocalHardwareBase):
    def test_pinned_model_is_available(self):
        result = _health_check(self.config["endpoint"])
        pinned = _pinned_model(self.config)
        self.assertIn(pinned, result["available_models"])


@pytest.mark.local_hardware
class TestAiderSubprocessEndToEnd(_LocalHardwareBase):
    """Spawns the real `aider` CLI against the real oMLX endpoint, mirroring
    exactly what dispatch_agent() does for agent='local' in production (Task
    Group 1, Steps 7 and 10): static dispatch_flags + dynamic model flags,
    prompt delivered via --message-file, run inside a scratch git worktree
    (Aider requires a git repo to operate in)."""

    def test_aider_edits_a_real_file(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q"], cwd=d, check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=d, check=True)
            subprocess.run(["git", "config", "user.name", "test"], cwd=d, check=True)

            target = os.path.join(d, "add.py")
            with open(target, "w") as f:
                f.write("# implement add(a, b) below\n")

            prompt_file = os.path.join(d, "prompt.txt")
            with open(prompt_file, "w") as f:
                f.write(
                    "In add.py, implement a function add(a, b) that returns a + b. "
                    "Only edit add.py."
                )

            flags = ["--no-auto-commits", "--yes-always"] + _local_dispatch_model_flags()
            proc = subprocess.run(
                ["aider"] + flags + ["--message-file", prompt_file, "add.py"],
                cwd=d,
                capture_output=True,
                text=True,
                timeout=180,
            )

            with open(target) as f:
                content = f.read()

        self.assertEqual(proc.returncode, 0)
        self.assertIn("def add", content)


if __name__ == "__main__":
    unittest.main()
