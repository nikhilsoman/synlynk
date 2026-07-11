import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def scheduler_db(monkeypatch, tmp_path):
    """Fresh state.db with schema + migrations applied, cwd set to a temp project."""
    from synlynk import _DB_SCHEMA
    from synlynk.db import _migrate_db

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)
    os.makedirs(".synlynk", exist_ok=True)
    db_path = ".synlynk/state.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(_DB_SCHEMA)
    _migrate_db(conn)
    conn.commit()
    conn.close()

    monkeypatch.setattr("synlynk._get_db", lambda: sqlite3.connect(db_path))
    yield db_path


def test_stories_table_has_priority_and_readiness_columns(scheduler_db):
    conn = sqlite3.connect(scheduler_db)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    conn.close()
    assert "priority" in cols
    assert "readiness" in cols


def test_priority_defaults_to_5_and_readiness_defaults_to_draft(scheduler_db):
    conn = sqlite3.connect(scheduler_db)
    conn.execute(
        "INSERT INTO stories (story_id, title) VALUES ('story-t1', 'test story')"
    )
    conn.commit()
    row = conn.execute(
        "SELECT priority, readiness FROM stories WHERE story_id='story-t1'"
    ).fetchone()
    conn.close()
    assert row == (5, "draft")

def test_cmd_story_ready_sets_readiness_to_ready(scheduler_db):
    from synlynk.db import cmd_story_create, cmd_story_ready

    story_id = cmd_story_create("readiness test", engg_domain="backend", org_domain="platform")
    cmd_story_ready(story_id)

    conn = sqlite3.connect(scheduler_db)
    readiness = conn.execute(
        "SELECT readiness FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()[0]
    conn.close()
    assert readiness == "ready"


def test_cmd_story_ready_all_marks_every_draft_story_ready(scheduler_db):
    from synlynk.db import cmd_story_create, cmd_story_ready

    s1 = cmd_story_create("story one", engg_domain="backend", org_domain="platform")
    s2 = cmd_story_create("story two", engg_domain="backend", org_domain="platform")
    cmd_story_ready(None, all_stories=True)

    conn = sqlite3.connect(scheduler_db)
    rows = conn.execute(
        "SELECT story_id, readiness FROM stories WHERE story_id IN (?, ?)", (s1, s2)
    ).fetchall()
    conn.close()
    assert dict(rows) == {s1: "ready", s2: "ready"}


def test_cmd_story_draft_reverts_readiness_to_draft(scheduler_db):
    from synlynk.db import cmd_story_create, cmd_story_draft, cmd_story_ready

    story_id = cmd_story_create("draft test", engg_domain="backend", org_domain="platform")
    cmd_story_ready(story_id)
    cmd_story_draft(story_id)

    conn = sqlite3.connect(scheduler_db)
    readiness = conn.execute(
        "SELECT readiness FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()[0]
    conn.close()
    assert readiness == "draft"

def test_story_failed_agents_returns_empty_set_with_no_history(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _story_failed_agents

    conn = _get_db()
    assert _story_failed_agents(conn, "story-none") == set()
    conn.close()


def test_story_failed_agents_returns_agents_from_failed_daemon_jobs(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _story_failed_agents

    conn = _get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
        "VALUES ('djob-f1', 'grok', 'do it', 'story-x', 'failed', '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
        "VALUES ('djob-f2', 'codex', 'do it', 'story-x', 'done', '2026-01-01T00:00:00')"
    )
    conn.commit()
    assert _story_failed_agents(conn, "story-x") == {"grok"}
    conn.close()


def test_story_retry_count_matches_failed_job_rows(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _story_retry_count

    conn = _get_db()
    for i in range(2):
        conn.execute(
            "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
            f"VALUES ('djob-r{i}', 'grok', 'do it', 'story-y', 'failed', '2026-01-01T00:00:00')"
        )
    conn.commit()
    assert _story_retry_count(conn, "story-y") == 2
    conn.close()
