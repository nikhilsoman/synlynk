import json
import os
import sqlite3
import pytest
from synlynk import _get_db
from synlynk.backlog import (
    stage_discovered_work,
    triage_backlog,
    synthesize_story_from_issue,
)
from synlynk.charters import (
    TRIGGER_REGISTRY,
    render_trigger_registry_markdown,
    refresh_agent_instruction_triggers,
)


@pytest.fixture
def test_db(tmp_path):
    conn = _get_db(db_path=str(tmp_path / "test.db"))
    conn.execute("""
        INSERT INTO goals (goal_id, outcome, criterion, status)
        VALUES ('goal-005ea87d', 'Ephemeral swarm runners and compute dispatch', 'Swarm runners execute', 'active')
    """)
    conn.commit()
    return conn


def test_synthesize_story_from_issue(test_db):
    issue = {
        "number": 123,
        "title": "Fix memory leak in swarm runner pod eviction",
        "body": "When running high-concurrency swarm jobs, pods leak memory during eviction. Need reproduction test and memory limit.",
        "labels": ["bug", "swarm"],
        "author": "devbot",
    }
    story = synthesize_story_from_issue(issue, db_conn=test_db)
    assert story["role"] in ("dev", "infra", "qa")
    assert story["complexity_tier"] in (1, 2, 3)
    assert story["goal_id"] == "goal-005ea87d"
    assert len(story["acceptance_criteria"]) >= 1


def test_triage_backlog_e2e(test_db):
    test_db.execute("""
        INSERT INTO backlog_items (item_id, title, body, author, status)
        VALUES ('item-101', 'Implement swarm runner heartbeats', 'Ephemeral swarm runners should report heartbeat every 30s.', 'bot', 'staged')
    """)
    test_db.commit()

    triaged = triage_backlog(auto_promote=False, db_conn=test_db)
    assert len(triaged) == 1
    assert triaged[0]["item_id"] == "item-101"
    assert triaged[0]["goal_id"] == "goal-005ea87d"


def test_trigger_registry_rendering():
    md = render_trigger_registry_markdown()
    assert "## Trigger registry" in md
    assert "synlynk swarm dispatch" in md
    assert "synlynk heal --magic" in md
    assert "synlynk init" in md
    assert len(TRIGGER_REGISTRY) >= 50


def test_refresh_agent_instruction_triggers(tmp_path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Claude Guide\n\n## Trigger registry\n- old triggers\n\n## End\n")

    gemini_md = tmp_path / "GEMINI.md"
    gemini_md.write_text("# Gemini Guide\n\n## Trigger registry\n- old triggers\n\n<!-- synlynk:end -->\n")

    res = refresh_agent_instruction_triggers(repo_root=str(tmp_path), dry_run=False)
    assert res["CLAUDE.md"] is True
    assert res["GEMINI.md"] is True

    # Check updated content
    updated_claude = claude_md.read_text()
    assert "synlynk heal --magic" in updated_claude
    assert "## End" in updated_claude
