import json
import os
import subprocess
import pytest
from synlynk.coldstart import (
    _detect_brownfield_stack,
    _detect_brownfield_tests,
    _detect_brownfield_linters,
    _detect_brownfield_build,
    _detect_git_churn,
    _detect_git_user,
    _bootstrap_4docs,
    run_brownfield_init,
)


def test_detect_brownfield_stack_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    stack = _detect_brownfield_stack(str(tmp_path))
    assert stack["primary"] == "Python"
    assert "Python" in stack["label"]


def test_detect_brownfield_stack_typescript(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "demo-app"}')
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {}}')
    stack = _detect_brownfield_stack(str(tmp_path))
    assert stack["primary"] == "TypeScript"
    assert "TypeScript" in stack["label"]


def test_detect_brownfield_stack_rust(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "demo"\nversion = "0.1.0"')
    stack = _detect_brownfield_stack(str(tmp_path))
    assert stack["primary"] == "Rust"


def test_detect_brownfield_stack_go(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/demo\n\ngo 1.22")
    stack = _detect_brownfield_stack(str(tmp_path))
    assert stack["primary"] == "Go"


def test_detect_brownfield_tests_python(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    cmd = _detect_brownfield_tests(str(tmp_path), "Python")
    assert cmd == "pytest"


def test_detect_brownfield_tests_npm(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
    cmd = _detect_brownfield_tests(str(tmp_path), "JavaScript")
    assert cmd == "npm test"


def test_detect_brownfield_linters_python(tmp_path):
    (tmp_path / "ruff.toml").write_text("line-length = 100\n")
    cmd = _detect_brownfield_linters(str(tmp_path), "Python")
    assert cmd == "ruff check ."


def test_detect_brownfield_linters_eslint(tmp_path):
    (tmp_path / ".eslintrc.json").write_text("{}")
    cmd = _detect_brownfield_linters(str(tmp_path), "TypeScript")
    assert cmd == "npx eslint ."


def test_detect_brownfield_build(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "demo"')
    cmd = _detect_brownfield_build(str(tmp_path), "Rust")
    assert cmd == "cargo build"


def test_bootstrap_4docs(tmp_path):
    created = _bootstrap_4docs(
        str(tmp_path),
        stack="Python",
        test_cmd="pytest",
        lint_cmd="ruff check .",
        build_cmd="pip install -e .",
        hotspots=["main.py", "utils.py"],
        user_name="alice",
        force=True
    )
    assert "roadmap.md" in created
    assert "memory.md" in created
    assert "todo.md" in created
    assert "costs.md" in created
    assert "devlogs/alice.md" in created

    # Verify roadmap content
    roadmap = (tmp_path / "project-docs" / "roadmap.md").read_text()
    assert "Brownfield Baseline & Stabilization" in roadmap
    assert "pytest" in roadmap

    # Verify memory content with attribution
    memory = (tmp_path / "project-docs" / "memory.md").read_text()
    assert "@alice" in memory
    assert "ruff check ." in memory

    # Verify devlog content
    devlog = (tmp_path / "project-docs" / "devlogs" / "alice.md").read_text()
    assert "@alice" in devlog
    assert "main.py, utils.py" in devlog


def test_run_brownfield_init_dry_run(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'sample'\n")
    res = run_brownfield_init(str(tmp_path), interactive=False, dry_run=True)
    assert res["success"] is True
    assert res["dry_run"] is True
    assert res["stack"] == "Python"
    assert not (tmp_path / ".synlynk").exists()
    assert not (tmp_path / "project-docs").exists()


def test_run_brownfield_init_e2e(tmp_path):
    # Initialize a git repo
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "testbot"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "testbot@synlynk.dev"], cwd=str(tmp_path), capture_output=True, check=True)

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'sample-repo'\n")
    (tmp_path / "main.py").write_text("def hello(): return 42\n")
    (tmp_path / "test_main.py").write_text("from main import hello\ndef test_hello(): assert hello() == 42\n")

    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), capture_output=True, check=True)

    res = run_brownfield_init(str(tmp_path), interactive=False, dry_run=False, force=True)
    assert res["success"] is True
    assert res["stack"] == "Python"
    assert res["test_command"] == "pytest"
    assert res["primary_author"] == "testbot"

    # Verify 4-doc structure created
    docs_dir = tmp_path / "project-docs"
    assert (docs_dir / "roadmap.md").exists()
    assert (docs_dir / "memory.md").exists()
    assert (docs_dir / "todo.md").exists()
    assert (docs_dir / "costs.md").exists()
    assert (docs_dir / "devlogs" / "testbot.md").exists()
