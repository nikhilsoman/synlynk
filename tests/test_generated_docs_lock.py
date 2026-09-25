"""goal-6733bbf1: generated 4-doc lock, worktree identity, generator write-through."""
import json
import os
import subprocess
from pathlib import Path

import pytest

import synlynk
from synlynk import instructions as instructions_mod
from synlynk.coldstart import _bootstrap_4docs, run_brownfield_init
from synlynk.db import cmd_roadmap_add, _generate_roadmap_md
from synlynk.scan import _static_scan


GENERATED_HEADER = "source of truth is state.db"
SKELETON_MARK = "Skeleton generated from git history"


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, check=True)


def _mark_migrated(root: Path):
    syn = root / ".synlynk"
    syn.mkdir(parents=True, exist_ok=True)
    (syn / ".synlynk_migrated").write_text("1\n")
    cfg = syn / "config.json"
    if not cfg.exists():
        cfg.write_text(json.dumps({"identity_slug": "synlynk", "project_docs_dir": "project-docs"}))


def test_write_informed_skeleton_skips_generated_docs_when_migrated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _mark_migrated(tmp_path)
    docs = tmp_path / "project-docs"
    docs.mkdir()
    (docs / "devlogs").mkdir()
    original = "# Roadmap (generated - source of truth is state.db)\n# locked\n"
    (docs / "roadmap.md").write_text(original)

    scan = {
        "project_name": "feat+vizor-governs-board-and-gantt-ia",
        "description": "should not land",
        "commit_count": 1,
        "has_structured_commits": False,
        "recent_topics": ["feat: clobber"],
        "top_dirs": ["src"],
        "languages": ["Python"],
        "readme_summary": "",
    }
    written = instructions_mod._write_informed_skeleton(scan, skip_existing=False)
    written_paths = [p for p, _ in written]
    assert "project-docs/roadmap.md" not in written_paths
    assert (docs / "roadmap.md").read_text() == original
    assert SKELETON_MARK not in (docs / "roadmap.md").read_text()


def test_bootstrap_4docs_does_not_clobber_migrated_roadmap_even_with_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _mark_migrated(tmp_path)
    docs = tmp_path / "project-docs"
    docs.mkdir(parents=True)
    original = "# Roadmap (generated - source of truth is state.db)\n# keep me\n"
    (docs / "roadmap.md").write_text(original)

    created = _bootstrap_4docs(
        str(tmp_path),
        stack="Python",
        test_cmd="pytest",
        lint_cmd="ruff check .",
        build_cmd="pip install -e .",
        hotspots=["main.py"],
        user_name="alice",
        force=True,
    )
    assert "roadmap.md" not in created
    assert (docs / "roadmap.md").read_text() == original


def test_static_scan_uses_identity_slug_not_worktree_folder(tmp_path):
    main = tmp_path / "synlynk"
    main.mkdir()
    _git(main, "init")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / ".synlynk").mkdir()
    (main / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": "synlynk"}))
    (main / "README.md").write_text("<p align='center'>logo</p>\n\nKeep your AI tools in sync.\n")
    _git(main, "add", ".")
    _git(main, "commit", "-m", "init")

    wt = tmp_path / "feat+vizor-governs-board-and-gantt-ia"
    _git(main, "worktree", "add", str(wt))

    scan = _static_scan(str(wt))
    assert scan["project_name"] == "synlynk"
    assert "feat+vizor" not in scan["project_name"]


def test_brownfield_project_name_uses_root_identity_not_worktree(tmp_path, monkeypatch):
    main = tmp_path / "synlynk"
    main.mkdir()
    _git(main, "init")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / ".synlynk").mkdir()
    (main / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": "synlynk"}))
    (main / "pyproject.toml").write_text("[project]\nname='synlynk'\n")
    _git(main, "add", ".")
    _git(main, "commit", "-m", "init")
    wt = tmp_path / "feat+vizor-governs-board-and-gantt-ia"
    _git(main, "worktree", "add", str(wt))

    monkeypatch.chdir(wt)
    res = run_brownfield_init(str(wt), interactive=False, dry_run=True)
    assert res["project_name"] == "synlynk"


def test_generate_roadmap_md_writes_git_tracked_copy_when_migrated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _mark_migrated(tmp_path)
    (tmp_path / "project-docs").mkdir()
    (tmp_path / ".synlynk" / "project-docs").mkdir()
    monkeypatch.setattr(synlynk, "_project_root", lambda: str(tmp_path))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    monkeypatch.setattr(synlynk, "_docs_dir", lambda: str(tmp_path / "project-docs"))
    monkeypatch.setattr(
        synlynk, "_synlynk_project_docs_dir", lambda: str(tmp_path / ".synlynk" / "project-docs")
    )

    cmd_roadmap_add(
        version="v0.23.0",
        title="Graphify canvas",
        status="shipped",
        role="pm",
    )
    _generate_roadmap_md()

    migrated = (tmp_path / ".synlynk" / "project-docs" / "roadmap.md").read_text()
    tracked = (tmp_path / "project-docs" / "roadmap.md").read_text()
    assert GENERATED_HEADER in migrated
    assert GENERATED_HEADER in tracked
    assert "v0.23.0" in tracked
    assert SKELETON_MARK not in tracked
