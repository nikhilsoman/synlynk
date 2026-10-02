import os
import subprocess

import pytest
from synlynk.regen_guard import check_regen_write_guard, RegenConflictError


def _repo_with_origin_main(tmp_path, monkeypatch, content):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    filepath = repo / "costs.md"
    filepath.write_text(content)
    subprocess.run(["git", "add", "costs.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True)
    subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=repo, check=True)
    monkeypatch.chdir(repo)
    return filepath


def test_regen_guard_append(tmp_path):
    f = tmp_path / "costs.md"
    f.write_text("Row 1\nRow 2\n")
    
    # Pure append should not raise
    check_regen_write_guard(str(f), "Row 1\nRow 2\nRow 3\n")
    
def test_regen_guard_conflict(tmp_path, monkeypatch):
    f = _repo_with_origin_main(tmp_path, monkeypatch, "Row 1\nRow 2\nRow 3\n")
    
    # Removing a row should raise
    with pytest.raises(RegenConflictError, match="would remove or replace 1 existing lines"):
        check_regen_write_guard(str(f), "Row 1\nRow 3\n")
        
def test_regen_guard_rewrite_with_change(tmp_path, monkeypatch):
    f = _repo_with_origin_main(tmp_path, monkeypatch, "Row 1\nRow 2\n")
    
    # Modifying a row should raise
    with pytest.raises(RegenConflictError):
        check_regen_write_guard(str(f), "Row 1\nRow X\n")

def test_regen_guard_new_file(tmp_path):
    f = tmp_path / "costs.md"
    # File doesn't exist
    check_regen_write_guard(str(f), "Row 1\nRow 2\n")
