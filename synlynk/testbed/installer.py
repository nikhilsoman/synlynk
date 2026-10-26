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


def _build_pure_wheel(workspace_root: Path, out_dir: Path) -> Path:
    """Build a PEP 427 pure-Python wheel directly without external build dependencies."""
    import zipfile
    from synlynk._constants import VERSION

    whl_name = f"synlynk-{VERSION}-py3-none-any.whl"
    whl_path = out_dir / whl_name
    synlynk_dir = workspace_root / "synlynk"

    with zipfile.ZipFile(whl_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(synlynk_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
            for f in files:
                if f.endswith(".pyc") or f.startswith("."):
                    continue
                full_path = Path(root) / f
                rel_path = full_path.relative_to(workspace_root)
                zf.write(full_path, str(rel_path))

        dist_info = f"synlynk-{VERSION}.dist-info"
        zf.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: synlynk\nVersion: {VERSION}\nSummary: Coordination OS for multi-agent development\n",
        )
        zf.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nGenerator: synlynk-wheel-builder\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        zf.writestr(
            f"{dist_info}/entry_points.txt",
            "[console_scripts]\nsynlynk = synlynk:main\n",
        )
        zf.writestr(f"{dist_info}/RECORD", "")

    return whl_path


def build_local_wheel(workspace_root: Path, output_dir: Optional[Path] = None) -> Path:
    """Builds a Python wheel or installable package from local workspace."""
    out_dir = output_dir or Path(tempfile.mkdtemp(prefix="synlynk_testbed_wheel_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # Try standard tools first (build or pip wheel)
    try:
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "-o", str(out_dir), str(workspace_root)],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        try:
            subprocess.run(
                ["python3", "-m", "pip", "wheel", "--no-deps", "-w", str(out_dir), str(workspace_root)],
                capture_output=True,
                text=True,
                check=True,
            )
        except Exception:
            # Build wheel directly via zipfile generator
            return _build_pure_wheel(workspace_root, out_dir)

    wheels = list(out_dir.glob("*.whl"))
    if wheels:
        return wheels[0]
    return _build_pure_wheel(workspace_root, out_dir)


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

    uid = os.getuid() if hasattr(os, "getuid") else "0"
    remote_tmp = f"/tmp/synlynk-{uid}"
    driver.exec_command(node_id, f"mkdir -p -m 0700 {remote_tmp}")

    if resolved.kind == "local_build":
        root = workspace_root or Path.cwd()
        wheel_path = build_local_wheel(root)
        remote_dest = f"{remote_tmp}/{wheel_path.name}"
        driver.copy_file(node_id, str(wheel_path), remote_dest)
        res = driver.exec_command(node_id, f"pip3 install --break-system-packages --force-reinstall {remote_dest} || pip3 install --force-reinstall {remote_dest}")
        return res.ok

    elif resolved.kind == "git_ref":
        src_dir = f"{remote_tmp}/synlynk_src"
        cmd = f"rm -rf {src_dir} && git clone --depth 1 -b {resolved.ref} {repo_url} {src_dir} && pip3 install --break-system-packages -e {src_dir} || pip3 install -e {src_dir}"
        res = driver.exec_command(node_id, cmd)
        return res.ok

    elif resolved.kind == "git_commit":
        src_dir = f"{remote_tmp}/synlynk_src"
        cmd = f"rm -rf {src_dir} && git clone {repo_url} {src_dir} && cd {src_dir} && git checkout {resolved.ref} && (pip3 install --break-system-packages -e . || pip3 install -e .)"
        res = driver.exec_command(node_id, cmd)
        return res.ok

    return False
