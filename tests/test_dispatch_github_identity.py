import json
import os
import subprocess
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
        dispatch_mod,
        "read_cached_installation_token",
        lambda role: f"token-for-{role}",
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
        dispatch_mod,
        "read_cached_installation_token",
        lambda role: f"token-for-{role}",
    )
    token = dispatch_mod._resolve_dispatch_gh_token("dev")  # dev.json does not exist
    assert token == "token-for-synlynk-bot"


def test_resolve_dispatch_gh_token_returns_none_when_cache_stale(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "2", "private_key_path": "dev.pem",
    }))

    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(dispatch_mod, "read_cached_installation_token", lambda role: None)
    assert dispatch_mod._resolve_dispatch_gh_token("dev") is None


def test_resolve_dispatch_gh_token_returns_none_when_nothing_provisioned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.dispatch as dispatch_mod

    assert dispatch_mod._resolve_dispatch_gh_token("dev") is None


def test_resolve_dispatch_gh_token_uses_main_repo_apps_from_worktree(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "tracked.txt").write_text("tracked\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repo, check=True)
    worktree = tmp_path / "worktree"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "test-worktree", str(worktree)],
        cwd=repo,
        check=True,
    )

    apps_dir = repo / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "qa.json").write_text(json.dumps({
        "role": "qa", "app_id": "1", "installation_id": "2", "private_key_path": "qa.pem",
    }))

    monkeypatch.chdir(worktree)
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod,
        "get_installation_token",
        lambda role, app_config: f"token-for-{role}",
    )
    assert dispatch_mod._resolve_dispatch_gh_token("qa") == "token-for-qa"


def test_resolve_github_apps_dir_prefers_cwd_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)

    import synlynk.dispatch as dispatch_mod

    def fail_git_lookup(*args, **kwargs):
        raise AssertionError("git-common-dir lookup should not run")

    monkeypatch.setattr(dispatch_mod.subprocess, "run", fail_git_lookup)
    assert dispatch_mod._resolve_github_apps_dir() == os.path.join(
        ".synlynk", "github_apps"
    )


def test_resolve_github_apps_dir_falls_back_to_cwd_path_when_unavailable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    import synlynk.dispatch as dispatch_mod

    def fail_git_lookup(*args, **kwargs):
        raise subprocess.CalledProcessError(128, args[0])

    monkeypatch.setattr(dispatch_mod.subprocess, "run", fail_git_lookup)
    assert dispatch_mod._resolve_github_apps_dir() == os.path.join(
        ".synlynk", "github_apps"
    )


def test_resolve_dispatch_gh_bot_login_uses_role_specific_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({"app_slug": "synlynk-synlynk-dev"}))

    import synlynk.dispatch as dispatch_mod

    assert dispatch_mod._resolve_dispatch_gh_bot_login("dev") == "synlynk-synlynk-dev[bot]"


def test_resolve_dispatch_gh_bot_login_returns_none_when_nothing_provisioned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.dispatch as dispatch_mod

    assert dispatch_mod._resolve_dispatch_gh_bot_login("dev") is None


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
    role=None,
    issue=None,
    gh_write_target_kind="issue",
    task_type=None,
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
        issue=issue,
        gh_write_target_kind=gh_write_target_kind,
        task_type=task_type,
        force_agent=True,
        role=role,
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


def test_dispatch_agent_uses_pr_target_kind(tmp_path, monkeypatch):
    _dispatch_mod, job, _captured_env = _dispatch_with_fake_popen(
        tmp_path,
        monkeypatch,
        requires_gh_write=True,
        token_resolver=lambda role: "minted-token-abc",
        role="qa",
        issue=1038,
        gh_write_target_kind="pr",
    )
    assert job["gh_write_target"] == "pr:1038"


def test_dispatch_agent_defaults_to_issue_target_kind(tmp_path, monkeypatch):
    dispatch_mod, job, _captured_env = _dispatch_with_fake_popen(
        tmp_path,
        monkeypatch,
        requires_gh_write=True,
        token_resolver=lambda role: "minted-token-abc",
        role="qa",
        issue=701,
    )
    assert job["gh_write_target"] == "issue:701"


def test_dispatch_agent_review_task_uses_review_posted_expectation(tmp_path, monkeypatch):
    _dispatch_mod, job, _captured_env = _dispatch_with_fake_popen(
        tmp_path,
        monkeypatch,
        requires_gh_write=True,
        token_resolver=lambda role: "minted-token-abc",
        role="qa",
        issue=1164,
        gh_write_target_kind="pr",
        task_type="review",
    )

    assert job["gh_write_target"] == "pr:1164"
    assert job["gh_write_expect"] == "review_posted"


def test_dispatch_agent_injects_gh_token_and_isolates_config_dir(tmp_path, monkeypatch):
    """#569: role token path also sets GH_CONFIG_DIR so host keyring is unused."""
    dispatch_mod, job, captured_env = _dispatch_with_fake_popen(
        tmp_path,
        monkeypatch,
        agent="grok",
        requires_gh_write=True,
        token_resolver=lambda role: "minted-token-abc",
        role_for_story="qa",
    )

    assert captured_env.get("GH_TOKEN") == "minted-token-abc"
    assert captured_env.get("GITHUB_TOKEN") == "minted-token-abc"
    assert "GH_CONFIG_DIR" in captured_env
    assert "gh-config" in captured_env["GH_CONFIG_DIR"].replace("\\", "/")


def test_dispatch_agent_fail_closed_when_requires_gh_write_token_missing(
    tmp_path, monkeypatch, capsys
):
    """#569 Epic B0: no App token → refuse dispatch (do not strip-and-proceed)."""
    monkeypatch.setenv("GH_TOKEN", "fake-personal-token-should-not-leak")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-personal-token-should-not-leak-2")
    monkeypatch.delenv("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH", raising=False)

    with pytest.raises(RuntimeError, match="requires a role-scoped GitHub App"):
        _dispatch_with_fake_popen(
            tmp_path,
            monkeypatch,
            agent="grok",
            requires_gh_write=True,
            token_resolver=lambda role: None,
            role_for_story="qa",
        )


def test_dispatch_agent_host_auth_escape_hatch_when_token_missing(
    tmp_path, monkeypatch, capsys
):
    """SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1 opts into host gh (warned)."""
    monkeypatch.setenv("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH", "1")
    monkeypatch.setenv("GH_TOKEN", "fake-personal-token-should-not-leak")

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
    # Ambient tokens still not injected into allowlisted env (host keyring via HOME).
    assert captured_env.get("GH_TOKEN") != "fake-personal-token-should-not-leak"
    assert "GH_TOKEN" not in captured_env or captured_env.get("GH_TOKEN") is None
    assert "SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH" in stderr or "host" in stderr.lower()


def test_build_subprocess_env_fail_closed_unit(tmp_path, monkeypatch):
    import synlynk.dispatch as dispatch_mod

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH", raising=False)
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: None)
    monkeypatch.setattr(dispatch_mod, "_role_for_story", lambda sid: "dev")

    with pytest.raises(RuntimeError, match="identity init"):
        dispatch_mod._build_subprocess_env("grok", {}, requires_gh_write=True, story_id="s1")


def test_dispatch_agent_does_not_inject_gh_token_by_default(tmp_path, monkeypatch):
    dispatch_mod, job, captured_env = _dispatch_with_fake_popen(
        tmp_path,
        monkeypatch,
        agent="codex",
        token_resolver=lambda role: (_ for _ in ()).throw(AssertionError("token resolver should not be called")),
    )

    assert job["agent"] == "codex"
    assert "GH_TOKEN" not in captured_env
