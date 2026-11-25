import sqlite3

from synlynk.migrations.m0041_native_session_capture import MIGRATION


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT NOT NULL,
            harness TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER,
            cache_read_tokens INTEGER, total_cost_usd REAL, cost_source TEXT NOT NULL,
            estimate_basis TEXT, job_id TEXT, session_id TEXT, pr_number INTEGER,
            turn_usage_json TEXT, payment_mode TEXT, notes TEXT)"""
    )
    return conn


def test_creates_tables_view_and_index():
    conn = _conn()
    MIGRATION.up(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"native_capture_cursor", "session_pr_links"} <= tables
    views = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")}
    assert "cost_entries_effective" in views


def test_unique_partial_index_blocks_duplicate_transcript_rows():
    conn = _conn()
    MIGRATION.up(conn)
    ins = ("INSERT INTO cost_entries (session_date, model, cost_source, session_id) "
           "VALUES ('2026-11-24', 'm', 'transcript_derived', 's1')")
    conn.execute(ins)
    try:
        conn.execute(ins.replace("2026-11-24", "2026-11-24T23:00:00"))
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    assert raised
    # other cost_source values are not constrained
    manual = ins.replace("transcript_derived", "estimated_manual")
    conn.execute(manual)
    conn.execute(manual)


def test_effective_view_hides_superseded_rows_only():
    conn = _conn()
    MIGRATION.up(conn)
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, estimate_basis) VALUES ('d','estimated_manual','superseded_by_transcript')")
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, estimate_basis) VALUES ('d','estimated_manual',NULL)")
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, estimate_basis) VALUES ('d','estimated_manual','unverified_estimate')")
    assert conn.execute("SELECT COUNT(*) FROM cost_entries_effective").fetchone()[0] == 2


def test_idempotent():
    conn = _conn()
    MIGRATION.up(conn)
    MIGRATION.up(conn)
