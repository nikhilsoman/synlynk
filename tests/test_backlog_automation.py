import sqlite3
import pytest
from unittest.mock import patch

from synlynk.backlog import (
    compute_fingerprint,
    check_duplicate,
    stage_discovered_work,
    list_staged_backlog,
    sync_backlog_to_github,
)
from synlynk.backlog_extractor import (
    extract_from_devlog_content,
    extract_from_job_summary,
    extract_from_doctor_failures,
)


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_state.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("""
        CREATE TABLE stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT UNIQUE,
            title TEXT,
            role TEXT DEFAULT "dev",
            stage TEXT DEFAULT "open",
            governs_stage TEXT DEFAULT "open",
            status TEXT DEFAULT "open",
            priority INTEGER DEFAULT 5,
            fingerprint TEXT UNIQUE,
            source_type TEXT,
            source_ref TEXT,
            gh_issue TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def test_compute_fingerprint_normalization():
    fp1 = compute_fingerprint("Fix SQLite lock timeout in dispatch", "synlynk/dispatch.py")
    fp2 = compute_fingerprint("fix sqlite  lock-timeout in DISPATCH!", "synlynk/dispatch.py")
    assert fp1 == fp2
    assert len(fp1) == 16


def test_stage_and_deduplication(test_db):
    res1 = stage_discovered_work(
        title="Add quota retry backoff",
        description="Exponential backoff when quota is exceeded",
        role="dev",
        stage="sustain",
        source_type="devlog",
        source_ref="devlog:nikhil",
        db_conn=test_db,
    )
    assert res1["staged"] is True
    assert res1["role"] == "dev"
    assert res1["stage"] == "sustain"
    assert res1["story_id"].startswith("story-")

    # Duplicate attempt
    res2 = stage_discovered_work(
        title="add quota retry backoff",
        description="Duplicate note",
        db_conn=test_db,
    )
    assert res2["staged"] is False
    assert res2["reason"] == "duplicate"


def test_list_staged_backlog(test_db):
    stage_discovered_work(title="Feature 1", stage="open", db_conn=test_db)
    stage_discovered_work(title="Bug fix 2", stage="sustain", db_conn=test_db)

    all_items = list_staged_backlog(db_conn=test_db)
    assert len(all_items) == 2

    sustain_items = list_staged_backlog(db_conn=test_db, stage="sustain")
    assert len(sustain_items) == 1
    assert sustain_items[0]["title"] == "Bug fix 2"


def test_extract_from_devlog():
    devlog_text = """
# Devlog — 2026-08-31
Some general working notes here.

### Discovered / Follow-up Work
- [ ] Refactor harness verb mapping table
- Add regression test for empty workspace charter resolution

<!-- discover: Auto-detect Herdr pane context | stage: visualize | role: architect -->
"""
    items = extract_from_devlog_content(devlog_text, author="nikhil")
    assert len(items) == 3

    # Check bullet items
    titles = [it["title"] for it in items]
    assert "Refactor harness verb mapping table" in titles
    assert "Add regression test for empty workspace charter resolution" in titles
    assert "Auto-detect Herdr pane context" in titles

    # Check explicit marker attributes
    marker_item = [it for it in items if it["title"] == "Auto-detect Herdr pane context"][0]
    assert marker_item["stage"] == "visualize"
    assert marker_item["role"] == "architect"


def test_extract_from_job_summary():
    summary = """
Job completed with status OK.
FOLLOWUP: Add missing mock for subprocess in test_runner
TECH-DEBT: Clean up deprecated agent_quotas table references
"""
    items = extract_from_job_summary(summary, job_id="job-1234", touched_files=["tests/test_runner.py"])
    assert len(items) == 2
    assert items[0]["title"] == "Add missing mock for subprocess in test_runner"
    assert items[0]["source_type"] == "job_output"
    assert items[0]["role"] == "qa"
    assert "touched files: tests/test_runner.py" in items[0]["description"]
    assert items[0]["touched_files"] == ["tests/test_runner.py"]
    assert items[1]["title"] == "Clean up deprecated agent_quotas table references"


def test_extract_from_doctor_failures():
    failures = [
        {"name": "gh_auth", "reason": "GitHub token expired"},
        {"name": "schema_drift", "reason": "todo.md has drifted from state.db"},
    ]
    items = extract_from_doctor_failures(failures)
    assert len(items) == 2
    assert items[0]["title"] == "Fix doctor check: gh_auth"
    assert items[0]["stage"] == "sustain"
    assert items[0]["role"] == "qa"


def test_check_duplicate_github_layer():
    with patch("synlynk.backlog._query_github_open_issues", return_value=[{"number": 1203, "title": "Design GOVERNS backlog automation"}]):
        assert check_duplicate("design governs backlog automation", check_gh=True) is True
        assert check_duplicate("completely new task", check_gh=True) is False


def test_sync_backlog_to_github_with_existing_issue_deduplication(test_db):
    stage_discovered_work(title="Existing issue on GitHub", db_conn=test_db)
    stage_discovered_work(title="Brand new issue", db_conn=test_db)

    # Mock GH open issues containing "Existing issue on GitHub" (#999)
    gh_mock_issues = [{"number": 999, "title": "Existing issue on GitHub"}]
    with patch("synlynk.backlog._query_github_open_issues", return_value=gh_mock_issues):
        with patch("synlynk.backlog._create_github_issue", return_value=1001) as mock_create:
            results = sync_backlog_to_github(db_conn=test_db, dry_run=False)
            assert len(results) == 2
            by_title = {r["title"]: r for r in results}
            # Existing issue linked without creating new issue
            assert by_title["Existing issue on GitHub"]["gh_issue"] == 999
            assert by_title["Existing issue on GitHub"]["action"] == "linked_existing_issue"
            # Brand new item created new issue
            assert by_title["Brand new issue"]["gh_issue"] == 1001
            assert by_title["Brand new issue"]["action"] == "created_issue"
            assert mock_create.call_count == 1


def test_cli_backlog_integration(capsys, monkeypatch, test_db):
    from synlynk.cli import main

    monkeypatch.setattr("synlynk.backlog._get_connection", lambda db_conn=None: test_db)

    # Test capture
    main(["backlog", "capture", "--title", "CLI discovered task", "--stage", "sustain", "--role", "qa"])
    captured = capsys.readouterr().out
    assert "Staged backlog item" in captured
    assert "CLI discovered task" in captured

    # Test list
    main(["backlog", "list"])
    captured = capsys.readouterr().out
    assert "CLI discovered task" in captured
    assert "sustain" in captured

    # Test sync dry run
    main(["backlog", "sync", "--dry-run"])
    captured = capsys.readouterr().out
    assert "[dry-run] Would create issue" in captured

