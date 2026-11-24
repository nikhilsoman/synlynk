"""Deterministic migration of legacy v1/v2.0 charters into the Charter v3.0 shape.

Per the migration strategy in docs/superpowers/specs/2026-11-24-charter-v3-schema-design.md:
- v1 charters (DEFAULT_ROLE_CHARTERS / .synlynk/charters/<role>.json without schema_version)
  get empty-but-valid reserved blocks added.
- v2.0 SFIA charters (schema_version: "2.0", tpm.json/wingman.json) carry their existing
  sfia_mapping/boundaries/governance-shaped fields forward unchanged.
No v1/v2 content is dropped; round-trip tests in this file's test module assert that.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from synlynk.charter_core.yaml_subset import dump_yaml
from synlynk.charters import DEFAULT_ROLE_CHARTERS


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def migrate_v1_to_v3(role: str, v1_data: dict) -> dict:
    return {
        "schema_version": "3.0.0",
        "core": {
            "charter_id": role,
            "mandate": v1_data.get("mandate", ""),
            "authorities": list(v1_data.get("autonomous_authorities", [])),
            "escalation": list(v1_data.get("escalation_triggers", [])),
            "sop": list(v1_data.get("wake_cycle_sop", [])),
        },
        "governance": {
            "tools": list(v1_data.get("tools", [])),
            "credentials": list(v1_data.get("credentials", [])),
            "evidence_contracts": list(v1_data.get("verification_contracts", [])),
        },
        "identity": {"app_ref": f"github-app:{role}"},
        "coordination": {"handoffs": []},
        "constitution_binding": {
            "tier_acknowledgements": [],
            "law_refs": [],
            "evidence_ref": "",
        },
        "requirements": {"task_types": []},
        "extensions": {},
        "migration_provenance": {
            "source_schema": "v1",
            "migrated_at": _now_iso(),
            "source_fields_dropped": [],
        },
    }


def migrate_v2_to_v3(role: str, v2_data: dict) -> dict:
    return {
        "schema_version": "3.0.0",
        "core": {
            "charter_id": role,
            "mandate": v2_data.get("mandate", ""),
            "authorities": list(v2_data.get("autonomous_authorities", [])),
            "escalation": list(v2_data.get("escalation_triggers", [])),
            "sop": list(v2_data.get("wake_cycle_sop", [])),
        },
        "sfia_mapping": v2_data.get("sfia_mapping"),
        "boundaries": list(v2_data.get("boundaries", [])),
        "governance": {
            "tools": list(v2_data.get("tools", [])),
            "credentials": list(v2_data.get("credentials", [])),
            "evidence_contracts": list(v2_data.get("evidence_contracts", [])),
        },
        "identity": {"app_ref": f"github-app:{role}"},
        "coordination": {"handoffs": []},
        "constitution_binding": {
            "tier_acknowledgements": [],
            "law_refs": [],
            "evidence_ref": "",
        },
        "requirements": {"task_types": []},
        "extensions": {
            "legacy_v2": {"coordination_pattern": v2_data.get("coordination_pattern")},
        },
        "migration_provenance": {
            "source_schema": "v2.0",
            "migrated_at": _now_iso(),
            "source_fields_dropped": [],
        },
    }


def cmd_charter_migrate(role: str, apply: bool = False, charters_dir: str = None) -> dict:
    """Migrate one role's v1 charter to v3. Returns a result dict; writes a file only if apply=True."""
    if role not in DEFAULT_ROLE_CHARTERS:
        raise ValueError(f"unknown role for migration: {role!r}")

    v1_data = DEFAULT_ROLE_CHARTERS[role]
    migrated = migrate_v1_to_v3(role, v1_data)

    if apply:
        if not charters_dir:
            raise ValueError("charters_dir is required when apply=True")
        os.makedirs(charters_dir, exist_ok=True)
        out_path = os.path.join(charters_dir, f"{role}.v3.yaml")
        with open(out_path, "w") as f:
            f.write(dump_yaml(migrated))

    return {"role": role, "applied": apply, "migrated": migrated}
