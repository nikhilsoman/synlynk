import sqlite3


def test_migration_adds_compaction_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY,
            harness TEXT,
            tokens_in INTEGER,
            tokens_out INTEGER,
            total_cost_usd REAL
        )
    """)
    conn.execute("INSERT INTO cost_entries (harness, tokens_in, tokens_out, total_cost_usd) VALUES ('claude', 100, 50, 0.01)")
    conn.commit()
    conn.close()

    from synlynk import migrate_cost_entries_for_compaction
    migrate_cost_entries_for_compaction(str(db_path))

    conn = sqlite3.connect(db_path)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")]
    assert "compaction_event_type" in cols

    row = conn.execute("SELECT compaction_event_type FROM cost_entries").fetchone()
    assert row[0] is None  # existing rows get NULL event type, not retroactively guessed
    conn.close()


def test_migration_idempotent(tmp_path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE cost_entries (id INTEGER PRIMARY KEY, harness TEXT)")
    conn.commit()
    conn.close()

    from synlynk import migrate_cost_entries_for_compaction
    migrate_cost_entries_for_compaction(str(db_path))
    migrate_cost_entries_for_compaction(str(db_path))  # second call must not raise

    conn = sqlite3.connect(db_path)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")]
    assert cols.count("compaction_event_type") == 1
    conn.close()


def test_log_cost_entry_writes_compaction_event_type(tmp_path):
    db_path = tmp_path / "state.db"
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY,
            harness TEXT,
            tokens_in INTEGER,
            tokens_out INTEGER,
            total_cost_usd REAL,
            compaction_event_type TEXT
        )
    """)
    conn.commit()
    conn.close()

    from synlynk import log_cost_entry
    log_cost_entry(str(db_path), harness="claude", tokens_in=10, tokens_out=5, total_cost_usd=0.001)
    log_cost_entry(str(db_path), harness="claude", tokens_in=1, tokens_out=1, total_cost_usd=0.0001,
                   compaction_event_type="checkpoint")

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT compaction_event_type FROM cost_entries ORDER BY id").fetchall()
    assert rows[0][0] is None       # ordinary row, not a compaction event
    assert rows[1][0] == "checkpoint"
    conn.close()

