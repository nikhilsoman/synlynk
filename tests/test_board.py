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


def test_board_stage_updates_and_fails_closed(tmp_path, monkeypatch):
    from synlynk.board import GOVERNS_STAGES, update_stage
    repo, db_path = _product_repo(tmp_path, monkeypatch)

    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE stories ADD COLUMN governs_stage TEXT")
    conn.commit()
    conn.close()

    res = update_stage("frontend-1", "execute", str(repo))
    assert res == {"ok": True, "story_id": "frontend-1", "stage": "execute"}

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT governs_stage FROM stories WHERE story_id='frontend-1'").fetchone()[0] == "execute"
    conn.close()

    payload = board_data(str(repo))
    assert payload["governs_stages"] == list(GOVERNS_STAGES)
    by_id = {card["story_id"]: card for card in payload["cards"]}
    assert by_id["frontend-1"]["governs_stage"] == "execute"
    assert by_id["api-1"]["governs_stage"] == "open"

    with pytest.raises(ValueError, match="unknown GOVERNS stage"):
        update_stage("frontend-1", "invalid_stage", str(repo))
    with pytest.raises(KeyError, match="story not found"):
        update_stage("nonexistent-card", "execute", str(repo))


def test_board_view_is_local_and_uses_status_api():
    from synlynk.viz import generate_board_html

    html = generate_board_html(8721)
    assert "Product graph" in html
    assert "api/board" in html
    assert "api/board/status" in html
    assert "api/board/stage" in html
    assert "GOVERNS" in html
    assert "github.com" not in html


def test_board_data_populates_goal_cards_and_links(tmp_path, monkeypatch):
    """Verify board_data() populates Goal stage from active goals and links stories (gh:#5175)."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    monkeypatch.chdir(repo)
    (repo / ".synlynk" / "config.json").write_text(json.dumps({
        "identity_slug": "acme",
        "github_repo": "acme/repo",
    }))
    db_path = state_db_path("acme")
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE stories (
            story_id TEXT PRIMARY KEY, title TEXT, status TEXT,
            repo_id TEXT, type_id TEXT, goal_id TEXT,
            source_type TEXT, source_ref TEXT, gh_issue TEXT, pr_number INTEGER,
            created_at TEXT, updated_at TEXT, governs_stage TEXT
        );
        CREATE TABLE goals (
            goal_id TEXT PRIMARY KEY, outcome TEXT, criterion TEXT,
            status TEXT DEFAULT 'active', kind TEXT DEFAULT 'feature'
        );
        INSERT INTO goals (goal_id, outcome, criterion, status, kind) VALUES
            ('goal-autonomy', 'Achieve Full Workspace Autonomy', 'Zero regressions', 'active', 'strategic');
        INSERT INTO stories (story_id, title, status, goal_id, gh_issue, pr_number, governs_stage) VALUES
            ('story-1', 'Build worker daemon', 'in_progress', 'goal-autonomy', '5175', 5180, 'execute');
        """
    )
    conn.commit()
    conn.close()

    payload = board_data(str(repo))
    cards = payload["cards"]
    assert len(cards) == 2

    # Goal card assertions
    goal_card = next(c for c in cards if c.get("is_goal"))
    assert goal_card["story_id"] == "goal-autonomy"
    assert goal_card["governs_stage"] == "goal"
    assert goal_card["title"] == "Achieve Full Workspace Autonomy"
    assert goal_card["criterion"] == "Zero regressions"
    assert goal_card["type_id"] == "strategic"
    assert goal_card["linked_stories_count"] == 1

    # Story card assertions
    story_card = next(c for c in cards if not c.get("is_goal"))
    assert story_card["story_id"] == "story-1"
    assert story_card["tracker"]["url"] == "https://github.com/acme/repo/issues/5175"
    assert story_card["pr_url"] == "https://github.com/acme/repo/pull/5180"

    # Context-scoped assertions (used by /w/<slug>/api/board daemon)
    from synlynk.vizor_daemon import WorkspaceContext
    ctx = WorkspaceContext(slug="acme", repo_path=repo, db_path=db_path)
    from synlynk.board import board_data_for_context
    ctx_payload = board_data_for_context(ctx)
    ctx_cards = ctx_payload["cards"]
    assert any(c.get("is_goal") and c["story_id"] == "goal-autonomy" for c in ctx_cards)
    assert "goal-autonomy" in ctx_payload["filters"]["goals"]

