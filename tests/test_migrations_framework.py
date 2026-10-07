def test_migration_dataclass_has_expected_fields():
    from synlynk.migrations import Migration

    def up(conn):
        pass

    m = Migration(version=16, name="example", up=up)
    assert m.version == 16
    assert m.name == "example"
    assert m.up is up


def test_run_pending_migrations_creates_history_table_when_registry_empty(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.migrations import runner

    monkeypatch.setattr(runner, "MIGRATIONS", [])

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 15")
    runner.run_pending_migrations(conn)

    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='migration_history'"
    ).fetchone()
    assert row is not None
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 15
    conn.close()


def test_run_pending_migrations_applies_pending_migration_in_order(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.migrations import Migration
    from synlynk.migrations import runner

    applied = []

    def up_16(conn):
        conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY)")
        applied.append(16)

    def up_17(conn):
        conn.execute("ALTER TABLE widgets ADD COLUMN name TEXT")
        applied.append(17)

    monkeypatch.setattr(
        runner,
        "MIGRATIONS",
        [
            Migration(version=17, name="add_widgets_name", up=up_17),
            Migration(version=16, name="create_widgets", up=up_16),
        ],
    )

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 15")
    runner.run_pending_migrations(conn)

    assert applied == [16, 17]
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 17
    cols = {row[1] for row in conn.execute("PRAGMA table_info(widgets)")}
    assert cols == {"id", "name"}
    history = conn.execute(
        "SELECT version, name FROM migration_history ORDER BY version"
    ).fetchall()
    assert history == [(16, "create_widgets"), (17, "add_widgets_name")]

    # Re-running is a no-op (retry-safety).
    runner.run_pending_migrations(conn)
    assert applied == [16, 17]
    conn.close()


def test_migration_0016_adds_cost_entries_pr_number_column(tmp_path):
    import sqlite3
    from synlynk.migrations.runner import run_pending_migrations

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY,
            job_id TEXT
        )"""
    )
    conn.execute("PRAGMA user_version = 15")
    conn.commit()

    run_pending_migrations(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    assert "pr_number" in cols
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 18

    # Re-running against an already-migrated db is a no-op, not a crash.
    run_pending_migrations(conn)
    cols_after = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    assert cols_after == cols
    conn.close()


def test_migration_0017_adds_typed_task_metadata_to_existing_jobs(tmp_path):
    import sqlite3
    from synlynk.migrations.runner import run_pending_migrations

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY)")
    conn.execute("PRAGMA user_version = 16")
    conn.commit()

    run_pending_migrations(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    assert {"task_type", "task_type_explicit", "purpose"} <= cols
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 18
    conn.close()


def test_m0018_creates_policy_gate_events_table(tmp_path):
    import sqlite3
    from synlynk.migrations.m0018_policy_gate_events import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 17")
    MIGRATION.up(conn)
    conn.commit()

    cols = {row[1] for row in conn.execute("PRAGMA table_info(policy_gate_events)")}
    assert cols == {"id", "pr_number", "gate", "mode", "verdict", "detail", "recorded_at"}

    conn.execute(
        "INSERT INTO policy_gate_events (pr_number, gate, mode, verdict, detail, recorded_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (2100, "governs_authority", "observe", "pass", "no violations", "2026-10-07T00:00:00+00:00"),
    )
    conn.commit()
    row = conn.execute("SELECT pr_number, gate, verdict FROM policy_gate_events").fetchone()
    assert row == (2100, "governs_authority", "pass")


def test_m0018_is_idempotent(tmp_path):
    import sqlite3
    from synlynk.migrations.m0018_policy_gate_events import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 17")
    MIGRATION.up(conn)
    MIGRATION.up(conn)
    conn.commit()
