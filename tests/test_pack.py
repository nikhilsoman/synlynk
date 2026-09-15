import json
import pytest
from pathlib import Path
from synlynk.pack import synthesize_context_pack, _cut_to_token_budget


def test_cut_to_token_budget():
    text = "word " * 3000
    cut = _cut_to_token_budget(text, token_budget=1500)
    # 1 token ~= 4 chars, 1500 tokens ~= 6000 chars
    assert len(cut) <= 6100
    assert "[Context truncated to 1500 token budget]" in cut


def test_synthesize_context_pack_extracts_target_symbols(tmp_path):
    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "synlynk.daemon:run_loop", "label": "run_loop", "file": "synlynk/daemon.py", "line": 145},
            {"id": "synlynk.db:init_db", "label": "init_db", "file": "synlynk/db.py", "line": 20},
        ],
        "edges": [
            {"source": "synlynk.daemon:run_loop", "target": "synlynk.db:init_db", "kind": "calls"}
        ]
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    pack = synthesize_context_pack(str(tmp_path), task_text="Fix error in run_loop during startup")
    assert "## Task Context Pack" in pack
    assert "run_loop" in pack
    assert "synlynk/daemon.py" in pack


def test_synthesize_context_pack_returns_empty_when_no_graph(tmp_path):
    pack = synthesize_context_pack(str(tmp_path), task_text="Some random task")
    assert pack == ""


def test_format_prompt_for_agent_injects_pack_on_turn_1(tmp_path):
    from synlynk.dispatch import _format_prompt_for_agent

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "synlynk.auth:verify_jwt", "label": "verify_jwt", "file": "synlynk/auth.py", "line": 42},
        ],
        "edges": []
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    prompt = _format_prompt_for_agent(
        agent="codex",
        context_text="Base project context",
        story_id="story-100",
        task="Refactor verify_jwt in auth module",
        file_section="",
        verify_section="",
        cwd_hint=str(tmp_path),
    )
    assert "## Task Context Pack" in prompt
    assert "verify_jwt" in prompt
    assert "synlynk/auth.py:L42" in prompt


def test_cmd_pack_cli(tmp_path, capsys):
    import argparse
    from synlynk.pack import cmd_pack

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "synlynk.auth:verify_jwt", "label": "verify_jwt", "file": "synlynk/auth.py", "line": 42},
        ],
        "edges": []
    }
    (out_dir / "graph.json").write_text(json.dumps(graph))

    args = argparse.Namespace(target="verify_jwt", budget=1500, repo_root=str(tmp_path))
    ret = cmd_pack(args)
    assert ret == 0
    captured = capsys.readouterr()
    assert "## Task Context Pack" in captured.out
    assert "verify_jwt" in captured.out

