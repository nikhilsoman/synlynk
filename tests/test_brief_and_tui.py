import pytest
from pathlib import Path
from synlynk.brief import generate_executive_brief, save_executive_brief, review_and_approve_goals_tui

def test_generate_and_save_executive_brief(tmp_path: Path):
    goals = [
        {"id": "g1", "title": "Setup OAuth", "category": "foundation", "priority": "P0", "rationale": "Needed for auth", "acceptance_criteria": ["Check 1"]}
    ]
    evidence = {"repo_path": str(tmp_path), "code_files": 0, "manifests": []}
    content = generate_executive_brief(str(tmp_path), goals, evidence, mode="Greenfield")
    assert "# Executive Project Brief" in content
    assert "Setup OAuth" in content
    assert "Needed for auth" in content

    brief_path = save_executive_brief(str(tmp_path), content)
    assert brief_path.exists()
    assert brief_path.name == "brief.md"

def test_review_and_approve_goals_non_interactive():
    goals = [
        {"id": "g1", "title": "Setup OAuth", "priority": "P0"},
        {"id": "g2", "title": "Add Charters", "priority": "P0"}
    ]
    approved = review_and_approve_goals_tui(goals, interactive=False)
    assert approved == goals
