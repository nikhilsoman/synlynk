import pytest
import sqlite3
from synlynk import _get_db

def test_governs_sweep_reconciles_unlinked_stories(tmp_path, monkeypatch, capsys):
    from synlynk.governs_cli import cmd_governs_sweep
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))

    # Insert parent goals
    conn.execute("INSERT OR IGNORE INTO goals (goal_id, outcome, criterion) VALUES ('goal-e3840370', 'Vizor Control Plane', 'ok')")
    conn.execute("INSERT OR IGNORE INTO goals (goal_id, outcome, criterion) VALUES ('goal-eacab0dc', 'Universal GOVERNS', 'ok')")
    
    # Insert unlinked stories
    conn.execute(
        "INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES (?, ?, ?, ?, ?)",
        ("story-unlinked-1", "Vizor Canvas Zoom Feature", None, "open", "open")
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES (?, ?, ?, ?, ?)",
        ("story-unlinked-2", "General refactor task", None, "open", "done")
    )
    conn.commit()

    # Run sweep
    stats = cmd_governs_sweep(repo_root=str(tmp_path), dry_run=False, verbose=True, conn=conn)
    assert stats["total_stories"] == 2
    assert stats["linked_updated"] == 2
    assert stats["stages_advanced"] >= 1

    # Verify story 1 got linked to vizor goal
    row1 = conn.execute("SELECT goal_id, governs_stage FROM stories WHERE story_id='story-unlinked-1'").fetchone()
    assert row1[0] == "goal-e3840370"

    # Verify story 2 got linked to master goal and stage advanced to sustain because status is done
    row2 = conn.execute("SELECT goal_id, governs_stage FROM stories WHERE story_id='story-unlinked-2'").fetchone()
    assert row2[0] == "goal-eacab0dc"
    assert row2[1] == "sustain"
    conn.close()

def test_governs_sweep_dry_run(tmp_path, monkeypatch):
    from synlynk.governs_cli import cmd_governs_sweep
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))

    conn.execute(
        "INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES (?, ?, ?, ?, ?)",
        ("story-dry-1", "Vizor Feature", None, "open", "open")
    )
    conn.commit()

    # Dry run should calculate updates but not commit
    stats = cmd_governs_sweep(repo_root=str(tmp_path), dry_run=True, conn=conn)
    assert stats["linked_updated"] == 1

    row = conn.execute("SELECT goal_id FROM stories WHERE story_id='story-dry-1'").fetchone()
    assert row[0] is None
    conn.close()
