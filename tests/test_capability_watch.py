import sqlite3
import time
from unittest.mock import patch

import pytest

from synlynk.capability_watch import (
    is_probe_stale,
    is_smoke_test_stale,
    mark_probe_run,
    mark_smoke_test_run,
    maybe_trigger_staleness_checks,
)
from synlynk.db import _migrate_db


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "state.db"
    connection = sqlite3.connect(str(db_path))
    _migrate_db(connection)
    return connection


def test_capability_watch_table_exists(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_watch)")}
    assert cols == {"id", "last_probe_at", "last_green_probe_at", "last_smoke_test_at", "last_green_smoke_at"}


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
    ) as mock_smoke:
        maybe_trigger_staleness_checks(conn, config={"auto_smoke_test": False})
    mock_probe.assert_called_once()
    mock_smoke.assert_not_called()


def test_maybe_trigger_staleness_checks_skips_paid_smoke_when_opted_out(conn):
    mark_probe_run(conn, green=True)
    with patch("synlynk.capability_watch._run_free_probe") as mock_probe, patch(
        "synlynk.capability_watch._run_paid_smoke_test"
    ) as mock_smoke:
        maybe_trigger_staleness_checks(conn, config={"auto_smoke_test": False})
    mock_probe.assert_not_called()
    mock_smoke.assert_not_called()


def test_maybe_trigger_staleness_checks_runs_paid_smoke_when_opted_in(conn):
    mark_probe_run(conn, green=True)
    with patch("synlynk.capability_watch._run_free_probe") as mock_probe, patch(
        "synlynk.capability_watch._run_paid_smoke_test"
    ) as mock_smoke:
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


def test_cli_main_does_not_crash_when_staleness_check_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch(
        "synlynk.capability_watch.spawn_staleness_check_thread",
        side_effect=RuntimeError("boom"),
    ):
        from synlynk.cli import build_parser

        assert build_parser() is not None
