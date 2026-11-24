from synlynk.charter_core.schema import validate_structure


def _valid_charter():
    return {
        "schema_version": "3.0.0",
        "core": {
            "charter_id": "pm",
            "mandate": "Own portfolio goal alignment.",
            "authorities": ["sweep_goals"],
            "escalation": ["budget_exceeded"],
            "sop": ["1. Sweep goals."],
        },
        "governance": {"tools": [], "credentials": [], "evidence_contracts": []},
        "identity": {"app_ref": "github-app:pm"},
        "coordination": {"handoffs": []},
        "constitution_binding": {
            "tier_acknowledgements": ["injected", "cited"],
            "law_refs": [],
            "evidence_ref": "state_db:capability_ratings",
        },
        "requirements": {"task_types": ["pm"]},
        "extensions": {},
        "migration_provenance": {
            "source_schema": "v1",
            "migrated_at": "2026-11-24T00:00:00Z",
        },
    }


def test_validate_structure_rejects_missing_core_block():
    errors = validate_structure({"schema_version": "3.0.0"}, known_roles=["pm", "dev"])
    assert any("core" in error for error in errors)


def test_validate_structure_accepts_minimal_valid_charter():
    assert validate_structure(_valid_charter(), known_roles=["pm", "dev"]) == []


def test_validate_structure_rejects_handoff_to_unknown_role():
    data = _valid_charter()
    data["coordination"]["handoffs"] = [
        {"to_role": "ghost", "operation": "delegate", "transport": "dispatch_job"}
    ]

    errors = validate_structure(data, known_roles=["pm", "dev"])

    assert any("ghost" in error for error in errors)
