from synlynk.config_schema import validate, CONFIG_SCHEMA, POLICY_SCHEMA


def test_valid_config_produces_no_errors():
    data = {"identity_slug": "synlynk", "local_fallback": "agy", "local_auto_threshold": 0.5}
    assert validate(data, CONFIG_SCHEMA) == []


def test_wrong_type_is_reported():
    data = {"identity_slug": 123}
    errors = validate(data, CONFIG_SCHEMA)
    assert any("identity_slug" in e and "type" in e for e in errors)


def test_missing_required_key_is_reported():
    errors = validate({}, POLICY_SCHEMA)
    assert any("schema_version" in e for e in errors)


def test_invalid_enum_value_is_reported():
    data = {"schema_version": 1, "repo_id": "x", "capability_policy": {"mode": "not-a-real-mode"}}
    errors = validate(data, POLICY_SCHEMA)
    assert any("mode" in e for e in errors)
