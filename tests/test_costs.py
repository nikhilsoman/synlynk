import json
import pytest
from synlynk.costs import (
    _extract_agy_structured,
    extract_tokens,
    resolve_payment_value,
    cmd_cost_true_up,
)


def test_parse_dispatch_telemetry_uses_codex_terminal_event_over_stdout_text():
    from synlynk.costs import parse_dispatch_telemetry

    telemetry = parse_dispatch_telemetry(
        'warning: failed earlier\n'
        '{"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":7,"reasoning_output_tokens":3}}\n',
        agent="codex",
    )
    assert telemetry.available is True
    assert telemetry.completed is True
    assert telemetry.input_tokens == 12
    assert telemetry.output_tokens == 10


def test_parse_dispatch_telemetry_uses_claude_result_event():
    from synlynk.costs import parse_dispatch_telemetry

    telemetry = parse_dispatch_telemetry(
        '{"type":"result","subtype":"success","is_error":false,'
        '"usage":{"input_tokens":20,"output_tokens":5},"result":"failed-looking prose"}',
        agent="claude",
    )
    assert telemetry.available is True
    assert telemetry.completed is True
    assert telemetry.input_tokens == 20
    assert telemetry.output_tokens == 5


def test_extract_agy_structured_captures_cache_read_tokens():
    output = json.dumps({
        "conversation_id": "c3203df0",
        "status": "SUCCESS",
        "response": "parity achieved",
        "duration_seconds": 15.2,
        "num_turns": 2,
        "usage": {
            "input_tokens": 1024,
            "output_tokens": 512,
            "thinking_tokens": 128,
            "cache_read_tokens": 32533,
            "total_tokens": 34201,
        },
    })
    result = _extract_agy_structured(output)
    assert result is not None
    assert result.input_tokens == 1024
    assert result.output_tokens == 512 + 128
    assert result.cache_read_tokens == 32533
    assert result.basis == "structured_output"


def test_extract_tokens_captures_agy_cache_read_tokens():
    output = json.dumps({
        "conversation_id": "c3203df0",
        "status": "SUCCESS",
        "response": "parity achieved",
        "duration_seconds": 15.2,
        "num_turns": 2,
        "usage": {
            "input_tokens": 1024,
            "output_tokens": 512,
            "thinking_tokens": 128,
            "cache_read_tokens": 32533,
            "total_tokens": 34201,
        },
    })
    counts = extract_tokens(output, agent="agy")
    assert counts.input_tokens == 1024
    assert counts.output_tokens == 640
    assert counts.cache_read_tokens == 32533
    in_tok, out_tok = counts
    assert in_tok == 1024
    assert out_tok == 640


def test_codex_cached_input_subset_is_not_priced_as_fresh_input(monkeypatch):
    """job-54fa8a6a: Codex input_tokens includes cached_input_tokens.

    Pricing the cumulative sum at the fresh-input rate billed this job at
    $5.03 and tripped COST_INFLATION. Cache reads stay on the cache rate.
    """
    from synlynk import costs

    monkeypatch.setattr(costs, "_payment_model_config_for_agent", lambda agent: {"mode": "pay_as_you_go"})
    monkeypatch.setattr(
        costs,
        "_model_rate_for_version",
        lambda model, agent=None: {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    )
    value = costs.resolve_payment_value(
        "codex",
        1_631_802,
        9_154,
        cache_read_tokens=1_560_832,
        model="gpt-5.6-luna",
    )
    fresh = 1_631_802 - 1_560_832
    expected = (
        (fresh / 1000) * 0.003
        + (9_154 / 1000) * 0.015
        + (1_560_832 / 1000) * 0.0000003
    )
    assert value.api_equivalent_usd == pytest.approx(expected)
    assert value.api_equivalent_usd < 1.0


def test_non_codex_cache_read_stays_an_additive_pool(monkeypatch):
    from synlynk import costs

    monkeypatch.setattr(costs, "_payment_model_config_for_agent", lambda agent: {"mode": "pay_as_you_go"})
    monkeypatch.setattr(
        costs,
        "_model_rate_for_version",
        lambda model, agent=None: {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
    )
    value = costs.resolve_payment_value(
        "claude",
        1_000,
        100,
        cache_read_tokens=5_000,
        model="claude-sonnet-4-6",
    )
    expected = (1_000 / 1000) * 0.003 + (100 / 1000) * 0.015 + (5_000 / 1000) * 0.0000003
    assert value.api_equivalent_usd == pytest.approx(expected)


def test_zero_cost_harness_has_api_value_but_no_cash_outlay(monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "load_config", lambda: {
        "harness_billing": {"local": {"payment_mode": "zero_cost"}},
    })
    value = resolve_payment_value("local", 1000, 500)
    assert value.mode == "zero_cost"
    assert value.actual_usd == 0.0
    assert value.api_equivalent_usd == 0.0


def test_subscription_amortizes_base_fee_over_configured_projection(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({
        "harness_billing": {
            "claude": {
                "payment_mode": "subscription",
                "monthly_base_fee_usd": 20.0,
                "projected_monthly_tokens": 10_000,
            }
        }
    }))
    import synlynk
    synlynk._get_db().close()
    value = resolve_payment_value("claude", 600, 400)
    assert value.mode == "subscription"
    assert value.actual_usd == pytest.approx(2.0)


def test_true_up_writes_reconciliation_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({
        "harness_billing": {"claude": {
            "payment_mode": "subscription", "monthly_base_fee_usd": 20.0,
        }}
    }))
    import synlynk
    conn = synlynk._get_db()
    conn.execute("INSERT INTO cost_entries (session_date, agent, harness, actual_usd, total_cost_usd, cost_source) VALUES (?, ?, ?, ?, ?, ?)",
                 ("2026-09-10", "claude", "claude", 2.0, 2.0, "actual"))
    conn.commit()
    conn.close()
    result = cmd_cost_true_up(month="2026-09", harness="claude")
    assert result["variance_usd"] == pytest.approx(18.0)
    conn = synlynk._get_db()
    row = conn.execute("SELECT cost_source, actual_usd, api_equivalent_usd FROM cost_entries WHERE cost_source='true_up_reconciliation'").fetchone()
    conn.close()
    assert tuple(row) == ("true_up_reconciliation", 18.0, 0.0)
