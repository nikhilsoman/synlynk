"""Test durable import root resolution for LIVE-30 (gh:#5144)."""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from synlynk import vizor_daemon


def test_synlynk_import_root_resolves_canonical_repo_from_worktree(tmp_path):
    """When synlynk is imported from a linked worktree, _synlynk_import_root()
    must resolve to the main repository root, never the ephemeral worktree path."""
    # Setup simulated git repo structure
    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    subprocess.run(["git", "init"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=main_repo, check=True, capture_output=True)

    # Create synlynk package in main_repo
    pkg_dir = main_repo / "synlynk"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("# main synlynk\n")
    (main_repo / "README.md").write_text("# Main\n")
    subprocess.run(["git", "add", "."], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=main_repo, check=True, capture_output=True)

    # Create linked worktree
    wt_dir = tmp_path / "worktrees" / "job-123"
    wt_dir.parent.mkdir()
    subprocess.run(["git", "worktree", "add", str(wt_dir), "-b", "feat/job-123"], cwd=main_repo, check=True, capture_output=True)

    # Simulate synlynk.__file__ being inside the linked worktree
    simulated_init = wt_dir / "synlynk" / "__init__.py"
    assert simulated_init.is_file()

    import synlynk
    with patch.object(synlynk, "__file__", str(simulated_init)):
        resolved = vizor_daemon._synlynk_import_root()
        # MUST resolve to main_repo, NOT wt_dir
        assert resolved == str(main_repo.resolve())
        assert resolved != str(wt_dir.resolve())


def test_synlynk_import_root_non_worktree_fallback(tmp_path):
    """When synlynk is imported from a normal non-worktree repo or directory,
    _synlynk_import_root() resolves to parent directory containing synlynk package."""
    pkg_dir = tmp_path / "standalone_repo" / "synlynk"
    pkg_dir.mkdir(parents=True)
    simulated_init = pkg_dir / "__init__.py"
    simulated_init.write_text("# standalone synlynk\n")

    import synlynk
    with patch.object(synlynk, "__file__", str(simulated_init)):
        resolved = vizor_daemon._synlynk_import_root()
        assert resolved == str((tmp_path / "standalone_repo").resolve())
