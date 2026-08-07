"""Platform ops cross-repo report smoke tests."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from synlynk.platform_ops import (
    PlatformReport,
    cmd_ops_report,
    collect_platform_report,
    count_sentinel_critical_lines,
    format_platform_report,
    _is_sentinel_critical_line,
    _parse_sentinel_line_ts,
)


def test_collect_platform_report_shape():
    report = collect_platform_report(hours=24)
    assert report.hours == 24
    assert "hygiene" in report.scoreboard or report.scoreboard.get("hygiene") in ("GREEN", "RED")
    assert report.scoreboard.get("ops") in ("GREEN", "RED")
    assert isinstance(report.jobs.get("count"), int)
    assert isinstance(report.costs.get("entries"), int)
    assert "summary" in report.scoreboard


def test_format_platform_report_contains_layers():
    report = collect_platform_report(hours=24)
    text = format_platform_report(report)
    assert "SYNLYNK PLATFORM OPS" in text
    assert "L0 HYGIENE" in text
    assert "L1 JOBS" in text
    assert "L2 COSTS" in text
    assert "SCOREBOARD" in text


def test_ops_cli_parser():
    from synlynk.cli import build_parser

    args = build_parser().parse_args(["ops", "report", "--hours", "48"])
    assert args.command == "ops"
    assert args.ops_action == "report"
    assert args.hours == 48


def test_cmd_ops_report_exit_1_when_ops_red():
    """Contract: ops=RED must exit 1 even if hygiene is GREEN."""
    red = PlatformReport(
        hours=24,
        generated_at="2026-08-05T00:00:00+00:00",
        scoreboard={
            "hygiene": "GREEN",
            "ops": "RED",
            "ops_red_reasons": ["open LIVE issues=1"],
            "summary": "hygiene GREEN / ops RED: open LIVE issues=1",
        },
    )
    with patch("synlynk.platform_ops.collect_platform_report", return_value=red):
        with patch("synlynk.platform_ops.format_platform_report", return_value="stub"):
            assert cmd_ops_report(hours=24, json_output=False) == 1


def test_cmd_ops_report_exit_0_when_ops_green():
    green = PlatformReport(
        hours=24,
        generated_at="2026-08-05T00:00:00+00:00",
        scoreboard={
            "hygiene": "GREEN",
            "ops": "GREEN",
            "ops_red_reasons": [],
            "summary": "hygiene GREEN / ops GREEN — quiet",
        },
    )
    with patch("synlynk.platform_ops.collect_platform_report", return_value=green):
        with patch("synlynk.platform_ops.format_platform_report", return_value="stub"):
            assert cmd_ops_report(hours=24, json_output=False) == 0


# --- #751 windowed sentinel_crit -------------------------------------------------

_MULTI_MONTH_SENTINEL = """# Sentinel Alerts
- [CRITICAL] [2026-07-03 21:36] HARNESS_PREFLIGHT_FAIL: endpoint unreachable
- [CRITICAL] [2026-07-04 17:34] HARNESS_PREFLIGHT_FAIL: TC-2 flag check failed for agy
- [WARNING] [2026-07-05 00:36] TOOL_PRESSURE: agy tool budget ~500
- [CRITICAL] [2026-07-14 07:14] HARNESS_INTERNAL_TIMEOUT: Job job-95c73664
- [CRITICAL] [2026-07-31 06:46] STALL_NO_OUTPUT: Job job-a4c15ac4
- [CRITICAL] [2026-08-02 15:28] HARNESS_PREFLIGHT_FAIL: TC-2 for grok degraded
- [CRITICAL] [2026-08-05 21:03] HARNESS_INTERNAL_TIMEOUT: Job job-ad59d3ea
- [CRITICAL] [2026-08-06 09:04] HARNESS_INTERNAL_TIMEOUT: Job job-e6dc8ee3
- [CRITICAL] [2026-08-06 09:59] HARNESS_INTERNAL_TIMEOUT: Job job-1e129726
- [WARNING] [2026-08-06 09:54] TOOL_PRESSURE: agy tool budget ~500
> Triage note: Kept CRITICAL/FLATLINE from last 48h (must not count)
CRITICAL mention in free text must not count
- [INFO] [2026-08-06 10:00] not a severity alert
- [CRITICAL] no-timestamp-line should be lifetime only
"""


def test_parse_sentinel_line_ts_bracket_format():
    ts = _parse_sentinel_line_ts(
        "- [CRITICAL] [2026-08-06 09:59] HARNESS_INTERNAL_TIMEOUT: x"
    )
    assert ts == datetime(2026, 8, 6, 9, 59, tzinfo=timezone.utc)


def test_is_sentinel_critical_line_requires_alert_bullet():
    assert _is_sentinel_critical_line(
        "- [CRITICAL] [2026-08-06 09:59] HARNESS_INTERNAL_TIMEOUT: x"
    )
    assert _is_sentinel_critical_line("- [FLATLINE] [2026-08-06 09:59] thrice")
    assert _is_sentinel_critical_line(
        "- [CRITICAL] [2026-08-06 09:59] QUOTA_EXHAUSTED: done"
    )
    # triage notes / headers
    assert not _is_sentinel_critical_line(
        "> Triage note: Kept CRITICAL/FLATLINE from last 48h"
    )
    assert not _is_sentinel_critical_line("# Sentinel Alerts")
    assert not _is_sentinel_critical_line("CRITICAL bare text")
    assert not _is_sentinel_critical_line(
        "- [WARNING] [2026-08-06 09:59] TOOL_PRESSURE: x"
    )


def test_count_sentinel_stale_history_does_not_inflate_window():
    """Multi-month CRITICAL log → windowed=0 when now is far past last alert."""
    now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    cutoff = now - timedelta(hours=24)
    windowed, lifetime, unts = count_sentinel_critical_lines(
        _MULTI_MONTH_SENTINEL, cutoff=cutoff, now=now
    )
    assert lifetime == 9  # 8 dated CRITICAL + 1 untimestamped
    assert windowed == 0
    assert unts == 1


def test_count_sentinel_recent_window_counts_only_in_range():
    """At 2026-08-07 09:00 with 48h window: only Aug 5–6 CRITICAL lines."""
    now = datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc)
    cutoff = now - timedelta(hours=48)
    windowed, lifetime, unts = count_sentinel_critical_lines(
        _MULTI_MONTH_SENTINEL, cutoff=cutoff, now=now
    )
    # 2026-08-05 21:03, 08-06 09:04, 08-06 09:59  → 3; Aug 2 is >48h
    assert windowed == 3
    assert lifetime == 9
    assert unts == 1


def test_count_sentinel_24h_window_excludes_36h_old():
    now = datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc)
    cutoff = now - timedelta(hours=24)
    windowed, lifetime, _ = count_sentinel_critical_lines(
        _MULTI_MONTH_SENTINEL, cutoff=cutoff, now=now
    )
    # only 08-06 09:04 and 09:59 (both ~24h-ish from 08-07 09:00)
    # 08-05 21:03 is ~36h → out
    assert windowed == 2
    assert lifetime == 9


def test_collect_platform_report_windowed_sentinel_signals(tmp_path, monkeypatch):
    """Integration: only in-window CRITICAL lines set sentinel_critical_lines."""
    repo = tmp_path / "fake-repo"
    syn = repo / ".synlynk"
    syn.mkdir(parents=True)
    (syn / "sentinel.md").write_text(_MULTI_MONTH_SENTINEL)

    # Freeze "now" so the multi-month fixture is deterministic.
    fixed_now = datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "synlynk.platform_ops._utc_now", lambda: fixed_now
    )
    monkeypatch.setattr(
        "synlynk.platform_ops._dev_roots", lambda: [repo]
    )
    # Avoid scanning real project DBs / gh / fleet matrix.
    monkeypatch.setattr(
        "synlynk.platform_ops._project_dbs", lambda hours: []
    )
    monkeypatch.delenv("SYNLYNK_OPS_SENTINEL_HOURS", raising=False)

    report = collect_platform_report(hours=48, dev_root=str(repo))
    sig = report.signals
    assert sig["sentinel_files_scanned"] == 1
    assert sig["sentinel_window_hours"] == 48
    assert sig["sentinel_critical_lines"] == 3
    assert sig["sentinel_critical_lines_lifetime"] == 9
    assert sig["sentinel_critical_untimestamped"] == 1
    # 3 < 5 and no LIVE → signals.pass True (assuming gh search empty/fails)
    assert sig["pass"] is True

    text = format_platform_report(report)
    assert "last 48h" in text or "sentinel_window" in text or "lifetime=" in text
    assert "lifetime=9" in text or "lifetime=9" in str(sig)


def test_collect_only_stale_sentinel_is_ops_green_for_signals(tmp_path, monkeypatch):
    """Acceptance: only STALE historical CRITICAL → windowed 0 → no sentinel finding."""
    repo = tmp_path / "stale-repo"
    (repo / ".synlynk").mkdir(parents=True)
    stale_pair = (
        "- [CRITICAL] [2026-07-03 21:36] HARNESS_PREFLIGHT_FAIL: old\n"
        "- [CRITICAL] [2026-07-14 07:14] HARNESS_INTERNAL_TIMEOUT: old\n"
    )
    (repo / ".synlynk" / "sentinel.md").write_text(
        "# Sentinel Alerts\n" + stale_pair * 20  # 40 stale — old threshold of 5
    )
    fixed_now = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("synlynk.platform_ops._utc_now", lambda: fixed_now)
    monkeypatch.setattr("synlynk.platform_ops._dev_roots", lambda: [repo])
    monkeypatch.setattr("synlynk.platform_ops._project_dbs", lambda hours: [])
    monkeypatch.delenv("SYNLYNK_OPS_SENTINEL_HOURS", raising=False)

    report = collect_platform_report(hours=24, dev_root=str(repo))
    assert report.signals["sentinel_critical_lines"] == 0
    assert report.signals["sentinel_critical_lines_lifetime"] >= 40
    assert report.signals["pass"] is True
    # No sentinel finding for STALE-only history
    assert not any(
        "sentinel" in (f.get("summary") or "").lower() for f in report.findings
    )
