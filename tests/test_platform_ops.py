"""Platform ops cross-repo report smoke tests."""

from unittest.mock import patch

from synlynk.platform_ops import (
    PlatformReport,
    cmd_ops_report,
    collect_platform_report,
    format_platform_report,
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
