import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_ver_tuple_basic():
    from synlynk import _ver_tuple

    assert _ver_tuple("0.10.0") > _ver_tuple("0.9.9")
    assert _ver_tuple("0.9.10") > _ver_tuple("0.9.9")
    assert _ver_tuple("1.0.0") > _ver_tuple("0.10.0")
    assert _ver_tuple("0.10.0") == _ver_tuple("0.10.0")


def test_ver_tuple_malformed():
    from synlynk import _ver_tuple

    assert _ver_tuple("bad") == (0,)


def test_detect_install_type_pipx_binary(monkeypatch):
    import shutil

    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: "/home/user/.local/pipx/venvs/synlynk/bin/synlynk",
    )
    from synlynk import _detect_install_type

    assert _detect_install_type() == "pipx"


def test_detect_install_type_pipx_env(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/synlynk")
    monkeypatch.setenv("PIPX_HOME", "/home/user/.local/pipx")
    from synlynk import _detect_install_type

    assert _detect_install_type() == "pipx"


def test_detect_install_type_script(monkeypatch, tmp_path):
    import importlib.metadata
    import synlynk
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/synlynk")
    monkeypatch.delenv("PIPX_HOME", raising=False)
    def _not_installed(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "distribution", _not_installed)
    fake_bin = tmp_path / ".synlynk" / "bin" / "synlynk"
    fake_bin.parent.mkdir(parents=True)
    fake_bin.touch()
    monkeypatch.setattr(
        synlynk.os.path,
        "expanduser",
        lambda p: str(tmp_path / p.lstrip("~/")),
    )
    from synlynk import _detect_install_type

    assert _detect_install_type() == "script"


def test_run_upgrade_pipx_prints_migrate_hint(monkeypatch, capsys):
    import synlynk

    monkeypatch.setattr(synlynk, "_detect_install_type", lambda: "pipx")

    class Result:
        returncode = 0

    monkeypatch.setattr(synlynk.subprocess, "run", lambda *args, **kwargs: Result())
    synlynk._run_upgrade("0.10.1")
    out = capsys.readouterr().out
    assert "✓ Upgraded to v0.10.1 via pipx" in out
    assert "Run 'synlynk migrate' if prompted" in out


def test_run_upgrade_pipx_local_path_reinstalls_release(monkeypatch, tmp_path, capsys):
    import synlynk

    metadata = {
        "main_package": {"package_or_url": "/home/user/dev/synlynk"}
    }
    meta_file = tmp_path / "venvs" / "synlynk" / "pipx_metadata.json"
    meta_file.parent.mkdir(parents=True)
    meta_file.write_text(json.dumps(metadata))
    monkeypatch.setenv("PIPX_HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "_detect_install_type", lambda: "pipx")

    calls = []

    class Result:
        returncode = 0

    def fake_run(args, text=True):
        calls.append(args)
        return Result()

    monkeypatch.setattr(synlynk.subprocess, "run", fake_run)
    synlynk._run_upgrade("0.10.1")
    out = capsys.readouterr().out
    assert calls[0] == [
        "pipx",
        "install",
        "git+https://github.com/nikhilsoman/synlynk@v0.10.1",
        "--force",
    ]
    assert "switched to release channel" in out


def test_run_upgrade_script_prints_migrate_hint(monkeypatch, capsys):
    import synlynk

    monkeypatch.setattr(synlynk, "_detect_install_type", lambda: "script")

    class Result:
        returncode = 0

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"echo installer"

    monkeypatch.setattr(synlynk.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setattr(synlynk.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    synlynk._run_upgrade("0.10.1")
    out = capsys.readouterr().out
    assert "✓ Upgraded to v0.10.1" in out
    assert "Run 'synlynk migrate' if prompted" in out


def test_get_pipx_source_local_path(monkeypatch, tmp_path):
    metadata = {
        "main_package": {"package_or_url": "/home/user/dev/synlynk"}
    }
    meta_file = tmp_path / "venvs" / "synlynk" / "pipx_metadata.json"
    meta_file.parent.mkdir(parents=True)
    meta_file.write_text(json.dumps(metadata))
    monkeypatch.setenv("PIPX_HOME", str(tmp_path))
    from synlynk import _get_pipx_source

    assert _get_pipx_source() == "/home/user/dev/synlynk"


def test_get_pipx_source_git_url(monkeypatch, tmp_path):
    metadata = {
        "main_package": {"package_or_url": "git+https://github.com/nikhilsoman/synlynk"}
    }
    meta_file = tmp_path / "venvs" / "synlynk" / "pipx_metadata.json"
    meta_file.parent.mkdir(parents=True)
    meta_file.write_text(json.dumps(metadata))
    monkeypatch.setenv("PIPX_HOME", str(tmp_path))
    from synlynk import _get_pipx_source

    assert _get_pipx_source().startswith("git+")


def test_get_pipx_source_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PIPX_HOME", str(tmp_path))
    from synlynk import _get_pipx_source

    assert _get_pipx_source() == ""


def test_warn_stale_script_install_no_shim(monkeypatch, tmp_path, capsys):
    import synlynk

    monkeypatch.setattr(
        synlynk.os.path,
        "expanduser",
        lambda p: str(tmp_path / p.replace("~/", "", 1)),
    )
    from synlynk import _warn_stale_script_install

    _warn_stale_script_install()
    out = capsys.readouterr().out
    assert out == ""


def test_warn_stale_script_install_with_shim_and_pipx(monkeypatch, tmp_path, capsys):
    import shutil as _shutil
    import synlynk

    shim = tmp_path / ".synlynk" / "bin" / "synlynk"
    shim.parent.mkdir(parents=True)
    shim.touch()
    monkeypatch.setattr(
        synlynk.os.path,
        "expanduser",
        lambda p: str(tmp_path / p.replace("~/", "", 1)),
    )
    monkeypatch.setattr(
        _shutil,
        "which",
        lambda name: str(tmp_path / ".local/pipx/venvs/synlynk/bin/synlynk"),
    )
    from synlynk import _warn_stale_script_install

    _warn_stale_script_install()
    out = capsys.readouterr().out
    assert "Legacy script install" in out
    assert "rm -rf" in out


def test_install_script_downloads_all_package_modules():
    install_script = Path(__file__).resolve().parents[1] / "install.sh"
    content = install_script.read_text()
    assert 'for f in __init__.py __main__.py cli.py db.py hud.py viz.py; do' in content
    assert 'curl -sSL "https://raw.githubusercontent.com/nikhilsoman/synlynk/main/synlynk/$f"' in content


def test_upgrade_dry_run_makes_no_subprocess_calls(tmp_path, monkeypatch, capsys):
    import importlib

    upgrade_mod = importlib.import_module("synlynk.upgrade")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(upgrade_mod, "VERSION", "0.12.0")
    calls = []
    monkeypatch.setattr(
        upgrade_mod.subprocess, "run",
        lambda *a, **kw: calls.append(a) or (_ for _ in ()).throw(AssertionError("should not run")),
    )
    monkeypatch.setattr(upgrade_mod, "_detect_install_type", lambda: "pipx")

    upgrade_mod.upgrade(dry_run=True)

    assert calls == []
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "pipx" in captured.out
