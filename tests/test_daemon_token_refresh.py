"""Tests for WatchDaemon's GitHub App token refresh responsibility."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ""))

from synlynk.daemon import SynlynkDaemon, WatchDaemon


def test_refresh_github_tokens_refreshes_each_provisioned_role(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))
    (apps_dir / "qa.json").write_text(json.dumps({
        "role": "qa", "app_id": "2", "installation_id": "20", "private_key_path": "qa.pem",
    }))

    refreshed = []
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(
        daemon_mod.github_app_auth, "refresh_installation_token",
        lambda role, app_config: refreshed.append(role),
    )

    WatchDaemon()._refresh_github_tokens()

    assert sorted(refreshed) == ["dev", "qa"]


def test_refresh_github_tokens_one_role_failure_does_not_block_others(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))
    (apps_dir / "qa.json").write_text(json.dumps({
        "role": "qa", "app_id": "2", "installation_id": "20", "private_key_path": "qa.pem",
    }))

    refreshed = []
    import synlynk.daemon as daemon_mod

    def fake_refresh(role, app_config):
        if role == "dev":
            raise RuntimeError("installation revoked")
        refreshed.append(role)

    monkeypatch.setattr(daemon_mod.github_app_auth, "refresh_installation_token", fake_refresh)

    WatchDaemon()._refresh_github_tokens()

    assert refreshed == ["qa"]
    assert "installation revoked" in capsys.readouterr().err


def test_refresh_github_tokens_skips_token_cache_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))
    (apps_dir / "dev.token.json").write_text(json.dumps({"token": "x", "expires_at": time.time() + 3600}))

    refreshed = []
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(
        daemon_mod.github_app_auth, "refresh_installation_token",
        lambda role, app_config: refreshed.append(role),
    )

    WatchDaemon()._refresh_github_tokens()

    assert refreshed == ["dev"]


def test_synlynk_daemon_run_loop_refreshes_tokens_on_interval(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))

    import synlynk.daemon as daemon_mod

    refresh_calls = []
    monkeypatch.setattr(
        daemon_mod,
        "_pkg",
        lambda name, default=None: {
            "load_config": lambda: {"watch_interval_seconds": 0},
        }.get(name, default),
    )
    monkeypatch.setattr(daemon_mod, "_reconcile_daemon_jobs", lambda: None)
    monkeypatch.setattr(daemon_mod, "_dispatch_ready_jobs", lambda max_parallel=4: None)

    def stop_after_n(self):
        refresh_calls.append(1)
        if len(refresh_calls) >= 2:
            raise KeyboardInterrupt()

    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_refresh_github_tokens", stop_after_n)

    import http.server as _http_server

    class FakeServer:
        allow_reuse_address = False

        def __init__(self, addr, handler):
            pass

        def serve_forever(self):
            return None

    monkeypatch.setattr(
        _http_server,
        "HTTPServer",
        FakeServer,
    )

    d = daemon_mod.SynlynkDaemon()
    d.token_refresh_interval_seconds = 0
    d._context_lock = __import__("threading").Lock()
    d._get_mtimes = lambda path: {}

    try:
        d._run_loop()
    except KeyboardInterrupt:
        pass

    assert len(refresh_calls) >= 2


def test_synlynk_daemon_start_calls_refresh_before_run_loop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.daemon as daemon_mod

    call_order = []
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_refresh_github_tokens", lambda self: call_order.append("refresh"))
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_run_loop", lambda self: call_order.append("run_loop"))
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_is_running", lambda self: False)
    monkeypatch.setattr(os, "fork", lambda: 0)
    monkeypatch.setattr(os, "setsid", lambda: None)
    monkeypatch.setattr(os, "dup2", lambda source, target: None)
    monkeypatch.setattr(os, "getpid", lambda: 12345)

    daemon_mod.SynlynkDaemon().start()

    assert call_order == ["refresh", "run_loop"]


def test_synlynk_daemon_start_refreshes_tokens_before_fork(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.daemon as daemon_mod

    call_order = []
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_refresh_github_tokens", lambda self: call_order.append("refresh"))
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_run_loop", lambda self: call_order.append("run_loop"))
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_is_running", lambda self: False)

    fork_calls = []

    def fake_fork():
        assert call_order == ["refresh"]
        fork_calls.append(1)
        return 0

    monkeypatch.setattr(os, "fork", fake_fork)
    monkeypatch.setattr(os, "setsid", lambda: None)
    monkeypatch.setattr(os, "dup2", lambda source, target: None)
    monkeypatch.setattr(os, "getpid", lambda: 12345)

    daemon_mod.SynlynkDaemon().start()

    assert call_order == ["refresh", "run_loop"]
    assert call_order.index("refresh") == 0
    assert len(fork_calls) == 2


def test_watch_daemon_start_refreshes_tokens_before_fork(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.daemon as daemon_mod

    call_order = []
    monkeypatch.setattr(daemon_mod.WatchDaemon, "_refresh_github_tokens", lambda self: call_order.append("refresh"))
    monkeypatch.setattr(daemon_mod.WatchDaemon, "_run_loop", lambda self: call_order.append("run_loop"))
    monkeypatch.setattr(daemon_mod.WatchDaemon, "_is_running", lambda self: False)
    monkeypatch.setattr(
        daemon_mod,
        "_pkg",
        lambda name, default=None: (lambda state: None) if name == "set_state" else default,
    )

    fork_calls = []

    def fake_fork():
        assert call_order == ["refresh"]
        fork_calls.append(1)
        return 0

    monkeypatch.setattr(os, "fork", fake_fork)
    monkeypatch.setattr(os, "setsid", lambda: None)
    monkeypatch.setattr(os, "dup2", lambda source, target: None)
    monkeypatch.setattr(os, "getpid", lambda: 12345)

    daemon_mod.WatchDaemon().start()

    assert call_order == ["refresh", "run_loop"]
    assert call_order.index("refresh") == 0
    assert len(fork_calls) == 2
