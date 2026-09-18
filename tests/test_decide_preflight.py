from types import SimpleNamespace

import pytest


def _result(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_run_agent_sync_fails_closed_on_auth_probe(monkeypatch):
    import synlynk.team as team

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return _result(
            '{"loggedIn": false, "authMethod": "none"}',
            "",
            0,
        )

    monkeypatch.setattr(team.subprocess, "run", fake_run)
    assert team._run_agent_sync("claude", "panel prompt") == ""
    failure = team._LAST_PANEL_RUNS["claude"]
    assert failure["ok"] is False
    assert failure["returncode"] == 0
    assert "loggedin" in failure["matched_marker"]
    assert len(calls) == 1


def test_run_agent_sync_preserves_stderr_and_exit_code(monkeypatch):
    import synlynk.team as team

    responses = iter([
        _result('{"loggedIn": true, "authMethod": "oauth"}'),
        _result("claude 2.1.274"),
        _result("", "oauth refresh failed", 7),
    ])
    monkeypatch.setattr(team.subprocess, "run", lambda *args, **kwargs: next(responses))

    assert team._run_agent_sync("claude", "panel prompt") == ""
    failure = team._LAST_PANEL_RUNS["claude"]
    assert failure["returncode"] == 7
    assert failure["stderr"] == "oauth refresh failed"
    assert failure["identity"]["agent"] == "claude"
    assert failure["identity"]["cwd"]


def test_run_agent_sync_records_model_and_version(monkeypatch):
    import synlynk.team as team

    calls = []
    responses = iter([
        _result('{"loggedIn": true, "authMethod": "oauth"}'),
        _result("claude 2.1.274"),
        _result("panel answer"),
    ])

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return next(responses)

    monkeypatch.setattr(team.subprocess, "run", fake_run)
    assert team._run_agent_sync("claude", "panel prompt", model="claude-sonnet-4-6") == "panel answer"
    run = team._LAST_PANEL_RUNS["claude"]
    assert run["model"] == "claude-sonnet-4-6"
    assert run["version"] == "claude 2.1.274"
    assert calls[-1][-2:] == ["--model", "claude-sonnet-4-6"]


def test_decide_refuses_partial_panel_before_synthesis(project_dir, monkeypatch, capsys):
    import synlynk

    calls = []

    def fake_run(agent, prompt, **kwargs):
        calls.append(agent)
        return "Claude advice" if agent == "claude" else ""

    monkeypatch.setattr(synlynk, "_run_agent_sync", fake_run)
    with pytest.raises(SystemExit) as exc:
        synlynk.cmd_decide("Harness parity", panel=["claude", "agy"])

    assert exc.value.code == 1
    assert calls == ["claude", "agy"]
    assert "refusing to synthesize" in capsys.readouterr().out
