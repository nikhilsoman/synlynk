from synlynk.baseline import (
    dispatch_flag_samples,
    dispatch_invocation_event,
    explicit_flags,
    render_markdown,
    summarize_telemetry,
)


def test_explicit_flags_counts_options_not_values():
    argv = ["dispatch", "codex", "--task", "small task", "--requires", "gh-write", "--dry-run"]
    assert explicit_flags(argv) == ["--task", "--requires", "--dry-run"]


def test_dispatch_invocation_event_records_measured_flags():
    event = dispatch_invocation_event(
        ["dispatch", "codex", "--task", "small task", "--dry-run"],
        "codex",
        "job-1",
        timestamp="2026-10-04 10:00:00",
    )
    assert event["explicit_flags"] == ["--task", "--dry-run"]
    assert event["explicit_flag_count"] == 2
    assert event["job_id"] == "job-1"


def test_legacy_dispatch_rows_are_not_treated_as_zero():
    samples, unavailable = dispatch_flag_samples([
        {"type": "dispatch", "job_id": "old"},
        {"type": "dispatch_invocation", "explicit_flag_count": 3},
    ])
    assert samples == [3]
    assert unavailable == 1
    assert summarize_telemetry([
        {"type": "dispatch", "job_id": "old"},
        {"type": "dispatch_invocation", "explicit_flag_count": 3},
    ])["explicit_flags_per_dispatch"]["median"] == 3


def test_summary_deduplicates_lifecycle_and_invocation_rows():
    summary = summarize_telemetry([
        {"type": "dispatch", "job_id": "job-1"},
        {"type": "dispatch_invocation", "job_id": "job-1", "explicit_flag_count": 4},
    ])
    assert summary["dispatch_events"] == 1
    assert summary["explicit_flags_per_dispatch"]["median"] == 4


def test_render_markdown_calls_out_unavailable_legacy_data():
    report = render_markdown({
        "dispatch_events": 1,
        "dispatch_samples_with_explicit_flags": 0,
        "dispatch_samples_without_explicit_flags": 1,
        "explicit_flags_per_dispatch": {"median": None, "samples": []},
    })
    assert "Median explicit flags per dispatch: **Unavailable**" in report
    assert "rather than treated as zero" in report.lower()
