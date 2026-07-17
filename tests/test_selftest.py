import sys

import pytest

from synlynk import selftest


def test_selftest_registry_includes_paid_command_scenarios():
    assert {"dispatch", "exec", "schedule", "release"} <= set(selftest.SELFTEST_SCENARIOS)


def test_dispatch_scenario_calls_dispatch_agent(monkeypatch, tmp_path):
    calls = []

    def fake_dispatch(*args, **kwargs):
        calls.append((args, kwargs))
        return {"job_id": "job-selftest"}

    monkeypatch.setattr(selftest, "dispatch_agent", fake_dispatch)
    result = selftest.SELFTEST_SCENARIOS["dispatch"](selftest.ScenarioContext("dispatch", tmp_path))

    assert result.status == "passed"
    assert calls == [
        (
            ("claude", "selftest dispatch smoke"),
            {"story_id": None, "skip_preflight": True, "job_id": "selftest-dispatch"},
        )
    ]


def test_exec_scenario_calls_exec_command(monkeypatch, tmp_path):
    calls = []

    def fake_exec(cmd_args, force=False):
        calls.append((cmd_args, force))
        return 0

    monkeypatch.setattr(selftest, "exec_command", fake_exec)
    result = selftest.SELFTEST_SCENARIOS["exec"](selftest.ScenarioContext("exec", tmp_path))

    assert result.status == "passed"
    assert calls == [(["echo", "synlynk selftest"], False)]


def test_schedule_scenario_calls_cmd_schedule(monkeypatch, tmp_path):
    calls = []

    def fake_schedule(*, execute=False, max_stories=None):
        calls.append((execute, max_stories))

    monkeypatch.setattr(selftest, "cmd_schedule", fake_schedule)
    result = selftest.SELFTEST_SCENARIOS["schedule"](selftest.ScenarioContext("schedule", tmp_path))

    assert result.status == "passed"
    assert calls == [(False, 1)]


def test_release_scenario_is_always_skipped(tmp_path):
    result = selftest.SELFTEST_SCENARIOS["release"](selftest.ScenarioContext("release", tmp_path))

    assert result.status == "skipped"
    assert "irreversible" in result.detail


def test_cli_routes_selftest_command(monkeypatch, tmp_path):
    import synlynk.cli as cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["synlynk", "selftest"])
    monkeypatch.setattr(selftest, "cmd_selftest", lambda: 0)

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 0

