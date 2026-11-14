"""Tests for Intent-Based Product Development (IBPD) Engine (Track 4 / v0.36.0)."""

import json
import pytest

from synlynk.editions import CAPABILITIES, is_capability_enabled
from synlynk.ibpd import (
    DELIVERY_TIERS,
    DeliveryTier,
    cmd_ibpd_quote,
    cmd_ibpd_status,
    cmd_ibpd_tiers,
    evaluate_engagement_quote,
    get_delivery_tier,
    get_ibpd_status,
    list_delivery_tiers,
)


def test_delivery_tiers_catalog():
    """Verify all 3 Master Roadmap Phase 3 delivery tiers are registered."""
    tiers = list_delivery_tiers()
    assert len(tiers) == 3
    tier_map = {t["tier_id"]: t for t in tiers}

    # Tier 1
    t1 = tier_map[1]
    assert t1["name"] == "Self-Serve"
    assert t1["driver"] == "Customer"
    assert t1["cost_bearer_category"] == "core"
    assert t1["required_capability"] is None

    # Tier 2
    t2 = tier_map[2]
    assert t2["name"] == "Assisted Self-Serve"
    assert t2["driver"] == "Customer"
    assert t2["cost_bearer_category"] == "hosted"
    assert t2["required_capability"] == "ibpd_tier2_assisted"

    # Tier 3
    t3 = tier_map[3]
    assert t3["name"] == "Fully Managed"
    assert "reviewer/approver" in t3["driver"]
    assert t3["cost_bearer_category"] == "hosted"
    assert t3["required_capability"] == "ibpd_tier3_managed"


def test_get_delivery_tier():
    """Test get_delivery_tier retrieves valid tiers and raises ValueError on invalid."""
    t1 = get_delivery_tier(1)
    assert t1.code == "self_serve"

    t2 = get_delivery_tier(2)
    assert t2.code == "assisted_self_serve"

    t3 = get_delivery_tier(3)
    assert t3.code == "fully_managed"

    with pytest.raises(ValueError, match="Invalid IBPD delivery tier: 4"):
        get_delivery_tier(4)


def test_evaluate_engagement_quote():
    """Test engagement quotes across all 3 tiers."""
    q1 = evaluate_engagement_quote(1, stories_count=3)
    assert q1["tier_id"] == 1
    assert q1["estimated_quote_usd"] == 0.0
    assert q1["billing_mode"] == "subscription"
    assert q1["operator_fleet_engaged"] is False

    q2 = evaluate_engagement_quote(2, stories_count=3)
    assert q2["tier_id"] == 2
    assert q2["estimated_quote_usd"] == 450.0
    assert q2["billing_mode"] == "consulting_line_item"
    assert q2["operator_fleet_engaged"] is False

    q3 = evaluate_engagement_quote(3, stories_count=4)
    assert q3["tier_id"] == 3
    assert q3["estimated_quote_usd"] == 1800.0
    assert q3["billing_mode"] == "verified_outcome_capacity"
    assert q3["operator_fleet_engaged"] is True
    assert len(q3["verification_guarantees"]) >= 4


def test_editions_capability_registration():
    """Verify IBPD capabilities are correctly registered in the Editions catalog."""
    assert "ibpd_tier2_assisted" in CAPABILITIES
    cap2 = CAPABILITIES["ibpd_tier2_assisted"]
    assert cap2.category == "hosted"
    assert cap2.hosted_key == "ibpd_tier2_assisted"

    assert "ibpd_tier3_managed" in CAPABILITIES
    cap3 = CAPABILITIES["ibpd_tier3_managed"]
    assert cap3.category == "hosted"
    assert cap3.hosted_key == "ibpd_tier3_managed"


def test_ibpd_status_gating(tmp_path, monkeypatch):
    """Test get_ibpd_status reflects active edition and hosted configuration."""
    monkeypatch.chdir(tmp_path)
    syn_dir = tmp_path / ".synlynk"
    syn_dir.mkdir(parents=True, exist_ok=True)

    # 1. Default personal edition without hosted config
    (syn_dir / "config.json").write_text(json.dumps({"edition": "personal"}))
    status1 = get_ibpd_status()
    assert status1["active_edition"] == "personal"
    assert status1["available_tiers"][0]["eligible"] is True
    assert status1["available_tiers"][1]["eligible"] is False
    assert status1["available_tiers"][2]["eligible"] is False

    # 2. Team edition with hosted tier 2 & tier 3 keys enabled
    (syn_dir / "config.json").write_text(
        json.dumps({
            "edition": "team",
            "hosted": ["ibpd_tier2_assisted", "ibpd_tier3_managed"],
        })
    )
    status2 = get_ibpd_status()
    assert status2["active_edition"] == "team"
    assert status2["available_tiers"][0]["eligible"] is True
    assert status2["available_tiers"][1]["eligible"] is True
    assert status2["available_tiers"][2]["eligible"] is True


def test_cli_ibpd_commands(capsys):
    """Test CLI commands format and return code zero."""
    # status human
    rc = cmd_ibpd_status(as_json=False)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Master Roadmap Phase 3" in out

    # status JSON
    rc = cmd_ibpd_status(as_json=True)
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["master_roadmap_phase"] == 3

    # tiers human
    rc = cmd_ibpd_tiers(as_json=False)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Tier 1: Self-Serve" in out
    assert "Tier 3: Fully Managed" in out

    # tiers JSON
    rc = cmd_ibpd_tiers(as_json=True)
    assert rc == 0
    out = capsys.readouterr().out
    tiers_data = json.loads(out)
    assert len(tiers_data) == 3

    # quote human
    rc = cmd_ibpd_quote(tier_id=3, stories_count=2, as_json=False)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Tier 3 — Fully Managed" in out
    assert "$900.00" in out

    # quote JSON
    rc = cmd_ibpd_quote(tier_id=3, stories_count=2, as_json=True)
    assert rc == 0
    out = capsys.readouterr().out
    quote_data = json.loads(out)
    assert quote_data["estimated_quote_usd"] == 900.0
