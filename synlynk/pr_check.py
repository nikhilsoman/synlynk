"""PR check verifiers: impact attestation using Graphify and constitutional spec linting."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import synlynk.impact


def _get_modified_symbols_from_diff(repo_root: str = ".") -> List[str]:
    """Extract modified function and class symbols from git diff."""
    symbols: List[str] = []
    try:
        diff_proc = subprocess.run(
            ["git", "-C", repo_root, "diff", "-U0", "HEAD~1"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if diff_proc.returncode != 0:
            diff_proc = subprocess.run(
                ["git", "-C", repo_root, "diff", "-U0", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )

        diff_text = diff_proc.stdout or ""
        pattern = re.compile(r"^\+\s*(?:async\s+def|def|class)\s+([a-zA-Z0-9_]+)", re.MULTILINE)
        symbols = pattern.findall(diff_text)
    except Exception:
        pass
    return sorted(list(set(symbols)))


def check_pr_impact_attestation(repo_root: str = ".") -> Dict[str, Any]:
    """Verify that all modified symbols in the PR have associated test coverage.
    
    Returns a dict with `passed: bool`, `error: Optional[str]`, and `untested_symbols: list`.
    """
    try:
        from synlynk.watch import check_and_refresh_ast_on_drift
        check_and_refresh_ast_on_drift(repo_root)
    except Exception:
        pass

    modified_symbols = _get_modified_symbols_from_diff(repo_root)
    if not modified_symbols:
        return {
            "passed": True,
            "untested_symbols": [],
            "tested_symbols": [],
            "message": "No modified symbols detected in PR diff.",
        }

    untested = []
    tested = []

    for sym in modified_symbols:
        report = synlynk.impact.calculate_impact(repo_root, sym)
        if not report.get("associated_tests"):
            untested.append(sym)
        else:
            tested.append(sym)

    if untested:
        first_untested = untested[0]
        return {
            "passed": False,
            "error": f"{first_untested} has no associated test coverage (total untested: {len(untested)})",
            "untested_symbols": untested,
            "tested_symbols": tested,
        }

    return {
        "passed": True,
        "untested_symbols": [],
        "tested_symbols": tested,
        "message": f"All {len(tested)} modified symbols have associated test coverage in the knowledge graph.",
    }


def _get_changed_files_in_pr(repo_root: str = ".", pr_number: Optional[int] = None) -> List[str]:
    """Get list of changed files relative to repo_root for a PR or active branch."""
    if pr_number is not None:
        try:
            from synlynk.qa_gate import _gh_pr_changed_files
            files = _gh_pr_changed_files(pr_number)
            if files:
                return files
        except Exception:
            pass

    # Fallback to git diff
    for cmd in (
        ["git", "-C", repo_root, "diff", "--name-only", "origin/main...HEAD"],
        ["git", "-C", repo_root, "diff", "--name-only", "main...HEAD"],
        ["git", "-C", repo_root, "diff", "--name-only", "HEAD~1"],
        ["git", "-C", repo_root, "diff", "--name-only", "HEAD"],
    ):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                return [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except Exception:
            pass
    return []


def check_pr_spec_gate(
    repo_root: str = ".",
    pr_number: Optional[int] = None,
    strict: bool = False,
    changed_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Check that any specifications modified or added in this PR pass constitutional spec linting.

    Returns a dict with:
        passed: bool
        specs_checked: List[str]
        findings: List[Dict[str, Any]]
        error: Optional[str]
        message: Optional[str]
    """
    if changed_files is None:
        changed_files = _get_changed_files_in_pr(repo_root, pr_number)

    spec_files: List[str] = []
    for f in (changed_files or []):
        norm_f = f.replace("\\", "/").lstrip("./")
        if norm_f.startswith("docs/superpowers/specs/") and norm_f.endswith(".md"):
            spec_files.append(norm_f)

    if not spec_files:
        return {
            "passed": True,
            "specs_checked": [],
            "findings": [],
            "error": None,
            "message": "No specifications modified in this PR.",
        }

    from synlynk.spec_lint import lint_spec_file, load_known_decision_ids, load_known_goal_ids

    known_goals = load_known_goal_ids(repo_root=repo_root)
    known_decisions = load_known_decision_ids(repo_root=repo_root)

    all_findings: List[Dict[str, Any]] = []
    errors_count = 0
    checked_existing: List[str] = []

    for spec_rel in spec_files:
        full_path = os.path.join(repo_root, spec_rel)
        if not os.path.exists(full_path):
            continue
        checked_existing.append(spec_rel)

        findings = lint_spec_file(
            full_path,
            repo_root=repo_root,
            known_goals=known_goals,
            known_decisions=known_decisions,
            strict=strict,
        )
        for f in findings:
            all_findings.append({
                "file": f.spec_path,
                "rule": f.rule,
                "severity": f.severity,
                "message": f.message,
                "line": f.line,
            })
            if f.severity == "ERROR" or (strict and f.severity == "WARN"):
                errors_count += 1

    if not checked_existing:
        return {
            "passed": True,
            "specs_checked": [],
            "findings": [],
            "error": None,
            "message": "No existing specifications modified in this PR.",
        }

    if errors_count > 0:
        return {
            "passed": False,
            "specs_checked": checked_existing,
            "findings": all_findings,
            "error": f"Constitutional spec linting failed with {errors_count} error(s) across modified specifications.",
            "message": f"{errors_count} error(s) detected in touched specifications.",
        }

    return {
        "passed": True,
        "specs_checked": checked_existing,
        "findings": all_findings,
        "error": None,
        "message": f"All {len(checked_existing)} modified specification(s) passed constitutional linting.",
    }
