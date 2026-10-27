"""1-Click installer and preflight detector for recommended ecosystem tools."""

import shutil
import subprocess
import sys
from typing import Dict, Any

RECOMMENDED_TOOLS: Dict[str, Dict[str, Any]] = {
    "graphify": {
        "binary": "graphify",
        "package": "graphifyy",
        "description": "Deterministic AST Knowledge Graph for 20x token reduction and blast radius analysis",
        "license": "Apache-2.0",
        "install_methods": ["uv", "pipx", "pip"],
    },
    "gh": {
        "binary": "gh",
        "package": "gh",
        "description": "GitHub official CLI for PR reviews and repository management",
        "license": "MIT",
        "install_methods": ["brew", "apt"],
    },
    "superpowers": {
        "binary": "superpowers",
        "package": "superpowers",
        "description": "Agentic brainstorming, specification, and TDD skill packs",
        "license": "MIT",
        "install_methods": ["skills", "git"],
    },

}


def is_tool_available(tool_name: str) -> bool:
    """Check if the tool binary is available on PATH."""
    import os
    config = RECOMMENDED_TOOLS.get(tool_name)
    binary = config["binary"] if config else tool_name
    if shutil.which(binary) is not None:
        return True
    extra_paths = [
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/.pyenv/shims"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]
    for p in extra_paths:
        full_p = os.path.join(p, binary)
        if os.path.isfile(full_p) and os.access(full_p, os.X_OK):
            return True
    return False


def _install_argv(method: str, package: str, *, user_pip: bool) -> list[str] | None:
    """Return the argv for one present installer, or None when that method is absent."""
    if method == "uv" and shutil.which("uv"):
        return ["uv", "tool", "install", package]
    if method == "pipx" and shutil.which("pipx"):
        return ["pipx", "install", package]
    if method == "pip" and shutil.which("pip"):
        if user_pip:
            return ["pip", "install", "--user", package]
        return ["pip", "install", package]
    if method == "brew" and shutil.which("brew"):
        return ["brew", "install", package]
    if method == "apt" and shutil.which("apt-get"):
        return ["sudo", "apt-get", "install", "-y", package]
    return None


def _run_install(cmd: list[str]) -> bool:
    """Run one installer command. CalledProcessError is logged and returns False."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.returncode == 0
    except subprocess.CalledProcessError as exc:
        err_msg = (exc.stderr or exc.stdout or "").strip()
        print(
            f"Error: Installer command '{' '.join(cmd)}' failed with code {exc.returncode}:\n{err_msg}",
            file=sys.stderr,
        )
        return False
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"Error: Failed to execute installer '{' '.join(cmd)}': {exc}", file=sys.stderr)
        raise


def install_tool(tool_name: str) -> bool:
    """Install a recommended tool using available package managers.

    Graphify walks uv, then pipx, then ``pip install --user`` when a command fails.
    Other tools keep the first present manager only.
    """
    if tool_name not in RECOMMENDED_TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}. Registered tools: {list(RECOMMENDED_TOOLS.keys())}")

    config = RECOMMENDED_TOOLS[tool_name]
    package = config["package"]
    methods = list(config.get("install_methods", []))

    if tool_name == "graphify":
        attempted = False
        for method in methods:
            cmd = _install_argv(method, package, user_pip=True)
            if cmd is None:
                continue
            attempted = True
            try:
                if _run_install(cmd):
                    return True
            except (subprocess.SubprocessError, OSError):
                return False
        if not attempted:
            _report_missing_manager(tool_name, methods)
        return False

    cmd = _first_present_command(methods, package)
    if cmd is None:
        _report_missing_manager(tool_name, methods)
        return False
    try:
        return _run_install(cmd)
    except (subprocess.SubprocessError, OSError):
        return False


def _first_present_command(methods: list[str], package: str) -> list[str] | None:
    for method in methods:
        cmd = _install_argv(method, package, user_pip=False)
        if cmd is not None:
            return cmd
    return None


def _report_missing_manager(tool_name: str, methods: list[str]) -> None:
    supported = ", ".join(methods) if methods else "none specified"
    print(
        f"Error: No supported package manager found to install '{tool_name}'. "
        f"Supported methods: {supported}.",
        file=sys.stderr,
    )

from typing import Optional, List
from synlynk.install_manifest import update_ecosystem_status

def provision_ecosystem_tools(tools: Optional[List[str]] = None) -> Dict[str, bool]:
    """Provision the ecosystem tools by checking and installing missing ones."""
    if tools is None:
        tools = list(RECOMMENDED_TOOLS.keys())
    
    results = {}
    for tool in tools:
        if tool not in RECOMMENDED_TOOLS:
            results[tool] = False
            continue
            
        try:
            if is_tool_available(tool):
                installed = True
            else:
                installed = install_tool(tool)
            
            results[tool] = installed
            
            try:
                update_ecosystem_status(tool, installed, {"provisioned": True})
            except Exception as e:
                # Non-fatal update
                print(f"Warning: Failed to update install manifest for {tool}: {e}", file=sys.stderr)
        except Exception as e:
            # Non-fatal overall loop
            print(f"Error provisioning {tool}: {e}", file=sys.stderr)
            results[tool] = False
            
    return results
