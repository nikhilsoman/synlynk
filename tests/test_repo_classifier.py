import pytest
from pathlib import Path
from synlynk.repo_classifier import classify_repository, RepoClassification, RepoType, prompt_welcome_fork

def test_classify_empty_directory_as_greenfield(tmp_path: Path):
    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.GREENFIELD
    assert res.code_file_count == 0
    assert len(res.manifests) == 0

def test_classify_repo_with_only_readme_as_greenfield(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Test Project")
    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.GREENFIELD
    assert res.code_file_count == 0

def test_classify_repo_with_package_json_as_brownfield(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name": "test"}')
    (tmp_path / "index.js").write_text('console.log("hello");')
    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.BROWNFIELD
    assert "package.json" in res.manifests
    assert res.code_file_count == 1

def test_classify_repo_with_pyproject_as_brownfield(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="test"')
    res = classify_repository(str(tmp_path))
    assert res.repo_type == RepoType.BROWNFIELD
    assert "pyproject.toml" in res.manifests

def test_welcome_fork_non_interactive_defaults_to_accelerate(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname="test"')
    res = classify_repository(str(tmp_path))
    choice = prompt_welcome_fork(res, interactive=False)
    assert choice == "accelerate_existing"
