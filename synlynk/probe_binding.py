"""Probe-verified harness and dependency binding engine."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict

from synlynk._constants import HARNESS_CAPABILITY_BASELINES

SYSTEM_DEPENDENCIES = {
    "git": {"min_version": "2.38", "install_hint": "brew install git"},
    "python": {"min_version": "3.10", "install_hint": "brew install python@3.11"},
    "gh": {"min_version": "2.20", "install_hint": "brew install gh"},
    "pytest": {"min_version": "7.0", "install_hint": "pip install pytest"},
    "graphify": {"min_version": "0.1", "install_hint": "pip install graphify"},
}

KNOWN_HARNESSES = ("claude", "codex", "agy", "grok")

_ENV_KEYS = {
    "claude": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_TOKEN"],
    "codex": ["OPENAI_API_KEY"],
    "agy": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "grok": ["XAI_API_KEY"],
}


def probe_dependency(name: str) -> Dict[str, Any]:
    spec = SYSTEM_DEPENDENCIES.get(name, {})
    path = shutil.which(name)
    if not path:
        return {
            "name": name,
            "installed": False,
            "path": None,
            "version": None,
            "status": "missing",
            "install_hint": spec.get("install_hint"),
        }

    version = None
    try:
        proc = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            lines = (proc.stdout or proc.stderr or "").strip().splitlines()
            if lines:
                version = lines[0]
    except Exception:
        pass

    return {
        "name": name,
        "installed": True,
        "path": path,
        "version": version,
        "status": "ok",
        "install_hint": spec.get("install_hint"),
    }


def probe_all_dependencies() -> Dict[str, Dict[str, Any]]:
    return {name: probe_dependency(name) for name in SYSTEM_DEPENDENCIES}


def _auth_spec(harness_name: str) -> Dict[str, Any]:
    baseline = HARNESS_CAPABILITY_BASELINES.get(harness_name) or {}
    spec = baseline.get("panel_auth_check") or baseline.get("auth_check") or {}
    return spec if isinstance(spec, dict) else {}


def _auth_probe_command(harness_name: str) -> list:
    probe = _auth_spec(harness_name).get("probe")
    if isinstance(probe, list) and probe:
        return list(probe)
    return [harness_name, "auth", "status"]


def _output_says_authenticated(harness_name: str, output: str, returncode: int) -> bool:
    if returncode != 0:
        return False
    text = (output or "").lower()
    markers = _auth_spec(harness_name).get("unauthenticated_markers") or []
    if any(str(marker).lower() in text for marker in markers):
        return False
    return "authenticated" in text or "logged in" in text


def _auth_config_path(harness_name: str) -> Path | None:
    home = Path.home()
    auth_paths = {
        "claude": home / ".claude.json",
        "codex": home / ".codex" / "config.json",
        "agy": home / ".gemini" / "antigravity-cli",
        "grok": home / ".grok" / "config.json",
    }
    return auth_paths.get(harness_name)


def probe_harness_live(harness_name: str) -> Dict[str, Any]:
    path = shutil.which(harness_name)
    if not path:
        return {
            "harness": harness_name,
            "installed": False,
            "auth_verified": False,
            "status": "missing",
            "message": f"CLI '{harness_name}' not found on PATH",
        }

    version = None
    try:
        proc = subprocess.run([harness_name, "--version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            lines = (proc.stdout or proc.stderr or "").strip().splitlines()
            if lines:
                version = lines[0]
    except Exception as e:
        return {
            "harness": harness_name,
            "installed": True,
            "auth_verified": False,
            "status": "unresponsive",
            "message": str(e),
        }

    auth_verified = False
    status = "unverified"
    message = "Installed but not authenticated"

    try:
        auth_proc = subprocess.run(
            _auth_probe_command(harness_name),
            capture_output=True,
            text=True,
            timeout=5,
        )
        auth_output = f"{auth_proc.stdout or ''}{auth_proc.stderr or ''}"
        if _output_says_authenticated(harness_name, auth_output, auth_proc.returncode):
            auth_verified = True
            status = "verified"
            message = "Authentication verified via harness probe"
    except Exception:
        pass

    if not auth_verified:
        keys = _ENV_KEYS.get(harness_name, [])
        if any(k in os.environ for k in keys):
            auth_verified = True
            status = "verified"
            message = "Authentication verified via environment"
        else:
            cand = _auth_config_path(harness_name)
            if cand and cand.exists():
                auth_verified = True
                status = "verified"
                message = "Authentication verified via session configuration"

    return {
        "harness": harness_name,
        "installed": True,
        "path": path,
        "version": version,
        "auth_verified": auth_verified,
        "status": status,
        "message": message,
    }


def probe_all_harnesses() -> Dict[str, Dict[str, Any]]:
    return {h: probe_harness_live(h) for h in KNOWN_HARNESSES}
