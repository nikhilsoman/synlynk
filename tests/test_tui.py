from types import SimpleNamespace
from unittest.mock import Mock, patch

from synlynk import tui


class FakeScreen:
    def __init__(self, keys):
        self.keys = iter(keys)
        self.lines = []

    def addstr(self, *args):
        self.lines.append(args[-1])

    def erase(self):
        pass

    def refresh(self):
        pass

    def nodelay(self, value):
        pass

    def getkey(self):
        return next(self.keys)


def _job(**kwargs):
    values = dict(ts="now", agent="codex", duration_s=1.0, exit_code=0, cost_usd=0.0)
    values.update(kwargs)
    return SimpleNamespace(**values)


def _run(keys, jobs, monkeypatch):
    screen = FakeScreen(keys)
    monkeypatch.setattr(tui.curses, "LINES", 24)
    monkeypatch.setattr(tui.curses, "COLS", 120)
    with patch.object(tui.uxcore, "get_fleet_state", return_value={}), patch.object(
        tui.uxcore, "get_jobs", return_value=jobs
    ):
        tui._main(screen)
    return screen


def test_approve_key_calls_uxcore_for_selected_pending_job(monkeypatch):
    job = _job(status="pending_approval", pr_number=846)
    with patch.object(tui.uxcore, "approve_pr", return_value=Mock(message="approved")) as approve:
        _run(["2", "a", "q"], [job], monkeypatch)
    approve.assert_called_once_with(pr_number=846)


def test_kill_requires_confirmation(monkeypatch):
    job = _job(status="running", job_id="job-846")
    with patch.object(tui.uxcore, "kill_job") as kill:
        _run(["2", "k", "n", "q"], [job], monkeypatch)
    kill.assert_not_called()


def test_kill_key_calls_uxcore_after_confirmation(monkeypatch):
    job = _job(status="running", job_id="job-846")
    with patch.object(tui.uxcore, "kill_job", return_value=Mock(message="killed")) as kill:
        _run(["2", "k", "y", "q"], [job], monkeypatch)
    kill.assert_called_once_with(job_id="job-846")


def test_actions_are_noops_when_selected_job_is_not_eligible(monkeypatch):
    approve_job = _job(status="running", pr_number=846)
    kill_job = _job(status="completed", job_id="job-846")
    with patch.object(tui.uxcore, "approve_pr") as approve, patch.object(
        tui.uxcore, "kill_job"
    ) as kill:
        _run(["2", "a", "q"], [approve_job], monkeypatch)
        _run(["2", "k", "q"], [kill_job], monkeypatch)
    approve.assert_not_called()
    kill.assert_not_called()
