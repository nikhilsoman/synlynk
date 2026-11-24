def test_load_charter_reads_v3_yaml_file(tmp_path, monkeypatch):
    from synlynk.charter_core.yaml_subset import dump_yaml
    from synlynk.charter_migrate import migrate_v1_to_v3
    from synlynk.charters import DEFAULT_ROLE_CHARTERS, load_charter

    charters_dir = tmp_path / ".synlynk" / "charters"
    charters_dir.mkdir(parents=True)
    v3 = migrate_v1_to_v3("pm", DEFAULT_ROLE_CHARTERS["pm"])
    (charters_dir / "pm.yaml").write_text(dump_yaml(v3))

    monkeypatch.chdir(tmp_path)
    charter = load_charter("pm")

    assert charter.role == "pm"
    assert charter.mandate == DEFAULT_ROLE_CHARTERS["pm"]["mandate"]
    assert charter.schema_version == "3.0.0"
    assert charter.identity == {"app_ref": "github-app:pm"}
    assert charter.coordination == {"handoffs": []}
