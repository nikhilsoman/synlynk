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
    docs = tmp_path / "synlynk" / "project-docs"
    docs.mkdir(parents=True)
    (docs / "roadmap.md").write_text("v1\n")
    backup_dir = rollback._backup_paths("op1", ["synlynk/project-docs"])
    (docs / "roadmap.md").write_text("v2\n")
    (docs / "new-file.md").write_text("should be removed\n")
    rollback._restore_paths(backup_dir, ["synlynk/project-docs"])
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
