import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_resolve_dispatch_gh_token_uses_role_specific_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "qa.json").write_text(json.dumps({
        "role": "qa", "app_id": "1", "installation_id": "2", "private_key_path": "qa.pem",
    }))

    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod, "get_installation_token",
        lambda role, app_config: f"token-for-{role}",
    )
    token = dispatch_mod._resolve_dispatch_gh_token("qa")
    assert token == "token-for-qa"


def test_resolve_dispatch_gh_token_falls_back_to_synlynk_bot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "synlynk-bot.json").write_text(json.dumps({
        "role": "synlynk-bot", "app_id": "9", "installation_id": "8", "private_key_path": "bot.pem",
    }))

    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod, "get_installation_token",
        lambda role, app_config: f"token-for-{role}",
    )
    token = dispatch_mod._resolve_dispatch_gh_token("dev")  # dev.json does not exist
    assert token == "token-for-synlynk-bot"


def test_resolve_dispatch_gh_token_returns_none_when_nothing_provisioned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.dispatch as dispatch_mod

    assert dispatch_mod._resolve_dispatch_gh_token("dev") is None


def _dispatch_with_fake_popen(
    tmp_path,
    monkeypatch,
    *,
    agent="codex",
    story_id="story-1",
    task="do a thing",
    requires_gh_write=False,
    token_resolver=None,
    role_for_story=None,
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agents").mkdir(parents=True, exist_ok=True)

    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    captured_env = {}

    class FakeProc:
        pid = 12345

    def fake_popen(cmd, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        return FakeProc()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_load_jobs", lambda: [])
    monkeypatch.setattr(sl, "_save_jobs", lambda jobs: None)
    monkeypatch.setattr(sl, "_count_dispatch_rework", lambda _story_id: 0)
    monkeypatch.setattr(sl, "_best_agent_for_story", lambda _story_id: None)
    monkeypatch.setattr(sl, "_get_db", lambda: None)
    monkeypatch.setattr(
        sl,
        "_preflight_dispatch",
        lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {
            "passed": True,
            "sentinel": None,
            "reason": None,
        },
    )
    monkeypatch.setattr(
        sl,
        "_load_agent_profile",
        lambda _agent: {},
    )
    monkeypatch.setattr(sl, "_probe_model_version", lambda _agent, _cli: "model")
    monkeypatch.setattr(sl, "_warn_context_size", lambda _context: None)
    monkeypatch.setattr(sl, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(sl, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(
        sl,
        "load_config",
        lambda: {
            "fenced_commands": [],
            "dispatch_mode": "daily-grind",
            "roles": {
                "claude": ["architect"],
                "agy": ["builder"],
                "codex": ["builder"],
                "grok": ["builder"],
            },
        },
    )
    monkeypatch.setattr(
        dispatch_mod,
        "_create_job_worktree",
        lambda job_id, agent, base=None: {
            "path": str(tmp_path),
            "branch": "branch",
            "base_branch": "main",
            "base_sha": "0" * 40,
        },
    )
    monkeypatch.setattr(
        dispatch_mod,
        "_job_worktree_details",
        lambda job_id, agent: (str(tmp_path), "branch"),
    )
    if token_resolver is not None:
        monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", token_resolver)
    if role_for_story is not None:
        monkeypatch.setattr(dispatch_mod, "_role_for_story", lambda _story_id: role_for_story)

    job = dispatch_mod.dispatch_agent(
        agent,
        task,
        story_id=story_id,
        context_mode="none",
        skip_preflight=True,
        job_id="job-test",
        requires_gh_write=requires_gh_write,
        force_agent=True,
    )
    return dispatch_mod, job, captured_env


def test_dispatch_agent_injects_gh_token_when_requires_gh_write(tmp_path, monkeypatch):
    dispatch_mod, job, captured_env = _dispatch_with_fake_popen(
        tmp_path,
        monkeypatch,
        agent="grok",
        requires_gh_write=True,
        token_resolver=lambda role: "minted-token-abc",
        role_for_story="qa",
    )

    assert job["agent"] == "grok"
    assert captured_env.get("GH_TOKEN") == "minted-token-abc"


def test_dispatch_agent_strips_inherited_gh_tokens_when_requires_gh_write_token_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GH_TOKEN", "fake-personal-token-should-not-leak")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-personal-token-should-not-leak-2")

    dispatch_mod, job, captured_env = _dispatch_with_fake_popen(
        tmp_path,
        monkeypatch,
        agent="grok",
        requires_gh_write=True,
        token_resolver=lambda role: None,
        role_for_story="qa",
    )

    stderr = capsys.readouterr().err

    assert job["agent"] == "grok"
    assert "GH_TOKEN" not in captured_env
    assert "GITHUB_TOKEN" not in captured_env
    assert "no role-scoped GitHub token available" in stderr


def test_dispatch_agent_does_not_inject_gh_token_by_default(tmp_path, monkeypatch):
    dispatch_mod, job, captured_env = _dispatch_with_fake_popen(
        tmp_path,
        monkeypatch,
        agent="codex",
        token_resolver=lambda role: (_ for _ in ()).throw(AssertionError("token resolver should not be called")),
    )

    assert job["agent"] == "codex"
    assert "GH_TOKEN" not in captured_env
