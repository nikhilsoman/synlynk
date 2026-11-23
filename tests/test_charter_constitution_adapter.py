def test_validate_constitution_binding_rejects_unknown_tier():
    from synlynk.charter_constitution_adapter import validate_constitution_binding

    data = {
        "constitution_binding": {
            "tier_acknowledgements": ["t0-fake"],
            "law_refs": [],
            "evidence_ref": "state_db:capability_ratings",
        }
    }
    errors = validate_constitution_binding(data)
    assert any("t0-fake" in e for e in errors)


def test_validate_constitution_binding_accepts_real_tiers_and_law_refs():
    from synlynk.charter_constitution_adapter import validate_constitution_binding

    data = {
        "constitution_binding": {
            "tier_acknowledgements": ["injected", "cited"],
            "law_refs": [
                {"law_id": "law-0", "applies_to": "sop_step:1", "evidence_ref": "state_db:row:1"},
                {"law_id": "law-3", "applies_to": "sop_step:2", "evidence_ref": "state_db:row:2"},
            ],
            "evidence_ref": "state_db:capability_ratings",
        }
    }
    errors = validate_constitution_binding(data)
    assert errors == []


def test_validate_constitution_binding_rejects_unknown_law_id():
    from synlynk.charter_constitution_adapter import validate_constitution_binding

    data = {
        "constitution_binding": {
            "tier_acknowledgements": ["injected"],
            "law_refs": [{"law_id": "law-99", "applies_to": "sop_step:1", "evidence_ref": "x"}],
            "evidence_ref": "x",
        }
    }
    errors = validate_constitution_binding(data)
    assert any("law-99" in e for e in errors)


def test_validate_identity_requires_github_app_dir(tmp_path):
    from synlynk.charter_constitution_adapter import validate_identity

    repo = tmp_path
    (repo / ".synlynk" / "github_apps" / "pm").mkdir(parents=True)
    ok = validate_identity({"identity": {"app_ref": "github-app:pm"}}, repo_path=str(repo))
    assert ok == []

    missing = validate_identity({"identity": {"app_ref": "github-app:ghost"}}, repo_path=str(repo))
    assert any("ghost" in e for e in missing)
