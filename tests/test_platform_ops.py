"""Platform ops cross-repo report smoke tests."""

from synlynk.platform_ops import collect_platform_report, format_platform_report


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
