import subprocess

import pytest

from synlynk.release_signals import _git_tags_with_dates


def _git_init(root):
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True, check=True)


def _commit(root, fname, content, msg):
    (root / fname).write_text(content)
    subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=root, capture_output=True, check=True)


def _tag(root, name, annotated=True):
    if annotated:
        subprocess.run(["git", "tag", "-a", name, "-m", name], cwd=root, capture_output=True, check=True)
    else:
        subprocess.run(["git", "tag", name], cwd=root, capture_output=True, check=True)


def test_git_tags_with_dates_empty_repo_returns_empty(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    assert _git_tags_with_dates(str(tmp_path)) == []


def test_git_tags_with_dates_returns_sorted_by_date(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")
    _commit(tmp_path, "b.txt", "b", "second")
    _tag(tmp_path, "v0.2.0")

    tags = _git_tags_with_dates(str(tmp_path))
    assert [t["tag"] for t in tags] == ["v0.1.0", "v0.2.0"]
    assert all("date" in t and "sha" in t for t in tags)


def test_git_tags_with_dates_handles_lightweight_tags(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0", annotated=False)

    tags = _git_tags_with_dates(str(tmp_path))
    assert [t["tag"] for t in tags] == ["v0.1.0"]


def test_git_tags_with_dates_non_git_dir_returns_empty(tmp_path):
    assert _git_tags_with_dates(str(tmp_path)) == []
