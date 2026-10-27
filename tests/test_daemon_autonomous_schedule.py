import json
import os
import sqlite3

import pytest


@pytest.fixture
def scheduler_db(monkeypatch, tmp_path):
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
    return db_path


def _seed_schedulable_story(db_path, story_id):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, "
        "phase, priority, readiness, estimated_tokens, goal_id) "
        "VALUES (?, ?, 'backend', 'platform', 'unknown', 'build', 5, 'ready', "
        "1000, 'goal-test')",
        (story_id, story_id),
    )
    capability_story_id = f"_capability-{story_id}"
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, "
        "phase, readiness, goal_id) VALUES (?, ?, 'backend', 'platform', "
        "'unknown', 'build', 'draft', 'goal-test')",
        (capability_story_id, capability_story_id),
    )
    conn.execute(
        "INSERT INTO capability_ratings (story_id, agent, model_version, engg_domain, "
        "org_domain, industry, phase, signal_source, quality) VALUES "
        "(?, 'codex', 'unknown', 'backend', 'platform', 'unknown', 'build', 'human', 0.9)",
        (capability_story_id,),
    )
    conn.execute(
        "INSERT INTO harness_quotas (harness, model, quota_type, unit, limit_tokens, "
        "used_tokens) VALUES ('codex', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()
    conn.close()


def _set_mode(mode):
    with open(".synlynk/config.json", "w", encoding="utf-8") as config_file:
        json.dump({"autonomy_mode": mode}, config_file)


def _disable_backlog_stages(monkeypatch, scheduler_mod):
    monkeypatch.setattr(scheduler_mod, "ingest_backlog", lambda *args, **kwargs: None)
    monkeypatch.setattr(scheduler_mod, "triage_backlog", lambda *args, **kwargs: None)
    monkeypatch.setattr(scheduler_mod, "auto_promote_backlog", lambda *args, **kwargs: [])
    monkeypatch.setattr(scheduler_mod, "_run_maintainer_triage_pass", lambda: None)


def test_autonomy_pass_supervised_computes_plan_without_dispatch(
    scheduler_db, monkeypatch, capsys
):
    from synlynk import scheduler as scheduler_mod

    _set_mode("supervised")
    _seed_schedulable_story(scheduler_db, "story-supervised")
    _disable_backlog_stages(monkeypatch, scheduler_mod)
    dispatched = []
    monkeypatch.setattr(
        "synlynk._dispatch_ready_jobs",
        lambda *args, **kwargs: dispatched.append(True),
    )

    scheduler_mod._autonomy_pass()

    assert "story-supervised" in capsys.readouterr().out
    assert dispatched == []
    conn = sqlite3.connect(scheduler_db)
    count = conn.execute("SELECT COUNT(*) FROM daemon_jobs").fetchone()[0]
    conn.close()
    assert count == 0


def test_autonomy_pass_autonomous_dispatches(scheduler_db, monkeypatch):
    from synlynk import scheduler as scheduler_mod

    _set_mode("autonomous")
    _seed_schedulable_story(scheduler_db, "story-autonomous")
    _disable_backlog_stages(monkeypatch, scheduler_mod)
    dispatched = []
    monkeypatch.setattr(
        "synlynk._dispatch_ready_jobs",
        lambda *args, **kwargs: dispatched.append(True) or 1,
    )

    scheduler_mod._autonomy_pass()

    assert dispatched == [True]
    conn = sqlite3.connect(scheduler_db)
    row = conn.execute(
        "SELECT status FROM daemon_jobs WHERE story_id='story-autonomous'"
    ).fetchone()
    conn.close()
    assert row == ("queued",)


def test_autonomy_pass_manual_skips_scheduling(scheduler_db, monkeypatch):
    from synlynk import scheduler as scheduler_mod

    _set_mode("manual")
    _disable_backlog_stages(monkeypatch, scheduler_mod)
    scheduled = []
    monkeypatch.setattr(
        scheduler_mod,
        "cmd_schedule",
        lambda *args, **kwargs: scheduled.append(True),
    )

    scheduler_mod._autonomy_pass()

    assert scheduled == []
