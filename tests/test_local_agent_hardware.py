"""Real-inference tests against a live oMLX instance + real Aider subprocess.
NOT run in standard CI — requires oMLX running locally (`omlx serve`) with the
.agents/local.json roster downloaded, and the `aider` CLI installed. Run explicitly:
`pytest tests/test_local_agent_hardware.py -m local_hardware -q`"""

import os
import shutil
import subprocess
import tempfile
import unittest

import pytest

from synlynk.local_agent import (
    _DEFAULT_CONFIG_PATH,
    _health_check,
    _load_local_config,
    _local_dispatch_model_flags,
    _pinned_model,
)


def _skip_unless_local_stack_ready(test_case: unittest.TestCase) -> dict:
    """Load real `.agents/local.json` and skip when the local stack is unavailable.

    Real-hardware tests must exercise the production roster path (not a temp
    fixture with stale model ids / ports). Missing config, unreachable oMLX,
    or a 401 without OPENAI_API_KEY all skip cleanly rather than fail CI.
    """
    try:
        config = _load_local_config()
    except FileNotFoundError as exc:
        test_case.skipTest(
            f"{exc} — materialize {_DEFAULT_CONFIG_PATH} (tracked on main) before "
            "running the local_hardware tier"
        )

    api_key = os.environ.get("OPENAI_API_KEY")
    result = _health_check(config["endpoint"], api_key=api_key)
    if not result["reachable"]:
        hint = f"oMLX not reachable at {config['endpoint']} — start with `omlx serve`"
        err = result.get("error", "")
        if "401" in err:
            hint += " (401 Unauthorized — export OPENAI_API_KEY and retry)"
        test_case.skipTest(hint)
    return config


@pytest.mark.local_hardware
class TestRealOmlxHealthCheck(unittest.TestCase):
    def setUp(self):
        self.config = _skip_unless_local_stack_ready(self)

    def test_pinned_model_is_available(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        result = _health_check(self.config["endpoint"], api_key=api_key)
        pinned = _pinned_model(self.config)
        self.assertIn(pinned, result["available_models"])


@pytest.mark.local_hardware
class TestAiderSubprocessEndToEnd(unittest.TestCase):
    """Spawns the real `aider` CLI against the real oMLX endpoint, mirroring
    exactly what dispatch_agent() does for agent='local' in production (Task
    Group 1, Steps 7 and 10): static dispatch_flags + dynamic model flags,
    prompt delivered via --message-file, run inside a scratch git worktree
    (Aider requires a git repo to operate in)."""

    def setUp(self):
        self.config = _skip_unless_local_stack_ready(self)
        if shutil.which("aider") is None:
            self.skipTest("aider CLI not on PATH — install aider to run this tier")

    def test_aider_edits_a_real_file(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q"], cwd=d, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=d, check=True
            )
            subprocess.run(
                ["git", "config", "user.name", "test"], cwd=d, check=True
            )

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

        self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:] if proc.stderr else "")
        self.assertIn("def add", content)


if __name__ == "__main__":
    unittest.main()
