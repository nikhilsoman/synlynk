import os
from pathlib import Path
import pytest

from synlynk.pr_check import check_pr_spec_gate


def test_spec_gate_passes_when_no_specs_modified(tmp_path, monkeypatch):
    """PR modifying only non-spec files should cleanly pass spec gate."""
    monkeypatch.setattr(
        "synlynk.pr_check._get_changed_files_in_pr",
        lambda repo_root, pr_number: ["synlynk/cli.py", "README.md", "tests/test_foo.py"],
    )
    res = check_pr_spec_gate(repo_root=str(tmp_path))
    assert res["passed"] is True
    assert res["specs_checked"] == []
    assert res["error"] is None


def test_spec_gate_passes_when_valid_spec_modified(tmp_path, monkeypatch):
    """PR modifying a constitutionally valid spec should pass."""
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    valid_spec = specs_dir / "2026-11-12-test-valid-design.md"
    valid_spec.write_text(
        "---\n"
        "status: approved\n"
        "parent_goal: goal-test-1234\n"
        "target_release: v0.32.3\n"
        "decision_id: dec-test-1234\n"
        "---\n\n"
        "# Test Spec\n\nValid specification content.\n"
    )

    monkeypatch.setattr(
        "synlynk.pr_check._get_changed_files_in_pr",
        lambda repo_root, pr_number: ["docs/superpowers/specs/2026-11-12-test-valid-design.md"],
    )
    monkeypatch.setattr(
        "synlynk.spec_lint.load_known_goal_ids",
        lambda repo_root: {"goal-test-1234"},
    )
    monkeypatch.setattr(
        "synlynk.spec_lint.load_known_decision_ids",
        lambda repo_root: {"dec-test-1234"},
    )

    res = check_pr_spec_gate(repo_root=str(tmp_path))
    assert res["passed"] is True
    assert len(res["specs_checked"]) == 1
    assert res["error"] is None


def test_spec_gate_fails_when_approved_spec_lacks_goal_or_decision(tmp_path, monkeypatch):
    """PR modifying an approved spec missing constitutional links must fail."""
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    invalid_spec = specs_dir / "2026-11-12-test-unanchored-design.md"
    invalid_spec.write_text(
        "---\n"
        "status: approved\n"
        "---\n\n"
        "# Unanchored Spec\n"
    )

    monkeypatch.setattr(
        "synlynk.pr_check._get_changed_files_in_pr",
        lambda repo_root, pr_number: ["docs/superpowers/specs/2026-11-12-test-unanchored-design.md"],
    )

    res = check_pr_spec_gate(repo_root=str(tmp_path))
    assert res["passed"] is False
    assert "error" in res and res["error"]
    rules_violated = {f["rule"] for f in res["findings"]}
    assert "MISSING_PARENT_GOAL" in rules_violated
    assert "MISSING_DECISION_ID" in rules_violated


def test_spec_gate_draft_spec_behavior(tmp_path, monkeypatch):
    """Draft specs are allowed non-strictly, but fail in strict mode."""
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    draft_spec = specs_dir / "2026-11-12-test-draft-design.md"
    draft_spec.write_text(
        "---\n"
        "status: draft\n"
        "---\n\n"
        "# Draft Spec\n"
    )

    monkeypatch.setattr(
        "synlynk.pr_check._get_changed_files_in_pr",
        lambda repo_root, pr_number: ["docs/superpowers/specs/2026-11-12-test-draft-design.md"],
    )

    # In standard mode, draft unanchored spec only generates INFO/WARN
    res_normal = check_pr_spec_gate(repo_root=str(tmp_path), strict=False)
    assert res_normal["passed"] is True

    # In strict mode, warnings fail the gate
    res_strict = check_pr_spec_gate(repo_root=str(tmp_path), strict=True)
    assert res_strict["passed"] is False


def test_spec_gate_handles_deleted_file(tmp_path, monkeypatch):
    """If a spec was deleted in the PR, it does not fail the gate."""
    monkeypatch.setattr(
        "synlynk.pr_check._get_changed_files_in_pr",
        lambda repo_root, pr_number: ["docs/superpowers/specs/deleted-spec.md"],
    )
    res = check_pr_spec_gate(repo_root=str(tmp_path))
    assert res["passed"] is True
    assert res["specs_checked"] == []


def test_cmd_pr_check_aborts_on_spec_gate_failure(monkeypatch, capsys):
    """synlynk pr check must fail-closed with SystemExit(1) on spec gate error."""
    import synlynk.db as sdb

    monkeypatch.setattr(
        "synlynk.pr_check.check_pr_spec_gate",
        lambda repo_root=".", pr_number=None, strict=False, changed_files=None: {
            "passed": False,
            "error": "Constitutional spec linting failed",
            "findings": [
                {
                    "severity": "ERROR",
                    "file": "docs/superpowers/specs/bad.md",
                    "line": 1,
                    "rule": "MISSING_PARENT_GOAL",
                    "message": "Missing parent_goal",
                }
            ],
            "specs_checked": ["docs/superpowers/specs/bad.md"],
        },
    )

    with pytest.raises(SystemExit) as exc_info:
        sdb.cmd_pr_check()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "🚫 [PR CHECK BLOCKED] Spec lint gate failed" in captured.out
    assert "MISSING_PARENT_GOAL" in captured.out
