"""Regression test for gh:#2442.

The globally installed `synlynk` launcher used to be a generated stub doing
a bare `from synlynk import main`, which raises
`ModuleNotFoundError: No module named 'synlynk'` whenever the installing
interpreter's package resolution is stale (editable install pointing at a
deleted checkout, removed venv) — notably inside dispatched jobs'
sandboxed subprocesses, which run with a trimmed PYTHONPATH from a
worktree cwd. `python3 bin/synlynk.py` kept working there because it puts
its checkout root on sys.path.

The installed launcher is now a resilient wrapper (scripts/synlynk, wired
via `script-files` in pyproject.toml): it prefers the installed package
and falls back to the enclosing checkout's `synlynk` package when the
installed import fails. These tests pin both paths.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import venv

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(ROOT, "scripts", "synlynk")


def load_launcher():
    from importlib.machinery import SourceFileLoader

    loader = SourceFileLoader("synlynk_launcher_under_test", LAUNCHER)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_find_checkout_root_from_nested_cwd(tmp_path):
    launcher = load_launcher()
    nested = tmp_path / "worktree" / "a" / "b"
    nested.mkdir(parents=True)
    pkg = tmp_path / "worktree" / "synlynk"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    assert launcher.find_checkout_root(str(nested)) == str(tmp_path / "worktree")


def test_find_checkout_root_at_root_itself(tmp_path):
    launcher = load_launcher()
    pkg = tmp_path / "synlynk"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    assert launcher.find_checkout_root(str(tmp_path)) == str(tmp_path)


def test_find_checkout_root_without_checkout(tmp_path):
    launcher = load_launcher()
    assert launcher.find_checkout_root(str(tmp_path)) is None


def _sandbox_env():
    """Minimal dispatch-sandbox-like env: no PYTHONPATH, no venv markers.

    Dispatch children always get SYNLYNK_ALLOW_CWD_FALLBACK=1 (see
    _create_dispatch_shims), so the child package may resolve state paths
    without requiring a git worktree at cwd.
    """
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": os.environ.get("HOME", ""),
        "TERM": os.environ.get("TERM", "xterm"),
        "SYNLYNK_ALLOW_CWD_FALLBACK": "1",
    }
    return {k: v for k, v in env.items() if v}


@pytest.mark.e2e
def test_broken_install_falls_back_to_worktree_checkout(tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    pip_exe = shutil.which("pip3") or shutil.which("pip")
    wheel_cmd = (
        [pip_exe, "wheel", "--no-deps", "-w", str(dist_dir), ROOT]
        if pip_exe
        else [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist_dir), ROOT]
    )
    build = subprocess.run(wheel_cmd, capture_output=True, text=True)
    assert build.returncode == 0, build.stderr

    wheels = list(dist_dir.glob("synlynk-*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, found {wheels}"

    sandbox_venv = tmp_path / "sandbox_env"
    venv.create(sandbox_venv, with_pip=True)
    if sys.platform == "win32":
        venv_python = sandbox_venv / "Scripts" / "python.exe"
        venv_bin = sandbox_venv / "Scripts" / "synlynk.exe"
    else:
        venv_python = sandbox_venv / "bin" / "python"
        venv_bin = sandbox_venv / "bin" / "synlynk"

    install = subprocess.run(
        [str(sandbox_venv / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip")),
         "install", str(wheels[0])],
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stderr
    assert venv_bin.exists(), "expected the installed synlynk launcher"

    installed_text = venv_bin.read_text(encoding="utf-8", errors="replace")
    assert "find_checkout_root" in installed_text, (
        "installed launcher is not the resilient wrapper"
    )

    # Healthy install works with no checkout in sight.
    healthy = subprocess.run(
        [str(venv_bin), "--version"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=_sandbox_env(),
    )
    assert healthy.returncode == 0, healthy.stderr
    assert "ModuleNotFoundError" not in healthy.stderr

    # Break the install the way the stale global launcher is broken: the
    # launcher script stays on PATH but the package is no longer importable.
    site_packages = subprocess.run(
        [str(venv_python), "-c",
         "import site; print(site.getsitepackages()[0])"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    for entry in os.listdir(site_packages):
        if entry == "synlynk" or entry.startswith(("synlynk-", "synlynk.", "__editable__synlynk")):
            path = os.path.join(site_packages, entry)
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.unlink(path)
    broken_check = subprocess.run(
        [str(venv_python), "-c", "import synlynk"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=_sandbox_env(),
    )
    assert broken_check.returncode != 0
    assert "ModuleNotFoundError" in broken_check.stderr

    # Simulated sparse dispatch worktree: only the package is present.
    worktree = tmp_path / "fake_worktree"
    nested = worktree / "sub" / "dir"
    nested.mkdir(parents=True)
    os.symlink(os.path.join(ROOT, "synlynk"), worktree / "synlynk")

    # Control: no enclosing checkout -> original error surfaces unchanged.
    control = subprocess.run(
        [str(venv_bin), "--version"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=_sandbox_env(),
    )
    assert control.returncode != 0
    assert "ModuleNotFoundError" in control.stderr

    # Fix: from inside the worktree the launcher falls back to the
    # checkout's package instead of raising ModuleNotFoundError.
    run = subprocess.run(
        [str(venv_bin), "--version"],
        capture_output=True,
        text=True,
        cwd=str(nested),
        env=_sandbox_env(),
    )
    assert run.returncode == 0, run.stderr
    assert "ModuleNotFoundError" not in run.stderr
    assert "synlynk" in (run.stdout + run.stderr).lower()
