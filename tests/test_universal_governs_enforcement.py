"""Tests for Universal GOVERNS Enforcement (gh:#5119, gh:#1990)."""

import sqlite3
import pytest
import synlynk as sl
import synlynk.dispatch as dispatch_mod
from synlynk.dispatch import _preflight_dispatch
from synlynk.doctor import _hc_loop_goals_operating_stories
from synlynk.policy_gates import gate_mode
from synlynk.tpm_sweep import find_unstaffed_loop_goals


def _quiet_unrelated_preflight(monkeypatch):
    monkeypatch.setattr(dispatch_mod, "_read_harness_probe_row", lambda *a, **k: ("ok", "[]"))
    monkeypatch.setattr(dispatch_mod, "_preflight_auth_check", lambda *a, **k: None)


def _make_test_db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE goals (
            id INTEGER PRIMARY KEY,
            goal_id TEXT UNIQUE,
            outcome TEXT,
            criterion TEXT,
            status TEXT DEFAULT 'active',
            kind TEXT DEFAULT 'feature',
            placement_status TEXT DEFAULT 'placed',
            phase_id INTEGER DEFAULT 1
        )"""
    )
    conn.execute(
        """CREATE TABLE stories (
            id INTEGER PRIMARY KEY,
            story_id TEXT UNIQUE,
            title TEXT,
            goal_id TEXT,
            status TEXT DEFAULT 'open',
            readiness TEXT DEFAULT 'ready'
        )"""
    )
    conn.execute(
        """CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY
        )"""
    )
    conn.execute("INSERT INTO roadmap_phases VALUES (1)")
    return conn


def test_preflight_blocks_when_unlinked_in_enforce_mode(monkeypatch):
    _quiet_unrelated_preflight(monkeypatch)
    import synlynk.policy_gates as pg
    monkeypatch.setattr(pg, "gate_mode", lambda gate, key, repo_root=".": "enforce")

    db = _make_test_db()
    result = _preflight_dispatch(
        harness_name="codex",
        dispatch_flags=[],
        db_conn=db,
        _task_hint="unlinked ad-hoc task with no issue reference",
    )
    assert result["passed"] is False
    assert result["sentinel"] == "GOVERNS_LINKAGE_MISSING"
    assert "Dispatch rejected: task is not linked to a GOVERNS story" in result["reason"]


def test_preflight_warns_when_unlinked_in_observe_mode(monkeypatch):
    _quiet_unrelated_preflight(monkeypatch)
    import synlynk.policy_gates as pg
    monkeypatch.setattr(pg, "gate_mode", lambda gate, key, repo_root=".": "observe")

    db = _make_test_db()
    result = _preflight_dispatch(
        harness_name="codex",
        dispatch_flags=[],
        db_conn=db,
        _task_hint="unlinked ad-hoc task with no issue reference",
    )
    assert result["passed"] is True
    assert result["sentinel"] is None


def test_preflight_passes_when_story_linked_to_placed_goal(monkeypatch):
    _quiet_unrelated_preflight(monkeypatch)
    import synlynk.policy_gates as pg
    monkeypatch.setattr(pg, "gate_mode", lambda gate, key, repo_root=".": "enforce")

    db = _make_test_db()
    db.execute("INSERT INTO goals (goal_id, outcome, criterion) VALUES ('goal-1', 'outcome', 'criterion')")
    db.execute("INSERT INTO stories (story_id, title, goal_id) VALUES ('story-1', 'story', 'goal-1')")
    db.commit()

    result = _preflight_dispatch(
        harness_name="codex",
        dispatch_flags=[],
        db_conn=db,
        story_id="story-1",
        _task_hint="task for story-1",
    )
    assert result["passed"] is True
    assert result["sentinel"] is None


def test_find_unstaffed_loop_goals_detects_missing_story():
    db = _make_test_db()
    db.execute("INSERT INTO goals (goal_id, outcome, criterion, kind, status) VALUES ('goal-loop-1', 'continuous loop', 'criterion', 'loop', 'active')")
    db.commit()

    unstaffed = find_unstaffed_loop_goals(db)
    assert len(unstaffed) == 1
    assert unstaffed[0]["goal_id"] == "goal-loop-1"


def test_find_unstaffed_loop_goals_ignores_completed_or_cancelled_stories():
    db = _make_test_db()
    db.execute("INSERT INTO goals (goal_id, outcome, criterion, kind, status) VALUES ('goal-loop-1', 'continuous loop', 'criterion', 'loop', 'active')")
    db.execute("INSERT INTO stories (story_id, title, goal_id, status) VALUES ('story-1', 'old story', 'goal-loop-1', 'done')")
    db.execute("INSERT INTO stories (story_id, title, goal_id, status) VALUES ('story-2', 'cancelled story', 'goal-loop-1', 'cancelled')")
    db.commit()

    unstaffed = find_unstaffed_loop_goals(db)
    assert len(unstaffed) == 1
    assert unstaffed[0]["goal_id"] == "goal-loop-1"


def test_find_unstaffed_loop_goals_passes_with_active_story():
    db = _make_test_db()
    db.execute("INSERT INTO goals (goal_id, outcome, criterion, kind, status) VALUES ('goal-loop-1', 'continuous loop', 'criterion', 'loop', 'active')")
    db.execute("INSERT INTO stories (story_id, title, goal_id, status) VALUES ('story-1', 'active story', 'goal-loop-1', 'open')")
    db.commit()

    unstaffed = find_unstaffed_loop_goals(db)
    assert len(unstaffed) == 0


def test_doctor_hc_loop_goals_operating_stories(monkeypatch):
    import synlynk.doctor as doc

    db = _make_test_db()
    db.execute("INSERT INTO goals (goal_id, outcome, criterion, kind, status) VALUES ('goal-loop-1', 'continuous loop', 'criterion', 'loop', 'active')")
    db.commit()

    monkeypatch.setattr(doc, "_pkg", lambda name: (lambda: db))
    hc = doc._hc_loop_goals_operating_stories()
    assert hc.status == "fail"
    assert "goal-loop-1" in hc.message

    db.execute("INSERT INTO stories (story_id, title, goal_id, status) VALUES ('story-1', 'active story', 'goal-loop-1', 'open')")
    db.commit()

    hc_pass = doc._hc_loop_goals_operating_stories()
    assert hc_pass.status == "ok"
