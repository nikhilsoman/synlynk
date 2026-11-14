"""Synlynk Editions classification engine and gating primitives.

Classifies capabilities by who bears their marginal cost of existing:
- Core: nobody extra bears the cost; local runtime execution.
- Opt-in: the user bears the cost via their own config or credentials.
- Hosted: Synlynk bears the cost via hosted infra or services.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

EDITION_ORDER: Tuple[str, ...] = ("personal", "team", "enterprise")


@dataclass(frozen=True)
class Capability:
    """Represents a discrete Synlynk capability and its gating requirements."""

    name: str
    category: str  # "core" | "opt_in" | "hosted"
    min_edition: Optional[str] = None  # None for core / opt_in
    hosted_key: Optional[str] = None  # Non-empty str if category == "hosted"
    note: str = ""


# Baseline capabilities catalog
CAPABILITIES: Dict[str, Capability] = {
    # Core capabilities (Local execution, no marginal hosting cost)
    "capability_tracking": Capability(
        name="capability_tracking",
        category="core",
        note="Local self-measurement of dispatch history across model catalog",
    ),
    "local_pilot": Capability(
        name="local_pilot",
        category="core",
        note="Single-operator orchestration and local Wingman runtime",
    ),
    "quota_tracking": Capability(
        name="quota_tracking",
        category="core",
        note="Tracking token and request usage against user's local API keys",
    ),
    "swarm_local": Capability(
        name="swarm_local",
        category="core",
        note="Local dispatch across worktrees within workspace",
    ),
    # Opt-in capabilities (User bears credentials/infrastructure cost)
    "github_app_auth": Capability(
        name="github_app_auth",
        category="opt_in",
        note="Workspace-scoped GitHub App tokens provided by the user",
    ),
    "relay_local": Capability(
        name="relay_local",
        category="opt_in",
        note="Peer-to-peer relay broker running on user-provided host",
    ),
    # Hosted capabilities (Synlynk bears cloud infra/operational cost)
    "hosted_relay": Capability(
        name="hosted_relay",
        category="hosted",
        hosted_key="hosted_relay",
        note="Synlynk-hosted cloud broker for distributed multi-seat relay",
    ),
    "audit_retention": Capability(
        name="audit_retention",
        category="hosted",
        min_edition="enterprise",
        hosted_key="audit_retention",
        note="Durable cloud audit log retention and export (Platform Vision Phase 1)",
    ),
    "sso": Capability(
        name="sso",
        category="hosted",
        min_edition="enterprise",
        hosted_key="sso",
        note="SAML / OIDC centralized authentication (Platform Vision Phase 1)",
    ),
    "rbac": Capability(
        name="rbac",
        category="hosted",
        min_edition="enterprise",
        hosted_key="rbac",
        note="Role-based access control across enterprise accounts (Platform Vision Phase 1)",
    ),
    "data_residency": Capability(
        name="data_residency",
        category="hosted",
        min_edition="enterprise",
        hosted_key="data_residency",
        note="Regional compliance data residency controls (Platform Vision Phase 1)",
    ),
    "swarm_cloud_provisioning": Capability(
        name="swarm_cloud_provisioning",
        category="hosted",
        hosted_key="swarm_cloud_provisioning",
        note="Dynamic cloud infrastructure provisioning for elastic swarms (Phase 4)",
    ),
}

DEFAULT_HOSTED_BY_EDITION: Dict[str, List[str]] = {
    "personal": [],
    "team": ["hosted_relay"],
    "enterprise": [
        "hosted_relay",
        "audit_retention",
        "sso",
        "rbac",
        "data_residency",
    ],
}


def check_edition(config: Dict[str, Any], capability_name: str) -> Tuple[bool, str]:
    """Check if the configured edition satisfies the capability's minimum edition.

    Args:
        config: Dict representing .synlynk/config.json content.
        capability_name: The registered capability name to check.

    Returns:
        (True, "") if allowed.
        (False, reason_string) if denied.

    Raises:
        KeyError: If capability_name is not registered in CAPABILITIES.
    """
    if capability_name not in CAPABILITIES:
        raise KeyError(f"Unknown capability '{capability_name}'")

    cap = CAPABILITIES[capability_name]
    if cap.min_edition is None:
        return True, ""

    cfg_edition = config.get("edition", "personal")
    if cfg_edition not in EDITION_ORDER:
        cfg_edition = "personal"

    try:
        current_rank = EDITION_ORDER.index(cfg_edition)
        required_rank = EDITION_ORDER.index(cap.min_edition)
    except ValueError:
        return False, f"Invalid edition comparison: '{cfg_edition}' vs '{cap.min_edition}'"

    if current_rank >= required_rank:
        return True, ""

    return False, f"Capability '{capability_name}' requires edition '{cap.min_edition}' or higher (configured: '{cfg_edition}')"


def check_hosted(config: Dict[str, Any], capability_name: str) -> Tuple[bool, str]:
    """Check if a hosted capability key is enabled in config['hosted'].

    Args:
        config: Dict representing .synlynk/config.json content.
        capability_name: The registered hosted capability name to check.

    Returns:
        (True, "") if enabled.
        (False, reason_string) if not enabled.

    Raises:
        KeyError: If capability_name is not registered.
        ValueError: If capability_name is not of category 'hosted'.
    """
    if capability_name not in CAPABILITIES:
        raise KeyError(f"Unknown capability '{capability_name}'")

    cap = CAPABILITIES[capability_name]
    if cap.category != "hosted":
        raise ValueError(f"Capability '{capability_name}' is not a 'hosted' capability (category: '{cap.category}')")

    hosted_list = config.get("hosted", [])
    if not isinstance(hosted_list, list):
        hosted_list = []

    if cap.hosted_key in hosted_list:
        return True, ""

    return False, f"Hosted capability '{cap.hosted_key}' is not enabled in config['hosted']"
