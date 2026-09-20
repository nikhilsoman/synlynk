"""Version Resolver and Package Installer for Testbed Nodes."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from synlynk.testbed.driver import TestbedDriver


@dataclass
class ResolvedTarget:
    kind: str  # "git_ref", "git_commit", "local_build"
    ref: str


class TargetResolver:
    """Resolves target flags to exact installation references."""

    def resolve(self, target_str: str) -> ResolvedTarget:
        target = target_str.strip()
        if target == "staging":
            return ResolvedTarget(kind="git_ref", ref="staging")
        elif target == "unstable":
            return ResolvedTarget(kind="git_ref", ref="unstable")
        elif target.startswith("commit:"):
            sha = target.split("commit:", 1)[1]
            return ResolvedTarget(kind="git_commit", ref=sha)
        elif target == "local":
            return ResolvedTarget(kind="local_build", ref="local")
        else:
            return ResolvedTarget(kind="git_ref", ref=target)


def build_local_wheel(workspace_root: Path, output_dir: Optional[Path] = None) -> Path:
    """Builds a Python wheel or installable package from local workspace."""
    out_dir = output_dir or Path(tempfile.mkdtemp(prefix="synlynk_testbed_wheel_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # Use python -m build or flit or pip wheel
    try:
        subprocess.run(
            ["python3", "-m", "pip", "wheel", "--no-deps", "-w", str(out_dir), str(workspace_root)],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        # Fallback to direct directory copy / tarball if build tool unavailable
        archive_path = out_dir / "synlynk_pkg.tar.gz"
        subprocess.run(
            ["tar", "-czf", str(archive_path), "-C", str(workspace_root), "synlynk", "pyproject.toml"],
            capture_output=True,
            text=True,
            check=True,
        )
        return archive_path

    wheels = list(out_dir.glob("*.whl"))
    if wheels:
        return wheels[0]
    raise RuntimeError(f"Failed to generate wheel in {out_dir}")


def install_target_on_node(
    driver: TestbedDriver,
    node_id: str,
    target_ref: str,
    repo_url: str = "https://github.com/nikhilsoman/synlynk.git",
    workspace_root: Optional[Path] = None,
) -> bool:
    """Installs the resolved target Synlynk version onto the specified node."""
    resolver = TargetResolver()
    resolved = resolver.resolve(target_ref)

    # Ensure system prerequisites (python3, git, pip)
    driver.exec_command(
        node_id,
        "which python3 || (sudo apt-get update -y && sudo apt-get install -y python3 python3-pip git sqlite3 iptables iproute2)",
    )

    if resolved.kind == "local_build":
        root = workspace_root or Path.cwd()
        wheel_path = build_local_wheel(root)
        remote_dest = f"/tmp/{wheel_path.name}"
        driver.copy_file(node_id, str(wheel_path), remote_dest)
        res = driver.exec_command(node_id, f"pip3 install --break-system-packages --force-reinstall {remote_dest} || pip3 install --force-reinstall {remote_dest}")
        return res.ok

    elif resolved.kind == "git_ref":
        cmd = f"rm -rf /tmp/synlynk_src && git clone --depth 1 -b {resolved.ref} {repo_url} /tmp/synlynk_src && pip3 install --break-system-packages -e /tmp/synlynk_src || pip3 install -e /tmp/synlynk_src"
        res = driver.exec_command(node_id, cmd)
        return res.ok

    elif resolved.kind == "git_commit":
        cmd = f"rm -rf /tmp/synlynk_src && git clone {repo_url} /tmp/synlynk_src && cd /tmp/synlynk_src && git checkout {resolved.ref} && (pip3 install --break-system-packages -e . || pip3 install -e .)"
        res = driver.exec_command(node_id, cmd)
        return res.ok

    return False
