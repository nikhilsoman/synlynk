import json
import pytest
from synlynk.costs import (
    _extract_agy_structured,
    extract_tokens,
    resolve_payment_value,
    cmd_cost_true_up,
)


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
