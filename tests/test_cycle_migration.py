from synlynk import _get_db


def test_migrate_remaps_old_cycle_values_in_cycle_capability():
    conn = _get_db()
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

    # re-open to re-trigger _migrate_db
    conn = _get_db()
    rows = {r[0] for r in conn.execute("SELECT DISTINCT cycle FROM cycle_capability").fetchall()}
    conn.close()
    assert rows == {"execute", "release"}
