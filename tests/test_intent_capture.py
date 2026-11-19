import json
import sqlite3
from types import SimpleNamespace

import pytest


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE goals (goal_id TEXT, outcome TEXT, criterion TEXT, status TEXT)")
    conn.execute("CREATE TABLE stories (story_id TEXT, title TEXT, goal_id TEXT, status TEXT)")
    conn.execute("CREATE TABLE roadmap_phases (id INTEGER, phase_title TEXT, notes TEXT)")
    return conn


def test_capture_persists_best_database_association_and_keeps_connection_open(tmp_path, monkeypatch):
    from synlynk.intent import capture_intent, list_intents

    monkeypatch.chdir(tmp_path)
    conn = _conn()
    conn.execute("INSERT INTO goals VALUES ('goal-search', 'Improve semantic search ranking', 'relevant results', 'active')")
    conn.execute("INSERT INTO stories VALUES ('story-billing', 'Repair invoice export', NULL, 'open')")

    captured = capture_intent("Semantic search ranking needs tuning", context={"card": "phase-2"}, conn=conn)

    assert captured["source"] == "terminal"
    assert captured["resolution"] == "attach_existing"
    assert captured["associations"][0]["kind"] == "goal"
    assert captured["associations"][0]["id"] == "goal-search"
    assert captured["proposal_status"] == "pending"
    assert list_intents(conn)[0]["context"] == {"card": "phase-2"}
    conn.execute("SELECT 1").fetchone()


def test_capture_uses_docgraph_and_impact_graph_and_orphans_cleanly(tmp_path, monkeypatch):
    from synlynk.intent import capture_intent

    monkeypatch.chdir(tmp_path)
    graph_dir = tmp_path / ".synlynk" / "graphify-out"
    graph_dir.mkdir(parents=True)
    (tmp_path / ".synlynk" / "docgraph.json").write_text(json.dumps({
        "nodes": {"docs/spec.md": {"title": "Webhook retry policy", "headers": ["Delivery"]}}
    }))
    (graph_dir / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "synlynk.delivery:retry", "label": "retry_webhook", "file": "synlynk/delivery.py"}],
        "edges": [],
    }))
    conn = _conn()

    doc = capture_intent("Clarify webhook retry policy", conn=conn)
    code = capture_intent("Fix retry_webhook in synlynk/delivery.py", conn=conn)
    orphan = capture_intent("quantum banana telescope", conn=conn)

    assert any(a["kind"] == "document" and a["id"] == "docs/spec.md" for a in doc["associations"])
    assert any(a["kind"] == "code" and a["id"] == "synlynk.delivery:retry" for a in code["associations"])
    assert orphan["resolution"] == "orphan_unclear"
    assert orphan["associations"] == []


def test_capture_rejects_blank_text():
    from synlynk.intent import capture_intent

    conn = _conn()
    with pytest.raises(ValueError, match="text"):
        capture_intent("   ", conn=conn)
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='intent_captures'").fetchone() is None


def test_github_events_filter_commands_and_deduplicate():
    from synlynk.intent import capture_github_intents, list_intents

    conn = _conn()
    events = [
        {"id": "issue:12", "kind": "issue", "text": "Add workspace intent inbox", "url": "https://example/issues/12"},
        {"id": "comment:99", "kind": "comment", "text": "/approve", "url": "https://example/issues/12#comment-99"},
    ]
    first = capture_github_intents(events, conn=conn)
    second = capture_github_intents(events, conn=conn)

    assert first == {"captured": 1, "skipped": 1, "duplicates": 0}
    assert second == {"captured": 0, "skipped": 1, "duplicates": 1}
    assert len(list_intents(conn)) == 1


def test_cli_parser_supports_intent_capture_and_list():
    from synlynk.cli import build_parser

    capture = build_parser().parse_args(["intent", "capture", "remember this"])
    listing = build_parser().parse_args(["intent", "list"])
    assert (capture.command, capture.intent_action, capture.text) == ("intent", "capture", "remember this")
    assert (listing.command, listing.intent_action) == ("intent", "list")


def test_vizor_intent_adapter_preserves_card_context(tmp_path, monkeypatch):
    from synlynk.viz.server import capture_vizor_intent
    from synlynk.viz.write_routes import WRITE_ROUTES

    monkeypatch.chdir(tmp_path)
    conn = _conn()
    result = capture_vizor_intent({"text": "Investigate latency", "context": {"card_type": "cost_anomaly", "card_id": "cost-7"}}, conn=conn)
    assert result["source"] == "vizor"
    assert result["context"]["card_id"] == "cost-7"
    assert WRITE_ROUTES["intent/capture"] == "keep"


def test_vizor_chrome_exposes_flag_as_intent_on_cards(monkeypatch):
    monkeypatch.setattr("synlynk.local_http_auth.ensure_local_token", lambda: "token")
    from synlynk.viz.chrome import _live_js

    html = _live_js(8721)
    assert "Flag as Intent" in html
    assert "/api/intent/capture" in html
    assert ".card,.sc,.prop-card" in html


def test_tpm_poll_hook_delegates_to_shared_capture(monkeypatch):
    import synlynk.tpm_sweep as sweep

    seen = {}
    monkeypatch.setattr("synlynk.intent.capture_github_intents", lambda events, conn=None: seen.setdefault("events", events) or {})
    events = [{"id": "issue:1", "kind": "issue", "text": "New idea"}]
    result = sweep.poll_and_capture_github_intents(events=events, conn=_conn())
    assert seen["events"] == events
    assert result == events


def test_tpm_poll_fetches_unlinked_issues_and_free_text_comments(monkeypatch):
    import synlynk.tpm_sweep as sweep

    conn = _conn()
    conn.execute("ALTER TABLE stories ADD COLUMN gh_issue TEXT")
    conn.execute("INSERT INTO stories VALUES ('story-1', 'Known', NULL, 'open', 'https://github.com/acme/repo/issues/1')")

    def fake_gh(_role, args, timeout=15):
        if args[:2] == ["issue", "list"]:
            payload = [
                {"number": 1, "title": "Linked", "body": "already governed", "url": "https://github.com/acme/repo/issues/1"},
                {"number": 2, "title": "Fresh idea", "body": "Add intent inbox", "url": "https://github.com/acme/repo/issues/2"},
            ]
        elif args[2] == "1":
            payload = {"comments": [
                {"id": "IC_linked", "body": "A new concern on governed work", "url": "https://github.com/acme/repo/issues/1#issuecomment-3"},
            ]}
        else:
            payload = {"comments": [
                {"id": "IC_kw1", "body": "/hold", "url": "https://github.com/acme/repo/issues/2#issuecomment-1"},
                {"id": "IC_kw2", "body": "This should support cards too", "url": "https://github.com/acme/repo/issues/2#issuecomment-2"},
            ]}
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    monkeypatch.setattr("synlynk.gh_role.run_gh_as_role", fake_gh)
    result = sweep.poll_and_capture_github_intents(conn=conn)

    assert result == {"captured": 3, "skipped": 1, "duplicates": 0}
    texts = {row["text"] for row in __import__("synlynk.intent", fromlist=["list_intents"]).list_intents(conn)}
    assert texts == {
        "Fresh idea\n\nAdd intent inbox",
        "This should support cards too",
        "A new concern on governed work",
    }
