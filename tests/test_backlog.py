import json
import sqlite3
import subprocess
from unittest.mock import patch, MagicMock
import pytest

import synlynk
from synlynk.backlog import (
    compute_fingerprint,
    fetch_open_github_issues,
    is_duplicate_issue,
    synthesize_story_from_issue,
    ingest_backlog,
    triage_backlog,
    auto_promote_backlog,
    stage_discovered_work,
    list_staged_backlog,
)
from synlynk.db import _migrate_db
from synlynk.taxonomy import COMMAND_TAXONOMY


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_file))
    _migrate_db(conn)
    return conn


def test_fetch_open_github_issues_parsing():
    sample_gh_output = json.dumps([
        {
            "number": 1340,
            "title": "PM Autonomous Backlog Triaging & Story Formation Engine",
            "body": "Implement PM Autonomous Backlog Triaging per spec.\n\n- [ ] Ingest issues\n- [ ] Synthesize stories",
            "labels": [{"name": "role:pm"}, {"name": "governs:open"}],
            "author": {"login": "nikhilsoman"},
            "createdAt": "2026-09-02T10:00:00Z",
            "updatedAt": "2026-09-02T11:00:00Z",
            "url": "https://github.com/nikhilsoman/synlynk/issues/1340",
        }
    ])
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = sample_gh_output

    with patch("subprocess.run", return_value=mock_proc):
        issues = fetch_open_github_issues(limit=10)
        assert len(issues) == 1
        iss = issues[0]
        assert iss["number"] == 1340
        assert iss["title"] == "PM Autonomous Backlog Triaging & Story Formation Engine"
        assert iss["author"] == "nikhilsoman"
        assert "role:pm" in iss["labels"]
        assert len(iss["fingerprint"]) == 16


def test_is_duplicate_issue_deduplication(test_db):
    # 1. Test clean issue is not duplicate
    issue1 = {
        "number": 2001,
        "title": "Add ephemeral runner Fly.io driver",
        "body": "Driver implementation for Fly micro-VMs",
        "labels": ["role:dev"],
    }
    is_dup, reason = is_duplicate_issue(issue1, db_conn=test_db, check_closed_prs=False)
    assert is_dup is False

    # 2. Insert into backlog_items and test duplicate detection
    fp = compute_fingerprint(issue1["title"], f"issue-{issue1['number']}")
    test_db.execute(
        "INSERT INTO backlog_items (item_id, title, issue_number, fingerprint, status) VALUES (?, ?, ?, ?, 'staged')",
        ("backlog-issue-2001", issue1["title"], 2001, fp),
    )
    test_db.commit()

    is_dup, reason = is_duplicate_issue(issue1, db_conn=test_db, check_closed_prs=False)
    assert is_dup is True
    assert "backlog" in reason

    # 3. Test duplicate against stories table
    issue2 = {
        "number": 2002,
        "title": "Cross-Harness Inter-Agent Event Relay",
        "body": "Event relay bus over SSE/JSON-RPC",
        "labels": ["role:architect"],
    }
    fp2 = compute_fingerprint(issue2["title"], f"issue-{issue2['number']}")
    test_db.execute(
        "INSERT INTO stories (story_id, title, gh_issue, fingerprint, status) VALUES (?, ?, ?, ?, 'open')",
        ("story-2002", issue2["title"], "2002", fp2),
    )
    test_db.commit()

    is_dup, reason = is_duplicate_issue(issue2, db_conn=test_db, check_closed_prs=False)
    assert is_dup is True
    assert "story" in reason


def test_is_duplicate_against_closed_prs_and_git(test_db):
    issue = {
        "number": 9999,
        "title": "Fix SQLite lock contention during sweep",
        "body": "Add retry backoff",
        "labels": ["bug"],
    }
    # Mock git log returning a commit fixing #9999
    mock_git = MagicMock()
    mock_git.returncode = 0
    mock_git.stdout = "abc1234 Fix SQLite lock contention (#9999)"

    with patch("subprocess.run", return_value=mock_git):
        is_dup, reason = is_duplicate_issue(issue, db_conn=test_db, check_closed_prs=True)
        assert is_dup is True
        assert reason == "resolved_in_git_commit"


def test_synthesize_story_from_issue_roles_and_tiers():
    # QA Role + Tier 2
    qa_issue = {
        "number": 101,
        "title": "Add reproduction test for quota reset window calculation",
        "body": "Write pytest fixture and test reproduction in tests/.",
        "labels": ["role:qa", "bug"],
    }
    qa_story = synthesize_story_from_issue(qa_issue)
    assert qa_story["role"] == "qa"
    assert qa_story["stage"] == "sustain"
    assert qa_story["complexity_tier"] == 2
    assert len(qa_story["acceptance_criteria"]) >= 3

    # Architect Role + Tier 3
    arch_issue = {
        "number": 102,
        "title": "Cross-cutting multi-agent distributed event relay protocol and architecture overhaul",
        "body": "Design spec and protocol schema for inter-agent relay.",
        "labels": ["role:architect"],
    }
    arch_story = synthesize_story_from_issue(arch_issue)
    assert arch_story["role"] == "architect"
    assert arch_story["stage"] == "visualize"
    assert arch_story["complexity_tier"] == 3
    assert arch_story["goal_id"] == "goal-ef42902a"  # mapped to event relay goal

    # Tier 1 Docs / Typo
    doc_issue = {
        "number": 103,
        "title": "Fix minor typo in readme documentation",
        "body": "Fix spelling in installation docs.",
        "labels": [],
    }
    doc_story = synthesize_story_from_issue(doc_issue)
    assert doc_story["complexity_tier"] == 1
    assert doc_story["stage"] == "notify" or doc_story["stage"] == "open"


def test_synthesize_story_markdown_acceptance_criteria_parsing():
    issue_with_boxes = {
        "number": 104,
        "title": "Implement CLI triage command",
        "body": """## Scope
Implement the triage command.

## Acceptance Criteria
- [ ] Parse `--auto-promote` CLI flag
- [ ] Synthesize structured story metadata
- [ ] Verify test suite passes
""",
        "labels": ["enhancement"],
    }
    story = synthesize_story_from_issue(issue_with_boxes)
    assert len(story["acceptance_criteria"]) == 3
    assert "Parse `--auto-promote` CLI flag" in story["acceptance_criteria"]
    assert "Synthesize structured story metadata" in story["acceptance_criteria"]


def test_ingest_backlog_pipeline(test_db):
    mock_issues = [
        {
            "number": 3001,
            "title": "Ephemeral cloud runner Fly.io driver",
            "body": "Support Fly micro-VM execution driver with budget caps",
            "labels": [{"name": "enhancement"}],
            "author": {"login": "nikhilsoman"},
            "createdAt": "2026-09-02T12:00:00Z",
            "updatedAt": "2026-09-02T12:00:00Z",
            "url": "https://github.com/nikhilsoman/synlynk/issues/3001",
        },
        {
            "number": 3002,
            "title": "Fix stale SOP section during roles repair",
            "body": "Repair stale SOP headers",
            "labels": [{"name": "bug"}],
            "author": {"login": "nikhilsoman"},
            "createdAt": "2026-09-02T12:00:00Z",
            "updatedAt": "2026-09-02T12:00:00Z",
            "url": "https://github.com/nikhilsoman/synlynk/issues/3002",
        },
    ]

    with patch("synlynk.backlog.fetch_open_github_issues", return_value=mock_issues):
        with patch("synlynk.backlog.is_duplicate_issue", return_value=(False, "")):
            res = ingest_backlog(db_conn=test_db)
            assert res["fetched"] == 2
            assert res["ingested"] == 2
            assert res["duplicates"] == 0

            # Verify in DB
            rows = test_db.execute("SELECT item_id, title, status FROM backlog_items").fetchall()
            assert len(rows) == 2
            assert rows[0][2] == "staged"


def test_triage_and_auto_promote_backlog(test_db):
    # Ingest mock item
    mock_issues = [
        {
            "number": 4001,
            "title": "Living Charter Evolution telemetry weight recalibration",
            "body": "Recalibrate dispatch routing weights based on verified telemetry.",
            "labels": [{"name": "role:dev"}],
            "author": {"login": "nikhilsoman"},
            "createdAt": "2026-09-02T12:00:00Z",
            "updatedAt": "2026-09-02T12:00:00Z",
            "url": "https://github.com/nikhilsoman/synlynk/issues/4001",
        }
    ]
    with patch("synlynk.backlog.fetch_open_github_issues", return_value=mock_issues):
        with patch("synlynk.backlog.is_duplicate_issue", return_value=(False, "")):
            ingest_backlog(db_conn=test_db)

    # Triage
    triaged = triage_backlog(auto_promote=False, db_conn=test_db)
    assert len(triaged) == 1
    assert triaged[0]["status"] == "triaged"
    assert triaged[0]["goal_id"] == "goal-adb60ccc"  # mapped to living charter goal

    # Auto promote
    promoted = auto_promote_backlog(db_conn=test_db, min_tier=1)
    assert len(promoted) == 1
    story_id = promoted[0]["story_id"]
    assert story_id.startswith("story-")

    # Verify state.db stories table
    story_row = test_db.execute(
        "SELECT story_id, title, readiness, status, goal_id FROM stories WHERE story_id = ?",
        (story_id,),
    ).fetchone()
    assert story_row is not None
    assert story_row[1] == "Living Charter Evolution telemetry weight recalibration"
    assert story_row[2] == "ready"
    assert story_row[3] == "open"
    assert story_row[4] == "goal-adb60ccc"

    # Verify goal contribution
    gc_row = test_db.execute(
        "SELECT goal_id, story_id FROM goal_contributions WHERE story_id = ?",
        (story_id,),
    ).fetchone()
    assert gc_row is not None
    assert gc_row[0] == "goal-adb60ccc"


def test_cli_backlog_subcommands_integration(capsys, monkeypatch, test_db):
    from synlynk.cli import main

    monkeypatch.setattr("synlynk.backlog._get_connection", lambda db_conn=None: test_db)

    mock_issues = [
        {
            "number": 5001,
            "title": "Model Registry entitlement tier enforcement",
            "body": "- [ ] Enforce model entitlement\n- [ ] Unit tests pass",
            "labels": [{"name": "role:dev"}],
            "author": {"login": "nikhilsoman"},
            "createdAt": "2026-09-02T12:00:00Z",
            "updatedAt": "2026-09-02T12:00:00Z",
            "url": "https://github.com/nikhilsoman/synlynk/issues/5001",
        }
    ]

    with patch("synlynk.backlog.fetch_open_github_issues", return_value=mock_issues):
        with patch("synlynk.backlog.is_duplicate_issue", return_value=(False, "")):
            # 1. synlynk backlog ingest
            main(["backlog", "ingest"])
            captured = capsys.readouterr().out
            assert "Ingested 1 backlog items" in captured

            # 2. synlynk backlog triage
            main(["backlog", "triage"])
            captured = capsys.readouterr().out
            assert "Triaged 1 backlog items" in captured
            assert "Model Registry entitlement tier enforcement" in captured

            # 3. synlynk backlog auto-promote
            main(["backlog", "auto-promote"])
            captured = capsys.readouterr().out
            assert "Promoted 1 backlog items to ready stories" in captured
            assert "story-" in captured


def test_taxonomy_registration_of_backlog_commands():
    cmds = {entry["command"] for entry in COMMAND_TAXONOMY}
    assert "backlog ingest" in cmds
    assert "backlog triage" in cmds
    assert "backlog auto-promote" in cmds
    assert "backlog capture" in cmds
    assert "backlog list" in cmds
    assert "backlog sync" in cmds
