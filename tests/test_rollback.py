import json
import os
import subprocess

import pytest

from synlynk import rollback


def test_dest_for_relative_path(tmp_path):
    dest = rollback._dest_for(str(tmp_path / "backup"), "project-docs/roadmap.md")
    assert dest == tmp_path / "backup" / "project-docs" / "roadmap.md"


def test_dest_for_absolute_path(tmp_path):
    dest = rollback._dest_for(str(tmp_path / "backup"), "/home/user/synlynk/bin")
    assert dest == tmp_path / "backup" / "home" / "user" / "synlynk" / "bin"
    assert not str(dest).startswith("//")


def test_backup_and_restore_file_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "CLAUDE.md"
    target.write_text("original content\n")
    backup_dir = rollback._backup_paths("op1", ["CLAUDE.md"])
    target.write_text("clobbered content\n")
    rollback._restore_paths(backup_dir, ["CLAUDE.md"])
    assert target.read_text() == "original content\n"


def test_backup_and_restore_dir_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / ".synlynk" / "project-docs"
    docs.mkdir(parents=True)
    (docs / "roadmap.md").write_text("v1\n")
    backup_dir = rollback._backup_paths("op1", [".synlynk/project-docs"])
    (docs / "roadmap.md").write_text("v2\n")
    (docs / "new-file.md").write_text("should be removed\n")
    rollback._restore_paths(backup_dir, [".synlynk/project-docs"])
    assert (docs / "roadmap.md").read_text() == "v1\n"
    assert not (docs / "new-file.md").exists()


def test_restore_removes_path_that_did_not_exist_before(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backup_dir = rollback._backup_paths("op1", ["never-existed.txt"])
    new_file = tmp_path / "never-existed.txt"
    new_file.write_text("created during the operation\n")
    rollback._restore_paths(backup_dir, ["never-existed.txt"])
    assert not new_file.exists()


def test_manifest_write_read_archive_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manifest = {"op_id": "abc123", "op_type": "init", "checkpoint_sha": "deadbeef"}
    rollback._write_manifest(manifest)
    assert os.path.exists(rollback.MANIFEST_PATH)
    loaded = rollback._read_manifest()
    assert loaded == manifest
    rollback._archive_manifest(manifest)
    assert not os.path.exists(rollback.MANIFEST_PATH)
    archived = rollback._read_manifest(op_id="abc123")
    assert archived == manifest


def _init_git_repo(path):
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)


def test_rollback_checkpoint_restores_on_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial", "-q"], cwd=tmp_path, check=True)
    hook = tmp_path / "untracked.txt"
    hook.write_text("original hook content\n")

    with pytest.raises(RuntimeError):
        with rollback.rollback_checkpoint("init", untracked_paths=["untracked.txt"]):
            tracked.write_text("v2 mutated\n")
            subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
            subprocess.run(["git", "commit", "-m", "mutation", "-q"], cwd=tmp_path, check=True)
            hook.write_text("clobbered hook content\n")
            raise RuntimeError("simulated mid-operation failure")

    assert tracked.read_text() == "v1\n"
    assert hook.read_text() == "original hook content\n"
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True
    ).stdout
    assert "mutation" not in log
    assert not os.path.exists(rollback.MANIFEST_PATH)


def test_rollback_checkpoint_restores_dirty_tree_stash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial", "-q"], cwd=tmp_path, check=True)
    tracked.write_text("uncommitted local edit\n")

    with pytest.raises(RuntimeError):
        with rollback.rollback_checkpoint("init", untracked_paths=[]):
            tracked.write_text("mutated during op\n")
            raise RuntimeError("simulated failure")

    assert tracked.read_text() == "uncommitted local edit\n"


def test_rollback_checkpoint_leaves_manifest_on_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "initial", "-q"], cwd=tmp_path, check=True)

    with rollback.rollback_checkpoint("migrate", untracked_paths=[]) as manifest:
        assert manifest["op_type"] == "migrate"

    assert os.path.exists(rollback.MANIFEST_PATH)
    loaded = rollback._read_manifest()
    assert loaded["op_type"] == "migrate"


def test_rollback_checkpoint_upgrade_pipx_restore_reinstalls_old_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recorded = []
    monkeypatch.setattr(
        rollback.subprocess,
        "run",
        lambda args, **kw: recorded.append(list(args)) or subprocess.CompletedProcess(args, 0),
    )

    with pytest.raises(RuntimeError):
        with rollback.rollback_checkpoint_upgrade("0.12.0", "pipx"):
            raise RuntimeError("simulated pipx failure")

    assert any(
        call[:2] == ["pipx", "install"] and "v0.12.0" in call[2]
        for call in recorded
    )
    assert not os.path.exists(rollback.MANIFEST_PATH)


def test_rollback_checkpoint_upgrade_script_restores_bin_and_lib(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "home"
    bin_dir = home / ".synlynk" / "bin"
    lib_dir = home / ".synlynk" / "lib"
    bin_dir.mkdir(parents=True)
    lib_dir.mkdir(parents=True)
    (bin_dir / "synlynk").write_text("#!/bin/sh\necho old\n")
    monkeypatch.setattr(rollback.os.path, "expanduser", lambda p: p.replace("~", str(home)))

    with pytest.raises(RuntimeError):
        with rollback.rollback_checkpoint_upgrade("0.12.0", "script"):
            (bin_dir / "synlynk").write_text("#!/bin/sh\necho new\n")
            raise RuntimeError("simulated script install failure")

    assert (bin_dir / "synlynk").read_text() == "#!/bin/sh\necho old\n"
