import subprocess
import sqlite3

import pytest

from synlynk.db import _migrate_db
from synlynk.capability_classifier import classify_failure


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=repo, check=True)
    target = repo / "synlynk" / "jobs.py"
    target.parent.mkdir(parents=True)
    target.write_text("def _maybe_open_worktree_pr():\n    pass\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


@pytest.fixture
def conn(tmp_path):
    connection = sqlite3.connect(str(tmp_path / "state.db"))
    _migrate_db(connection)
    return connection


def test_classify_regression_when_synlynk_path_changed_since_green(git_repo, conn):
    green_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True
    ).stdout.strip()
    target = git_repo / "synlynk" / "jobs.py"
    target.write_text("def _maybe_open_worktree_pr():\n    return 'changed'\n")
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "change jobs.py"], cwd=git_repo, check=True)

    result = classify_failure(
        conn,
        harness="codex",
        failing_path="synlynk/jobs.py",
        repo_path=str(git_repo),
        last_green_sha=green_sha,
        harness_fingerprint_changed=False,
    )
    assert result["classification"] == "regression"
    row = conn.execute(
        "SELECT classification FROM capability_incidents WHERE harness = 'codex'"
    ).fetchone()
    assert row[0] == "regression"


def test_classify_drift_when_only_harness_fingerprint_changed(git_repo, conn):
    green_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True
    ).stdout.strip()
    result = classify_failure(
        conn,
        harness="codex",
        failing_path="synlynk/jobs.py",
        repo_path=str(git_repo),
        last_green_sha=green_sha,
        harness_fingerprint_changed=True,
    )
    assert result["classification"] == "drift"


def test_classify_unclassified_when_neither_changed(git_repo, conn):
    green_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True
    ).stdout.strip()
    result = classify_failure(
        conn,
        harness="codex",
        failing_path="synlynk/jobs.py",
        repo_path=str(git_repo),
        last_green_sha=green_sha,
        harness_fingerprint_changed=False,
    )
    assert result["classification"] == "unclassified"
