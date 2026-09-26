import json
import pytest
import sqlite3
from synlynk import _get_db
from synlynk.board import board_data, GOVERNS_STAGES
from synlynk.governs_cli import cmd_governs_sweep
from synlynk.product_store import state_db_path
from synlynk.uxcore import get_gantt_data

def _setup_product_workspace(tmp_path, monkeypatch, slug="testws"):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True, exist_ok=True)
    (repo / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": slug}))
    db_file = state_db_path(slug)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_file))
    return repo, db_file

def test_board_cards_distribution_across_7_stages(tmp_path, monkeypatch):
    repo, db_file = _setup_product_workspace(tmp_path, monkeypatch, "boardws")
    conn = _get_db(db_path=str(db_file))

    # Insert parent goals
    conn.execute("INSERT OR IGNORE INTO goals (goal_id, outcome, criterion) VALUES ('goal-e3840370', 'Vizor Control Plane', 'ok')")
    conn.execute("INSERT OR IGNORE INTO goals (goal_id, outcome, criterion) VALUES ('goal-eacab0dc', 'Universal GOVERNS', 'ok')")

    # Insert stories at various stages
    stages = ["goal", "open", "visualize", "execute", "release", "notify", "sustain"]
    for i, stg in enumerate(stages):
        conn.execute(
            "INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES (?, ?, ?, ?, ?)",
            (f"story-stage-{i}", f"Feature for {stg}", "goal-e3840370", stg, "done" if stg == "sustain" else "open")
        )
    conn.commit()
    conn.close()

    board_data_res = board_data(str(repo))
    assert len(board_data_res["cards"]) == 7
    assert board_data_res["governs_stages"] == list(GOVERNS_STAGES)
    
    stages_present = {c["governs_stage"] for c in board_data_res["cards"]}
    assert stages_present == set(stages)

def test_governs_sweep_populates_board_and_gantt(tmp_path, monkeypatch):
    repo, db_file = _setup_product_workspace(tmp_path, monkeypatch, "sweepws")
    conn = _get_db(db_path=str(db_file))

    # Insert goals
    conn.execute("INSERT OR IGNORE INTO goals (goal_id, outcome, criterion) VALUES ('goal-e3840370', 'Vizor Control Plane', 'ok')")
    conn.execute("INSERT OR IGNORE INTO goals (goal_id, outcome, criterion) VALUES ('goal-eacab0dc', 'Universal GOVERNS', 'ok')")

    # Insert 5 unlinked stories with keywords
    conn.execute("INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES ('s1', 'Vizor Topbar Refresh', NULL, 'open', 'open')")
    conn.execute("INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES ('s2', 'Vizor Gantt Chart Pivot', NULL, 'open', 'done')")
    conn.execute("INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES ('s3', 'DeepSeek Jev routing', NULL, 'open', 'open')")
    conn.execute("INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES ('s4', 'General task', NULL, 'open', 'done')")
    conn.execute("INSERT INTO stories (story_id, title, goal_id, governs_stage, status) VALUES ('s5', 'Platform health sentinel', NULL, 'open', 'open')")
    conn.commit()

    # Before sweep: 5 unlinked
    unlinked_before = conn.execute("SELECT count(*) FROM stories WHERE goal_id IS NULL").fetchone()[0]
    assert unlinked_before == 5

    # Run sweep
    cmd_governs_sweep(repo_root=str(repo), dry_run=False, conn=conn)

    # After sweep: 0 unlinked!
    unlinked_after = conn.execute("SELECT count(*) FROM stories WHERE goal_id IS NULL").fetchone()[0]
    assert unlinked_after == 0

    # Board cards check
    board_res = board_data(str(repo))
    assert len(board_res["cards"]) == 5
    assert all(c.get("goal_id") is not None for c in board_res["cards"])
    
    # Completed tasks s2 and s4 advanced to sustain
    s2_card = next(c for c in board_res["cards"] if c["story_id"] == "s2")
    assert s2_card["governs_stage"] == "sustain"
    conn.close()
