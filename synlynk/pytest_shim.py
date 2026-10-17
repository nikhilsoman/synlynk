"""Quiet pytest guard used inside dispatched harness environments."""

from __future__ import annotations

import os
import shutil
import stat
import sys
from typing import Mapping, Optional


def _real_pytest_path(env: Mapping[str, str], shim_dir: str) -> Optional[str]:
    """Find ``pytest`` after removing this shim's directory from ``PATH``."""
    entries = env.get("PATH", "").split(os.pathsep)
    shim_real = os.path.realpath(shim_dir)
    real_path = os.pathsep.join(
        entry for entry in entries if os.path.realpath(entry or os.curdir) != shim_real
    )
    return shutil.which("pytest", path=real_path)


def run_shim(args: list, *, env: Optional[Mapping[str, str]] = None,
             shim_dir: Optional[str] = None) -> int:
    child_env = dict(env if env is not None else os.environ)
    current_shim_dir = shim_dir or os.path.dirname(os.path.realpath(sys.argv[0]))
    real_pytest = _real_pytest_path(child_env, current_shim_dir)
    if not real_pytest:
        print("synlynk pytest shim: real pytest binary not found on PATH", file=sys.stderr)
        return 127

    filtered = [arg for arg in args if arg not in {"-v", "--verbose", "-vv", "-vvv"}]
    if "-q" not in filtered:
        filtered.append("-q")
    os.execvpe(real_pytest, [real_pytest] + filtered, child_env)
    return 127


def write_shim(path: str) -> str:
    """Write an executable wrapper at *path* and return the path."""
    shim_dir = os.path.dirname(os.path.realpath(path))
    package_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    script = (
        f"#!{sys.executable}\n"
        "import os\n"
        "import sys\n"
        "os.environ.setdefault('SYNLYNK_ALLOW_CWD_FALLBACK', '1')\n"
        "os.environ.setdefault('SYNLYNK_FAST_CLI', '1')\n"
        f"sys.path.insert(0, {package_root!r})\n"
        "from synlynk.pytest_shim import run_shim\n"
        "raise SystemExit(run_shim(sys.argv[1:], shim_dir=os.path.dirname(os.path.realpath(__file__))))\n"
    )
    os.makedirs(shim_dir, mode=0o700, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(script)
    os.chmod(path, stat.S_IRWXU)
    return path


def main(args: Optional[list] = None, shim_dir: Optional[str] = None) -> int:
    return run_shim(list(sys.argv[1:] if args is None else args), shim_dir=shim_dir)


__all__ = ["main", "run_shim", "write_shim"]
