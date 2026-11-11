"""Unit tests for TPM L1_ADVISORY Release-Scale Proposals and Human Gates (v0.32.1)."""

import json
from unittest.mock import MagicMock, patch

import pytest
import synlynk as sl
from synlynk.greenfield.fleet_probe import probe_fleet
from synlynk.tpm_sweep import (
    dispatch_tpm_advisory_proposal,
    format_release_proposal_markdown,
    package_next_release_proposal,
    process_proposal_comments,
)


def test_format_release_proposal_markdown_has_required_sections():
    proposal = {
        "release_version": "v0.32.1",
        "theme": "Living Ledger & Smart Auto-Update Engine",
        "bookend_mtd": "Shipped v0.30.0, v0.31.0, and v0.32.0.",
        "bookend_wtd": "Ratified multi-cadence roadmap.",
        "bookend_today": "Shipped DGX Spark gateway discovery.",
        "stories": [
            {
                "story_id": "story-doc-graph",
                "issue_number": 5211,
                "title": "Document Sidecar Knowledge Graph",
                "role": "dev",
                "harness": "agy",
                "estimated_tokens": 28000,
                "estimated_cost_usd": 0.04,
                "status": "Ready",
            },
            {
                "story_id": "story-auto-upd",
                "issue_number": 5212,
                "title": "Smart Auto-Update & Background Notification",
                "role": "dev",
                "harness": "codex",
                "estimated_tokens": 35000,
                "estimated_cost_usd": 0.06,
                "status": "Ready",
            },
        ],
        "role_breakdown": {
            "dev": ["Document Sidecar Knowledge Graph", "Smart Auto-Update"],
            "qa": ["Verification Contracts"],
            "finops": ["Cost Ledger Reconciliation"],
        },
        "bookend_horizon": "Day 3 (v0.32.2): Constitutional Gate; Day 4: DGX Deep Integration.",
    }

    body = format_release_proposal_markdown(proposal)

    # 1. Orientation Book-End
    assert "Situational Orientation" in body
    assert "Month-to-Date" in body
    assert "Week-to-Date" in body
    assert "Earlier Today" in body

    # 2. Compact task references
    assert "[#5211]" in body
    assert "(story-doc-graph)" in body
    assert "[#5212]" in body

    # 3. Role breakdown
    assert "Breakdown by Agent Role" in body
    assert "dev" in body
    assert "finops" in body

    # 4. Roadmap Horizon
    assert "Roadmap Horizon" in body
    assert "v0.32.2" in body

    # 5. Comment command instruction set footer
    assert "Operator Action & Commands" in body
    assert "`/approve`" in body
    assert "`/revise" in body
    assert "`/drop" in body
    assert "`/hold`" in body


def test_max_active_proposals_throttling(tmp_path, monkeypatch):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        # Create approval_tickets table if needed and seed 3 open proposals
        conn.execute(
            """CREATE TABLE IF NOT EXISTS approval_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id TEXT,
                action TEXT,
                issue_url TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        for i in range(3):
            conn.execute(
                "INSERT INTO approval_tickets (story_id, action, issue_url, status) "
                "VALUES (?, 'release_proposal', ?, 'open')",
                (f"proposal-{i}", f"https://github.com/nikhilsoman/synlynk/issues/{5210+i}"),
            )
        conn.commit()

        # Attempt to dispatch proposal with limit 3: should return None (throttled)
        dispatched = dispatch_tpm_advisory_proposal(
            conn=conn, max_active_proposals=3, assignee="nikhilsoman"
        )
        assert dispatched is None
    finally:
        conn.close()


def test_process_proposal_comment_approval(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        # Seed stories
        conn.execute(
            """CREATE TABLE IF NOT EXISTS stories (
                story_id TEXT PRIMARY KEY,
                title TEXT,
                role TEXT,
                readiness TEXT,
                goal_id TEXT
            )"""
        )
        conn.execute(
            "INSERT INTO stories (story_id, title, role, readiness) VALUES ('s1', 'Task 1', 'dev', 'advisory')"
        )
        conn.execute(
            "INSERT INTO stories (story_id, title, role, readiness) VALUES ('s2', 'Task 2', 'qa', 'advisory')"
        )
        conn.commit()

        # Human comment '/approve'
        comments = [{"user": "nikhilsoman", "body": "/approve LGTM let's go"}]
        result = process_proposal_comments(
            comments, constituent_story_ids=["s1", "s2"], conn=conn
        )
        assert result["verdict"] == "approved"
        assert result["promoted_count"] == 2

        # Verify stories are now ready
        ready_stories = [
            r[0]
            for r in conn.execute(
                "SELECT story_id FROM stories WHERE readiness='ready'"
            ).fetchall()
        ]
        assert "s1" in ready_stories
        assert "s2" in ready_stories
    finally:
        conn.close()


def test_fleet_probe_discovers_openai_compatible_gateways(monkeypatch):
    # Mock probe_local_runtimes returning a discovered local model
    from synlynk.models import ModelSpec

    fake_spec = ModelSpec(
        model_id="deepseek-r1:70b",
        family_id="deepseek",
        harness_binding="local",
        discovery_source="openai_gateway:http://localhost:8001/v1/models",
    )
    monkeypatch.setattr(
        "synlynk.models.probe_local_runtimes", lambda *args, **kwargs: [fake_spec]
    )
    monkeypatch.setattr("shutil.which", lambda name: False)

    res = probe_fleet()
    local_entry = next(h for h in res["harnesses"] if h["harness"] == "local")
    assert local_entry["available"] is True
    assert "Found ✓" in local_entry["status"]
