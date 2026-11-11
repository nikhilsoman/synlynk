"""Unit tests for Constitutional Spec Linter (v0.32.3 / dec-9b41a7c3)."""

import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from synlynk.spec_lint import (
    SpecLintFinding,
    SpecLintResult,
    cmd_spec_lint,
    lint_spec_file,
    lint_specs,
    load_known_decision_ids,
    load_known_goal_ids,
)


def test_load_known_decision_ids(tmp_path):
    dec_dir = tmp_path / "project-docs" / "decisions"
    dec_dir.mkdir(parents=True)

    dec_file1 = dec_dir / "2026-11-11-authoritative-platform-roadmap.md"
    dec_file1.write_text(
        "---\ndecision_id: dec-9b41a7c3\ntopic: Test Roadmap\n---\n# Decision Content",
        encoding="utf-8",
    )

    dec_file2 = dec_dir / "dec-f34a2f5f-companion.md"
    dec_file2.write_text("# Companion decision", encoding="utf-8")

    dec_ids = load_known_decision_ids(repo_root=str(tmp_path))
    assert "dec-9b41a7c3" in dec_ids
    assert "dec-f34a2f5f" in dec_ids


def test_load_known_goal_ids():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (1,)
    mock_conn.execute.return_value.fetchall.return_value = [
        ("goal-2458-master-roadmap",),
        ("goal-eacab0dc",),
    ]

    goals = load_known_goal_ids(conn=mock_conn)
    assert "goal-2458-master-roadmap" in goals
    assert "goal-eacab0dc" in goals


def test_lint_spec_valid_approved(tmp_path):
    spec = tmp_path / "test-spec.md"
    spec.write_text(
        """---
title: Valid Approved Spec
status: approved
parent_goal: goal-2458-master-roadmap
target_release: v0.32.3
decision_id: dec-9b41a7c3
---
# Specification
Valid body.
""",
        encoding="utf-8",
    )

    findings = lint_spec_file(
        str(spec),
        repo_root=str(tmp_path),
        known_goals={"goal-2458-master-roadmap"},
        known_decisions={"dec-9b41a7c3"},
    )
    assert len(findings) == 0


def test_lint_spec_missing_parent_goal_on_approved(tmp_path):
    spec = tmp_path / "test-spec.md"
    spec.write_text(
        """---
title: Bad Spec
status: approved
target_release: v0.32.3
decision_id: dec-9b41a7c3
---
# Spec without parent goal
""",
        encoding="utf-8",
    )

    findings = lint_spec_file(
        str(spec),
        repo_root=str(tmp_path),
        known_goals={"goal-2458-master-roadmap"},
        known_decisions={"dec-9b41a7c3"},
    )
    assert any(f.rule == "MISSING_PARENT_GOAL" and f.severity == "ERROR" for f in findings)


def test_lint_spec_unregistered_goal_id(tmp_path):
    spec = tmp_path / "test-spec.md"
    spec.write_text(
        """---
title: Bad Spec
status: approved
parent_goal: goal-unknown-fake
target_release: v0.32.3
decision_id: dec-9b41a7c3
---
# Spec with unknown goal
""",
        encoding="utf-8",
    )

    findings = lint_spec_file(
        str(spec),
        repo_root=str(tmp_path),
        known_goals={"goal-2458-master-roadmap"},
        known_decisions={"dec-9b41a7c3"},
    )
    assert any(f.rule == "UNREGISTERED_GOAL_ID" and f.severity == "ERROR" for f in findings)


def test_lint_spec_missing_decision_id_on_approved(tmp_path):
    spec = tmp_path / "test-spec.md"
    spec.write_text(
        """---
title: Spec Without Decision
status: approved
parent_goal: goal-2458-master-roadmap
target_release: v0.32.3
---
# Spec missing decision
""",
        encoding="utf-8",
    )

    findings = lint_spec_file(
        str(spec),
        repo_root=str(tmp_path),
        known_goals={"goal-2458-master-roadmap"},
        known_decisions={"dec-9b41a7c3"},
    )
    assert any(f.rule == "MISSING_DECISION_ID" and f.severity == "ERROR" for f in findings)


def test_lint_spec_unratified_decision_id(tmp_path):
    spec = tmp_path / "test-spec.md"
    spec.write_text(
        """---
title: Spec With Ghost Decision
status: approved
parent_goal: goal-2458-master-roadmap
target_release: v0.32.3
decision_id: dec-nonexistent
---
# Spec with ghost decision
""",
        encoding="utf-8",
    )

    findings = lint_spec_file(
        str(spec),
        repo_root=str(tmp_path),
        known_goals={"goal-2458-master-roadmap"},
        known_decisions={"dec-9b41a7c3"},
    )
    assert any(f.rule == "UNRATIFIED_DECISION_ID" and f.severity == "ERROR" for f in findings)


def test_lint_spec_draft_status_is_tolerant(tmp_path):
    spec = tmp_path / "draft-spec.md"
    spec.write_text(
        """---
title: Early Brainstorm Draft
status: draft
---
# Rough Notes
No goal, no decision yet.
""",
        encoding="utf-8",
    )

    findings = lint_spec_file(
        str(spec),
        repo_root=str(tmp_path),
        known_goals={"goal-2458-master-roadmap"},
        known_decisions={"dec-9b41a7c3"},
        strict=False,
    )
    # Draft specs should only produce INFO/WARN, not breaking errors
    errors = [f for f in findings if f.severity == "ERROR"]
    assert len(errors) == 0


def test_cmd_spec_lint_single_file_cli(tmp_path, capsys):
    spec = tmp_path / "test.md"
    spec.write_text(
        """---
title: Spec
status: approved
parent_goal: g1
target_release: v0.32.3
decision_id: d1
---
""",
        encoding="utf-8",
    )
    args = argparse.Namespace(
        repo_root=str(tmp_path),
        spec_file=str(spec),
        strict=False,
    )

    # Mock load helpers to match d1 and g1
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("synlynk.spec_lint.load_known_goal_ids", lambda *a, **k: {"g1"})
        mp.setattr("synlynk.spec_lint.load_known_decision_ids", lambda *a, **k: {"d1"})
        rc = cmd_spec_lint(args)
        assert rc == 0

    captured = capsys.readouterr()
    assert "satisfies constitutional frontmatter" in captured.out
