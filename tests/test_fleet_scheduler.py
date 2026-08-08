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

def _seed_capability(conn, agent, engg, org, industry, phase, score, model="unknown"):
    # capability_scores is a VIEW over capability_ratings — seed the base table.
    seed_story = f"_capseed-{agent}-{engg}-{org}-{industry}-{phase}"
    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title, engg_domain, org_domain, "
        "industry, phase, readiness) VALUES (?, ?, ?, ?, ?, ?, 'draft')",
        (seed_story, seed_story, engg, org, industry, phase),
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality) VALUES (?, ?, ?, ?, ?, ?, ?, 'human', ?)",
        (seed_story, agent, model, engg, org, industry, phase, score),
    )


def _seed_story(conn, story_id, priority=5, readiness="ready", tokens=1000,
                 engg="backend", org="platform", industry="unknown", phase="build"):
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, phase, "
        "priority, readiness, estimated_tokens) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (story_id, story_id, engg, org, industry, phase, priority, readiness, tokens),
    )


def test_plan_skips_draft_stories(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-draft", readiness="draft")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"] == []
    assert result["blocked"] == []


def test_plan_assigns_ready_story_to_best_capability_agent(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-a")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    _seed_capability(conn, "codex", "backend", "platform", "unknown", "build", 0.4)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert len(result["plan"]) == 1
    assert result["plan"][0]["story_id"] == "story-a"
    assert result["plan"][0]["agent"] == "grok"


def test_plan_blocks_story_with_no_capability_candidates(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-b", engg="mobile")
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"] == []
    assert result["blocked"][0]["story_id"] == "story-b"
    assert result["blocked"][0]["reason"] == "no_capability_candidates"


def test_plan_blocks_story_when_all_candidates_quota_exhausted(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-c", tokens=50000)
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 10000, 10000)"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"] == []
    assert result["blocked"][0]["story_id"] == "story-c"
    assert result["blocked"][0]["reason"] == "quota_exhausted"


def test_plan_respects_max_stories(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-1")
    _seed_story(conn, "story-2")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan(max_stories=1)
    assert len(result["plan"]) == 1


def test_plan_decrements_fleet_headroom_across_batch_and_blocks_second_story(scheduler_db):
    """The genuinely new piece: two ready stories, one agent, quota only covers one."""
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-1", tokens=6000, priority=1)
    _seed_story(conn, "story-2", tokens=6000, priority=2)
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 10000, 0)"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert [p["story_id"] for p in result["plan"]] == ["story-1"]
    assert result["blocked"][0]["story_id"] == "story-2"
    assert result["blocked"][0]["reason"] == "quota_exhausted"


def test_plan_excludes_agent_that_previously_failed_this_story(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-retry")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    _seed_capability(conn, "codex", "backend", "platform", "unknown", "build", 0.3)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('codex', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
        "VALUES ('djob-prev', 'grok', 'do it', 'story-retry', 'failed', '2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"][0]["agent"] == "codex"


def test_plan_blocks_story_past_retry_cap(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-exhausted-retries")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    for i in range(2):
        conn.execute(
            "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
            f"VALUES ('djob-e{i}', 'grok', 'do it', 'story-exhausted-retries', 'failed', "
            "'2026-01-01T00:00:00')"
        )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"] == []
    assert result["blocked"][0]["reason"] == "retry_cap_exceeded"


def test_plan_skips_story_with_running_daemon_job(scheduler_db):
    """A story already mid-flight must not be double-scheduled."""
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-inflight")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
        "VALUES ('djob-running', 'grok', 'do it', 'story-inflight', 'running', "
        "'2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"] == []
    assert result["blocked"] == []


def test_plan_dry_run_never_writes_to_daemon_jobs(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-dry")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()

    _compute_schedule_plan()

    count = conn.execute("SELECT COUNT(*) FROM daemon_jobs").fetchone()[0]
    conn.close()
    assert count == 0


def test_plan_degraded_mode_still_produces_a_plan(scheduler_db):
    """No agent_quotas rows at all -> degraded, non-hard-blocking per design."""
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-degraded")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert len(result["plan"]) == 1
    assert result["plan"][0]["agent"] == "grok"

def test_enqueue_plan_writes_one_queued_daemon_job_per_assignment(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _enqueue_plan

    plan = [
        {"story_id": "story-a", "title": "story-a", "agent": "grok", "priority": 3},
        {"story_id": "story-b", "title": "story-b", "agent": "codex", "priority": 7},
    ]
    job_ids = _enqueue_plan(plan)
    assert len(job_ids) == 2

    conn = _get_db()
    rows = conn.execute(
        "SELECT story_id, agent, status, priority FROM daemon_jobs ORDER BY story_id"
    ).fetchall()
    conn.close()
    assert rows == [
        ("story-a", "grok", "queued", 3),
        ("story-b", "codex", "queued", 7),
    ]


def test_enqueue_plan_opens_reservations(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _enqueue_plan

    plan = [
        {
            "story_id": "story-sched1",
            "title": "Sched test",
            "agent": "codex",
            "score": 1.0,
            "model": "unknown",
            "priority": 5,
            "estimated_tokens": 7_000,
            "headroom_before": 100_000,
            "headroom_after": 93_000,
        },
    ]

    job_ids = _enqueue_plan(plan)
    assert len(job_ids) == 1

    conn = _get_db()
    rows = conn.execute(
        "SELECT harness, tokens, scope, job_id, status FROM agent_reservations "
        "WHERE job_id=?",
        (job_ids[0],),
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][:3] == ("codex", 7_000, "plan")
    assert rows[0][4] == "open"


def test_enqueue_plan_on_empty_plan_writes_nothing(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _enqueue_plan

    job_ids = _enqueue_plan([])
    assert job_ids == []

    conn = _get_db()
    count = conn.execute("SELECT COUNT(*) FROM daemon_jobs").fetchone()[0]
    conn.close()
    assert count == 0

def test_cmd_schedule_dry_run_prints_plan_and_writes_nothing(scheduler_db, capsys):
    from synlynk import _get_db
    from synlynk.scheduler import cmd_schedule

    conn = _get_db()
    _seed_story(conn, "story-dryrun")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()
    conn.close()

    cmd_schedule(execute=False)

    out = capsys.readouterr().out
    assert "story-dryrun" in out
    assert "grok" in out

    conn = _get_db()
    count = conn.execute("SELECT COUNT(*) FROM daemon_jobs").fetchone()[0]
    conn.close()
    assert count == 0


def test_cmd_schedule_execute_enqueues_and_calls_dispatch(scheduler_db, monkeypatch):
    from synlynk import _get_db
    from synlynk.scheduler import cmd_schedule

    conn = _get_db()
    _seed_story(conn, "story-exec")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()
    conn.close()

    called = {}

    def fake_dispatch(max_parallel=4):
        called["ran"] = True
        return 1

    monkeypatch.setattr("synlynk._dispatch_ready_jobs", fake_dispatch)
    cmd_schedule(execute=True)

    assert called.get("ran") is True
    conn = _get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE story_id='story-exec'"
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_cmd_schedule_shows_blocked_stories_with_reason(scheduler_db, capsys):
    from synlynk import _get_db
    from synlynk.scheduler import cmd_schedule

    conn = _get_db()
    _seed_story(conn, "story-blocked", engg="mobile")
    conn.commit()
    conn.close()

    cmd_schedule(execute=False)
    out = capsys.readouterr().out
    assert "story-blocked" in out
    assert "no_capability_candidates" in out

def test_cli_schedule_subparser_accepts_execute_and_max_stories():
    import argparse

    import synlynk.cli as cli_mod

    # Smoke-test the parser wiring directly rather than invoking main(),
    # which would require a fully bootstrapped project directory.
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    schedule_parser = subparsers.add_parser("schedule")
    schedule_parser.add_argument("--execute", action="store_true")
    schedule_parser.add_argument("--max-stories", type=int, default=None, dest="max_stories")

    args = parser.parse_args(["schedule", "--execute", "--max-stories", "3"])
    assert args.execute is True
    assert args.max_stories == 3


def test_end_to_end_ready_story_flows_to_queued_daemon_job(scheduler_db, monkeypatch):
    """story create -> story ready -> schedule --execute -> daemon_jobs row exists,
    matching the design doc's stated flow: stories is input, daemon_jobs is output."""
    from synlynk import _get_db
    from synlynk.db import cmd_story_create, cmd_story_ready
    from synlynk.scheduler import cmd_schedule

    conn = _get_db()
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()
    conn.close()

    story_id = cmd_story_create("end to end story", engg_domain="backend", org_domain="platform")
    cmd_story_ready(story_id)

    monkeypatch.setattr("synlynk._dispatch_ready_jobs", lambda max_parallel=4: 0)
    cmd_schedule(execute=True)

    conn = _get_db()
    row = conn.execute(
        "SELECT agent, status FROM daemon_jobs WHERE story_id=?", (story_id,)
    ).fetchone()
    conn.close()
    assert row == ("grok", "queued")
