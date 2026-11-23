"""Passive probe engine and sandbox profile generator for agent CLIs."""

import shutil
import subprocess
from typing import Dict, List, Optional
from harness_spec.models import HarnessContract, SandboxProfile

KNOWN_HARNESS_DEFAULTS = {
    "claude": {
        "display_name": "Claude Code",
        "headless_prompt_flag": "-p",
        "default_sandbox_flag": "--dangerously-skip-permissions",
    },
    "agy": {
        "display_name": "AntiGravity (Agy)",
        "headless_prompt_flag": "-p",
        "default_sandbox_flag": "--sandbox",
        "env_overrides": {"PYTHONUNBUFFERED": "1"},
    },
    "codex": {
        "display_name": "Codex CLI",
        "headless_prompt_flag": "-c",
        "default_sandbox_flag": "--sandbox",
    },
    "grok": {
        "display_name": "Grok CLI",
        "headless_prompt_flag": "-p",
        "default_sandbox_flag": "--sandbox",
    },
}


def probe_binary(name: str) -> HarnessContract:
    """Probe an individual binary passively using --version."""
    binary_path = shutil.which(name)
    installed = binary_path is not None
    version_str: Optional[str] = None

    if installed:
        try:
            res = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=3)
            out = (res.stdout or res.stderr).strip()
            if out:
                version_str = out.split("\n")[0]
        except Exception:
            version_str = "unknown"

    meta = KNOWN_HARNESS_DEFAULTS.get(name, {
        "display_name": name.capitalize(),
        "headless_prompt_flag": "-p",
        "default_sandbox_flag": None,
    })

    return HarnessContract(
        binary_name=name,
        display_name=meta["display_name"],
        installed=installed,
        version=version_str,
        headless_prompt_flag=meta["headless_prompt_flag"],
        default_sandbox_flag=meta.get("default_sandbox_flag"),
        env_overrides=meta.get("env_overrides", {}),
    )


def probe_all_known() -> Dict[str, HarnessContract]:
    """Probe all standard harness binaries in the fleet."""
    contracts = {}
    for name in KNOWN_HARNESS_DEFAULTS:
        contracts[name] = probe_binary(name)
    return contracts
