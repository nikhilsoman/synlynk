"""Minimal, stdlib-only schema validation for .synlynk/config.json and policy.json.

No jsonschema dependency (pyproject.toml declares dependencies=[]). The key
set in both files is small and known, so a hand-rolled type/required/enum
checker covers the real failure modes (wrong type, missing key, bad enum)
without implementing $ref resolution or other full-JSON-Schema machinery.
"""

from __future__ import annotations

_MISSING = object()


def _check_field(data: dict, key: str, spec: dict, path: str, errors: list) -> None:
    value = data.get(key, _MISSING)
    if value is _MISSING:
        if spec.get("required"):
            errors.append(f"{path}{key}: required field is missing")
        return
    expected_type = spec.get("type")
    if expected_type and not isinstance(value, expected_type):
        type_name = getattr(expected_type, "__name__", str(expected_type))
        errors.append(f"{path}{key}: expected type {type_name}, got {type(value).__name__}")
        return
    enum = spec.get("enum")
    if enum and value not in enum:
        errors.append(f"{path}{key}: value {value!r} not in allowed set {enum}")
    nested = spec.get("fields")
    if nested and isinstance(value, dict):
        validate_fields(value, nested, path=f"{path}{key}.", errors=errors)


def validate_fields(data: dict, schema_fields: dict, *, path: str = "", errors: list = None) -> list:
    errors = errors if errors is not None else []
    for key, spec in schema_fields.items():
        _check_field(data, key, spec, path, errors)
    return errors


def validate(data: dict, schema: dict) -> list:
    """Return a list of human-readable error strings; empty means valid."""
    if not isinstance(data, dict):
        return [f"root: expected a JSON object, got {type(data).__name__}"]
    return validate_fields(data, schema["fields"])


# Stable nested shapes from load_config() schema-v1 defaults and the live
# .synlynk/config.json contract. Harness names under harness_billing vary
# (claude/codex/agy/grok/local and others), so only the object type is fixed.
_BUDGET_FIELDS = {
    "limit_usd": {"type": (int, float), "required": True},
    "limit_requests": {"type": int, "required": True},
}

CONFIG_SCHEMA = {
    "fields": {
        "schema_version": {"type": int, "required": True},
        "budget": {"type": dict, "required": True, "fields": _BUDGET_FIELDS},
        "harness_billing": {"type": dict, "required": True},
        "workspace_id": {"type": str, "required": True},
        "identity_slug": {"type": str},
        "local_fallback": {"type": str},
        "local_auto_threshold": {"type": (int, float)},
    }
}

POLICY_SCHEMA = {
    "fields": {
        "schema_version": {"type": int, "required": True},
        "repo_id": {"type": str, "required": True},
        "capability_policy": {
            "type": dict,
            "fields": {
                "mode": {"type": str, "enum": ["empirical", "heuristic"]},
                "min_sample_size": {"type": int},
            },
        },
        "overrides": {"type": dict},
    }
}
