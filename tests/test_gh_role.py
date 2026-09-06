import subprocess

import pytest


def test_cmd_gh_runs_gh_with_role_token(monkeypatch):
    import synlynk.gh_role as gh_role

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env") or {}
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(gh_role.subprocess, "run", fake_run)
    monkeypatch.setattr(gh_role, "_resolve_dispatch_gh_token", lambda role: "ghs_qa" if role == "qa" else None)
    monkeypatch.setattr(gh_role, "_isolated_gh_config_dir", lambda: "/tmp/synlynk-gh-config-test")
    monkeypatch.delenv("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH", raising=False)

    rc = gh_role.cmd_gh("qa", ["pr", "view", "1452"])
    assert rc == 0
    assert captured["cmd"] == ["gh", "pr", "view", "1452"]
    assert captured["env"].get("GH_TOKEN") == "ghs_qa"
    assert captured["env"].get("GITHUB_TOKEN") == "ghs_qa"
    assert captured["env"].get("GH_CONFIG_DIR") == "/tmp/synlynk-gh-config-test"


def test_cmd_gh_strips_leading_double_dash(monkeypatch):
    import synlynk.gh_role as gh_role

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(gh_role.subprocess, "run", fake_run)
    monkeypatch.setattr(gh_role, "_resolve_dispatch_gh_token", lambda role: "ghs_qa")
    monkeypatch.setattr(gh_role, "_isolated_gh_config_dir", lambda: "/tmp/x")

    rc = gh_role.cmd_gh("qa", ["--", "pr", "create", "--title", "t"])
    assert rc == 0
    assert captured["cmd"] == ["gh", "pr", "create", "--title", "t"]


def test_cmd_gh_fails_closed_without_token(monkeypatch):
    import synlynk.gh_role as gh_role

    monkeypatch.setattr(gh_role, "_resolve_dispatch_gh_token", lambda role: None)
    monkeypatch.delenv("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH", raising=False)

    def boom(*_a, **_k):
        raise AssertionError("gh must not run without a role token")

    monkeypatch.setattr(gh_role.subprocess, "run", boom)
    with pytest.raises(SystemExit) as exc:
        gh_role.cmd_gh("qa", ["pr", "view", "1"])
    assert exc.value.code == 1


def test_cmd_gh_rejects_unknown_role():
    import synlynk.gh_role as gh_role

    with pytest.raises(SystemExit) as exc:
        gh_role.cmd_gh("not-a-role", ["pr", "view", "1"])
    assert exc.value.code == 1
