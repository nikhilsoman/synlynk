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


def test_migrate_v2_to_v3_preserves_sfia_and_governance_fields():
    from synlynk.charter_migrate import migrate_v2_to_v3

    tpm_v2 = {
        "schema_version": "2.0",
        "role": "tpm",
        "mandate": "Own technical program sequencing.",
        "sfia_mapping": {"sfia_code": "PROG", "sfia_level": 5},
        "boundaries": ["no_direct_prod_deploy"],
        "coordination_pattern": "orchestrator",
        "tools": [{"id": "gh_write", "scope": "pr", "mode": "allow"}],
        "credentials": [{"secret_ref": "env:GH_TOKEN"}],
        "evidence_contracts": ["capability_ratings_row"],
    }
    v3 = migrate_v2_to_v3("tpm", tpm_v2)

    assert v3["core"]["charter_id"] == "tpm"
    assert v3["core"]["mandate"] == tpm_v2["mandate"]
    assert v3["sfia_mapping"] == tpm_v2["sfia_mapping"]
    assert v3["boundaries"] == tpm_v2["boundaries"]
    assert v3["governance"]["tools"] == tpm_v2["tools"]
    assert v3["governance"]["credentials"] == tpm_v2["credentials"]
    assert v3["governance"]["evidence_contracts"] == tpm_v2["evidence_contracts"]
    assert v3["coordination"]["handoffs"] == []
    assert v3["migration_provenance"]["source_schema"] == "v2.0"
    # coordination_pattern's old string value is preserved, not discarded, under extensions.
    assert v3["extensions"]["legacy_v2"]["coordination_pattern"] == "orchestrator"
