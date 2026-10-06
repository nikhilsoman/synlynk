def test_migration_dataclass_has_expected_fields():
    from synlynk.migrations import Migration

    def up(conn):
        pass

    m = Migration(version=16, name="example", up=up)
    assert m.version == 16
    assert m.name == "example"
    assert m.up is up


def test_run_pending_migrations_creates_history_table_when_registry_empty(tmp_path):
    import sqlite3
    from synlynk.migrations.runner import run_pending_migrations

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 15")
    run_pending_migrations(conn)

    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='migration_history'"
    ).fetchone()
    assert row is not None
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 15
    conn.close()
