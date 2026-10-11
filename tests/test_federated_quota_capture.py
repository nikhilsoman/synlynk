import json
import sqlite3
import threading
import time
from datetime import datetime, timezone


def test_migration_0020_creates_quota_snapshots(tmp_path, monkeypatch):
    from synlynk.migrations import runner
    from synlynk.migrations.m0020_quota_snapshots import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA user_version = 19")
    conn.commit()
    monkeypatch.setattr(runner, "MIGRATIONS", [MIGRATION])

    runner.run_pending_migrations(conn)

    cols = {row[1]: row for row in conn.execute("PRAGMA table_info(quota_snapshots)")}
    assert set(cols) == {
        "id", "harness", "window", "used_percent", "resets_at",
        "captured_at", "source", "staleness_seconds", "job_id",
    }
    assert cols["harness"][3] == 1
    assert cols["used_percent"][3] == 1
    assert cols["resets_at"][3] == 0
    assert cols["staleness_seconds"][3] == 0
    assert cols["job_id"][3] == 0
    indexes = {row[1] for row in conn.execute("PRAGMA index_list(quota_snapshots)")}
    assert "idx_quota_snapshots_harness_window" in indexes
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 20

    runner.run_pending_migrations(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 20
    conn.close()


def test_runner_registry_includes_migration_20_in_order():
    from synlynk.migrations.runner import MIGRATIONS

    versions = [item.version for item in MIGRATIONS]
    assert versions == [16, 17, 18, 19, 20]
    assert MIGRATIONS[-1].name == "quota_snapshots"


def test_default_registry_matches_the_spec():
    from synlynk.quota_capture import DEFAULT_POLL_INTERVAL_SECONDS, load_registry

    registry = load_registry(repo_path="/nonexistent/quota-capture-repo")
    assert DEFAULT_POLL_INTERVAL_SECONDS == 900
    assert registry["claude"]["cli_usage_cmd"] == 'claude -p "/usage" --output-format text'
    assert registry["claude"]["log_scrape"] is None
    assert registry["claude"]["has_5h_window"] is True
    assert registry["claude"]["interactive_pane_id"] is None
    assert registry["agy"]["cli_usage_cmd"] == 'agy -p "/usage" --output-format text'
    assert registry["agy"]["has_5h_window"] is True
    assert registry["codex"]["cli_usage_cmd"] is None
    assert registry["codex"]["log_scrape"] == {
        "path": "~/.codex/sessions/**/*.jsonl",
        "jq_filter": ".payload.rate_limits",
    }
    assert registry["codex"]["has_5h_window"] == "unknown"
    assert registry["grok"]["cli_usage_cmd"] is None
    assert registry["grok"]["has_5h_window"] is False
    assert registry["grok"]["log_scrape"]["path"] == "~/.grok/logs/unified.jsonl"
    assert registry["grok"]["log_scrape"]["jq_filter"] == 'select(.msg == "billing: fetched credits config")'
    assert "muse" not in registry


def test_repo_overlay_replaces_one_harness(tmp_path):
    from synlynk.quota_capture import load_registry

    syn = tmp_path / ".synlynk"
    syn.mkdir()
    (syn / "quota_capture.json").write_text(
        '{"grok": {"cli_usage_cmd": null, "log_scrape": {"path": "~/.grok/logs/unified.jsonl",'
        ' "jq_filter": "select(.msg == \\"billing: fetched credits config\\")"},'
        ' "has_5h_window": false, "interactive_pane_id": "pane-grok"}}'
    )
    registry = load_registry(repo_path=str(tmp_path))
    assert registry["grok"]["interactive_pane_id"] == "pane-grok"
    assert registry["claude"]["cli_usage_cmd"].startswith("claude ")
    assert "muse" not in registry


CLAUDE_USAGE = """\
Current session
12% used
Resets 4:30pm (America/Los_Angeles)

Current week (all models)
98% used
Resets 2026-10-12T15:30:00Z

Current week (Sonnet only)
40% used
Resets 2026-10-12T15:30:00Z
"""

AGY_USAGE = """\
Gemini 3 Pro
Current session
8% used

Current week
15% used

Claude
Current session
3% used

Current week
22% used
"""

CODEX_RATE_LIMITS = {
    "plan_type": "plus",
    "primary": {"used_percent": 14.0, "window_minutes": 10080, "resets_at": 1791953738},
    "secondary": None,
}

GROK_BILLING = {
    "ts": "2026-10-10T07:04:04.780Z",
    "src": "shell",
    "lvl": "info",
    "msg": "billing: fetched credits config",
    "ctx": {
        "config": {
            "creditUsagePercent": 21.0,
            "currentPeriod": {
                "type": "USAGE_PERIOD_TYPE_WEEKLY",
                "start": "2026-10-07T03:27:47.938919+00:00",
                "end": "2026-10-14T03:27:47.938919+00:00",
            },
        }
    },
}


def test_parse_claude_usage_text_keeps_session_and_all_models_week():
    from synlynk.quota_capture import parse_claude_usage_text

    readings = {item.window: item for item in parse_claude_usage_text(CLAUDE_USAGE)}
    assert set(readings) == {"5h", "weekly"}
    assert readings["5h"].used_percent == 12.0
    assert readings["5h"].resets_at is None
    assert readings["weekly"].used_percent == 98.0
    assert readings["weekly"].resets_at == "2026-10-12T15:30:00Z"


def test_parse_agy_usage_text_uses_the_max_family_percent():
    from synlynk.quota_capture import parse_agy_usage_text

    readings = {item.window: item for item in parse_agy_usage_text(AGY_USAGE)}
    assert readings["5h"].used_percent == 8.0
    assert readings["weekly"].used_percent == 22.0


def test_parse_codex_rate_limits_weekly_only_when_secondary_is_null():
    from synlynk.quota_capture import parse_codex_rate_limits

    readings = parse_codex_rate_limits(CODEX_RATE_LIMITS, observed_at="2026-10-10T06:16:10.058Z")
    assert len(readings) == 1
    assert readings[0].window == "weekly"
    assert readings[0].used_percent == 14.0
    assert readings[0].resets_at == "2026-10-14T04:55:38Z"
    assert readings[0].observed_at == "2026-10-10T06:16:10.058Z"


def test_parse_codex_rate_limits_maps_300_minutes_to_5h():
    from synlynk.quota_capture import parse_codex_rate_limits

    payload = {
        "primary": {"used_percent": 14.0, "window_minutes": 10080, "resets_at": 1791953738},
        "secondary": {"used_percent": 40.0, "window_minutes": 300, "resets_at": 1791400000},
    }
    windows = {item.window: item.used_percent for item in parse_codex_rate_limits(payload, "2026-10-10T00:00:00Z")}
    assert windows == {"weekly": 14.0, "5h": 40.0}


def test_parse_codex_ignores_unknown_window_minutes():
    from synlynk.quota_capture import parse_codex_rate_limits

    payload = {"primary": {"used_percent": 5.0, "window_minutes": 60, "resets_at": 1}, "secondary": None}
    assert parse_codex_rate_limits(payload, "2026-10-10T00:00:00Z") == []


def test_parse_grok_billing_line_is_weekly_only():
    from synlynk.quota_capture import parse_grok_billing_line

    readings = parse_grok_billing_line(GROK_BILLING)
    assert len(readings) == 1
    assert readings[0].window == "weekly"
    assert readings[0].used_percent == 21.0
    assert readings[0].resets_at == "2026-10-14T03:27:47.938919+00:00"
    assert readings[0].observed_at == "2026-10-10T07:04:04.780Z"
    assert parse_grok_billing_line({"msg": "something else"}) == []


def _snapshots_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from synlynk.migrations.m0020_quota_snapshots import MIGRATION
    MIGRATION.up(conn)
    conn.execute(
        """CREATE TABLE harness_quotas (
            id INTEGER PRIMARY KEY,
            harness TEXT NOT NULL,
            track TEXT NOT NULL DEFAULT 'default',
            model TEXT NOT NULL DEFAULT 'unknown',
            quota_type TEXT NOT NULL,
            unit TEXT NOT NULL DEFAULT 'tokens',
            limit_tokens INTEGER NOT NULL,
            used_tokens INTEGER NOT NULL DEFAULT 0,
            reset_at TEXT,
            updated_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY,
            session_date TEXT NOT NULL,
            agent TEXT,
            harness TEXT,
            total_cost_usd REAL,
            cost_source TEXT NOT NULL
        )"""
    )
    return conn


def test_task_boundary_insert_stores_null_staleness_and_job_id():
    from synlynk.quota_capture import WindowReading, insert_snapshots

    conn = _snapshots_db()
    count = insert_snapshots(
        conn,
        "claude",
        [WindowReading("weekly", 98.0, "2026-10-12T15:30:00Z", "2026-10-10T00:00:00Z"),
         WindowReading("5h", 12.0, None, "2026-10-10T00:00:00Z")],
        source="task_boundary",
        job_id="job-1",
        captured_at="2026-10-10T01:00:00+00:00",
        staleness_by_window={"weekly": 999, "5h": 999},
    )
    conn.commit()
    assert count == 2
    rows = conn.execute(
        "SELECT window, used_percent, source, staleness_seconds, job_id FROM quota_snapshots ORDER BY window"
    ).fetchall()
    assert rows[0]["window"] == "5h"
    assert rows[0]["staleness_seconds"] is None
    assert rows[0]["job_id"] == "job-1"
    assert rows[1]["window"] == "weekly"
    assert rows[1]["used_percent"] == 98.0
    assert rows[1]["source"] == "task_boundary"


def test_stale_snapshot_is_unknown_until_calibrate_fallback():
    from synlynk.quota_capture import WindowReading, insert_snapshots, window_status

    conn = _snapshots_db()
    insert_snapshots(
        conn, "claude",
        [WindowReading("weekly", 10.0, None, "2026-10-01T00:00:00Z")],
        source="poller", job_id=None,
        captured_at="2026-10-01T00:00:00+00:00",
        staleness_by_window={"weekly": 0},
    )
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    status = window_status(conn, "claude", "weekly", now=now)
    assert status["state"] == "unknown"
    assert status["reason"] == "stale"
    assert status["used_percent"] is None

    conn.execute(
        "INSERT INTO harness_quotas (harness, quota_type, unit, limit_tokens, used_tokens, updated_at)"
        " VALUES ('claude', 'weekly', 'tokens', 100, 40, '2026-10-09T00:00:00Z')"
    )
    fallback = window_status(conn, "claude", "weekly", now=now)
    assert fallback == {
        "state": "known",
        "used_percent": 40.0,
        "reason": None,
        "source": "calibrate",
        "resets_at": None,
        "captured_at": None,
    }


def test_fresh_poller_row_with_old_log_age_is_unknown():
    from synlynk.quota_capture import WindowReading, insert_snapshots, window_status

    conn = _snapshots_db()
    insert_snapshots(
        conn, "codex",
        [WindowReading("weekly", 14.0, None, "2026-10-01T00:00:00Z")],
        source="poller", job_id=None,
        captured_at="2026-10-10T00:00:00+00:00",
        staleness_by_window={"weekly": 90000},
    )
    status = window_status(conn, "codex", "weekly", now=datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc))
    assert status["state"] == "unknown"
    assert status["reason"] == "stale"


def test_missing_snapshot_is_unknown_not_zero():
    from synlynk.quota_capture import window_status

    conn = _snapshots_db()
    status = window_status(conn, "grok", "5h", now=datetime(2026, 10, 10, tzinfo=timezone.utc))
    assert status["state"] == "unknown"
    assert status["used_percent"] is None
    assert status["reason"] == "missing"


def test_federated_rows_include_registry_gaps_and_seven_day_cost():
    from synlynk.quota_capture import WindowReading, federated_rows, insert_snapshots

    conn = _snapshots_db()
    insert_snapshots(
        conn, "claude",
        [WindowReading("weekly", 98.0, "2026-10-12T15:30:00Z", "2026-10-10T00:00:00Z")],
        source="task_boundary", job_id="job-9",
        captured_at="2026-10-10T00:30:00+00:00",
        staleness_by_window={},
    )
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, harness, total_cost_usd, cost_source)"
        " VALUES ('2026-10-09', 'claude', 'claude', 4.5, 'actual'),"
        "        ('2026-10-01', 'claude', 'claude', 100, 'actual')"
    )
    now = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
    rows = {(row["harness"], row["window"]): row for row in federated_rows(conn, now=now)}
    assert rows[("claude", "weekly")]["state"] == "known"
    assert rows[("claude", "weekly")]["used_percent"] == 98.0
    assert rows[("claude", "weekly")]["cost_7d_usd"] == 4.5
    assert rows[("claude", "5h")]["state"] == "unknown"
    assert rows[("grok", "weekly")]["state"] == "unknown"
    assert rows[("grok", "5h")]["state"] == "unknown"
    assert rows[("codex", "5h")]["state"] == "unknown"
    assert ("muse", "weekly") not in rows


def test_format_federated_text_names_unknown_grok():
    from synlynk.quota_capture import format_federated_text

    text = format_federated_text([
        {"harness": "grok", "window": "weekly", "state": "unknown", "used_percent": None,
         "source": None, "resets_at": None, "captured_at": None, "cost_7d_usd": 0.0, "reason": "missing"},
    ])
    assert "grok" in text
    assert "weekly" in text
    assert "unknown" in text
    assert "0%" not in text
    assert "100%" not in text


def test_boundary_capture_returns_before_the_slow_write(monkeypatch):
    from synlynk.quota_capture import schedule_boundary_capture

    started = threading.Event()
    release = threading.Event()
    wrote = {}

    def slow_capture(harness, **kwargs):
        started.set()
        assert release.wait(2)
        wrote["harness"] = harness
        wrote["job_id"] = kwargs.get("job_id")
        wrote["source"] = kwargs.get("source")
        return 1

    monkeypatch.setattr("synlynk.quota_capture.capture_harness", slow_capture)
    monkeypatch.setattr("synlynk.quota_capture._open_db", lambda: None)

    started_at = time.perf_counter()
    thread = schedule_boundary_capture("codex", "job-77")
    elapsed = time.perf_counter() - started_at
    assert elapsed < 0.2
    assert started.wait(1)
    assert wrote == {}
    release.set()
    thread.join(2)
    assert not thread.is_alive()
    assert wrote == {"harness": "codex", "job_id": "job-77", "source": "task_boundary"}


def test_capture_harness_skips_an_unregistered_name():
    from synlynk.quota_capture import capture_harness

    class ExplodingConn:
        def execute(self, *args, **kwargs):
            raise AssertionError("unregistered harness must not write")

    assert capture_harness("muse", source="task_boundary", job_id=None, conn=ExplodingConn()) == 0


def test_exec_finished_schedules_only_registered_binaries(monkeypatch):
    from synlynk.quota_capture import on_exec_finished

    scheduled = []
    monkeypatch.setattr(
        "synlynk.quota_capture.schedule_boundary_capture",
        lambda harness, job_id: scheduled.append((harness, job_id)) or None,
    )
    on_exec_finished(["/usr/local/bin/claude", "-p", "hello"])
    on_exec_finished(["gemini", "-p", "hello"])
    on_exec_finished(["muse", "-p", "hello"])
    assert scheduled == [("claude", None), ("agy", None)]


def test_job_terminal_schedules_only_done_registered_jobs(monkeypatch):
    from synlynk.quota_capture import on_job_terminal

    scheduled = []
    monkeypatch.setattr(
        "synlynk.quota_capture.schedule_boundary_capture",
        lambda harness, job_id: scheduled.append((harness, job_id)),
    )
    on_job_terminal("codex", "job-1", "done")
    on_job_terminal("codex", "job-2", "failed")
    on_job_terminal("muse", "job-3", "done")
    assert scheduled == [("codex", "job-1")]


def test_note_exec_return_schedules_and_preserves_exit_code(monkeypatch):
    from synlynk.quota_capture import note_exec_return

    calls = []

    def boom(cmd):
        calls.append(list(cmd))
        raise RuntimeError("capture must not change the exit code")

    monkeypatch.setattr("synlynk.quota_capture.on_exec_finished", boom)
    assert note_exec_return(["claude", "-p", "hi"], exit_code=7) == 7
    assert calls == [["claude", "-p", "hi"]]


def test_note_job_settled_schedules_when_done(monkeypatch):
    from synlynk.quota_capture import note_job_settled

    calls = []
    monkeypatch.setattr(
        "synlynk.quota_capture.on_job_terminal",
        lambda harness, job_id, status: calls.append((harness, job_id, status)),
    )
    note_job_settled(settled=True, harness="grok", job_id="job-5", status="done")
    note_job_settled(settled=False, harness="grok", job_id="job-6", status="done")
    note_job_settled(settled=True, harness="grok", job_id="job-7", status="failed")
    assert calls == [("grok", "job-5", "done")]


def _grok_registry(log_path: str, pane_id):
    return {
        "grok": {
            "cli_usage_cmd": None,
            "log_scrape": {
                "path": log_path,
                "jq_filter": 'select(.msg == "billing: fetched credits config")',
            },
            "has_5h_window": False,
            "interactive_pane_id": pane_id,
        }
    }


def _grok_line(ts: str, percent: float) -> str:
    return json.dumps({
        "ts": ts,
        "msg": "billing: fetched credits config",
        "ctx": {"config": {
            "creditUsagePercent": percent,
            "currentPeriod": {
                "type": "USAGE_PERIOD_TYPE_WEEKLY",
                "end": "2026-10-14T03:27:47.938919+00:00",
            },
        }},
    })


def test_grok_poller_sends_usage_only_when_the_log_line_is_stale(tmp_path):
    from synlynk.quota_capture import poll_once

    log_path = tmp_path / "unified.jsonl"
    log_path.write_text(_grok_line("2026-10-10T00:00:00Z", 21.0) + "\n")
    calls = []

    def runner(argv, timeout):
        calls.append(argv)
        if argv[2] == "send-keys":
            with log_path.open("a") as handle:
                handle.write(_grok_line("2026-10-10T01:00:00Z", 22.0) + "\n")
        return ""

    conn = _snapshots_db()
    now = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
    written = poll_once(
        conn=conn,
        registry=_grok_registry(str(log_path), "pane-grok"),
        now=now,
        runner=runner,
        sleeper=lambda seconds: None,
    )
    assert calls == [
        ["herdr", "pane", "send-text", "pane-grok", "/usage"],
        ["herdr", "pane", "send-keys", "pane-grok", "Enter"],
    ]
    assert written == 1
    row = conn.execute("SELECT used_percent, source, staleness_seconds FROM quota_snapshots").fetchone()
    assert row["used_percent"] == 22.0
    assert row["source"] == "poller"
    assert row["staleness_seconds"] == 0


def test_grok_poller_does_not_refresh_a_fresh_line(tmp_path):
    from synlynk.quota_capture import poll_once

    log_path = tmp_path / "unified.jsonl"
    log_path.write_text(_grok_line("2026-10-10T00:50:00Z", 21.0) + "\n")
    calls = []
    conn = _snapshots_db()
    written = poll_once(
        conn=conn,
        registry=_grok_registry(str(log_path), "pane-grok"),
        now=datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc),
        runner=lambda argv, timeout: calls.append(argv),
        sleeper=lambda seconds: None,
    )
    assert calls == []
    assert written == 1
    row = conn.execute("SELECT used_percent, staleness_seconds FROM quota_snapshots").fetchone()
    assert row["used_percent"] == 21.0
    assert row["staleness_seconds"] == 600


def test_grok_poller_without_a_pane_does_not_call_herdr(tmp_path):
    from synlynk.quota_capture import poll_once

    log_path = tmp_path / "unified.jsonl"
    log_path.write_text(_grok_line("2026-10-09T00:00:00Z", 21.0) + "\n")
    calls = []
    conn = _snapshots_db()
    poll_once(
        conn=conn,
        registry=_grok_registry(str(log_path), None),
        now=datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc),
        runner=lambda argv, timeout: calls.append(argv),
        sleeper=lambda seconds: None,
    )
    assert calls == []


def test_claude_poller_runs_the_registry_command():
    from synlynk.quota_capture import poll_once

    seen = []

    def runner(argv, timeout):
        seen.append(argv)
        return "Current session\n4% used\n\nCurrent week (all models)\n10% used\n"

    conn = _snapshots_db()
    written = poll_once(
        conn=conn,
        registry={"claude": {
            "cli_usage_cmd": 'claude -p "/usage" --output-format text',
            "log_scrape": None,
            "has_5h_window": True,
            "interactive_pane_id": None,
        }},
        now=datetime(2026, 10, 10, tzinfo=timezone.utc),
        runner=runner,
        sleeper=lambda seconds: None,
    )
    assert seen == [["claude", "-p", "/usage", "--output-format", "text"]]
    assert written == 2


def test_quota_federated_json_prints_unknown_without_raising(monkeypatch, capsys):
    from synlynk.quota_capture import cmd_quota_federated

    class _Conn:
        def close(self):
            return None

    monkeypatch.setattr(
        "synlynk.quota_capture.federated_rows",
        lambda conn, now=None, registry=None: [{
            "harness": "grok",
            "window": "weekly",
            "state": "unknown",
            "used_percent": None,
            "source": None,
            "resets_at": None,
            "captured_at": None,
            "cost_7d_usd": 0.0,
            "reason": "missing",
        }],
    )
    monkeypatch.setattr("synlynk.quota_capture._open_db", lambda: _Conn())
    cmd_quota_federated(json_output=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["harness"] == "grok"
    assert payload[0]["state"] == "unknown"
    assert payload[0]["used_percent"] is None


def test_taxonomy_and_parser_both_have_quota_federated():
    from synlynk.cli import build_parser
    from synlynk.taxonomy import COMMAND_TAXONOMY, iter_leaf_commands

    parser = build_parser()
    assert "quota federated" in set(iter_leaf_commands(parser))
    assert "quota federated" in {entry["command"] for entry in COMMAND_TAXONOMY}


def test_routing_prefers_the_known_weekly_reading_with_headroom():
    from synlynk.quota_capture import WindowReading, insert_snapshots, prefer_harness_by_weekly_headroom

    conn = _snapshots_db()
    now = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
    captured = "2026-10-10T00:50:00+00:00"
    insert_snapshots(
        conn, "claude", [WindowReading("weekly", 98.0, None, captured)],
        source="task_boundary", job_id="job-c", captured_at=captured, staleness_by_window={},
    )
    insert_snapshots(
        conn, "codex", [WindowReading("weekly", 14.0, None, captured)],
        source="task_boundary", job_id="job-x", captured_at=captured, staleness_by_window={},
    )
    choice = prefer_harness_by_weekly_headroom("claude", ["codex", "agy"], conn=conn, now=now)
    assert choice == "codex"


def test_routing_does_not_treat_unknown_as_free_capacity():
    from synlynk.quota_capture import WindowReading, insert_snapshots, prefer_harness_by_weekly_headroom

    conn = _snapshots_db()
    now = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
    insert_snapshots(
        conn, "codex", [WindowReading("weekly", 14.0, None, "2026-10-10T00:50:00Z")],
        source="task_boundary", job_id=None, captured_at="2026-10-10T00:50:00+00:00", staleness_by_window={},
    )
    choice = prefer_harness_by_weekly_headroom("claude", ["grok", "codex"], conn=conn, now=now)
    assert choice == "codex"


def test_routing_keeps_incumbent_when_every_reading_is_unknown():
    from synlynk.quota_capture import prefer_harness_by_weekly_headroom

    conn = _snapshots_db()
    choice = prefer_harness_by_weekly_headroom(
        "claude", ["muse"], conn=conn, now=datetime(2026, 10, 10, tzinfo=timezone.utc),
    )
    assert choice == "claude"


def test_routing_skips_a_full_5h_window():
    from synlynk.quota_capture import WindowReading, insert_snapshots, prefer_harness_by_weekly_headroom

    conn = _snapshots_db()
    captured = "2026-10-10T00:50:00+00:00"
    now = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
    insert_snapshots(
        conn, "codex",
        [WindowReading("weekly", 14.0, None, captured), WindowReading("5h", 100.0, None, captured)],
        source="task_boundary", job_id=None, captured_at=captured, staleness_by_window={},
    )
    insert_snapshots(
        conn, "claude", [WindowReading("weekly", 98.0, None, captured)],
        source="task_boundary", job_id=None, captured_at=captured, staleness_by_window={},
    )
    choice = prefer_harness_by_weekly_headroom("claude", ["codex"], conn=conn, now=now)
    assert choice == "claude"


def test_routing_uses_calibrate_when_the_snapshot_is_stale():
    from synlynk.quota_capture import WindowReading, insert_snapshots, prefer_harness_by_weekly_headroom

    conn = _snapshots_db()
    insert_snapshots(
        conn, "claude", [WindowReading("weekly", 98.0, None, "2026-10-01T00:00:00Z")],
        source="poller", job_id=None, captured_at="2026-10-01T00:00:00+00:00",
        staleness_by_window={"weekly": 0},
    )
    conn.execute(
        "INSERT INTO harness_quotas (harness, quota_type, unit, limit_tokens, used_tokens, updated_at)"
        " VALUES ('agy', 'weekly', 'tokens', 100, 10, '2026-10-09')"
    )
    choice = prefer_harness_by_weekly_headroom(
        "claude", ["agy"], conn=conn, now=datetime(2026, 10, 10, tzinfo=timezone.utc),
    )
    assert choice == "agy"


def _policy_for_infer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    policy_path = tmp_path / ".synlynk" / "policy.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(
        '{"schema_version": 1, "repo_id": "test", "capability_policy": {},'
        ' "overrides": {"dev_authority": {"task_allocation": '
        '{"implement": {"harness": "claude", "fallback": ["agy", "codex"]}}}}}'
    )


def test_infer_dispatch_defaults_calls_headroom_when_the_harness_is_unpinned(tmp_path, monkeypatch):
    from synlynk.dispatch import _infer_dispatch_defaults

    _policy_for_infer(tmp_path, monkeypatch)
    monkeypatch.setattr("synlynk.capability.ranked_harness_for_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "synlynk.quota_capture.prefer_harness_by_weekly_headroom",
        lambda incumbent, fallbacks, conn, now=None, registry=None: "agy",
    )
    preview = _infer_dispatch_defaults("implement the quota view", task_type="implement", agent=None)
    assert preview["harness"] == "agy"


def test_infer_dispatch_defaults_does_not_override_an_explicit_harness(tmp_path, monkeypatch):
    from synlynk.dispatch import _infer_dispatch_defaults

    _policy_for_infer(tmp_path, monkeypatch)
    monkeypatch.setattr("synlynk.capability.ranked_harness_for_task", lambda *args, **kwargs: None)

    def explode(*args, **kwargs):
        raise AssertionError("explicit harness must skip quota routing")

    monkeypatch.setattr("synlynk.quota_capture.prefer_harness_by_weekly_headroom", explode)
    preview = _infer_dispatch_defaults(
        "implement the quota view", task_type="implement", agent="codex",
    )
    assert preview["harness"] == "codex"


def test_unregistered_harness_never_writes_and_routing_does_not_raise():
    from synlynk.quota_capture import capture_harness, prefer_harness_by_weekly_headroom

    conn = _snapshots_db()
    assert capture_harness(
        "muse", source="poller", job_id=None, conn=conn,
        now=datetime(2026, 10, 10, tzinfo=timezone.utc),
    ) == 0
    assert conn.execute("SELECT COUNT(*) FROM quota_snapshots").fetchone()[0] == 0
    assert prefer_harness_by_weekly_headroom(
        "claude", ["muse"], conn=conn, now=datetime(2026, 10, 10, tzinfo=timezone.utc),
    ) == "claude"
