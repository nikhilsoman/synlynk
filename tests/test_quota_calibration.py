"""Unit tests for Rolling /usage CLI Calibration Engine (MC-3) and automatic snapshot diffing (v0.26.9)."""

import pytest
import synlynk as sl
from synlynk.quota import (
    _read_agent_quota_rows,
    calculate_burn_runway,
    calibrate_and_update_quota,
    calibrate_quota_window,
    is_quota_calibration_stale,
    maybe_calibrate_quota,
    parse_cli_usage_output,
)


def test_parse_cli_usage_claude():
    text = """
    5-hour limit: 45.0% used (resets in 2h 15m)
    Weekly limit: 12.5% used (resets on Mon 00:00 UTC)
    """
    parsed = parse_cli_usage_output("claude", text)
    assert parsed["harness"] == "claude"
    assert "5h" in parsed["windows"]
    assert parsed["windows"]["5h"]["pct_used"] == 45.0
    assert parsed["windows"]["weekly"]["pct_used"] == 12.5


def test_parse_cli_usage_agy_multitrack():
    text = """
    Google AI Pro Quota Status:
    - Gemini Native 5H: 22.0% used (resets in 3h 10m)
    - Claude Proxy 5H: 68.5% used (resets in 1h 05m)
    - GPT/OSS 5H: 10.0% used (resets in 4h 00m)
    - Weekly Quota: 40.0% used
    """
    parsed = parse_cli_usage_output("agy", text)
    assert parsed["harness"] == "agy"
    assert "gemini" in parsed["tracks"]
    assert parsed["tracks"]["gemini"]["5h"]["pct_used"] == 22.0
    assert parsed["tracks"]["claude_proxy"]["5h"]["pct_used"] == 68.5
    assert parsed["tracks"]["gpt_oss"]["5h"]["pct_used"] == 10.0
    assert parsed["windows"]["weekly"]["pct_used"] == 40.0


def test_parse_cli_usage_codex():
    text = """
    Current consumption:
    5-hour session: 50% consumed
    Weekly allowance: 30% consumed
    """
    parsed = parse_cli_usage_output("codex", text)
    assert parsed["harness"] == "codex"
    assert parsed["windows"]["5h"]["pct_used"] == 50.0
    assert parsed["windows"]["weekly"]["pct_used"] == 30.0


def test_calibrate_quota_window_formula():
    # 50,000 tokens consumed led to 20% increase in reported usage (e.g. 10% -> 30%)
    res = calibrate_quota_window(delta_tokens=50_000, p1_pct=10.0, p2_pct=30.0)
    assert res["valid"] is True
    assert res["delta_tokens"] == 50_000
    assert res["delta_pct"] == 20.0
    # Ceiling = 50,000 / (20/100) = 250,000 tokens
    assert res["calculated_ceiling"] == 250_000


def test_calibrate_quota_window_invalid_delta():
    # Zero or negative delta percentage cannot compute ceiling
    res_zero = calibrate_quota_window(delta_tokens=10_000, p1_pct=20.0, p2_pct=20.0)
    assert res_zero["valid"] is False
    assert res_zero["calculated_ceiling"] is None

    res_neg = calibrate_quota_window(delta_tokens=10_000, p1_pct=30.0, p2_pct=20.0)
    assert res_neg["valid"] is False


def test_calculate_burn_runway():
    # 100k remaining, burning 50k tokens/hour -> 2.0 hours runway
    runway = calculate_burn_runway(remaining_tokens=100_000, burn_rate_tokens_per_hr=50_000)
    assert runway["runway_hours"] == 2.0
    assert runway["status"] == "warning"

    # Critical runway (< 1 hour)
    runway_crit = calculate_burn_runway(remaining_tokens=20_000, burn_rate_tokens_per_hr=50_000)
    assert runway_crit["runway_hours"] == 0.4
    assert runway_crit["status"] == "critical"

    # Healthy runway (> 3 hours)
    runway_ok = calculate_burn_runway(remaining_tokens=300_000, burn_rate_tokens_per_hr=50_000)
    assert runway_ok["runway_hours"] == 6.0
    assert runway_ok["status"] == "healthy"

    # Idle (0 burn rate)
    runway_idle = calculate_burn_runway(remaining_tokens=100_000, burn_rate_tokens_per_hr=0)
    assert runway_idle["runway_hours"] is None
    assert runway_idle["status"] == "idle"


def test_calibrate_and_update_quota_writes_to_db(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        # Delta: 40k tokens between 10% and 30% -> calculated ceiling 200k, current used 60k (30%)
        result = calibrate_and_update_quota(
            "claude",
            "5h",
            p1_pct=10.0,
            p2_pct=30.0,
            delta_tokens=40_000,
            track="default",
            conn=conn,
        )
        assert result["valid"] is True
        assert result["calculated_ceiling"] == 200_000

        rows = _read_agent_quota_rows(conn, "claude")
        assert len(rows) == 1
        r = rows[0]
        assert r["limit_tokens"] == 200_000
        assert r["used_tokens"] == 60_000
        assert r["headroom"] == 140_000
    finally:
        conn.close()


def test_capability_watch_has_quota_calibration_column(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_watch)")}
        assert "last_quota_calibration_at" in cols
    finally:
        conn.close()


def test_is_quota_calibration_stale_true_when_never_run(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        assert is_quota_calibration_stale(conn, threshold_hours=24) is True
    finally:
        conn.close()


def test_maybe_calibrate_quota_derives_delta_from_snapshots_and_cost_entries(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        conn.execute(
            "INSERT INTO quota_snapshots (harness, window, used_percent, resets_at, captured_at, source) "
            "VALUES ('claude', '5h', 10.0, '2026-10-31T18:00:00Z', '2026-10-31T10:00:00Z', 'poll')"
        )
        conn.execute(
            "INSERT INTO quota_snapshots (harness, window, used_percent, resets_at, captured_at, source) "
            "VALUES ('claude', '5h', 30.0, '2026-10-31T18:00:00Z', '2026-10-31T12:00:00Z', 'poll')"
        )
        for i in range(2):
            conn.execute(
                "INSERT INTO cost_entries (session_date, agent, harness, model, input_tokens, "
                "output_tokens, cache_read_tokens, cost_source, job_id, recorded_at) "
                "VALUES ('2026-10-31', 'claude', 'claude', 'claude-opus-4-7', 15000, 5000, 0, "
                "'actual', ?, '2026-10-31T11:00:00')",
                (f"job-cal-{i}",),
            )
        conn.commit()

        results = maybe_calibrate_quota(conn=conn)
        assert any(r["harness"] == "claude" and r["window"] == "5h" and r["valid"] for r in results)

        row = conn.execute("SELECT last_quota_calibration_at FROM capability_watch WHERE id=1").fetchone()
        assert row is not None and row[0] is not None
    finally:
        conn.close()
