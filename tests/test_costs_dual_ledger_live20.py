import os
import json
import pytest
import synlynk as sl
from synlynk.db import _generate_costs_md
from synlynk.costs import parse_costs_md, cmd_cost_billing
from unittest.mock import patch, MagicMock

def test_generate_costs_md_formats_subscription_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    monkeypatch.setattr(sl, "DB_PATH", os.path.join(tmp_path, ".synlynk", "state.db"))
    
    # Initialize DB schema
    conn = sl._get_db()
    sl._migrate_db(conn)
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, model, input_tokens, output_tokens, "
        "total_cost_usd, cost_source, story_id, notes, api_equivalent_usd, actual_usd, payment_mode) "
        "VALUES ('2026-10-02', 'codex', 'model1', 10, 20, 1.2345, 'src', NULL, 'note', 5.6789, 1.2345, 'subscription')"
    )
    conn.commit()
    conn.close()

    docs_dir = sl._synlynk_project_docs_dir()
    os.makedirs(docs_dir, exist_ok=True)
    monkeypatch.setattr(sl, "_docs_dir", sl._synlynk_project_docs_dir)
    monkeypatch.setattr(sl, "_is_migrated", lambda: True)

    _generate_costs_md()

    costs_file = os.path.join(docs_dir, "costs.md")
    print(os.listdir(docs_dir))
    with open(costs_file) as f:
        content = f.read()

    assert "$1.2345 [sub] (API: $5.6789)" in content
    # Test 3: Verify the table header is preserved exactly:
    assert "| Date | Agent | Model | Tokens In | Tokens Out | Cost | Source | Story | Notes |" in content
    # Test 4: Verify an active monthly summary section is appended:
    assert "## Subscription Amortization & Dual-Ledger Summary" in content

def test_parse_costs_md_dual_ledger(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    docs_dir = sl._synlynk_project_docs_dir()
    os.makedirs(docs_dir, exist_ok=True)
    monkeypatch.setattr(sl, "_docs_dir", sl._synlynk_project_docs_dir)

    costs_file = os.path.join(docs_dir, "costs.md")
    with open(costs_file, "w") as f:
        f.write("| Date | Agent | Model | Tokens In | Tokens Out | Cost | Source | Story | Notes |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        f.write("| 2026-10-02 | codex | model1 | 10 | 20 | $1.2345 [sub] (API: $5.6789) | src | story1 | note |\n")

    total_usd, total_requests = parse_costs_md()
    assert total_usd == pytest.approx(1.2345)
    assert total_requests == 1

def test_cmd_cost_billing(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({
            "harness_billing": {
                "claude": {"payment_mode": "subscription", "subscription_fee_usd": 20},
                "codex": {"payment_mode": "subscription", "subscription_fee_usd": 20},
                "agy": {"payment_mode": "subscription", "subscription_fee_usd": 20},
                "grok": {"payment_mode": "subscription", "subscription_fee_usd": 30}
            }
        }, f)
    
    cmd_cost_billing(None)
    captured = capsys.readouterr()
    assert "90" in captured.out
    assert "claude" in captured.out
    assert "codex" in captured.out
    assert "agy" in captured.out
    assert "grok" in captured.out

