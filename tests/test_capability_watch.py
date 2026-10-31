import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import synlynk.capability_watch as _capability_watch_mod
from synlynk.capability_watch import (
    capability_sweep_status,
    is_capability_sweep_overdue,
    is_model_catalog_stale,
    is_probe_stale,
    is_smoke_test_stale,
    mark_probe_run,
    mark_smoke_test_run,
    maybe_trigger_staleness_checks,
)
from synlynk.db import _migrate_db

_REAL_SPAWN_STALENESS_CHECK_THREAD = _capability_watch_mod.spawn_staleness_check_thread


def _utc_ago(seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds))


def _insert_discovered_model(conn, discovered_at: str) -> None:
    conn.execute(
        "INSERT INTO harness_models ("
        "harness_name, model_id, provider, first_seen_at, last_seen_at, "
        "status, discovery_source, discovered_at"
        ") VALUES ('grok', 'grok-4', 'native', ?, ?, 'active', 'cli:grok', ?)",
        (discovered_at, discovered_at, discovered_at),
    )
    conn.commit()


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "state.db"
    connection = sqlite3.connect(str(db_path))
    _migrate_db(connection)
    return connection


def test_capability_watch_table_exists(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_watch)")}
    assert cols == {
        "id", "last_probe_at", "last_green_probe_at", "last_smoke_test_at",
        "last_green_smoke_at", "last_sweep_at", "sweep_job_count",
        "last_quota_calibration_at",
    }


def test_capability_watch_singleton_row_seeded(conn):
    row = conn.execute("SELECT id FROM capability_watch WHERE id = 1").fetchone()
    assert row is not None


def test_gh_write_capability_table_exists(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(gh_write_capability)")}
    assert cols == {"harness", "mode", "action", "status", "checked_at"}
    pk_cols = {row[1] for row in conn.execute("PRAGMA table_info(gh_write_capability)") if row[5] > 0}
    assert pk_cols == {"harness", "mode", "action"}


def test_capability_incidents_table_exists(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_incidents)")}
    assert cols == {
        "id", "harness", "failing_path", "classification", "evidence", "detected_at",
    }


def test_is_probe_stale_true_when_never_run(conn):
    assert is_probe_stale(conn, threshold_hours=24) is True


def test_is_probe_stale_false_when_recent(conn):
    mark_probe_run(conn, green=True)
    assert is_probe_stale(conn, threshold_hours=24) is False


def test_is_probe_stale_true_when_old(conn):
    old_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 25 * 3600))
    conn.execute("UPDATE capability_watch SET last_probe_at = ? WHERE id = 1", (old_ts,))
    conn.commit()
    assert is_probe_stale(conn, threshold_hours=24) is True


def test_is_smoke_test_stale_true_when_never_run(conn):
    assert is_smoke_test_stale(conn, threshold_days=7) is True


def test_capability_sweep_overdue_when_never_run(conn):
    assert is_capability_sweep_overdue(conn) is True


def test_capability_sweep_overdue_after_job_threshold(conn):
    conn.execute("UPDATE capability_watch SET last_sweep_at = datetime('now'), sweep_job_count = 0 WHERE id = 1")
    conn.executemany(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at) VALUES (?, ?, ?, 'done', datetime('now'))",
        [(f"job-{i}", "codex", "test") for i in range(25)],
    )
    conn.commit()
    status = capability_sweep_status(conn)
    assert status["jobs_since_sweep"] == 25
    assert status["overdue"] is True


def test_capability_sweep_not_overdue_before_job_or_time_threshold(conn):
    conn.execute(
        "UPDATE capability_watch SET last_sweep_at = ?, sweep_job_count = 0 WHERE id = 1",
        (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),),
    )
    conn.executemany(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at) VALUES (?, ?, ?, 'done', datetime('now'))",
        [(f"job-{i}", "codex", "test") for i in range(24)],
    )
    conn.commit()
    assert is_capability_sweep_overdue(conn) is False


def test_mark_smoke_test_run_updates_timestamp(conn):
    mark_smoke_test_run(conn, green=True)
    row = conn.execute(
        "SELECT last_smoke_test_at, last_green_smoke_at FROM capability_watch WHERE id = 1"
    ).fetchone()
    assert row[0] is not None
    assert row[1] is not None


def test_maybe_trigger_staleness_checks_runs_free_probe_when_stale(conn):
    with patch("synlynk.capability_watch._run_free_probe") as mock_probe, patch(
        "synlynk.capability_watch._run_paid_smoke_test"
    ) as mock_smoke, patch(
        "synlynk.capability_watch._run_model_catalog_refresh"
    ) as mock_catalog:
        maybe_trigger_staleness_checks(conn, config={"auto_smoke_test": False})
    mock_probe.assert_called_once()
    mock_smoke.assert_not_called()
    mock_catalog.assert_called_once()


def test_maybe_trigger_staleness_checks_skips_paid_smoke_when_opted_out(conn):
    mark_probe_run(conn, green=True)
    with patch("synlynk.capability_watch._run_free_probe") as mock_probe, patch(
        "synlynk.capability_watch._run_paid_smoke_test"
    ) as mock_smoke, patch(
        "synlynk.capability_watch._run_model_catalog_refresh"
    ) as mock_catalog:
        maybe_trigger_staleness_checks(conn, config={"auto_smoke_test": False})
    mock_probe.assert_not_called()
    mock_smoke.assert_not_called()
    mock_catalog.assert_called_once()


def test_maybe_trigger_staleness_checks_runs_paid_smoke_when_opted_in(conn):
    mark_probe_run(conn, green=True)
    with patch("synlynk.capability_watch._run_free_probe") as mock_probe, patch(
        "synlynk.capability_watch._run_paid_smoke_test"
    ) as mock_smoke, patch(
        "synlynk.capability_watch._run_model_catalog_refresh"
    ):
        maybe_trigger_staleness_checks(conn, config={"auto_smoke_test": True})
    mock_probe.assert_not_called()
    mock_smoke.assert_called_once()


def test_run_free_probe_classifies_failures(conn, tmp_path):
    from unittest.mock import patch

    from synlynk.capability_watch import _run_free_probe

    conn.execute(
        "UPDATE capability_watch SET last_green_probe_at = datetime('now') WHERE id = 1"
    )
    conn.commit()

    fake_result = type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()
    with patch("synlynk.discover_agents", return_value=[{"name": "codex"}]), patch(
        "subprocess.run", return_value=fake_result
    ), patch("synlynk.capability_classifier.classify_failure") as mock_classify:
        _run_free_probe(conn)
    mock_classify.assert_called_once()
    call_kwargs = mock_classify.call_args.kwargs
    assert call_kwargs["harness"] == "codex"


def test_run_paid_smoke_test_classifies_failures(conn, tmp_path):
    from unittest.mock import patch

    from synlynk.capability_watch import _run_paid_smoke_test

    conn.execute(
        "UPDATE capability_watch SET last_green_smoke_at = datetime('now') WHERE id = 1"
    )
    conn.commit()

    fake_result = type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()
    with patch("subprocess.run", return_value=fake_result), patch(
        "synlynk.capability_classifier.classify_failure"
    ) as mock_classify:
        _run_paid_smoke_test(conn)
    mock_classify.assert_called_once()
    call_kwargs = mock_classify.call_args.kwargs
    assert call_kwargs["harness"] == "selftest"
    assert call_kwargs["failing_path"] == "synlynk/selftest.py"


def test_run_paid_smoke_test_writes_actionable_sentinel_on_failure(conn, tmp_path):
    from synlynk.capability_watch import _run_paid_smoke_test

    fake_result = type("R", (), {"returncode": 1, "stdout": "FAIL", "stderr": "boom"})()
    with patch("synlynk.capability_watch.subprocess.run", return_value=fake_result), patch(
        "synlynk.capability_watch._write_sentinel_alert"
    ) as mock_alert:
        _run_paid_smoke_test(conn)

    mock_alert.assert_called_once()
    args, kwargs = mock_alert.call_args
    assert args[:2] == ("ERROR", "AUTO_SMOKE_TEST_FAILED")
    assert "boom" in args[2]
    assert kwargs["sentinel_path"].endswith("sentinel.md")


def test_daemon_capability_watch_tick_runs_due_checks(tmp_path):
    import synlynk.daemon as daemon_mod
    from synlynk.daemon import SynlynkDaemon

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    daemon = SynlynkDaemon()
    with patch.object(daemon_mod, "_pkg", side_effect=lambda name, default=None: {
        "_get_db": lambda: conn,
    }.get(name, default)), patch(
        "synlynk.capability_watch.maybe_trigger_staleness_checks"
    ) as mock_check:
        daemon._run_capability_watch_tick({"auto_smoke_test": True})

    mock_check.assert_called_once_with(conn, {"auto_smoke_test": True})
    conn.close()


def test_cli_main_does_not_crash_when_staleness_check_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch(
        "synlynk.capability_watch.spawn_staleness_check_thread",
        side_effect=RuntimeError("boom"),
    ):
        from synlynk.cli import build_parser

        assert build_parser() is not None


def test_is_model_catalog_stale_boundary(conn):
    assert is_model_catalog_stale(conn, threshold_hours=24) is True

    _insert_discovered_model(conn, _utc_ago(23 * 3600 + 59 * 60))
    assert is_model_catalog_stale(conn, threshold_hours=24) is False

    conn.execute("DELETE FROM harness_models")
    _insert_discovered_model(conn, _utc_ago(24 * 3600 + 60))
    assert is_model_catalog_stale(conn, threshold_hours=24) is True

    fresh = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    conn.execute("UPDATE harness_models SET discovered_at = ?", (fresh,))
    conn.commit()
    assert is_model_catalog_stale(conn, threshold_hours=24) is False


def test_model_catalog_refresh_fires_once_per_due_window(conn):
    mark_probe_run(conn, green=True)
    _insert_discovered_model(conn, _utc_ago(24 * 3600 + 60))

    def _discover(connection):
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        connection.execute("UPDATE harness_models SET discovered_at = ?", (now,))

    with patch("synlynk.models.run_model_catalog_discovery", side_effect=_discover) as mock_discover:
        maybe_trigger_staleness_checks(conn, config={"auto_smoke_test": False})
        maybe_trigger_staleness_checks(conn, config={"auto_smoke_test": False})

    assert mock_discover.call_count == 1
    assert is_model_catalog_stale(conn, threshold_hours=24) is False


def test_model_catalog_refresh_skips_duplicate_concurrent_spawn(tmp_path):
    db_path = tmp_path / "state.db"
    primary = sqlite3.connect(str(db_path), check_same_thread=False)
    _migrate_db(primary)
    mark_probe_run(primary, green=True)
    _insert_discovered_model(primary, _utc_ago(24 * 3600 + 60))
    secondary = sqlite3.connect(str(db_path), check_same_thread=False)

    started = threading.Event()
    release = threading.Event()
    calls = []

    def _discover(_connection):
        calls.append(threading.get_ident())
        started.set()
        assert release.wait(3)

    with patch("synlynk.models.run_model_catalog_discovery", side_effect=_discover):
        first = threading.Thread(
            target=maybe_trigger_staleness_checks,
            args=(primary, {"auto_smoke_test": False}),
        )
        second = threading.Thread(
            target=maybe_trigger_staleness_checks,
            args=(secondary, {"auto_smoke_test": False}),
        )
        first.start()
        assert started.wait(2)
        second.start()
        second.join(2)
        assert not second.is_alive()
        release.set()
        first.join(2)

    assert len(calls) == 1
    assert not first.is_alive()
    primary.close()
    secondary.close()


def test_daemon_tick_runs_due_model_catalog_check(tmp_path):
    import synlynk.daemon as daemon_mod
    from synlynk.daemon import SynlynkDaemon

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    mark_probe_run(conn, green=True)
    daemon = SynlynkDaemon()
    with patch.object(daemon_mod, "_pkg", side_effect=lambda name, default=None: {
        "_get_db": lambda: conn,
    }.get(name, default)), patch(
        "synlynk.capability_watch._run_model_catalog_refresh"
    ) as mock_catalog, patch(
        "synlynk.capability_watch._run_free_probe"
    ) as mock_probe:
        daemon._run_capability_watch_tick({"auto_smoke_test": False})

    mock_probe.assert_not_called()
    mock_catalog.assert_called_once_with(conn)
    conn.close()


def test_cli_startup_runs_due_model_catalog_check(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    mark_probe_run(conn, green=True)
    conn.close()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    monkeypatch.setattr("synlynk._reconcile_jobs", lambda: None)

    def _joining_spawn(watch_conn, config):
        thread = _REAL_SPAWN_STALENESS_CHECK_THREAD(watch_conn, config)
        thread.join(5)
        assert not thread.is_alive()
        return thread

    monkeypatch.setattr(
        _capability_watch_mod, "spawn_staleness_check_thread", _joining_spawn
    )
    with patch("synlynk.capability_watch._run_model_catalog_refresh") as mock_catalog, patch(
        "synlynk.capability_watch._run_free_probe"
    ):
        from synlynk.cli import main

        with pytest.raises(SystemExit):
            main(["not-a-command"])

    mock_catalog.assert_called_once()
