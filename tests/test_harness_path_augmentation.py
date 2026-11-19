import os
from pathlib import Path
import pytest
from synlynk._constants import augment_path_for_harnesses
from synlynk.dispatch import _build_subprocess_env
from synlynk.probe_binding import probe_harness_live


def test_augment_path_appends_standard_directories(tmp_path, monkeypatch):
    home = tmp_path / "fakehome"
    local_bin = home / ".local" / "bin"
    grok_bin = home / ".grok" / "bin"
    local_bin.mkdir(parents=True)
    grok_bin.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("NVM_DIR", raising=False)

    bare_path = "/usr/bin:/bin"
    augmented = augment_path_for_harnesses(bare_path)
    parts = augmented.split(os.pathsep)

    assert "/usr/bin" in parts
    assert "/bin" in parts
    assert str(local_bin) in parts
    assert str(grok_bin) in parts


def test_augment_path_discovers_nvm_node_versions(tmp_path, monkeypatch):
    home = tmp_path / "fakehome"
    nvm_dir = home / ".nvm"
    node_v24_bin = nvm_dir / "versions" / "node" / "v24.15.0" / "bin"
    node_v22_bin = nvm_dir / "versions" / "node" / "v22.10.0" / "bin"
    node_v24_bin.mkdir(parents=True)
    node_v22_bin.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("NVM_DIR", str(nvm_dir))

    bare_path = "/usr/bin:/bin"
    augmented = augment_path_for_harnesses(bare_path)
    parts = augmented.split(os.pathsep)

    assert str(node_v24_bin) in parts
    assert str(node_v22_bin) in parts
    assert parts.index(str(node_v24_bin)) < parts.index(str(node_v22_bin))


def test_build_subprocess_env_augments_path(tmp_path, monkeypatch):
    home = tmp_path / "fakehome"
    local_bin = home / ".local" / "bin"
    local_bin.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    proc_env, tmp_dir = _build_subprocess_env("codex", {}, False, "story-test")
    try:
        assert str(local_bin) in proc_env["PATH"].split(os.pathsep)
    finally:
        if tmp_dir:
            tmp_dir.cleanup()


def test_probe_harness_live_fallback_with_augmented_path(tmp_path, monkeypatch):
    home = tmp_path / "fakehome"
    nvm_bin = home / ".nvm" / "versions" / "node" / "v24.15.0" / "bin"
    nvm_bin.mkdir(parents=True)
    fake_codex = nvm_bin / "codex"
    fake_codex.write_text("#!/bin/sh\necho 'codex-cli 1.2.3'\n")
    fake_codex.chmod(0o755)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("NVM_DIR", str(home / ".nvm"))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    res = probe_harness_live("codex")
    assert res["installed"] is True
    assert res["status"] != "missing"
