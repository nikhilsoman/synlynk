"""Verification tests for Phase 6 of #5272: Backlog Burndown Arc, Spec/Decision Mining, and Decide Panels."""

import sqlite3
import json
from unittest.mock import patch
import pytest

from synlynk.backlog import mine_specs_and_decisions, ingest_backlog
from synlynk.maintainer import (
    is_issue_remediated,
    cluster_open_issues,
    run_backlog_burndown_sweep,
)
from synlynk.tpm_sweep import resolve_ambiguity_via_decide, run_tpm_wake_cycle


def test_mine_specs_and_decisions(tmp_path):
    """Verify committed specs, plans, and decisions are accurately mined into backlog_items."""
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    spec_file = specs_dir / "2026-11-15-example-feature-design.md"
    spec_file.write_text(
        "# Example Feature Design\n\n"
        "## Tasks\n"
        "- [ ] Build the autonomous caching layer for telemetry\n"
        "- [ ] Implement cross-node synchronization protocol\n"
        "- [x] Completed task that should not be mined\n"
    )

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE backlog_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT UNIQUE,
            title TEXT,
            body TEXT,
            fingerprint TEXT,
            role TEXT,
            stage TEXT,
            governs_stage TEXT,
            complexity_tier INTEGER,
            goal_id TEXT,
            acceptance_criteria TEXT,
            status TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT UNIQUE,
            title TEXT,
            fingerprint TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT UNIQUE,
            decision_text TEXT,
            rationale TEXT,
            status TEXT,
            goal_id TEXT,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "INSERT INTO decisions (decision_id, decision_text, rationale, status, goal_id) "
        "VALUES ('dec-test01', 'Adopt decentralized consensus for worker agents', 'Lower latency', 'approved', 'goal-005ea87d')"
    )
    conn.commit()

    mined = mine_specs_and_decisions(repo_root=str(tmp_path), db_conn=conn)
    assert len(mined) >= 3

    spec_items = [m for m in mined if m["source_type"] == "spec"]
    assert len(spec_items) == 2
    assert any("autonomous caching layer" in m["title"] for m in spec_items)

    dec_items = [m for m in mined if m["source_type"] == "decision"]
    assert len(dec_items) == 1
    assert "Adopt decentralized consensus" in dec_items[0]["title"]

    # Verify rows in backlog_items table
    rows = conn.execute("SELECT item_id, title, status FROM backlog_items").fetchall()
    assert len(rows) >= 3
    assert all(r[2] == "staged" for r in rows)

    conn.close()


def test_resolve_ambiguity_via_decide(tmp_path):
    """Verify ambiguous or Tier-3 backlog items trigger automated decide panel consensus."""
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE backlog_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT UNIQUE,
            title TEXT,
            complexity_tier INTEGER,
            goal_id TEXT,
            status TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT UNIQUE,
            decision_text TEXT,
            rationale TEXT,
            status TEXT,
            goal_id TEXT,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "INSERT INTO backlog_items (item_id, title, complexity_tier, goal_id, status) "
        "VALUES ('item-ambig-1', 'Architectural dilemma: multi-tenant mesh partitioning', 3, NULL, 'staged')"
    )
    conn.commit()

    item = {
        "id": 1,
        "item_id": "item-ambig-1",
        "title": "Architectural dilemma: multi-tenant mesh partitioning",
        "complexity_tier": 3,
        "goal_id": None,
    }

    res = resolve_ambiguity_via_decide(item, conn=conn, repo_root=str(tmp_path))
    assert res is not None
    assert res["verdict"] == "consensus_reached"
    assert res["decision_id"].startswith("dec-")

    # Verify decision recorded in database
    dec_row = conn.execute("SELECT decision_id, decision_text, status FROM decisions").fetchone()
    assert dec_row is not None
    assert dec_row[0] == res["decision_id"]
    assert dec_row[2] == "approved"

    # Verify backlog item updated to tpm_drafted with complexity tier 2
    item_row = conn.execute("SELECT complexity_tier, goal_id, status FROM backlog_items WHERE id=1").fetchone()
    assert item_row[0] == 2
    assert item_row[1] is not None
    assert item_row[2] == "tpm_drafted"

    conn.close()


def test_is_issue_remediated():
    """Verify issue remediation detection from commit messages, issue numbers, and tags."""
    commits = [
        "feat(db): rebuild goals table to strip stale FKs (gh:#5274)",
        "fix: circuit breaker trip on live-19",
        "chore: update dependencies",
    ]

    # Explicit issue number
    assert is_issue_remediated("goal create fails with foreign key mismatch", commits, issue_number=5274)
    # Non-remediated issue number
    assert not is_issue_remediated("unrelated problem", commits, issue_number=9999)

    # LIVE tag in issue text matching commit message
    assert is_issue_remediated("[LIVE-19] Circuit breaker reset failure", commits)

    # Unrelated issue
    assert not is_issue_remediated("Add new button to dashboard", commits)


def test_cluster_open_issues():
    """Verify open issues are grouped by domain for sprint formation."""
    issues = [
        {"number": 1, "title": "SQLite migration locked error", "labels": ["backend"]},
        {"number": 2, "title": "Fix database deadlock on state.db", "labels": ["backend"]},
        {"number": 3, "title": "Update README installation steps", "labels": ["docs"]},
        {"number": 4, "title": "CLI flag --timeout ignored", "labels": ["cli"]},
        {"number": 5, "title": "Vizor css button styling broken", "labels": ["frontend"]},
    ]
    clusters = cluster_open_issues(issues)
    assert len(clusters["backend"]) == 2
    assert len(clusters["docs"]) == 1
    assert len(clusters["cli"]) == 1
    assert len(clusters["frontend"]) == 1


def test_run_backlog_burndown_sweep(tmp_path):
    """Verify burndown sweep identifies remediated tickets and forms sprint clusters."""
    sample_issues = [
        {"number": 5274, "title": "Foreign key mismatch on goals", "body": "Sev1 crash"},
        {"number": 101, "title": "Fix database WAL lock on state.db", "body": "backend lock"},
        {"number": 102, "title": "Database connection timeout in backend", "body": "db timeout"},
        {"number": 103, "title": "SQL query optimization for state.db", "body": "backend perf"},
    ]

    with patch("synlynk.backlog.fetch_open_github_issues", return_value=sample_issues):
        with patch("subprocess.run") as mock_git:
            # Mock git log returning commit for 5274
            mock_git.return_value.returncode = 0
            mock_git.return_value.stdout = "fix(db): rebuild goals table (gh:#5274)\x1fchore: unrelated commit\x1f"

            res = run_backlog_burndown_sweep(repo_root=str(tmp_path), dry_run=True)
            assert res["inspected"] == 4
            assert res["remediated_count"] == 1
            assert res["remediated"][0]["number"] == 5274
            assert res["remaining_count"] == 3
            assert res["sprint_staged"] is not None
            assert res["sprint_staged"]["domain"] == "backend"
            assert res["sprint_staged"]["count"] == 3


def test_mine_specs_and_decisions_does_not_truncate_at_ten(tmp_path):
    """Verify plans with >10 tasks (e.g. 24 tasks) are not truncated at 10 (dec-fcec4295)."""
    plans_dir = tmp_path / "docs" / "superpowers" / "plans"
    plans_dir.mkdir(parents=True)
    plan_file = plans_dir / "2026-11-18-large-24-task-plan.md"

    tasks_content = ["# Large Plan with 24 Tasks\n\n"]
    for i in range(1, 25):
        tasks_content.append(f"### Task {i}: Implement feature component {i}\n\n- [ ] **Step 1: Write test**\n- [ ] **Step 2: Implement**\n\n")
    plan_file.write_text("".join(tasks_content))

    mined = mine_specs_and_decisions(repo_root=str(tmp_path), db_conn=None, limit=100)
    spec_items = [m for m in mined if m["source_type"] == "spec"]

    # Must mine all 24 tasks without 10-item truncation
    assert len(spec_items) == 24
    for i in range(1, 25):
        assert any(f"Implement feature component {i}" in m["title"] for m in spec_items)

