import json
import os
import subprocess
import pytest
from synlynk.heal import (
    _discover_ast_gaps,
    _generate_magic_test_content,
    run_magic_heal,
)


def test_discover_ast_gaps(tmp_path):
    (tmp_path / "module_a.py").write_text("def add(a, b): return a + b\n")
    (tmp_path / "module_b.py").write_text("def sub(a, b): return a - b\n")
    (tmp_path / "test_module_a.py").write_text("from module_a import add\ndef test_add(): assert add(1, 2) == 3\n")

    gaps = _discover_ast_gaps(str(tmp_path))
    assert len(gaps) >= 1
    untested_targets = [g["target_file"] for g in gaps]
    assert "module_b.py" in untested_targets
    assert "module_a.py" not in untested_targets


def test_generate_magic_test_content():
    gap = {
        "slug": "calculator",
        "target_file": "synlynk/calc.py",
        "title": "Add test for synlynk/calc.py",
        "description": "Module has no dedicated test file.",
    }
    test_relpath, test_code, verify_cmd = _generate_magic_test_content(gap, ".")
    assert test_relpath == os.path.join("tests", "test_magic_calculator.py")
    assert "synlynk.calc" in test_code
    assert "def test_magic_module_importable" in test_code
    assert verify_cmd == f"pytest {test_relpath} -q"


def test_run_magic_heal_dry_run(tmp_path):
    (tmp_path / "calculator.py").write_text("def multiply(a, b): return a * b\n")
    res = run_magic_heal(repo_root=str(tmp_path), dry_run=True)
    assert res["success"] is True
    assert res["dry_run"] is True
    assert "calculator" in res["branch"]
    assert "feat(magic-heal):" in res["pr_title"]
    assert "Magic Heal Auto-Remediation" in res["pr_body"]
    assert not (tmp_path / "tests").exists()


def test_run_magic_heal_e2e(tmp_path):
    # Setup git repo
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "testbot"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "testbot@synlynk.dev"], cwd=str(tmp_path), capture_output=True, check=True)

    (tmp_path / "sample_service.py").write_text("SERVICE_NAME = 'sample'\ndef get_status(): return 'OK'\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), capture_output=True, check=True)

    res = run_magic_heal(repo_root=str(tmp_path), dry_run=False, auto_pr=False)
    assert res["success"] is True
    assert res["verification_passed"] is True
    assert res["committed"] is True
    assert "feat/magic-heal-sample_service" in res["branch"]
    assert (tmp_path / res["test_file"]).exists()

    # Check git log on new branch
    log_res = subprocess.run(["git", "log", "-n", "1", "--pretty=%B"], cwd=str(tmp_path), capture_output=True, text=True, check=True)
    assert "feat(magic-heal):" in log_res.stdout
    assert "Co-Authored-By: Codex <noreply@openai.com>" in log_res.stdout
