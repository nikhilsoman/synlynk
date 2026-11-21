"""Regression coverage for Personal-edition FTUE first-win dispatches."""

import sqlite3
from unittest.mock import MagicMock

from synlynk.editions import require_linked_goal_mode
from synlynk.launch import dispatch_first_win_remediation
import synlynk.dispatch as dispatch


def _quiet_unrelated_preflight(monkeypatch):
    monkeypatch.setattr(
        dispatch, "_read_harness_probe_row", lambda *args, **kwargs: ("ok", "[]")
    )
    monkeypatch.setattr(dispatch, "_preflight_auth_check", lambda *args, **kwargs: None)


def test_personal_edition_defaults_linked_goal_requirement_off():
    assert require_linked_goal_mode({}) is False
    assert require_linked_goal_mode({"edition": "personal"}) is False
    assert require_linked_goal_mode({"edition": "team"}) is True


def test_first_win_dispatch_supplies_synthetic_story_id(monkeypatch, tmp_path):
    mock_dispatch = MagicMock(return_value={"job_id": "job-first-win"})
    monkeypatch.setattr("synlynk.dispatch.dispatch_agent", mock_dispatch)

    result = dispatch_first_win_remediation(repo_dir=str(tmp_path))

    assert result["status"] == "dispatched"
    assert mock_dispatch.call_args.kwargs["story_id"] == "story-ftue-firstwin"
    assert "role" not in mock_dispatch.call_args.kwargs


def test_synthetic_first_win_story_bypasses_governs_linkage(monkeypatch):
    _quiet_unrelated_preflight(monkeypatch)
    monkeypatch.setattr(
        "synlynk.editions.require_linked_goal_mode", lambda: True
    )
    db = sqlite3.connect(":memory:")

    result = dispatch._preflight_dispatch(
        harness_name="codex",
        dispatch_flags=[],
        db_conn=db,
        story_id="story-ftue-firstwin",
        _task_hint="FTUE first-win remediation",
    )

    assert result == {"passed": True, "sentinel": None, "reason": None}
