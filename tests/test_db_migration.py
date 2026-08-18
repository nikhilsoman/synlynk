def test_registry_v2_tables_exist(tmp_path, monkeypatch):
    from synlynk import db
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    for tbl in (
        "harness_models", "harness_modes",
        "capability_calibration_tasks", "capability_calibration_results",
    ):
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        assert row is not None, f"{tbl} not created"
