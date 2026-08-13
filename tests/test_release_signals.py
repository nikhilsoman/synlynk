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


from synlynk.release_signals import _detect_tag_pattern


def test_detect_pattern_semver():
    tags = [{"tag": "v0.1.0"}, {"tag": "v0.2.0"}, {"tag": "v1.0.0"}]
    assert _detect_tag_pattern(tags) == "semver"


def test_detect_pattern_semver_no_v_prefix():
    tags = [{"tag": "0.1.0"}, {"tag": "0.2.0"}]
    assert _detect_tag_pattern(tags) == "semver"


def test_detect_pattern_calver():
    tags = [{"tag": "2026.01.15"}, {"tag": "2026.03.02"}]
    assert _detect_tag_pattern(tags) == "calver"


def test_detect_pattern_monorepo():
    tags = [{"tag": "api@1.0.0"}, {"tag": "web@2.3.1"}, {"tag": "api@1.1.0"}]
    assert _detect_tag_pattern(tags) == "monorepo"


def test_detect_pattern_none_when_no_tags():
    assert _detect_tag_pattern([]) == "none"


def test_detect_pattern_mixed_when_inconsistent():
    tags = [{"tag": "v1.0.0"}, {"tag": "release-candidate-7"}, {"tag": "checkpoint"}]
    assert _detect_tag_pattern(tags) == "mixed"


from synlynk.release_signals import _latest_tag, _commits_since


def test_latest_tag_returns_most_recent_by_date(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")
    _commit(tmp_path, "b.txt", "b", "second")
    _tag(tmp_path, "v0.2.0")

    latest = _latest_tag(str(tmp_path))
    assert latest["tag"] == "v0.2.0"


def test_latest_tag_none_when_no_tags(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    assert _latest_tag(str(tmp_path)) is None


def test_commits_since_counts_commits_after_ref(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")
    _commit(tmp_path, "b.txt", "b", "second")
    _commit(tmp_path, "c.txt", "c", "third")

    assert _commits_since(str(tmp_path), "v0.1.0") == 2


def test_commits_since_zero_when_tag_is_head(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")

    assert _commits_since(str(tmp_path), "v0.1.0") == 0


from synlynk.release_signals import _release_status


def test_release_status_no_tags(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")

    status = _release_status(str(tmp_path))
    assert status == {
        "pattern": "none",
        "latest_tag": None,
        "latest_tag_date": None,
        "in_flight_commit_count": None,
        "in_flight_summary": None,
    }


def test_release_status_with_in_flight_commits(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")
    _commit(tmp_path, "b.txt", "b", "second")
    _commit(tmp_path, "c.txt", "c", "third")

    status = _release_status(str(tmp_path))
    assert status["pattern"] == "semver"
    assert status["latest_tag"] == "v0.1.0"
    assert status["in_flight_commit_count"] == 2
    assert status["in_flight_summary"] == "2 commits ahead of v0.1.0, not yet released"


def test_release_status_at_latest_tag_has_no_in_flight_summary(tmp_path):
    _git_init(tmp_path)
    _commit(tmp_path, "a.txt", "a", "first")
    _tag(tmp_path, "v0.1.0")

    status = _release_status(str(tmp_path))
    assert status["in_flight_commit_count"] == 0
    assert status["in_flight_summary"] is None


import json
from unittest.mock import patch, MagicMock

from synlynk.release_signals import _fetch_github_releases


def test_fetch_github_releases_parses_json_output(tmp_path):
    fake_output = json.dumps([
        {"tagName": "v0.2.0", "name": "v0.2.0", "publishedAt": "2026-08-01T00:00:00Z"},
        {"tagName": "v0.1.0", "name": "v0.1.0", "publishedAt": "2026-07-01T00:00:00Z"},
    ])
    fake_result = MagicMock(returncode=0, stdout=fake_output)
    with patch("subprocess.run", return_value=fake_result) as mock_run:
        releases = _fetch_github_releases(str(tmp_path))
    assert releases == [
        {"tag": "v0.2.0", "name": "v0.2.0", "published_at": "2026-08-01T00:00:00Z"},
        {"tag": "v0.1.0", "name": "v0.1.0", "published_at": "2026-07-01T00:00:00Z"},
    ]
    mock_run.assert_called_once()


def test_fetch_github_releases_returns_empty_when_gh_not_installed(tmp_path):
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert _fetch_github_releases(str(tmp_path)) == []


def test_fetch_github_releases_returns_empty_on_nonzero_exit(tmp_path):
    fake_result = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=fake_result):
        assert _fetch_github_releases(str(tmp_path)) == []


def test_fetch_github_releases_returns_empty_on_malformed_json(tmp_path):
    fake_result = MagicMock(returncode=0, stdout="not json")
    with patch("subprocess.run", return_value=fake_result):
        assert _fetch_github_releases(str(tmp_path)) == []




