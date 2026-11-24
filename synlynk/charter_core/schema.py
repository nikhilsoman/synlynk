"""Charter v3.0 structural schema validation.

This module validates shape and enum values only.  Semantic checks that need
Synlynk-specific state belong in an adapter layer, keeping this core suitable
for standalone extraction.
"""
from __future__ import annotations


CHARTER_V3_REQUIRED_BLOCKS = (
    "schema_version",
    "core",
    "governance",
    "identity",
    "coordination",
    "constitution_binding",
    "requirements",
    "extensions",
    "migration_provenance",
)

CHARTER_V3_REQUIRED_CORE_KEYS = (
    "charter_id",
    "mandate",
    "authorities",
    "escalation",
    "sop",
)
CHARTER_V3_REQUIRED_GOVERNANCE_KEYS = (
    "tools",
    "credentials",
    "evidence_contracts",
)
CHARTER_V3_REQUIRED_CONSTITUTION_KEYS = (
    "tier_acknowledgements",
    "law_refs",
    "evidence_ref",
)

VALID_OPERATIONS = ("delegate", "request", "notify", "escalate")
VALID_TRANSPORTS = (
    "dispatch_job",
    "gh_pr_comment",
    "gh_issue",
    "state_db_table",
    "queue",
)
VALID_AUTONOMY_LEVELS = ("none", "supervised", "scoped", "full")


def validate_structure(data: dict, known_roles: list) -> list[str]:
    """Return structural validation errors; an empty list means valid.

    The validator deliberately reports all independently discoverable errors
    rather than failing on the first missing or malformed block.
    """
    errors = []

    if not isinstance(data, dict):
        return ["charter: expected a mapping"]

    for block in CHARTER_V3_REQUIRED_BLOCKS:
        if block not in data:
            errors.append(f"missing required top-level block: 'core' chain -> '{block}'")

    core = data.get("core", {})
    if isinstance(core, dict):
        for key in CHARTER_V3_REQUIRED_CORE_KEYS:
            if key not in core:
                errors.append(f"core: missing required key '{key}'")
    elif "core" in data:
        errors.append("core: expected a mapping")

    governance = data.get("governance", {})
    if isinstance(governance, dict):
        for key in CHARTER_V3_REQUIRED_GOVERNANCE_KEYS:
            if key not in governance:
                errors.append(f"governance: missing required key '{key}'")
    elif "governance" in data:
        errors.append("governance: expected a mapping")

    identity = data.get("identity", {})
    if isinstance(identity, dict):
        if "app_ref" not in identity:
            errors.append("identity: missing required key 'app_ref'")
        elif not isinstance(identity["app_ref"], str) or ":" not in identity["app_ref"]:
            errors.append("identity.app_ref: must be a typed URI string, e.g. 'github-app:<role>'")
    elif "identity" in data:
        errors.append("identity: expected a mapping")

    coordination = data.get("coordination", {})
    if isinstance(coordination, dict):
        handoffs = coordination.get("handoffs", [])
        if not isinstance(handoffs, list):
            errors.append("coordination.handoffs: expected a list")
        else:
            for i, edge in enumerate(handoffs):
                if not isinstance(edge, dict):
                    errors.append(f"coordination.handoffs[{i}]: expected a mapping")
                    continue
                to_role = edge.get("to_role")
                if to_role not in known_roles:
                    errors.append(
                        f"coordination.handoffs[{i}]: to_role '{to_role}' is not a known role"
                    )
                operation = edge.get("operation")
                if operation not in VALID_OPERATIONS:
                    errors.append(
                        f"coordination.handoffs[{i}]: operation '{operation}' not in {VALID_OPERATIONS}"
                    )
                transport = edge.get("transport")
                if transport not in VALID_TRANSPORTS:
                    errors.append(
                        f"coordination.handoffs[{i}]: transport '{transport}' not in {VALID_TRANSPORTS}"
                    )
    elif "coordination" in data:
        errors.append("coordination: expected a mapping")

    constitution_binding = data.get("constitution_binding", {})
    if isinstance(constitution_binding, dict):
        for key in CHARTER_V3_REQUIRED_CONSTITUTION_KEYS:
            if key not in constitution_binding:
                errors.append(f"constitution_binding: missing required key '{key}'")
    elif "constitution_binding" in data:
        errors.append("constitution_binding: expected a mapping")

    requirements = data.get("requirements", {})
    if isinstance(requirements, dict):
        if "task_types" not in requirements:
            errors.append("requirements: missing required key 'task_types'")
    elif "requirements" in data:
        errors.append("requirements: expected a mapping")

    return errors
