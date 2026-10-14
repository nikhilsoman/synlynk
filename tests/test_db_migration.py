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


def test_v10_reconciles_databases_stamped_at_v9(tmp_path):
    """A v9 ledger may predate columns added inside the v9 migration block."""
    import sqlite3
    from synlynk import db
    from synlynk.migrations import runner

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 9")
    db._migrate_db(conn)

    watch_cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_watch)")}
    daemon_cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    final_version = max(m.version for m in runner.MIGRATIONS)
    assert {"last_sweep_at", "sweep_job_count"} <= watch_cols
    assert conn.execute("PRAGMA user_version").fetchone()[0] == final_version
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()


def _table_exists_test_helper(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def test_harness_model_catalog_migration_is_idempotent_and_backfills_provider(tmp_path):
    import sqlite3
    from synlynk.migrations.m0021_harness_model_catalog import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("""CREATE TABLE harness_models (
        harness_name TEXT NOT NULL, model_id TEXT NOT NULL,
        first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active', superseded_by TEXT,
        discovery_source TEXT NOT NULL DEFAULT 'curated',
        PRIMARY KEY (harness_name, model_id))""")
    conn.execute("INSERT INTO harness_models VALUES ('codex', 'gpt-test', '2026-01-01', '2026-02-01', 'active', NULL, 'probe')")
    MIGRATION.up(conn)
    MIGRATION.up(conn)

    info = conn.execute("PRAGMA table_info(harness_models)").fetchall()
    pk = tuple(row[1] for row in sorted((r for r in info if r[5]), key=lambda r: r[5]))
    assert pk == ("harness_name", "model_id", "provider")
    row = conn.execute("SELECT provider, discovered_at FROM harness_models").fetchone()
    assert row == ("native", "2026-02-01")
    assert conn.execute("SELECT COUNT(*) FROM harness_models").fetchone()[0] == 1


def test_harness_model_upsert_and_active_read_round_trip(tmp_path, monkeypatch):
    from synlynk import db

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    db.upsert_harness_model(
        conn, "codex", "gpt-catalog", provider="openai", rate_input_per_mtok=2.5,
        rate_output_per_mtok=10.0, rate_cache_read_per_mtok=0.25,
        rate_cache_write_per_mtok=3.0, rate_tool_use_per_mtok=1.5,
        rate_currency="usd", rate_source="official", complexity_tier="high",
        max_effort_level="xhigh", context_window_tokens=256000,
        max_output_tokens=32000, discovered_at="2026-10-14T10:00:00+00:00",
    )
    db.upsert_harness_model(
        conn, "codex", "inactive", status="inactive", complexity_tier="high",
        discovered_at="2026-10-14T11:00:00+00:00",
    )
    row = db.get_active_harness_models(conn, harness="codex", tier="high")[0]
    assert row["provider"] == "openai"
    assert row["rate_input_per_mtok"] == 2.5
    assert row["rate_output_per_mtok"] == 10.0
    assert row["rate_cache_read_per_mtok"] == 0.25
    assert row["rate_cache_write_per_mtok"] == 3.0
    assert row["rate_tool_use_per_mtok"] == 1.5
    assert row["rate_currency"] == "usd"
    assert row["rate_source"] == "official"
    assert row["complexity_tier"] == "high"
    assert row["max_effort_level"] == "xhigh"
    assert row["context_window_tokens"] == 256000
    assert row["max_output_tokens"] == 32000
    assert row["discovered_at"] == "2026-10-14T10:00:00+00:00"
    assert db.get_active_harness_models(conn, harness="codex", tier="low") == []
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


def test_migrate_db_delegates_to_legacy_function_and_runner(tmp_path, monkeypatch):
    """Regression guard for the Component 1 rename: _migrate_db must still
    bring a fresh DB to the current version AND leave a migration_history
    table behind (proof run_pending_migrations actually ran)."""
    from synlynk import db
    from synlynk.migrations import runner

    db_path = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    conn = db._get_db()

    final_version = max(m.version for m in runner.MIGRATIONS)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == final_version
    history_row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='migration_history'"
    ).fetchone()
    assert history_row is not None
    assert hasattr(db, "_run_legacy_migration_and_repairs")


def test_fresh_db_has_unpushed_branch_check_attempts_column(tmp_path, monkeypatch):
    from synlynk import db

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()

    cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}

    assert "unpushed_branch_check_attempts" in cols
