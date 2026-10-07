from synlynk.config_schema import validate, CONFIG_SCHEMA, POLICY_SCHEMA


def _valid_config():
    return {
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "harness_billing": {
            "grok": {
                "payment_mode": "subscription",
                "monthly_base_fee_usd": 30.0,
                "projected_monthly_tokens": 10_000_000,
                "allow_extra_usage": False,
            }
        },
        "workspace_id": "2a6aa76a-94fb-4a45-9350-9fc71ec3bac8",
        "identity_slug": "synlynk",
        "local_fallback": "agy",
        "local_auto_threshold": 0.5,
    }


def test_valid_config_produces_no_errors():
    assert validate(_valid_config(), CONFIG_SCHEMA) == []


def test_wrong_type_is_reported():
    data = {"identity_slug": 123}
    errors = validate(data, CONFIG_SCHEMA)
    assert any("identity_slug" in e and "type" in e for e in errors)


def test_missing_required_key_is_reported():
    errors = validate({}, POLICY_SCHEMA)
    assert any("schema_version" in e for e in errors)


def test_config_missing_required_top_level_field_fails_validation():
    """A config that omits a live required field must not validate as OK.

    validate({"budget": 1}, CONFIG_SCHEMA) used to return [] because
    schema_version, budget, harness_billing, and workspace_id were undeclared.
    """
    errors = validate({"budget": 1}, CONFIG_SCHEMA)
    assert errors
    assert any("schema_version" in e and "required" in e for e in errors)
    assert any("harness_billing" in e and "required" in e for e in errors)
    assert any("workspace_id" in e and "required" in e for e in errors)
    assert any("budget" in e and "type" in e for e in errors)


def test_invalid_enum_value_is_reported():
    data = {"schema_version": 1, "repo_id": "x", "capability_policy": {"mode": "not-a-real-mode"}}
    errors = validate(data, POLICY_SCHEMA)
    assert any("mode" in e for e in errors)
