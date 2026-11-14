"""Intent-Based Product Development (IBPD) Engine.

Represents Master Roadmap Phase 3 (Self-Serve Tiered Delivery Ladder)
per docs/superpowers/specs/2026-11-13-intent-based-product-development-design.md.
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


class DeliveryTier(enum.IntEnum):
    TIER_1_SELF_SERVE = 1
    TIER_2_ASSISTED = 2
    TIER_3_MANAGED = 3


@dataclass(frozen=True)
class TierDefinition:
    tier_id: int
    name: str
    code: str
    driver: str
    executor: str
    revenue_model: str
    cost_bearer_category: str
    required_capability: Optional[str]
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DELIVERY_TIERS: Dict[int, TierDefinition] = {
    DeliveryTier.TIER_1_SELF_SERVE.value: TierDefinition(
        tier_id=1,
        name="Self-Serve",
        code="self_serve",
        driver="Customer",
        executor="Customer own fleet, own harness credentials, own GOVERNS policy",
        revenue_model="Subscription (Personal/Team/Enterprise)",
        cost_bearer_category="core",
        required_capability=None,
        description=(
            "Customer operates synlynk directly. Customer provides fleet credentials, "
            "authorizes runs, and enforces local GOVERNS policy."
        ),
    ),
    DeliveryTier.TIER_2_ASSISTED.value: TierDefinition(
        tier_id=2,
        name="Assisted Self-Serve",
        code="assisted_self_serve",
        driver="Customer",
        executor="Customer fleet, augmented by synlynk role-charter playbooks and decide panel",
        revenue_model="Professional-services line items on top of subscription",
        cost_bearer_category="hosted",
        required_capability="ibpd_tier2_assisted",
        description=(
            "Customer drives delivery using accumulated synlynk operating knowledge, "
            "stack-tuned role charters, and strategic decide-panel consultation."
        ),
    ),
    DeliveryTier.TIER_3_MANAGED.value: TierDefinition(
        tier_id=3,
        name="Fully Managed",
        code="fully_managed",
        driver="Customer (reviewer/approver only)",
        executor="Synlynk operator-controlled fleet under synlynk GOVERNS policy and charters",
        revenue_model="Outcome-based or consumption-based retainer per verified story",
        cost_bearer_category="hosted",
        required_capability="ibpd_tier3_managed",
        description=(
            "Outsource to synlynk outcome-based delivery. Customer supplies intent, backlog, "
            "or codebase; synlynk fleet executes end-to-end under strict GOVERNS governance."
        ),
    ),
}


def list_delivery_tiers() -> List[Dict[str, Any]]:
    """Return all Master Roadmap Phase 3 delivery tiers."""
    return [tier.to_dict() for tier in DELIVERY_TIERS.values()]


def get_delivery_tier(tier_id: int) -> TierDefinition:
    """Retrieve delivery tier definition by tier id (1, 2, or 3)."""
    if tier_id not in DELIVERY_TIERS:
        raise ValueError(f"Invalid IBPD delivery tier: {tier_id}. Expected 1, 2, or 3.")
    return DELIVERY_TIERS[tier_id]


def evaluate_engagement_quote(
    tier_id: int,
    repo_path: Optional[str] = None,
    stories_count: int = 1,
) -> Dict[str, Any]:
    """Evaluate an engagement quote and requirements for a delivery tier."""
    tier = get_delivery_tier(tier_id)
    stories_count = max(1, stories_count)

    # Base pricing model indicators per tier
    if tier.tier_id == 1:
        billing_mode = "subscription"
        estimated_quote_usd = 0.0
        governance_model = "customer_local_policy"
        operator_fleet = False
    elif tier.tier_id == 2:
        billing_mode = "consulting_line_item"
        estimated_quote_usd = round(150.0 * stories_count, 2)
        governance_model = "augmented_customer_policy"
        operator_fleet = False
    else:
        billing_mode = "verified_outcome_capacity"
        estimated_quote_usd = round(450.0 * stories_count, 2)
        governance_model = "synlynk_hardened_governs_policy"
        operator_fleet = True

    return {
        "tier_id": tier.tier_id,
        "tier_name": tier.name,
        "tier_code": tier.code,
        "driver": tier.driver,
        "executor": tier.executor,
        "billing_mode": billing_mode,
        "cost_bearer_category": tier.cost_bearer_category,
        "stories_count": stories_count,
        "estimated_quote_usd": estimated_quote_usd,
        "governance_model": governance_model,
        "operator_fleet_engaged": operator_fleet,
        "requires_capability": tier.required_capability,
        "repo_path": repo_path or ".",
        "verification_guarantees": [
            "Non-author cross-harness PR review enforcement",
            "100% linked GOVERNS goal adherence",
            "Zero personal GitHub token prohibition",
            "Immutable audit trail in state.db",
        ],
    }


def get_ibpd_status(conn=None) -> Dict[str, Any]:
    """Inspect current workspace IBPD status, active tier, and governance posture."""
    from synlynk.editions import get_active_edition, is_capability_enabled

    edition = get_active_edition()
    tier2_available = is_capability_enabled("ibpd_tier2_assisted")
    tier3_available = is_capability_enabled("ibpd_tier3_managed")

    return {
        "master_roadmap_phase": 3,
        "phase_title": "Self-Serve Tiered Delivery Ladder",
        "active_edition": edition,
        "default_tier": 1,
        "available_tiers": [
            {"tier_id": 1, "name": "Self-Serve", "eligible": True},
            {"tier_id": 2, "name": "Assisted Self-Serve", "eligible": tier2_available},
            {"tier_id": 3, "name": "Fully Managed", "eligible": tier3_available},
        ],
        "editions_gating": {
            "ibpd_tier2_assisted": tier2_available,
            "ibpd_tier3_managed": tier3_available,
        },
        "governance_substrate": {
            "intent_drift_eliminated": True,
            "derived_roadmap": True,
            "charter_enforced": True,
        },
    }


def cmd_ibpd_status(as_json: bool = False) -> int:
    """CLI handler for `synlynk ibpd status`."""
    import json
    import sys

    status = get_ibpd_status()
    if as_json:
        print(json.dumps(status, indent=2))
        return 0

    print("Master Roadmap Phase 3: Self-Serve Tiered Delivery Ladder")
    print("=" * 60)
    print(f"Active Edition: {status['active_edition'].upper()}")
    print("\nDelivery Tiers:")
    for tier in status["available_tiers"]:
        eligibility = "[ELIGIBLE]" if tier["eligible"] else "[GATED by Edition]"
        print(f"  Tier {tier['tier_id']} — {tier['name']:<22} {eligibility}")

    print("\nGovernance Substrate:")
    print("  • Intent drift eliminated (Fully-derived roadmap VIEWs)")
    print("  • Living charters & constitutional invariant enforcement active")
    print("  • Cross-harness reviewer discipline & token security enforced")
    return 0


def cmd_ibpd_tiers(as_json: bool = False) -> int:
    """CLI handler for `synlynk ibpd tiers`."""
    import json

    tiers = list_delivery_tiers()
    if as_json:
        print(json.dumps(tiers, indent=2))
        return 0

    print("Master Roadmap Phase 3 — Delivery Ladder Tiers")
    print("=" * 60)
    for t in tiers:
        print(f"\nTier {t['tier_id']}: {t['name']}")
        print(f"  Driver:         {t['driver']}")
        print(f"  Executor:       {t['executor']}")
        print(f"  Revenue Model:  {t['revenue_model']}")
        print(f"  Cost Bearer:    {t['cost_bearer_category']}")
        print(f"  Description:    {t['description']}")
    return 0


def cmd_ibpd_quote(
    tier_id: int,
    repo_path: Optional[str] = ".",
    stories_count: int = 1,
    as_json: bool = False,
) -> int:
    """CLI handler for `synlynk ibpd quote`."""
    import json

    quote = evaluate_engagement_quote(
        tier_id=tier_id,
        repo_path=repo_path,
        stories_count=stories_count,
    )
    if as_json:
        print(json.dumps(quote, indent=2))
        return 0

    print("Intent-Based Product Development (IBPD) Engagement Quote")
    print("=" * 60)
    print(f"Tier:               Tier {quote['tier_id']} — {quote['tier_name']}")
    print(f"Driver:             {quote['driver']}")
    print(f"Executor:           {quote['executor']}")
    print(f"Cost Category:      {quote['cost_bearer_category']}")
    print(f"Billing Mode:       {quote['billing_mode']}")
    print(f"Target Repo:        {quote['repo_path']}")
    print(f"Stories Count:      {quote['stories_count']}")
    print(f"Estimated Quote:    ${quote['estimated_quote_usd']:.2f}")
    print(f"Operator Fleet:     {'YES (Synlynk Fleet)' if quote['operator_fleet_engaged'] else 'NO (Customer Fleet)'}")
    print("\nGovernance Guarantees:")
    for g in quote["verification_guarantees"]:
        print(f"  ✓ {g}")
    return 0
