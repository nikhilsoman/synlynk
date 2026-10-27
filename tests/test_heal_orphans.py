"""Orphan-symbol report. Story creation must not rewrite project-docs/todo.md."""

import json
import sqlite3

from synlynk.heal_orphans import cmd_heal_orphans, find_orphan_symbols


def _graph(tmp_path, nodes, edges=None):
    out = tmp_path / ".synlynk" / "graphify-out"
    out.mkdir(parents=True)
    (out / "graph.json").write_text(json.dumps({"nodes": nodes, "edges": edges or []}))
    (out / "manifest.json").write_text(json.dumps({
        "built_at_commit": "abc",
        "lifecycle": "brownfield",
    }))


def test_orphan_report_skips_entrypoints_tests_and_dunder(tmp_path):
    _graph(tmp_path, [
        {"id": "cli", "label": "main", "file": "synlynk/cli.py", "kind": "function"},
        {"id": "orphan", "label": "unused_helper", "file": "synlynk/orphans.py", "kind": "function"},
        {"id": "used", "label": "used_helper", "file": "synlynk/used.py", "kind": "function"},
        {"id": "dunder", "label": "__init__", "file": "synlynk/pkg.py", "kind": "function"},
        {"id": "testfn", "label": "test_unused", "file": "tests/test_orphans.py", "kind": "function"},
        {"id": "klass", "label": "LonelyClass", "file": "synlynk/lonely.py", "kind": "class"},
    ], edges=[{"source": "cli", "target": "used"}])
    found = find_orphan_symbols(str(tmp_path))
    labels = sorted(item["label"] for item in found)
    assert labels == ["LonelyClass", "unused_helper"]


def test_orphan_stories_insert_without_touching_todo(tmp_path, monkeypatch):
    _graph(tmp_path, [
        {"id": "orphan", "label": "unused_helper", "file": "synlynk/orphans.py", "kind": "function"},
    ])
    conn = sqlite3.connect(str(tmp_path / "state.db"))
    conn.execute(
        "CREATE TABLE stories (story_id TEXT, title TEXT, description TEXT, criteria TEXT, status TEXT, priority TEXT)"
    )
    monkeypatch.setattr("synlynk.heal_orphans._get_db", lambda: conn)

    def forbid_todo(*args, **kwargs):
        raise AssertionError("todo.md must not be regenerated")

    monkeypatch.setattr("synlynk.db._generate_todo_md", forbid_todo)
    code = cmd_heal_orphans(type("Args", (), {"repo_root": str(tmp_path), "stories": True})())
    assert code == 0
    row = conn.execute("SELECT title, status FROM stories").fetchone()
    assert row[0].startswith("Orphan symbol unused_helper")
    assert row[1] == "ready"
    assert not (tmp_path / "project-docs" / "todo.md").exists()
