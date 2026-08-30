"""Tests for WatchDaemon's GitHub App token refresh responsibility."""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ""))

from synlynk.daemon import SynlynkDaemon, WatchDaemon, _repo_common_dir


def _git_run(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_repo_common_dir_is_shared_by_main_repo_and_worktree(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_run(["init"], repo)
    _git_run(["config", "user.email", "test@example.com"], repo)
    _git_run(["config", "user.name", "Test"], repo)
    (repo / "tracked.txt").write_text("tracked\n")
    _git_run(["add", "tracked.txt"], repo)
    _git_run(["commit", "-m", "initial"], repo)
    worktree = tmp_path / "worktree"
    _git_run(["worktree", "add", str(worktree)], repo)

    monkeypatch.chdir(repo)
    main_root = _repo_common_dir()
    monkeypatch.chdir(worktree)
    assert _repo_common_dir() == main_root == str(repo)


def test_repo_common_dir_falls_back_to_cwd_outside_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _repo_common_dir() == str(tmp_path)


def test_daemon_paths_and_token_refresh_use_main_repo_from_worktree(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_run(["init"], repo)
    _git_run(["config", "user.email", "test@example.com"], repo)
    _git_run(["config", "user.name", "Test"], repo)
    (repo / "tracked.txt").write_text("tracked\n")
    _git_run(["add", "tracked.txt"], repo)
    _git_run(["commit", "-m", "initial"], repo)
    worktree = tmp_path / "worktree"
    _git_run(["worktree", "add", str(worktree)], repo)

    apps_dir = repo / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({"installation_id": "10"}))
    refreshed = []
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(
        daemon_mod.github_app_auth,
        "refresh_installation_token",
        lambda role, app_config, apps_dir=None: refreshed.append(role),
    )
    monkeypatch.chdir(worktree)

    watch = WatchDaemon()
    daemon = SynlynkDaemon()
    assert watch.pidfile == str(repo / ".synlynk" / "watch.pid")
    assert watch.logfile == str(repo / ".synlynk" / "watch.log")
    assert daemon.pidfile == str(repo / ".synlynk" / "daemon.pid")
    assert daemon.logfile == str(repo / ".synlynk" / "daemon.log")
    watch._refresh_github_tokens()
    assert refreshed == ["dev"]


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
        lambda role, app_config, apps_dir=None: refreshed.append(role),
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

    def fake_refresh(role, app_config, apps_dir=None):
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
        lambda role, app_config, apps_dir=None: refreshed.append(role),
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


def test_synlynk_daemon_run_loop_survives_job_tick_exception(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    import synlynk.daemon as daemon_mod
    import http.server as _http_server

    monkeypatch.setattr(
        daemon_mod,
        "_pkg",
        lambda name, default=None: {
            "load_config": lambda: {"watch_interval_seconds": 0},
        }.get(name, default),
    )

    reconcile_calls = []
    dispatch_calls = []

    def fail_once():
        reconcile_calls.append(1)
        if len(reconcile_calls) == 1:
            raise RuntimeError("transient reconciliation failure")

    monkeypatch.setattr(daemon_mod, "_reconcile_daemon_jobs", fail_once)
    monkeypatch.setattr(
        daemon_mod,
        "_dispatch_ready_jobs",
        lambda max_parallel=4: dispatch_calls.append(max_parallel),
    )

    refresh_calls = []

    def stop_after_two_ticks(self):
        refresh_calls.append(1)
        if len(refresh_calls) >= 3:
            raise KeyboardInterrupt()

    monkeypatch.setattr(
        daemon_mod.SynlynkDaemon,
        "_refresh_github_tokens",
        stop_after_two_ticks,
    )

    class FakeServer:
        allow_reuse_address = False

        def __init__(self, addr, handler):
            pass

        def serve_forever(self):
            return None

    monkeypatch.setattr(_http_server, "HTTPServer", FakeServer)

    daemon = daemon_mod.SynlynkDaemon()
    daemon.token_refresh_interval_seconds = 0
    daemon._context_lock = __import__("threading").Lock()
    daemon._get_mtimes = lambda path: {}

    try:
        daemon._run_loop()
    except KeyboardInterrupt:
        pass

    assert len(reconcile_calls) >= 2
    assert dispatch_calls == [4]
    assert "transient reconciliation failure" in capsys.readouterr().err


def test_watch_daemon_run_loop_refreshes_tokens_before_first_sleep(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    import synlynk.daemon as daemon_mod

    refresh_calls = []
    monkeypatch.setattr(
        daemon_mod,
        "_pkg",
        lambda name, default=None: {"load_config": lambda: {"watch_interval_seconds": 30}}.get(
            name, default
        ),
    )

    monkeypatch.setattr(
        daemon_mod.WatchDaemon,
        "_refresh_github_tokens",
        lambda self: refresh_calls.append(1),
    )

    def stop_sleep(_seconds):
        raise KeyboardInterrupt()

    monkeypatch.setattr(time, "sleep", stop_sleep)

    daemon = WatchDaemon()
    try:
        daemon._run_loop()
    except KeyboardInterrupt:
        pass

    assert refresh_calls == [1]


def test_synlynk_daemon_run_loop_refreshes_tokens_before_first_sleep(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    import synlynk.daemon as daemon_mod
    import http.server as _http_server

    refresh_calls = []
    monkeypatch.setattr(
        daemon_mod,
        "_pkg",
        lambda name, default=None: {
            "load_config": lambda: {"watch_interval_seconds": 30},
        }.get(name, default),
    )
    monkeypatch.setattr(daemon_mod, "_reconcile_daemon_jobs", lambda: None)
    monkeypatch.setattr(daemon_mod, "_dispatch_ready_jobs", lambda max_parallel=4: None)

    def stop_sleep(_seconds):
        raise KeyboardInterrupt()

    monkeypatch.setattr(time, "sleep", stop_sleep)

    class FakeServer:
        allow_reuse_address = False

        def __init__(self, addr, handler):
            pass

        def serve_forever(self):
            return None

    monkeypatch.setattr(_http_server, "HTTPServer", FakeServer)

    monkeypatch.setattr(
        daemon_mod.SynlynkDaemon,
        "_refresh_github_tokens",
        lambda self: refresh_calls.append(1),
    )

    daemon = daemon_mod.SynlynkDaemon()
    daemon._get_mtimes = lambda path: {}
    try:
        daemon._run_loop()
    except KeyboardInterrupt:
        pass

    assert refresh_calls == [1]


def test_daemonize_via_reexec_spawns_detached_subprocess(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk.daemon as daemon_mod

    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(daemon_mod.subprocess, "Popen", FakePopen)
    logfile = str(tmp_path / "test.log")
    daemon_mod._daemonize_via_reexec("synlynk.daemon._watch_daemon_child_main", logfile)

    assert captured["args"] == [
        daemon_mod.sys.executable, "-c",
        "from synlynk.daemon import _watch_daemon_child_main; _watch_daemon_child_main()",
    ]
    assert captured["kwargs"]["start_new_session"] is True
    assert captured["kwargs"]["close_fds"] is True
    assert captured["kwargs"]["stdin"] == daemon_mod.subprocess.DEVNULL
    assert captured["kwargs"]["stderr"] == daemon_mod.subprocess.STDOUT
    assert captured["kwargs"]["env"]["_SYNLYNK_DAEMON_CHILD"] == "1"
    assert os.path.exists(logfile)


def test_watch_daemon_start_spawns_detached_child_and_returns_immediately(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(daemon_mod.WatchDaemon, "_is_running", lambda self: False)
    daemon = daemon_mod.WatchDaemon()
    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(daemon_mod.subprocess, "Popen", FakePopen)
    daemon.start()
    assert captured["args"] == [
        daemon_mod.sys.executable, "-c",
        "from synlynk.daemon import _watch_daemon_child_main; _watch_daemon_child_main()",
    ]


def test_watch_daemon_child_main_writes_pidfile_then_runs_loop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    import synlynk.daemon as daemon_mod
    call_order = []
    monkeypatch.setattr(daemon_mod, "_pkg", lambda name, default=None:
                        (lambda state: call_order.append(f"set_state:{state}"))
                        if name == "set_state" else default)
    monkeypatch.setattr(daemon_mod.WatchDaemon, "_run_loop", lambda self: call_order.append("run_loop"))
    monkeypatch.setattr(os, "getpid", lambda: 12345)
    daemon_mod._watch_daemon_child_main()
    assert (tmp_path / ".synlynk" / "watch.pid").read_text() == "12345"
    assert call_order == ["set_state:watching", "run_loop"]


def test_synlynk_daemon_start_spawns_detached_child_and_returns_immediately(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_is_running", lambda self: False)
    daemon = daemon_mod.SynlynkDaemon()
    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(daemon_mod.subprocess, "Popen", FakePopen)
    daemon.start()
    assert captured["args"] == [
        daemon_mod.sys.executable, "-c",
        "from synlynk.daemon import _synlynk_daemon_child_main; _synlynk_daemon_child_main()",
    ]


def test_synlynk_daemon_child_main_writes_pidfile_and_start_file_then_runs_loop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    import synlynk.daemon as daemon_mod
    call_order = []
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_run_loop", lambda self: call_order.append("run_loop"))
    monkeypatch.setattr(os, "getpid", lambda: 54321)
    daemon_mod._synlynk_daemon_child_main()
    assert (tmp_path / ".synlynk" / "daemon.pid").read_text() == "54321"
    assert (tmp_path / ".synlynk" / "daemon.start").exists()
    assert call_order == ["run_loop"]


def test_refresh_github_tokens_passes_apps_dir_through_to_refresh_call(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))
    calls = []
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(daemon_mod.github_app_auth, "refresh_installation_token",
                        lambda role, app_config, apps_dir=None: calls.append((role, apps_dir)))
    WatchDaemon()._refresh_github_tokens()
    assert calls == [("dev", str(apps_dir))]
