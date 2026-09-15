import json
import sqlite3
import pytest
from pathlib import Path
from synlynk.heal_cycles import detect_import_cycles, heal_import_cycles


def test_detect_import_cycles_identifies_circular_dependencies(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "pkg_a", "label": "pkg_a", "kind": "module"},
            {"id": "pkg_b", "label": "pkg_b", "kind": "module"},
        ],
        "edges": [
            {"source": "pkg_a", "target": "pkg_b", "kind": "imports"},
            {"source": "pkg_b", "target": "pkg_a", "kind": "imports"},
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    cycles = detect_import_cycles(str(tmp_path))
    assert len(cycles) == 1
    assert set(cycles[0]) == {"pkg_a", "pkg_b"}


def test_detect_import_cycles_returns_empty_when_no_cycles(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "pkg_a", "label": "pkg_a", "kind": "module"},
            {"id": "pkg_b", "label": "pkg_b", "kind": "module"},
        ],
        "edges": [
            {"source": "pkg_a", "target": "pkg_b", "kind": "imports"},
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    cycles = detect_import_cycles(str(tmp_path))
    assert cycles == []


def test_detect_import_cycles_handles_missing_graph(tmp_path):
    cycles = detect_import_cycles(str(tmp_path))
    assert cycles == []


def test_heal_import_cycles_creates_stories(tmp_path, monkeypatch):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "mod1", "label": "mod1"},
            {"id": "mod2", "label": "mod2"},
            {"id": "mod3", "label": "mod3"},
        ],
        "edges": [
            {"source": "mod1", "target": "mod2", "kind": "imports"},
            {"source": "mod2", "target": "mod3", "kind": "imports"},
            {"source": "mod3", "target": "mod1", "kind": "imports"},
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    created = []
    def fake_create_story(**kwargs):
        created.append(kwargs)
        return "story-test-cycle"

    monkeypatch.setattr("synlynk.heal_cycles._create_story_safe", fake_create_story)

    stories = heal_import_cycles(str(tmp_path), create_stories=True)
    assert len(stories) == 1
    assert len(created) == 1
    assert "circular dependency" in created[0]["title"].lower()


def test_cmd_heal_cycles_cli(tmp_path, capsys):
    import argparse
    from synlynk.heal_cycles import cmd_heal_cycles

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "a", "label": "a"},
            {"id": "b", "label": "b"},
        ],
        "edges": [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "a"},
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    args = argparse.Namespace(repo_root=str(tmp_path), create_stories=False)
    ret = cmd_heal_cycles(args)
    assert ret == 0
    captured = capsys.readouterr()
    assert "Found 1 circular dependency cycle" in captured.out

