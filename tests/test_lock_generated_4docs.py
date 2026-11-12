import os
import stat
import subprocess
import pytest

import synlynk
from synlynk.db import _write_generated_project_doc, _detect_hand_edit


def test_write_generated_project_doc_handles_locked_file(tmp_path, monkeypatch):
    """Writing a generated doc must succeed even if the target file is read-only (0o444)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir(parents=True)
    (tmp_path / "project-docs").mkdir(parents=True)

    target_file = tmp_path / "project-docs" / "todo.md"
    target_file.write_text("# Initial Content\n")
    os.chmod(target_file, 0o444)  # locked read-only

    # Mock _is_migrated to True so it relocks
    monkeypatch.setattr("synlynk._is_migrated", lambda: True)
    monkeypatch.setattr("synlynk.db._resolved_docs_dir", lambda: str(tmp_path / "project-docs"))
    monkeypatch.setattr("synlynk._synlynk_project_docs_dir", lambda: str(tmp_path / ".synlynk" / "project-docs"))
    monkeypatch.setattr("synlynk._generated_doc_side_effects_allowed", lambda: True)

    new_content = "# Tasks (generated - source of truth is state.db)\n- [ ] Task A\n"
    _write_generated_project_doc("todo.md", new_content)

    assert target_file.read_text() == new_content
    # Permissions must be locked back to read-only (not writable by owner)
    mode = os.stat(target_file).st_mode
    assert not (mode & stat.S_IWUSR), f"Expected read-only 0o444, got mode {oct(mode)}"


def test_write_generated_project_doc_dual_writes_both_locations(tmp_path, monkeypatch):
    """When migrated, writes to both .synlynk/project-docs/ and project-docs/ with lock."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk" / "project-docs").mkdir(parents=True)
    (tmp_path / "project-docs").mkdir(parents=True)

    monkeypatch.setattr("synlynk._is_migrated", lambda: True)
    monkeypatch.setattr("synlynk.db._resolved_docs_dir", lambda: str(tmp_path / "project-docs"))
    monkeypatch.setattr("synlynk._synlynk_project_docs_dir", lambda: str(tmp_path / ".synlynk" / "project-docs"))
    monkeypatch.setattr("synlynk._generated_doc_side_effects_allowed", lambda: True)

    content = "# Roadmap\n## v0.32.3\n"
    _write_generated_project_doc("roadmap.md", content)

    migrated_copy = tmp_path / ".synlynk" / "project-docs" / "roadmap.md"
    workspace_copy = tmp_path / "project-docs" / "roadmap.md"

    assert migrated_copy.exists()
    assert migrated_copy.read_text() == content

    assert workspace_copy.exists()
    assert workspace_copy.read_text() == content
    assert not (os.stat(workspace_copy).st_mode & stat.S_IWUSR)


def test_cmd_migrate_locks_all_four_generated_docs(tmp_path, monkeypatch):
    """cmd_migrate must lock todo.md, roadmap.md, memory.md, costs.md to read-only."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    # Initialize a git repo
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=tmp_path, check=True)

    docs = tmp_path / "project-docs"
    docs.mkdir()
    (docs / "todo.md").write_text("# Tasks\n- [ ] Task 1\n")
    (docs / "roadmap.md").write_text("# Roadmap\n## v0.1.0\n")
    (docs / "memory.md").write_text("# Memory\n## Section\nContent\n")
    (docs / "costs.md").write_text("# Costs\n| Date | Agent | Cost |\n")

    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init", "-q"], cwd=tmp_path, check=True)

    (tmp_path / ".synlynk").mkdir()

    synlynk.cmd_migrate()

    for fname in ("todo.md", "roadmap.md", "memory.md", "costs.md"):
        doc_file = docs / fname
        assert doc_file.exists()
        mode = os.stat(doc_file).st_mode
        assert not (mode & stat.S_IWUSR), f"{fname} is not read-only: {oct(mode)}"
