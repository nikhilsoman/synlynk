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
}


def is_tool_available(tool_name: str) -> bool:
    """Check if the tool binary is available on PATH."""
    config = RECOMMENDED_TOOLS.get(tool_name)
    binary = config["binary"] if config else tool_name
    return shutil.which(binary) is not None


def install_tool(tool_name: str) -> bool:
    """Install a recommended tool using available package managers."""
    if tool_name not in RECOMMENDED_TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}. Registered tools: {list(RECOMMENDED_TOOLS.keys())}")

    config = RECOMMENDED_TOOLS[tool_name]
    package = config["package"]
    methods = config.get("install_methods", [])

    cmd = None
    if "uv" in methods and shutil.which("uv"):
        cmd = ["uv", "tool", "install", package]
    elif "pipx" in methods and shutil.which("pipx"):
        cmd = ["pipx", "install", package]
    elif "pip" in methods and shutil.which("pip"):
        cmd = ["pip", "install", package]
    elif "brew" in methods and shutil.which("brew"):
        cmd = ["brew", "install", package]
    elif "apt" in methods and shutil.which("apt-get"):
        cmd = ["sudo", "apt-get", "install", "-y", package]
    else:
        supported = ", ".join(methods) if methods else "none specified"
        print(
            f"Error: No supported package manager found to install '{tool_name}'. "
            f"Supported methods: {supported}.",
            file=sys.stderr,
        )
        return False

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
        return False
