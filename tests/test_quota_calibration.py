"""Unit tests for Rolling /usage CLI Calibration Engine (MC-3)."""

import pytest

from synlynk.quota import (
    parse_cli_usage_output,
    calibrate_quota_window,
    calculate_burn_runway,
    calibrate_and_update_quota,
    _read_agent_quota_rows,
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
    import synlynk as sl
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
