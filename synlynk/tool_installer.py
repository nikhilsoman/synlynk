"""1-Click installer and preflight detector for recommended ecosystem tools."""

import shutil
import subprocess
from typing import Dict, Any, Optional

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

    # Prefer uv, then pipx, then pip
    if shutil.which("uv"):
        cmd = ["uv", "tool", "install", package]
    elif shutil.which("pipx"):
        cmd = ["pipx", "install", package]
    elif shutil.which("pip"):
        cmd = ["pip", "install", package]
    else:
        return False

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False
