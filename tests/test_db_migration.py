def test_harness_rename_migration_preserves_data(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import db

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE harness_records (
            agent_name TEXT PRIMARY KEY,
            harness_name TEXT NOT NULL,
            installed_version TEXT NOT NULL DEFAULT 'unknown',
            compliance_status TEXT NOT NULL DEFAULT 'unknown',
            active_contract TEXT NOT NULL DEFAULT '{}',
            active_flags TEXT NOT NULL DEFAULT '{}',
            last_probe_at TEXT,
            capability_hash TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "INSERT INTO harness_records VALUES ('claude', 'claude-cli', '1.2.0', 'ok', '{}', '{}', '2026-08-18', 'abc')"
    )
    conn.execute("""
        CREATE TABLE agent_quotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL, model TEXT NOT NULL DEFAULT 'unknown',
            quota_type TEXT NOT NULL, unit TEXT NOT NULL DEFAULT 'tokens',
            limit_tokens INTEGER NOT NULL, used_tokens INTEGER NOT NULL DEFAULT 0,
            reset_at TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent, model, quota_type, unit)
        )
    """)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, limit_tokens) VALUES ('codex', 'gpt-5', '5h', 100000)"
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    conn = db._get_db()
    db._run_harness_rename_migration(conn)
    conn.commit()

    cols = {row[1] for row in conn.execute("PRAGMA table_info(harness_records)")}
    assert "harness_name" in cols
    assert "agent_name" not in cols
    row = conn.execute("SELECT harness_name, installed_version FROM harness_records WHERE harness_name='claude-cli'").fetchone()
    assert row == ("claude-cli", "1.2.0")

    quota_cols = {row[1] for row in conn.execute("PRAGMA table_info(harness_quotas)")}
    assert "harness" in quota_cols
    assert "agent" not in quota_cols
    qrow = conn.execute("SELECT harness, model, limit_tokens FROM harness_quotas WHERE harness='codex'").fetchone()
    assert qrow == ("codex", "gpt-5", 100000)


def test_migrate_db_renames_pre_existing_agent_quotas_without_collision(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import db

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE agent_quotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL, model TEXT NOT NULL DEFAULT 'unknown',
            quota_type TEXT NOT NULL, unit TEXT NOT NULL DEFAULT 'tokens',
            limit_tokens INTEGER NOT NULL, used_tokens INTEGER NOT NULL DEFAULT 0,
            reset_at TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent, model, quota_type, unit)
        )
    """)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, limit_tokens) VALUES ('codex', 'gpt-5', '5h', 100000)"
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    conn = db._get_db()
    db._migrate_db(conn)
    conn.commit()

    quota_cols = {row[1] for row in conn.execute("PRAGMA table_info(harness_quotas)")}
    assert "harness" in quota_cols
    row = conn.execute(
        "SELECT harness, model, limit_tokens FROM harness_quotas WHERE harness='codex'"
    ).fetchone()
    assert row == ("codex", "gpt-5", 100000)
    assert not _table_exists_test_helper(conn, "agent_quotas")


def _table_exists_test_helper(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None
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
