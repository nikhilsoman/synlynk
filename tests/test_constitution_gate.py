import os
import pytest
from synlynk.constitution_gate import check_constitution_gate


def test_constitution_gate_observe_mode(tmp_path):
    """Verify that in observe mode, missing citations generate warnings but do not fail the gate."""
    # Create mock policy with observe mode
    policy = {
        "constitution_authority": {
            "require_citation_mode": "observe"
        }
    }
    # Create empty repo structure with uncited instruction file
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Instructions\nDo some work here without citation tags.\n", encoding="utf-8")

    result = check_constitution_gate(str(tmp_path), policy)
    assert result["passed"] is True
    assert result["mode"] == "observe"
    assert len(result["warnings"]) > 0
    assert len(result["errors"]) == 0


def test_constitution_gate_enforce_mode_fails_on_uncited_clauses(tmp_path):
    """Verify that in enforce mode, uncited instruction files cause gate failure."""
    policy = {
        "constitution_authority": {
            "require_citation_mode": "enforce"
        }
    }
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Instructions\nDo some work here without citation tags.\n", encoding="utf-8")

    result = check_constitution_gate(str(tmp_path), policy)
    assert result["passed"] is False
    assert result["mode"] == "enforce"
    assert len(result["errors"]) > 0


def test_constitution_gate_passes_when_cited(tmp_path):
    """Verify that gate passes when all laws are cited across instructions."""
    policy = {
        "constitution_authority": {
            "require_citation_mode": "enforce"
        }
    }
    content = """# Instructions
<!-- constitution: law-0 -->
Secrets rule.
<!-- constitution: law-1 -->
Attribution rule.
<!-- constitution: law-2 -->
Evidence rule.
<!-- constitution: law-3 -->
Circuit breaker.
<!-- constitution: intent-invariant -->
GOVERNS linkage.
"""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(content, encoding="utf-8")

    result = check_constitution_gate(str(tmp_path), policy)
    assert result["passed"] is True
    assert len(result["errors"]) == 0
