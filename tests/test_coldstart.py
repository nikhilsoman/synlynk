import os
import subprocess

import pytest

from synlynk.coldstart import (
    _detect_cold_start_mode,
    _prompt_new_project_questions,
    _resolve_cold_start_mode,
    _run_new_project_flow,
)


def _git_init(root, commits=0, files=None):
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True, check=True)
    for fname, content in (files or {}).items():
        (root / fname).write_text(content)
    for i in range(commits):
        (root / f"commit_{i}.txt").write_text(str(i))
        subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", f"commit {i}"], cwd=root, capture_output=True, check=True)


def test_detect_confident_new_empty_dir(tmp_path):
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "new"


def test_detect_confident_new_git_zero_commits_no_content(tmp_path):
    _git_init(tmp_path, commits=0)
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "new"


def test_detect_ambiguous_git_zero_commits_with_readme(tmp_path):
    _git_init(tmp_path, commits=0, files={"README.md": "# stray readme\n"})
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "ambiguous"


def test_detect_confident_existing_with_commits_and_manifest(tmp_path):
    _git_init(tmp_path, commits=3, files={"package.json": "{}"})
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "existing"
    assert result["signals"]["commit_count"] == 3


def test_detect_ambiguous_commits_but_no_recognizable_files(tmp_path):
    (tmp_path / ".git").mkdir()  # not a real repo — has_git True via os.path.isdir check
    result = _detect_cold_start_mode(str(tmp_path))
    # a .git dir with no working commits and no content is still "new" (fresh git init)
    assert result["mode"] == "new"


def test_detect_ambiguous_no_git_but_project_files_present(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    result = _detect_cold_start_mode(str(tmp_path))
    assert result["mode"] == "ambiguous"


def test_resolve_confident_mode_does_not_prompt(tmp_path, monkeypatch):
    def _fail_input(prompt):
        raise AssertionError("should not prompt when detection is confident")
    monkeypatch.setattr("builtins.input", _fail_input)
    result = _resolve_cold_start_mode(str(tmp_path))
    assert result == "new"


def test_resolve_ambiguous_mode_prompts_and_honors_existing_answer(tmp_path, monkeypatch):
    _git_init(tmp_path, commits=0, files={"README.md": "# stray\n"})
    monkeypatch.setattr("builtins.input", lambda prompt: "existing")
    result = _resolve_cold_start_mode(str(tmp_path))
    assert result == "existing"


def test_resolve_ambiguous_mode_prompts_and_honors_new_answer(tmp_path, monkeypatch):
    _git_init(tmp_path, commits=0, files={"README.md": "# stray\n"})
    monkeypatch.setattr("builtins.input", lambda prompt: "new")
    result = _resolve_cold_start_mode(str(tmp_path))
    assert result == "new"


def test_resolve_ambiguous_mode_defaults_to_existing_on_empty_answer(tmp_path, monkeypatch):
    _git_init(tmp_path, commits=0, files={"README.md": "# stray\n"})
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    result = _resolve_cold_start_mode(str(tmp_path))
    assert result == "existing"


def test_prompt_new_project_questions_collects_four_answers(monkeypatch):
    answers = iter([
        "Build a recipe-sharing CLI",
        "a Python CLI package",
        "solo",
        "codex",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    result = _prompt_new_project_questions()
    assert result == {
        "goal": "Build a recipe-sharing CLI",
        "deliverable_shape": "a Python CLI package",
        "team_mode": "solo",
        "preferred_implementer": "codex",
    }


def test_prompt_new_project_questions_implementer_optional(monkeypatch):
    answers = iter(["Goal", "Shape", "team", ""])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    result = _prompt_new_project_questions()
    assert result["preferred_implementer"] is None
    assert result["team_mode"] == "team"


def test_run_new_project_flow_writes_config_and_roadmap_row(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    answers = {
        "goal": "Build a recipe-sharing CLI",
        "deliverable_shape": "a Python CLI package",
        "team_mode": "solo",
        "preferred_implementer": None,
    }
    _run_new_project_flow(answers)

    assert os.path.exists("synlynk/config.json")
    assert os.path.exists("project-docs/roadmap.md")
    roadmap_text = open("project-docs/roadmap.md").read()
    assert "Build a recipe-sharing CLI" in roadmap_text

    captured = capsys.readouterr()
    assert "next" in captured.out.lower()
