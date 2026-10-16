"""Tests for WatchDaemon's GitHub App token refresh responsibility."""

import json
import os
import subprocess
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ""))

from synlynk.daemon import SynlynkDaemon, WatchDaemon, _repo_common_dir
import synlynk.daemon as daemon_mod


def test_maybe_run_autonomy_pass_fires_on_interval_elapsed(monkeypatch):
    from synlynk.daemon import SynlynkDaemon
    from synlynk import daemon as daemon_mod

    d = SynlynkDaemon()
    d._last_autonomy_pass_at = 0.0
    d._last_dispatch_count = 0

    calls = {"n": 0}
    monkeypatch.setattr(daemon_mod, "_autonomy_pass", lambda conn=None: calls.__setitem__("n", calls["n"] + 1))
    monkeypatch.setattr(daemon_mod, "_autonomy_pass_interval_seconds", lambda: 0)

    d._maybe_run_autonomy_pass(launched=0)

    assert calls["n"] == 1
    assert d._last_dispatch_count == 0


def test_maybe_run_autonomy_pass_fires_on_idle_transition(monkeypatch):
    import time
    from synlynk.daemon import SynlynkDaemon
    from synlynk import daemon as daemon_mod

    d = SynlynkDaemon()
    d._last_autonomy_pass_at = time.time()
    d._last_dispatch_count = 2

    calls = {"n": 0}
    monkeypatch.setattr(daemon_mod, "_autonomy_pass", lambda conn=None: calls.__setitem__("n", calls["n"] + 1))
    monkeypatch.setattr(daemon_mod, "_autonomy_pass_interval_seconds", lambda: 999999)

    class _FakeConn:
        def execute(self, query, params=()):
            class _Row:
                def fetchone(self):
                    return (0,)
            return _Row()

        def close(self):
            pass

    monkeypatch.setattr(daemon_mod, "_pkg", lambda name: (lambda: _FakeConn()) if name == "_get_db" else None)

    d._maybe_run_autonomy_pass(launched=0)

    assert calls["n"] == 1
    assert d._last_dispatch_count == 0


def test_maybe_run_autonomy_pass_no_trigger_does_not_fire(monkeypatch):
    import time
    from synlynk.daemon import SynlynkDaemon
    from synlynk import daemon as daemon_mod

    d = SynlynkDaemon()
    d._last_autonomy_pass_at = time.time()
    d._last_dispatch_count = 0

    calls = {"n": 0}
    monkeypatch.setattr(daemon_mod, "_autonomy_pass", lambda conn=None: calls.__setitem__("n", calls["n"] + 1))
    monkeypatch.setattr(daemon_mod, "_autonomy_pass_interval_seconds", lambda: 999999)

    d._maybe_run_autonomy_pass(launched=0)

    assert calls["n"] == 0
    assert d._last_dispatch_count == 0


def test_maybe_run_autonomy_pass_swallows_exception(monkeypatch):
    from synlynk.daemon import SynlynkDaemon
    from synlynk import daemon as daemon_mod

    d = SynlynkDaemon()
    d._last_autonomy_pass_at = 0.0
    d._last_dispatch_count = 0

    def boom(conn=None):
        raise RuntimeError("autonomy pass exploded")

    monkeypatch.setattr(daemon_mod, "_autonomy_pass", boom)
    monkeypatch.setattr(daemon_mod, "_autonomy_pass_interval_seconds", lambda: 0)

    d._maybe_run_autonomy_pass(launched=0)


@pytest.fixture(autouse=True)
def _allow_temp_workspace_roots(monkeypatch, request):
    # Most tests exercise loop behavior from non-repository tmp_path dirs.
    # Model the explicit root provided by real daemon launchers there.
    if request.node.name not in {
        "test_repo_common_dir_strict_raises_while_default_falls_back",
        "test_daemon_paths_and_token_refresh_use_main_repo_from_worktree",
    }:
        monkeypatch.setattr(
            daemon_mod,
            "_repo_common_dir",
            lambda *, strict=False: os.path.abspath(os.getcwd()),
        )


def test_repo_common_dir_strict_raises_while_default_falls_back(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(
        daemon_mod.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("git unavailable")),
    )
    monkeypatch.setattr(daemon_mod.os, "getcwd", lambda: str(tmp_path))

    assert _repo_common_dir() == str(tmp_path)
    import pytest
    with pytest.raises(RuntimeError, match="git unavailable"):
        _repo_common_dir(strict=True)


def test_watch_daemon_start_refuses_disposable_workspace_root(tmp_path, monkeypatch):
    import pytest
    import synlynk.daemon as daemon_mod

    disposable = tmp_path / "worktrees" / "job-test"
    disposable.mkdir(parents=True)
    daemon = WatchDaemon.__new__(WatchDaemon)
    daemon.workspace_root = str(disposable)

    with pytest.raises(RuntimeError, match="disposable worktree as its workspace root"):
        daemon.start()


def test_refresh_github_tokens_uses_bound_workspace_root(tmp_path, monkeypatch):
    daemon = WatchDaemon()
    bound_root = daemon.workspace_root
    helper_calls = []
    resolved_roots = []
    monkeypatch.setattr(daemon_mod, "_repo_common_dir", lambda *args, **kwargs: helper_calls.append("repo"))
    monkeypatch.setattr(daemon_mod.os, "getcwd", lambda: (_ for _ in ()).throw(AssertionError("cwd re-read")))
    monkeypatch.setattr(daemon_mod.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("git re-run")))
    monkeypatch.setattr(daemon_mod, "resolve_github_apps_dir", lambda root: resolved_roots.append(root) or tmp_path / "absent")

    daemon._refresh_github_tokens()

    assert helper_calls == []
    assert resolved_roots == [bound_root]


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


def test_repo_common_dir_reports_deleted_cwd_clearly(monkeypatch):
    monkeypatch.setattr(
        daemon_mod.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("git unavailable")),
    )
    monkeypatch.setattr(
        daemon_mod.os,
        "getcwd",
        lambda: (_ for _ in ()).throw(FileNotFoundError("deleted cwd")),
    )

    with pytest.raises(RuntimeError, match="cwd no longer exists; cannot resolve repo root"):
        _repo_common_dir()


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


def test_daemonize_via_reexec_pins_workspace_cwd(tmp_path, monkeypatch):
    import synlynk.daemon as daemon_mod

    monkeypatch.chdir(tmp_path)
    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["kwargs"] = kwargs

    monkeypatch.setattr(daemon_mod.subprocess, "Popen", FakePopen)
    logfile = str(tmp_path / "test.log")
    daemon_mod._daemonize_via_reexec(
        "synlynk.daemon._watch_daemon_child_main", logfile, str(tmp_path)
    )

    assert captured["kwargs"]["cwd"] == str(tmp_path)
    assert captured["kwargs"]["env"]["SYNLYNK_DAEMON_WORKSPACE_ROOT"] == str(tmp_path)


def test_daemonize_via_reexec_repins_disposable_worktree_cwd(tmp_path, monkeypatch):
    """gh:#2261: never detach a child with a dispatch worktree as its cwd."""
    import synlynk.daemon as daemon_mod

    repo_root = tmp_path / "repo"
    disposable = tmp_path / "worktrees" / "job-dead"
    repo_root.mkdir()
    (repo_root / ".synlynk").mkdir()
    disposable.mkdir(parents=True)
    monkeypatch.chdir(disposable)
    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["kwargs"] = kwargs

    monkeypatch.setattr(daemon_mod.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(
        daemon_mod, "_repo_common_dir", lambda *, strict=False: str(repo_root)
    )
    logfile = str(repo_root / ".synlynk" / "daemon.log")
    daemon_mod._daemonize_via_reexec(
        "synlynk.daemon._synlynk_daemon_child_main", logfile, str(disposable)
    )

    assert captured["kwargs"]["cwd"] == str(repo_root)
    assert captured["kwargs"]["env"]["SYNLYNK_DAEMON_WORKSPACE_ROOT"] == str(repo_root)
    assert "worktrees" not in captured["kwargs"]["cwd"]


def test_watch_daemon_start_spawns_detached_child_and_returns_immediately(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(daemon_mod.WatchDaemon, "_is_running", lambda self: False)
    monkeypatch.setattr(daemon_mod.WatchDaemon, "_await_child_pidfile", lambda self, timeout=2.0: None)
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
    assert captured["kwargs"]["cwd"] == daemon.workspace_root
    assert captured["kwargs"]["env"]["_SYNLYNK_DAEMON_CHILD"] == "1"
    assert (
        captured["kwargs"]["env"]["SYNLYNK_DAEMON_WORKSPACE_ROOT"]
        == daemon.workspace_root
    )


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
    assert (tmp_path / ".synlynk" / "watch.pid.lock").exists()


def test_watch_daemon_child_main_pins_repo_root_before_constructor(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    launch_dir = tmp_path / "launch"
    repo_root.mkdir()
    (repo_root / ".synlynk").mkdir()
    launch_dir.mkdir()
    monkeypatch.chdir(launch_dir)
    monkeypatch.delenv("SYNLYNK_DAEMON_WORKSPACE_ROOT", raising=False)
    monkeypatch.setattr(daemon_mod, "_repo_common_dir", lambda *, strict=False: str(repo_root))
    monkeypatch.setattr(daemon_mod.WatchDaemon, "_run_loop", lambda self: None)
    monkeypatch.setattr(daemon_mod, "_pkg", lambda name, default=None:
                        (lambda state: None) if name == "set_state" else default)

    daemon_mod._watch_daemon_child_main()

    assert os.getcwd() == str(repo_root)
    assert (repo_root / ".synlynk" / "watch.pid").exists()


def test_synlynk_daemon_start_spawns_detached_child_and_returns_immediately(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_is_running", lambda self: False)
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_await_child_pidfile", lambda self, timeout=2.0: None)
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
    assert captured["kwargs"]["cwd"] == daemon.workspace_root
    assert (
        captured["kwargs"]["env"]["SYNLYNK_DAEMON_WORKSPACE_ROOT"]
        == daemon.workspace_root
    )


def test_synlynk_daemon_child_main_writes_pidfile_and_start_file_then_runs_loop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    import synlynk.daemon as daemon_mod
    call_order = []
    monkeypatch.setattr(
        daemon_mod.SynlynkDaemon,
        "_reconcile_orphans_on_startup",
        lambda self: call_order.append("reconcile_orphans"),
    )
    monkeypatch.setattr(daemon_mod.SynlynkDaemon, "_run_loop", lambda self: call_order.append("run_loop"))
    monkeypatch.setattr(os, "getpid", lambda: 54321)
    daemon_mod._synlynk_daemon_child_main()
    assert (tmp_path / ".synlynk" / "daemon.pid").read_text() == "54321"
    assert (tmp_path / ".synlynk" / "daemon.start").exists()
    assert call_order == ["reconcile_orphans", "run_loop"]
    assert (tmp_path / ".synlynk" / "daemon.pid.lock").exists()


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


def test_refresh_github_tokens_uses_product_scoped_apps_dir(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".synlynk").mkdir()
    (repo / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": "product-1746"}))
    _git_run(["init"], repo)

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(repo)

    from synlynk.product_store import resolve_github_apps_dir

    product_apps_dir = resolve_github_apps_dir(repo)
    product_apps_dir.mkdir(parents=True)
    (product_apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10",
    }))
    repo_apps_dir = repo / ".synlynk" / "github_apps"

    import synlynk.daemon as daemon_mod

    def fake_refresh(role, app_config, apps_dir=None):
        token_path = os.path.join(apps_dir, f"{role}.token.json")
        with open(token_path, "w") as fh:
            json.dump({"token": "refreshed"}, fh)

    monkeypatch.setattr(daemon_mod.github_app_auth, "refresh_installation_token", fake_refresh)

    WatchDaemon()._refresh_github_tokens()

    assert (product_apps_dir / "dev.token.json").exists()
    assert not (repo_apps_dir / "dev.token.json").exists()
