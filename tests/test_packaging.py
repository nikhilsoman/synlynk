from importlib import metadata as importlib_metadata
import os
import sys
import types


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import synlynk


def test_detect_install_type_pipx(monkeypatch, tmp_path):
    fake_meta = types.SimpleNamespace(
        locate_file=lambda _: tmp_path / "pipx" / "venvs" / "synlynk"
    )
    monkeypatch.setattr(importlib_metadata, "distribution", lambda _: fake_meta)
    assert synlynk._detect_install_type() == "pipx"


def test_detect_install_type_pip(monkeypatch, tmp_path):
    fake_meta = types.SimpleNamespace(locate_file=lambda _: tmp_path / "site-packages")
    monkeypatch.setattr(importlib_metadata, "distribution", lambda _: fake_meta)
    assert synlynk._detect_install_type() == "pip"


def test_detect_install_type_script(monkeypatch, tmp_path):
    monkeypatch.setattr(
        importlib_metadata,
        "distribution",
        lambda _: (_ for _ in ()).throw(Exception("no dist")),
    )
    shim = tmp_path / "synlynk"
    shim.write_text("#!/bin/bash\npython3 synlynk")
    monkeypatch.setattr(
        os.path,
        "expanduser",
        lambda p: str(tmp_path / "synlynk") if "~/synlynk/bin/synlynk" in p else p,
    )
    assert synlynk._detect_install_type() == "script"


def test_detect_install_type_unknown(monkeypatch):
    monkeypatch.setattr(
        importlib_metadata,
        "distribution",
        lambda _: (_ for _ in ()).throw(Exception("no dist")),
    )
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    assert synlynk._detect_install_type() == "unknown"


def test_run_upgrade_pipx_success(monkeypatch, capsys):
    import subprocess

    monkeypatch.setattr(synlynk, "_detect_install_type", lambda: "pipx")
    calls = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kw: (calls.append(cmd), types.SimpleNamespace(returncode=0))[-1],
    )
    synlynk._run_upgrade("9.9.9")
    assert calls[0] == ["pipx", "upgrade", "synlynk"]
    out = capsys.readouterr().out
    assert "via pipx" in out


def test_run_upgrade_pipx_failure(monkeypatch, capsys):
    import subprocess

    monkeypatch.setattr(synlynk, "_detect_install_type", lambda: "pipx")
    monkeypatch.setattr(
        subprocess, "run", lambda cmd, **kw: types.SimpleNamespace(returncode=1)
    )
    synlynk._run_upgrade("9.9.9")
    out = capsys.readouterr().out
    assert "run manually" in out


def test_run_upgrade_script_falls_back_to_install_sh(monkeypatch, capsys):
    import urllib.request

    monkeypatch.setattr(synlynk, "_detect_install_type", lambda: "script")
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **kw: (_ for _ in ()).throw(Exception("network")),
    )
    monkeypatch.setattr(urllib.request, "Request", lambda *a, **kw: None)
    synlynk._run_upgrade("9.9.9")
    out = capsys.readouterr().out
    assert "Auto-install failed" in out or "run manually" in out
