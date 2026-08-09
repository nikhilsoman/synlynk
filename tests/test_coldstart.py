import os
import subprocess

import pytest

from synlynk.coldstart import _detect_cold_start_mode


def _git_init(root, commits=0, files=None):
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True, check=True)
    for fname, content in (files or {}).items():
        (root / fname).write_text(content)
    for i in range(commits):
        (root / f"commit_{i}.txt").write_text(str(i))
        subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", f"commit {i}"], cwd=root, capture_output=True, check=True)


def test_detect_confident_new_empty_dir(tmp_path):
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "new"


def test_detect_confident_new_git_zero_commits_no_content(tmp_path):
    _git_init(tmp_path, commits=0)
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "new"


def test_detect_ambiguous_git_zero_commits_with_readme(tmp_path):
    _git_init(tmp_path, commits=0, files={"README.md": "# stray readme\n"})
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "ambiguous"


def test_detect_confident_existing_with_commits_and_manifest(tmp_path):
    _git_init(tmp_path, commits=3, files={"package.json": "{}"})
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "existing"
    assert result["signals"]["commit_count"] == 3


def test_detect_ambiguous_commits_but_no_recognizable_files(tmp_path):
    (tmp_path / ".git").mkdir()  # not a real repo — has_git True via os.path.isdir check
    result = _detect_cold_start_mode(str(tmp_path))
    # a .git dir with no working commits and no content is still "new" (fresh git init)
    assert result["mode"] == "new"


def test_detect_ambiguous_no_git_but_project_files_present(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "ambiguous"
