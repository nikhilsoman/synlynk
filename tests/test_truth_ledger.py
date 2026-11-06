"""Unit tests for Day 4 Truth Ledger (v0.28.4):

- Blocking stray/shadow state.db creation in linked worktrees (#4239).
- Enforcing canonical state database registry resolution under permission restrictions (#4239).
- Single-source authority model for state.db vs git-ignored generated project docs (#4705).
- Clean roadmap and story sync CLI commands (#4371).
"""

import json
import os
import subprocess
import pytest

from synlynk import _get_db, _resolve_db_path
from synlynk.db import _detect_hand_edit, _generate_roadmap_md, _generate_todo_md
from synlynk.state_registry import canonical_path, StateRegistryError


def test_connect_blocks_shadow_db_inside_worktree(tmp_path, monkeypatch):
    """Verify _connect refuses to create a shadow state.db inside a git worktree."""
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    shadow_db = worktree_root / ".synlynk" / "state.db"

    monkeypatch.setattr("synlynk._is_git_worktree", lambda: True)
    monkeypatch.setattr("synlynk._working_tree_root", lambda: str(worktree_root))
    monkeypatch.setattr("synlynk._IS_TESTING", False)
    monkeypatch.delenv("SYNLYNK_ALLOW_WORKTREE_DB", raising=False)

    with pytest.raises(RuntimeError, match="refusing to create or open shadow state database inside linked worktree"):
        _get_db(str(shadow_db), read_only=False)


def test_connect_allows_shadow_db_when_explicitly_permitted(tmp_path, monkeypatch):
    """Verify _connect allows worktree DB when SYNLYNK_ALLOW_WORKTREE_DB=1."""
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    allowed_db = worktree_root / "custom.db"

    monkeypatch.setattr("synlynk._is_git_worktree", lambda: True)
    monkeypatch.setattr("synlynk._working_tree_root", lambda: str(worktree_root))
    monkeypatch.setattr("synlynk._IS_TESTING", False)
    monkeypatch.setenv("SYNLYNK_ALLOW_WORKTREE_DB", "1")

    conn = _get_db(str(allowed_db), read_only=False)
    try:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_canonical_path_recovers_when_permission_denied(tmp_path, monkeypatch):
    """Verify canonical_path recovers to existing fallback when registry reading is permission denied."""
    registry = tmp_path / "registry.json"
    registry.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))

    fallback = tmp_path / "fallback" / "state.db"
    fallback.parent.mkdir(parents=True)
    fallback.write_text("state")

    # Simulate sandboxed permission error on registry read
    monkeypatch.setattr(
        "synlynk.state_registry._read_unlocked",
        lambda path: {"version": 1, "products": {}, "_permission_denied": True},
    )

    resolved = canonical_path("synlynk", fallback)
    assert resolved == fallback.resolve()


def test_detect_hand_edit_skips_gitignored_project_docs(tmp_path, monkeypatch):
    """Verify _detect_hand_edit returns None for files ignored by git."""
    monkeypatch.chdir(tmp_path)
    docs_dir = tmp_path / "project-docs"
    docs_dir.mkdir(parents=True)
    doc_file = docs_dir / "todo.md"
    doc_file.write_text("# Old Todo Content")

    monkeypatch.setattr("synlynk.db._resolved_docs_dir", lambda: str(docs_dir))

    # Mock subprocess.run to simulate git check-ignore returning 0 (ignored)
    orig_run = subprocess.run
    def mock_run(args, **kwargs):
        if "check-ignore" in args:
            class Result:
                returncode = 0
            return Result()
        return orig_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)
    assert _detect_hand_edit("todo.md") is None


def test_cli_roadmap_render_and_story_sync(tmp_path, monkeypatch, capsys):
    """Verify roadmap render and story sync CLI commands invoke generators and exit 0."""
    from synlynk.cli import main

    monkeypatch.setattr("synlynk.db._generate_roadmap_md", lambda: None)
    monkeypatch.setattr("synlynk.db._generate_todo_md", lambda: None)

    main(["roadmap", "render"])
    out = capsys.readouterr().out
    assert "Rendered roadmap.md from state.db" in out

    main(["story", "sync"])
    out = capsys.readouterr().out
    assert "Rendered todo.md from state.db" in out
