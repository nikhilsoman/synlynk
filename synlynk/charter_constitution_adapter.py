"""Synlynk-specific semantic validation for Charter v3.0's constitution_binding and
identity blocks. This is deliberately NOT in synlynk/charter_core/ — it reads real
data from synlynk/constitution.py and .synlynk/github_apps/, which charter_core must
never import (standalone-extraction-readiness constraint)."""
from __future__ import annotations

import os

from synlynk.constitution import CONSTITUTION_LAWS, DeliveryTier

_VALID_TIERS = {tier.value for tier in DeliveryTier}


def validate_constitution_binding(data: dict) -> list:
    errors = []
    binding = data.get("constitution_binding", {})
    if not isinstance(binding, dict):
        return ["constitution_binding: expected a mapping"]

    for tier in binding.get("tier_acknowledgements", []):
        if tier not in _VALID_TIERS:
            errors.append(f"constitution_binding.tier_acknowledgements: '{tier}' is not a real DeliveryTier value {sorted(_VALID_TIERS)}")

    for i, ref in enumerate(binding.get("law_refs", [])):
        if not isinstance(ref, dict):
            errors.append(f"constitution_binding.law_refs[{i}]: expected a mapping")
            continue
        law_id = ref.get("law_id")
        if law_id not in CONSTITUTION_LAWS:
            errors.append(f"constitution_binding.law_refs[{i}]: law_id '{law_id}' is not a known law in constitution.CONSTITUTION_LAWS")
        if not ref.get("evidence_ref"):
            errors.append(f"constitution_binding.law_refs[{i}]: missing evidence_ref")

    if not binding.get("evidence_ref"):
        errors.append("constitution_binding: missing top-level evidence_ref")

    return errors


def validate_identity(data: dict, repo_path: str) -> list:
    identity = data.get("identity", {})
    app_ref = identity.get("app_ref", "")
    if not app_ref.startswith("github-app:"):
        return [f"identity.app_ref: '{app_ref}' is not a github-app: typed ref"]
    role = app_ref.split(":", 1)[1]
    app_dir = os.path.join(repo_path, ".synlynk", "github_apps", role)
    if not os.path.isdir(app_dir):
        return [f"identity.app_ref: no GitHub App record found for role '{role}' at {app_dir}"]
    return []
