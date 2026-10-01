"""End-to-end tests for the Autonomous Repo Intelligence & Goal Forming epic:
repo classification -> goal synthesis (Greenfield/Brownfield) -> executive
brief, plus the `synlynk brainstorm` / `synlynk brief` CLI commands that wire
those stages together."""

import argparse
from pathlib import Path

from synlynk.repo_classifier import classify_repository, RepoType
from synlynk.greenfield_blueprints import synthesize_greenfield_goals
from synlynk.goal_synthesizer import synthesize_brownfield_goals
from synlynk.brief import generate_executive_brief, save_executive_brief
from synlynk.cli import cmd_brainstorm, cmd_brief, _collect_brownfield_evidence


def test_full_greenfield_personal_assistant_journey(tmp_path: Path):
    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.GREENFIELD

    goals = synthesize_greenfield_goals("personal_assistant", ["bills", "reimbursements"])
    assert len(goals) == 4

    content = generate_executive_brief(str(tmp_path), goals, {"code_files": 0}, mode="Greenfield")
    brief_path = save_executive_brief(str(tmp_path), content)
    assert brief_path.exists()
    assert "Bills & Invoices" in brief_path.read_text()
    assert "Reimbursements & Deductibles" in brief_path.read_text()


def test_full_brownfield_journey(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="demo"')
    (tmp_path / "main.py").write_text("def run(): pass")

    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.BROWNFIELD

    evidence = _collect_brownfield_evidence(str(tmp_path))
    assert evidence["manifests"] == ["pyproject.toml"]
    assert evidence["code_files"] == ["main.py"]

    goals = synthesize_brownfield_goals(evidence)
    assert 3 <= len(goals) <= 5

    content = generate_executive_brief(str(tmp_path), goals, {"code_files": 1}, mode="Brownfield")
    brief_path = save_executive_brief(str(tmp_path), content)
    assert brief_path.exists()
    assert "Baseline Health" in brief_path.read_text()


def test_cmd_brainstorm_greenfield_prints_approved_goals(tmp_path: Path, capsys):
    args = argparse.Namespace(path=str(tmp_path), non_interactive=True, blueprint="personal_assistant", charters="bills")
    cmd_brainstorm(args)
    out = capsys.readouterr().out
    assert "Greenfield goal synthesis complete" in out
    assert "goal-assistant-oauth-hub" in out


def test_cmd_brainstorm_brownfield_prints_approved_goals(tmp_path: Path, capsys):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="demo"')
    (tmp_path / "main.py").write_text("def run(): pass")
    (tmp_path / "test_main.py").write_text("def test_run(): pass")

    args = argparse.Namespace(path=str(tmp_path), non_interactive=True, blueprint=None, charters=None)
    cmd_brainstorm(args)
    out = capsys.readouterr().out
    assert "Brownfield goal synthesis complete" in out
    assert "goal-baseline-preflight" in out


def test_cmd_brief_writes_brief_for_greenfield_repo(tmp_path: Path, capsys):
    args = argparse.Namespace(path=str(tmp_path), blueprint="personal_assistant", charters="bills,reimbursements")
    cmd_brief(args)

    brief_path = tmp_path / "project-docs" / "brief.md"
    assert brief_path.exists()
    assert "Executive Project Brief" in brief_path.read_text()
    out = capsys.readouterr().out
    assert "Executive Project Brief saved to" in out


def test_cmd_brief_writes_brief_for_brownfield_repo(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="demo"')
    (tmp_path / "main.py").write_text("def run(): pass")

    args = argparse.Namespace(path=str(tmp_path), blueprint=None, charters=None)
    cmd_brief(args)

    brief_path = tmp_path / "project-docs" / "brief.md"
    assert brief_path.exists()
    assert "Baseline Health" in brief_path.read_text()
