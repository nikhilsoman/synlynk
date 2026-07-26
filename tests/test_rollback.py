import json
import os
import subprocess
import sqlite3

import pytest

import synlynk
from synlynk import rollback
from synlynk.db import MigrationImportError


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


def test_cmd_migrate_rolls_back_real_db_path_on_import_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "project-docs").mkdir()

    external_db = tmp_path.parent / f"{tmp_path.name}-external" / "projects" / "deadbeef" / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(external_db))

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, status) VALUES (?,?,?)",
        ("story-sentinel", "sentinel", "open"),
    )
    conn.commit()
    conn.close()

    def fake_migrate_import(docs_dir: str, dry_run: bool = False) -> None:
        db = sqlite3.connect(synlynk.DB_PATH)
        try:
            db.execute(
                "INSERT INTO stories (story_id, title, status) VALUES (?,?,?)",
                ("story-bad", "bad", "open"),
            )
            db.commit()
        finally:
            db.close()
        raise MigrationImportError("simulated partial import failure")

    monkeypatch.setattr(synlynk, "_migrate_import", fake_migrate_import, raising=False)
    monkeypatch.setattr(rollback.subprocess, "run", lambda *args, **kwargs: None)

    with pytest.raises(SystemExit) as excinfo:
        synlynk.cmd_migrate()

    assert excinfo.value.code == 1

    conn = sqlite3.connect(str(external_db))
    rows = conn.execute(
        "SELECT story_id, title FROM stories ORDER BY story_id"
    ).fetchall()
    conn.close()

    assert ("story-sentinel", "sentinel") in rows
    assert ("story-bad", "bad") not in rows


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


def test_rollback_checkpoint_stash_excludes_out_of_repo_untracked_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial", "-q"], cwd=tmp_path, check=True)
    tracked.write_text("uncommitted local edit\n")

    external_db = tmp_path.parent / f"{tmp_path.name}-external" / "state.db"
    external_db.parent.mkdir(parents=True, exist_ok=True)
    external_db.write_text("db\n")

    with rollback.rollback_checkpoint("migrate", untracked_paths=[str(external_db)]) as manifest:
        assert manifest["op_type"] == "migrate"

    assert tracked.read_text() == "uncommitted local edit\n"


def test_rollback_checkpoint_stash_excludes_gitignored_untracked_path(tmp_path, monkeypatch):
    """Regression test: an untracked_paths entry that lives inside a
    gitignored directory (e.g. .synlynk/project-docs, .synlynk/.synlynk_migrated)
    must NOT get an explicit `:!` exclude pathspec in the auto-stash command —
    git treats that as an attempt to add an ignored file and aborts the whole
    `git stash push` with exit 1, even though `-u` would already have skipped
    the ignored path on its own.
    """
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    (tmp_path / ".gitignore").write_text(".synlynk/\n")
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1\n")
    subprocess.run(["git", "add", ".gitignore", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial", "-q"], cwd=tmp_path, check=True)
    tracked.write_text("uncommitted local edit\n")

    docs_dir = tmp_path / ".synlynk" / "project-docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "roadmap.md").write_text("v1\n")

    with rollback.rollback_checkpoint(
        "migrate", untracked_paths=[".synlynk/project-docs", ".synlynk/.synlynk_migrated"]
    ) as manifest:
        assert manifest["op_type"] == "migrate"

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


def test_git_head_sha_returns_none_when_subprocess_run_returns_none(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: None)
    assert rollback._git_head_sha() is None


def test_git_dirty_returns_false_when_subprocess_run_returns_none(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: None)
    assert rollback._git_dirty() is False


def test_rollback_checkpoint_pops_stash_on_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True)
    (tmp_path / "committed.txt").write_text("v1\n")
    subprocess.run(["git", "add", "committed.txt"], check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], check=True)

    # Simulate a dirty tree with an untracked file present before the op starts,
    # mirroring the live-selftest migrate workspace scenario.
    untracked = tmp_path / "project-docs" / "memory.md"
    untracked.parent.mkdir(parents=True)
    untracked.write_text("original memory\n")

    with rollback.rollback_checkpoint("migrate", untracked_paths=[]):
        pass

    assert untracked.exists()
    assert untracked.read_text() == "original memory\n"
    listing = subprocess.run(["git", "stash", "list"], capture_output=True, text=True)
    assert listing.stdout.strip() == ""


def test_cmd_rollback_last_restores_and_archives(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial", "-q"], cwd=tmp_path, check=True)

    with rollback.rollback_checkpoint("init", untracked_paths=[]):
        tracked.write_text("v2\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-m", "unwanted change", "-q"], cwd=tmp_path, check=True)

    assert tracked.read_text() == "v2\n"

    rollback.cmd_rollback(last=True)

    assert tracked.read_text() == "v1\n"
    assert not os.path.exists(rollback.MANIFEST_PATH)


def test_cmd_rollback_clear_discards_without_restoring(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "initial", "-q"], cwd=tmp_path, check=True)

    with rollback.rollback_checkpoint("init", untracked_paths=[]):
        pass

    assert os.path.exists(rollback.MANIFEST_PATH)
    rollback.cmd_rollback(clear=True)
    assert not os.path.exists(rollback.MANIFEST_PATH)
    archived = os.listdir(rollback.ARCHIVE_DIR)
    assert len(archived) == 1


def test_cmd_rollback_no_manifest_prints_message(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rollback.cmd_rollback(last=True)
    captured = capsys.readouterr()
    assert "no rollback checkpoint" in captured.out.lower()
