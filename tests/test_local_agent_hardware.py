"""Real-inference tests against a live oMLX instance + real Aider subprocess.

NOT run in standard CI. They use the repository's current ``.agents/local.json``
instead of a stale fixture, require its models to be served by oMLX, and require
``OPENAI_API_KEY`` when the endpoint requires authentication. Run explicitly:
``pytest tests/test_local_agent_hardware.py -m local_hardware -v``.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest

from synlynk.local_agent import (
    _health_check,
    _load_local_config,
    _local_dispatch_model_flags,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LOCAL_CONFIG_PATH = _REPO_ROOT / ".agents" / "local.json"


class _LocalHardwareBase(unittest.TestCase):
    def setUp(self):
        if not _LOCAL_CONFIG_PATH.exists():
            self.skipTest(f"local config not found: {_LOCAL_CONFIG_PATH}")
        self.config_path = str(_LOCAL_CONFIG_PATH)
        self.config = _load_local_config(self.config_path)
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            self.skipTest("OPENAI_API_KEY is required for authenticated local oMLX checks")
        result = _health_check(self.config["endpoint"], api_key=self.api_key)
        if not result["reachable"]:
            self.skipTest(
                f"authenticated oMLX unavailable at {self.config['endpoint']}: "
                f"{result['error']}"
            )
        self.available_models = set(result["available_models"])

    def selected_model_id(self) -> str:
        flags = _local_dispatch_model_flags(self.config_path)
        model_index = flags.index("--model")
        return flags[model_index + 1].removeprefix("openai/")


@pytest.mark.local_hardware
class TestRealOmlxHealthCheck(_LocalHardwareBase):
    def test_effective_local_model_is_available(self):
        self.assertIn(self.selected_model_id(), self.available_models)


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

            flags = ["--no-auto-commits", "--yes-always"] + _local_dispatch_model_flags(
                self.config_path
            )
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
        self.assertNotEqual(content, "# implement add(a, b) below\n")


if __name__ == "__main__":
    unittest.main()
