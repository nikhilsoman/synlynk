def test_migration_dataclass_has_expected_fields():
    from synlynk.migrations import Migration

    def up(conn):
        pass

    m = Migration(version=16, name="example", up=up)
    assert m.version == 16
    assert m.name == "example"
    assert m.up is up


def test_m0029_adds_is_milestone_eligible_and_normalizes_known_rows(tmp_path):
    import sqlite3
    from synlynk.migrations.m0029_roadmap_arcs_milestone_eligibility import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE roadmap_arcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            title TEXT, status TEXT DEFAULT 'planned',
            target_date TEXT, notes TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arc_version TEXT NOT NULL REFERENCES roadmap_arcs(version),
            phase_title TEXT NOT NULL, status TEXT DEFAULT 'planned',
            priority TEXT, story_id TEXT, notes TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            epic_id INTEGER REFERENCES roadmap_arcs(id)
        )"""
    )
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('v1.0.0', 'First release')")
    v1_id = conn.execute(
        "SELECT id FROM roadmap_arcs WHERE version='v1.0.0'"
    ).fetchone()[0]
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('1.0.0', 'First release dupe')")
    dupe_id = conn.execute(
        "SELECT id FROM roadmap_arcs WHERE version='1.0.0'"
    ).fetchone()[0]
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('Future Expansions', 'placeholder')")
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('v0.1–v0.3.0', 'early range')")
    conn.execute(
        "INSERT INTO roadmap_phases (arc_version, phase_title) VALUES ('1.0.0', 'phase on dupe')"
    )
    conn.execute("INSERT INTO cost_entries (epic_id) VALUES (?)", (dupe_id,))
    conn.commit()

    MIGRATION.up(conn)
    conn.commit()

    cols = {row[1] for row in conn.execute("PRAGMA table_info(roadmap_arcs)")}
    assert "is_milestone_eligible" in cols

    rows = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT version, is_milestone_eligible FROM roadmap_arcs"
        )
    }
    assert rows["v1.0.0"] == 1
    assert rows["Future Expansions"] == 0
    assert rows["v0.1–v0.3.0"] == 0
    assert "1.0.0" not in rows

    assert conn.execute(
        "SELECT arc_version FROM roadmap_phases WHERE phase_title='phase on dupe'"
    ).fetchone()[0] == "v1.0.0"
    assert conn.execute("SELECT epic_id FROM cost_entries").fetchone()[0] == v1_id
    conn.close()


def test_m0029_is_idempotent(tmp_path):
    import sqlite3
    from synlynk.migrations.m0029_roadmap_arcs_milestone_eligibility import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE roadmap_arcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            title TEXT, status TEXT DEFAULT 'planned',
            target_date TEXT, notes TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arc_version TEXT NOT NULL REFERENCES roadmap_arcs(version),
            phase_title TEXT NOT NULL, status TEXT DEFAULT 'planned',
            priority TEXT, story_id TEXT, notes TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            epic_id INTEGER REFERENCES roadmap_arcs(id)
        )"""
    )
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('v1.0.0', 'First release')")
    conn.commit()

    MIGRATION.up(conn)
    MIGRATION.up(conn)
    conn.commit()

    assert conn.execute(
        "SELECT COUNT(*) FROM roadmap_arcs WHERE version='v1.0.0'"
    ).fetchone()[0] == 1
    conn.close()


def test_m0030_creates_github_sync_map_table(tmp_path):
    import sqlite3
    from synlynk.migrations.m0030_github_sync_map import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    MIGRATION.up(conn)
    conn.commit()

    cols = {row[1] for row in conn.execute("PRAGMA table_info(github_sync_map)")}
    assert cols == {
        "entity_type", "entity_id", "github_number", "github_node_id",
        "content_hash", "last_synced_at",
    }

    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number, content_hash) "
        "VALUES ('roadmap_arc', '7', 42, 'abc123')"
    )
    conn.commit()
    row = conn.execute(
        "SELECT github_number, content_hash FROM github_sync_map "
        "WHERE entity_type='roadmap_arc' AND entity_id='7'"
    ).fetchone()
    assert row == (42, "abc123")
    conn.close()


def test_m0030_entity_type_and_id_are_primary_key(tmp_path):
    import sqlite3
    from synlynk.migrations.m0030_github_sync_map import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    MIGRATION.up(conn)
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('story', 'story-abc', 10)"
    )
    conn.commit()
    with __import__("pytest").raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
            "VALUES ('story', 'story-abc', 99)"
        )
    conn.close()


def test_m0030_is_idempotent(tmp_path):
    import sqlite3
    from synlynk.migrations.m0030_github_sync_map import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    MIGRATION.up(conn)
    MIGRATION.up(conn)
    conn.commit()
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='github_sync_map'"
    ).fetchone()
    assert row is not None
    conn.close()


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


def test_migration_0016_adds_cost_entries_pr_number_column(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.migrations import runner
    from synlynk.migrations.m0016_cost_entries_pr_number import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY,
            job_id TEXT
        )"""
    )
    conn.execute("PRAGMA user_version = 15")
    conn.commit()

    monkeypatch.setattr(runner, "MIGRATIONS", [MIGRATION])
    runner.run_pending_migrations(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    assert "pr_number" in cols
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 16

    # Re-running against an already-migrated db is a no-op, not a crash.
    runner.run_pending_migrations(conn)
    cols_after = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    assert cols_after == cols
    conn.close()


def test_migration_0017_adds_typed_task_metadata_to_existing_jobs(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.migrations import runner
    from synlynk.migrations.m0017_daemon_job_purpose import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY)")
    conn.execute("PRAGMA user_version = 16")
    conn.commit()

    monkeypatch.setattr(runner, "MIGRATIONS", [MIGRATION])
    runner.run_pending_migrations(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    assert {"task_type", "task_type_explicit", "purpose"} <= cols
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 17
    conn.close()


def test_m0019_creates_policy_gate_events_table(tmp_path):
    import sqlite3
    from synlynk.migrations.m0019_policy_gate_events import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 18")
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


def test_m0019_is_idempotent(tmp_path):
    import sqlite3
    from synlynk.migrations.m0019_policy_gate_events import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 18")
    MIGRATION.up(conn)
    MIGRATION.up(conn)
    conn.commit()
