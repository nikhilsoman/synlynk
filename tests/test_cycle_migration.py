import sqlite3

from synlynk import _get_db


def test_migrate_remaps_old_cycle_values_in_cycle_capability(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE cycle_capability (
            agent_name TEXT NOT NULL,
            cycle TEXT NOT NULL,
            support TEXT NOT NULL,
            verb_count INTEGER DEFAULT 0,
            full_count INTEGER DEFAULT 0,
            partial_count INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (agent_name, cycle)
        )
        """
    )
    conn.execute(
        "INSERT INTO cycle_capability (agent_name, cycle, support, verb_count, full_count, partial_count, updated_at) "
        "VALUES ('codex', 'work', 'full', 3, 3, 0, datetime('now'))"
    )
    conn.execute(
        "INSERT INTO cycle_capability (agent_name, cycle, support, verb_count, full_count, partial_count, updated_at) "
        "VALUES ('codex', 'ship', 'full', 2, 2, 0, datetime('now'))"
    )
    conn.commit()
    conn.close()

    conn = _get_db()
    rows = {r[0] for r in conn.execute("SELECT DISTINCT cycle FROM cycle_capability").fetchall()}
    conn.close()
    assert rows == {"execute", "release"}
