def test_devlog_append_links_session_and_goal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_devlog_append
    from synlynk import _get_db

    conn = _get_db()
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion) VALUES (?, ?, ?)",
        ("goal-def67890", "Ship session MVP", "Devlog entries are linked"),
    )
    conn.commit()
    conn.close()

    cmd_devlog_append(
        author="nikhil", entry_date="2026-08-17", body="Shipped session MVP",
        session_id="session-abc12345", goal_id="goal-def67890",
    )

    conn = _get_db()
    row = conn.execute(
        "SELECT session_id, goal_id, body FROM devlog_entries WHERE author=?", ("nikhil",)
    ).fetchone()
    conn.close()
    assert row == ("session-abc12345", "goal-def67890", "Shipped session MVP")


def test_devlog_append_session_id_defaults_to_active_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_devlog_append, cmd_session_open
    from synlynk import _get_db

    session_id = cmd_session_open("Ship v0.14.0")
    cmd_devlog_append(author="nikhil", entry_date="2026-08-17", body="No explicit session_id passed")

    conn = _get_db()
    row = conn.execute(
        "SELECT session_id FROM devlog_entries WHERE author=?", ("nikhil",)
    ).fetchone()
    conn.close()
    assert row == (session_id,)
