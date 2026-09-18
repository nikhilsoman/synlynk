import json
import sqlite3

import pytest

from synlynk.board import board_data, update_status
from synlynk.product_store import state_db_path


def _product_repo(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    (repo / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": "acme"}))
    db_path = state_db_path("acme")
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE stories (
            story_id TEXT PRIMARY KEY, title TEXT, status TEXT,
            repo_id TEXT, type_id TEXT, goal_id TEXT,
            source_type TEXT, source_ref TEXT, gh_issue TEXT,
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE goals (goal_id TEXT PRIMARY KEY, outcome TEXT);
        INSERT INTO stories VALUES
          ('frontend-1', 'Frontend card', 'ready', 'frontend', 'feature', 'goal-1',
           'github', '{"tracker":"github","container":"acme/frontend","id":"41"}', NULL, '2026-01-01', '2026-01-01'),
          ('api-1', 'API card', 'in_progress', 'api', 'bug', NULL,
           'linear', '{"tracker":"linear","container":"HITCH","id":"HIT-7"}', NULL, '2026-01-02', '2026-01-02'),
          ('unknown-1', 'Unknown tracker', 'open', 'api', 'bug', NULL,
           'jira', '{"tracker":"jira","container":"acme","id":"J-1"}', NULL, '2026-01-03', '2026-01-03');
        """
    )
    conn.commit()
    conn.close()
    return repo, db_path


def test_board_reads_product_graph_and_deep_links(tmp_path, monkeypatch):
    repo, _ = _product_repo(tmp_path, monkeypatch)
    payload = board_data(str(repo))

    assert payload["identity_slug"] == "acme"
    assert {card["story_id"] for card in payload["cards"]} == {"frontend-1", "api-1", "unknown-1"}
    by_id = {card["story_id"]: card for card in payload["cards"]}
    assert by_id["frontend-1"]["tracker"]["url"] == "https://github.com/acme/frontend/issues/41"
    assert by_id["api-1"]["tracker"]["url"] == "https://linear.app/HITCH/issue/HIT-7"
    assert by_id["unknown-1"]["tracker"]["url"] is None
    assert payload["filters"] == {"repos": ["api", "frontend"], "types": ["bug", "feature"], "goals": ["goal-1"]}


def test_board_filters_are_composable(tmp_path, monkeypatch):
    repo, _ = _product_repo(tmp_path, monkeypatch)
    payload = board_data(str(repo), repo_id="api", type_id="bug")
    assert [card["story_id"] for card in payload["cards"]] == ["api-1", "unknown-1"]
    assert board_data(str(repo), goal_id="goal-1")["cards"][0]["story_id"] == "frontend-1"


def test_board_status_writes_product_db_only(tmp_path, monkeypatch):
    repo, db_path = _product_repo(tmp_path, monkeypatch)
    assert update_status("frontend-1", "done", str(repo)) == {
        "ok": True, "story_id": "frontend-1", "status": "done"
    }
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT status FROM stories WHERE story_id='frontend-1'").fetchone()[0] == "done"
    conn.close()


def test_board_status_fails_closed(tmp_path, monkeypatch):
    repo, _ = _product_repo(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="unknown board status"):
        update_status("frontend-1", "shipped", str(repo))
    with pytest.raises(KeyError, match="story not found"):
        update_status("missing", "done", str(repo))


def test_board_view_is_local_and_uses_status_api():
    from synlynk.viz import generate_board_html

    html = generate_board_html(8721)
    assert "Product graph" in html
    assert "/api/board" in html
    assert "/api/board/status" in html
    assert "github.com" not in html
