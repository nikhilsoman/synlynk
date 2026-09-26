import pytest
import sqlite3
from synlynk import _get_db

def test_advance_stage_transitions(tmp_path, monkeypatch):
    from synlynk.governs_fsm import advance_story_governs_stage, GOVERNS_STAGE_RANKS
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))

    # Insert a story at open stage
    conn.execute(
        "INSERT INTO stories (story_id, title, governs_stage, status) VALUES (?, ?, ?, ?)",
        ("story-test-1", "Test Feature", "open", "open")
    )
    conn.commit()

    # 1. Spec committed -> visualize
    stage1 = advance_story_governs_stage("story-test-1", "spec_or_plan_committed", {"spec_path": "docs/superpowers/specs/feature-design.md"}, conn=conn)
    assert stage1 == "visualize"
    row1 = conn.execute("SELECT governs_stage FROM stories WHERE story_id='story-test-1'").fetchone()
    assert row1[0] == "visualize"

    # 2. Plan approved / PR opened -> execute
    stage2 = advance_story_governs_stage("story-test-1", "spec_or_plan_committed", {"plan_path": "docs/superpowers/plans/feature-plan.md"}, conn=conn)
    assert stage2 == "execute"

    # 3. PR merged -> release
    stage3 = advance_story_governs_stage("story-test-1", "pr_merged", {"pr_number": 100}, conn=conn)
    assert stage3 == "release"

    # 4. Marketing synced -> notify
    stage4 = advance_story_governs_stage("story-test-1", "marketing_synced", {}, conn=conn)
    assert stage4 == "notify"

    # 5. Story done / closeout receipt -> sustain
    stage5 = advance_story_governs_stage("story-test-1", "story_done", {}, conn=conn)
    assert stage5 == "sustain"
    row5 = conn.execute("SELECT governs_stage, status FROM stories WHERE story_id='story-test-1'").fetchone()
    assert row5[0] == "sustain"
    assert row5[1] == "done"
    conn.close()

def test_emit_event_triggers_governs_fsm(tmp_path, monkeypatch):
    from synlynk.events import emit_event
    test_db = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(test_db))
    conn = _get_db(db_path=str(test_db))

    conn.execute(
        "INSERT INTO stories (story_id, title, governs_stage, status) VALUES (?, ?, ?, ?)",
        ("story-auto-evt", "Auto Event Story", "open", "open")
    )
    conn.commit()
    conn.close()

    # Emit pr_merged event
    emit_event("pr_merged", {"story_id": "story-auto-evt", "pr_number": 123}, emitted_by="qa_gate")

    conn2 = _get_db(db_path=str(test_db))
    row = conn2.execute("SELECT governs_stage FROM stories WHERE story_id='story-auto-evt'").fetchone()
    assert row[0] == "release"
    conn2.close()
