import json
import sqlite3

from synlynk.board import board_data_for_context, update_stage_for_context
from synlynk.viz.gantt import generate_gantt_html
from synlynk.viz.server import save_viz_note
from synlynk.vizor_daemon import WorkspaceContext, stamp_workspace_kind


def test_save_viz_note_roundtrip(tmp_path):
    path = tmp_path / "viz-notes.json"
    save_viz_note(path, {"id": "rel-1", "text": "hi", "tags": [], "state": "info"})
    data = json.loads(path.read_text())
    assert data["rel-1"]["text"] == "hi"
    assert data["rel-1"]["state"] == "info"


def test_save_viz_note_requires_id(tmp_path):
    path = tmp_path / "viz-notes.json"
    try:
        save_viz_note(path, {"text": "nope"})
    except ValueError as exc:
        assert "id" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")


def test_gantt_js_posts_relative_api_note():
    html = generate_gantt_html(
        {
            "workspace": {"name": "synlynk"},
            "releases": [],
            "dreams": [],
            "goals": [],
            "spec_verifications": [],
            "product_id": "synlynk",
            "notes": {},
        },
        33333,
    )
    assert "fetch('/note'" not in html
    assert "fetch('api/note'" in html


def _workspace_context(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT UNIQUE, title TEXT, "
        "status TEXT DEFAULT 'open', stage TEXT DEFAULT 'open', governs_stage TEXT DEFAULT 'open', goal_id TEXT)"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, status, stage, governs_stage, goal_id) "
        "VALUES ('story-001', 'Test Story', 'open', 'open', 'open', 'goal-123')"
    )
    conn.commit()
    conn.close()
    return WorkspaceContext(slug="test-slug", repo_path=repo, db_path=db_path)


def test_stage_update_rejected_until_unlocked(tmp_path):
    ctx = _workspace_context(tmp_path)
    assert update_stage_for_context(ctx, "story-001", "execute") is False
    assert board_data_for_context(ctx)["cards"][0]["governs_stage"] == "open"
    assert update_stage_for_context(ctx, "story-001", "execute", unlocked=True) is True
    assert board_data_for_context(ctx)["cards"][0]["governs_stage"] == "execute"


def test_stamp_workspace_kind_updates_custom_registry(tmp_path, monkeypatch):
    repo = tmp_path / "synlynk"
    repo.mkdir()
    db = tmp_path / "state.db"
    db.write_bytes(b"")
    registry = tmp_path / "state_registry.json"
    registry.write_text(json.dumps({
        "version": 1,
        "products": {
            "synlynk": {
                "slug": "synlynk",
                "repo_path": str(repo),
                "canonical_path": str(db),
            }
        },
    }))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))
    entry = {"repo_path": str(repo), "canonical_path": str(db)}
    stamped = stamp_workspace_kind("synlynk", entry)
    assert stamped["kind"] == "local"
    assert stamped["path_root"] == str(repo)
    saved = json.loads(registry.read_text())["products"]["synlynk"]
    assert saved["kind"] == "local"
    assert saved["path_root"] == str(repo)
