import sqlite3

from synlynk.governs_cli import cmd_governs_rephase


def test_rephase_is_atomic_and_audited():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
    CREATE TABLE goals (goal_id TEXT PRIMARY KEY, phase_id INTEGER, placement_status TEXT, placement_reason TEXT);
    CREATE TABLE roadmap_phases (id INTEGER PRIMARY KEY);
    CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL, emitted_by TEXT NOT NULL, authority_scope TEXT);
    INSERT INTO goals VALUES ('goal-1', 1, 'placed', NULL);
    INSERT INTO roadmap_phases VALUES (2);
    """)
    cmd_governs_rephase('goal-1', 2, 'align with release phase', conn=conn)
    assert conn.execute("SELECT phase_id, placement_reason FROM goals").fetchone() == (2, 'rephased: align with release phase')
    assert conn.execute("SELECT event_type FROM events").fetchone()[0] == 'GOVERNS_REPHASE'
