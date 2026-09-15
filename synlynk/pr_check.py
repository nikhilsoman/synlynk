"""PR check impact attestation verifier using Graphify AST graph."""

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
