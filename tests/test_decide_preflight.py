from types import SimpleNamespace
from copy import deepcopy

import pytest


CORE_HARNESSES = ("claude", "codex", "agy", "grok")


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


def _isolated_baseline(team, agent, tmp_path, monkeypatch):
    baselines = deepcopy(team.HARNESS_CAPABILITY_BASELINES)
    auth_file = tmp_path / f"{agent}-auth-state"
    auth_file.write_text("authenticated\n")
    cfg = baselines[agent]
    cfg["panel_auth_check"] = {
        "probe": ["fake-auth", agent],
        "required_paths": [str(auth_file)],
        "unauthenticated_markers": ["unauthenticated"],
    }
    baselines[agent] = cfg
    monkeypatch.setattr(team, "HARNESS_CAPABILITY_BASELINES", baselines)
    return cfg


@pytest.mark.parametrize("agent", CORE_HARNESSES)
def test_core_harness_panel_preflight_and_invocation_receipt(agent, tmp_path, monkeypatch):
    import synlynk.team as team

    cfg = _isolated_baseline(team, agent, tmp_path, monkeypatch)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:1] == ["fake-auth"]:
            return _result("authenticated")
        if cmd == [cfg["cli"], "--version"]:
            return _result(f"{agent} 1.2.3")
        return _result("panel answer")

    monkeypatch.setattr(team.subprocess, "run", fake_run)
    assert team._run_agent_sync(agent, "panel prompt") == "panel answer"
    receipt = team._LAST_PANEL_RUNS[agent]
    assert receipt["ok"] is True
    assert receipt["coverage"] == "invocation"
    assert receipt["version"] == f"{agent} 1.2.3"
    assert calls[:2] == [["fake-auth", agent], [cfg["cli"], "--version"]]


@pytest.mark.parametrize("agent", CORE_HARNESSES)
def test_core_harness_panel_preflight_rejects_missing_required_auth_path(agent, tmp_path, monkeypatch):
    import synlynk.team as team

    cfg = _isolated_baseline(team, agent, tmp_path, monkeypatch)
    missing = tmp_path / f"{agent}-auth-state"
    missing.unlink()
    calls = []
    monkeypatch.setattr(
        team.subprocess,
        "run",
        lambda cmd, **kwargs: calls.append(cmd) or _result("should not run"),
    )

    assert team._run_agent_sync(agent, "panel prompt") == ""
    failure = team._LAST_PANEL_RUNS[agent]
    assert failure["reason"] == "required auth state is missing"
    assert failure["missing_paths"] == [str(missing)]
    assert failure["coverage"] == "probe-only"
    assert calls == []


@pytest.mark.parametrize("agent", CORE_HARNESSES)
def test_core_harness_panel_preflight_preserves_execution_failure_identity(agent, tmp_path, monkeypatch):
    import synlynk.team as team

    cfg = _isolated_baseline(team, agent, tmp_path, monkeypatch)
    responses = iter([
        _result("authenticated"),
        _result(f"{agent} 1.2.3"),
        _result("", "execution failed", 9),
    ])
    monkeypatch.setattr(team.subprocess, "run", lambda *args, **kwargs: next(responses))

    assert team._run_agent_sync(agent, "panel prompt") == ""
    failure = team._LAST_PANEL_RUNS[agent]
    assert failure["returncode"] == 9
    assert failure["stderr"] == "execution failed"
    assert failure["coverage"] == "invocation"
    assert failure["identity"]["agent"] == agent
    assert failure["identity"]["executable"]


@pytest.mark.parametrize("agent", CORE_HARNESSES)
def test_core_harness_panel_preflight_rejects_auth_failure(agent, tmp_path, monkeypatch):
    import synlynk.team as team

    _isolated_baseline(team, agent, tmp_path, monkeypatch)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _result("unauthenticated", "", 0)

    monkeypatch.setattr(team.subprocess, "run", fake_run)
    assert team._run_agent_sync(agent, "panel prompt") == ""
    failure = team._LAST_PANEL_RUNS[agent]
    assert failure["reason"] == "auth probe reported an unavailable or unauthenticated harness"
    assert failure["matched_marker"] == "unauthenticated"
    assert failure["coverage"] == "probe-only"
    assert calls == [["fake-auth", agent]]
