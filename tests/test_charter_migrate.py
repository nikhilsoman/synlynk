def test_migrate_v1_to_v3_preserves_pm_content_and_adds_reserved_blocks():
    from synlynk.charter_migrate import migrate_v1_to_v3
    from synlynk.charters import DEFAULT_ROLE_CHARTERS

    pm_v1 = DEFAULT_ROLE_CHARTERS["pm"]
    v3 = migrate_v1_to_v3("pm", pm_v1)

    assert v3["schema_version"].startswith("3.")
    assert v3["core"]["charter_id"] == "pm"
    assert v3["core"]["mandate"] == pm_v1["mandate"]
    assert v3["core"]["authorities"] == pm_v1["autonomous_authorities"]
    assert v3["core"]["escalation"] == pm_v1["escalation_triggers"]
    assert v3["core"]["sop"] == pm_v1["wake_cycle_sop"]
    # Reserved blocks exist even though v1 had no data for them.
    assert v3["governance"] == {"tools": [], "credentials": [], "evidence_contracts": []}
    assert v3["identity"] == {"app_ref": "github-app:pm"}
    assert v3["coordination"] == {"handoffs": []}
    assert v3["constitution_binding"]["tier_acknowledgements"] == []
    assert v3["requirements"]["task_types"] == []
    assert v3["extensions"] == {}
    assert v3["migration_provenance"]["source_schema"] == "v1"
