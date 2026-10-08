from synlynk.config_schema import validate, WORKSPACE_SCHEMA, BILLING_SCHEMA, POLICY_SCHEMA


def test_workspace_schema_accepts_valid_document():
    doc = {"schema_version": 1, "workspace_id": "ws-1", "local_fallback": "agy"}
    assert validate(doc, WORKSPACE_SCHEMA) == []


def test_workspace_schema_rejects_missing_schema_version():
    doc = {"workspace_id": "ws-1"}
    errors = validate(doc, WORKSPACE_SCHEMA)
    assert any("schema_version" in e for e in errors)


def test_billing_schema_accepts_valid_document():
    doc = {
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "harness_billing": {},
    }
    assert validate(doc, BILLING_SCHEMA) == []


def test_billing_schema_rejects_wrong_budget_type():
    doc = {"schema_version": 1, "budget": "not-a-dict", "harness_billing": {}}
    errors = validate(doc, BILLING_SCHEMA)
    assert any("budget" in e for e in errors)


def test_policy_schema_accepts_migrated_fields():
    doc = {
        "schema_version": 1,
        "repo_id": "synlynk",
        "qa_gate_mode": "block-only",
        "roles": {"claude": ["pm", "review"]},
        "story_classification": {"method": "heuristic"},
        "sentinel": {"dedup_window_seconds": 86400},
    }
    assert validate(doc, POLICY_SCHEMA) == []


def test_policy_schema_rejects_bad_qa_gate_mode_type():
    doc = {"schema_version": 1, "repo_id": "synlynk", "qa_gate_mode": 123}
    errors = validate(doc, POLICY_SCHEMA)
    assert any("qa_gate_mode" in e for e in errors)
