"""Unit tests for Empirical Dynamic Allocation & Advisory Service (MC-4)."""

from datetime import datetime, timezone
import pytest

from synlynk.advisory import (
    get_current_capacity_factor,
    get_utilization_advisory,
    format_advisory_text,
    export_advisory_json,
)


def test_capacity_factor_by_utc_hour():
    # 04:00 UTC -> off-peak (expanded capacity ~1.6x)
    off_peak = get_current_capacity_factor(utc_hour=4)
    assert off_peak["window_type"] == "off_peak"
    assert off_peak["capacity_multiplier"] >= 1.4
    assert "dispatch" in off_peak["recommended_action"].lower() or "swarm" in off_peak["recommended_action"].lower()

    # 15:00 UTC -> peak surge (throttling ~0.65x)
    peak = get_current_capacity_factor(utc_hour=15)
    assert peak["window_type"] == "peak_surge"
    assert peak["capacity_multiplier"] <= 0.75

    # 10:00 UTC -> standard (1.0x)
    std = get_current_capacity_factor(utc_hour=10)
    assert std["window_type"] == "standard"
    assert std["capacity_multiplier"] == 1.0


def test_utilization_advisory_structure():
    fixed_time = datetime(2026, 9, 20, 3, 30, 0, tzinfo=timezone.utc)
    adv = get_utilization_advisory(now_dt=fixed_time)
    assert adv["current_utc_hour"] == 3
    assert adv["current_status"]["window_type"] == "off_peak"
    assert len(adv["time_blocks"]) == 4
    assert "claude" in adv["harness_recommendations"]
    assert "agy" in adv["harness_recommendations"]


def test_format_advisory_text_width_constraint():
    adv = get_utilization_advisory()
    text = format_advisory_text(adv)
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        assert len(line) <= 56, f"Line {idx + 1} exceeds 56 chars: {line!r} (len={len(line)})"


def test_export_advisory_json():
    import json
    adv = get_utilization_advisory()
    json_str = export_advisory_json(adv)
    data = json.loads(json_str)
    assert "current_status" in data
    assert "time_blocks" in data
