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


def test_install_script_downloads_all_package_modules():
    install_script = Path(__file__).resolve().parents[1] / "install.sh"
    content = install_script.read_text()
    assert 'for f in __init__.py __main__.py cli.py db.py hud.py viz.py; do' in content
    assert 'curl -sSL "https://raw.githubusercontent.com/nikhilsoman/synlynk/main/synlynk/$f"' in content
