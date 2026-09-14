import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synlynk.sandbox import scaffold_greenfield_sandbox, build_artifact_tour


def test_scaffold_greenfield_sandbox_creates_ping_app(tmp_path):
    result = scaffold_greenfield_sandbox(str(tmp_path))
    assert (tmp_path / "syn_ping.py").exists()
    assert (tmp_path / "tests" / "test_syn_ping.py").exists()
    assert result["app_name"] == "syn-ping"
    assert result["tests_passing"] is True


def test_build_artifact_tour_returns_core_pillars(tmp_path):
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "context.md").write_text("# Context Snapshot")
    tour = build_artifact_tour(str(tmp_path))
    assert "state_db" in tour
    assert "context_md" in tour
    assert "project_docs" in tour
    assert "worktrees" in tour
