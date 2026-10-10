"""Brownfield evidence mapping and deterministic goal synthesis.

Converts discovered repository evidence (AST metrics, test ratio, manifests,
open issues) into 3-5 durable goals adhering to the standard Synlynk goal
schema (see `synlynk.greenfield_blueprints.synthesize_greenfield_goals` for
the Greenfield counterpart). Also provides an ambient, 1-shot fleet
enrichment pass that refines the deterministic goals when a harness is
available, with a strict offline/timeout fail-safe back to the original
goals.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Callable, List, Optional

TARGET_MILESTONE = "v1.0.0-rc1"

_TEST_RATIO_THRESHOLD = 0.25

_KNOWN_HARNESS_CLIS = ["claude", "codex", "agy", "grok"]


def _test_ratio(evidence: dict) -> float:
    code_files = evidence.get("code_files") or []
    test_files = evidence.get("test_files") or []
    if not code_files:
        return 0.0
    return len(test_files) / len(code_files)


def synthesize_brownfield_goals(evidence: Optional[dict]) -> List[dict]:
    """Map Brownfield repository evidence into 3-5 deterministic goals.

    `evidence` keys: code_files, test_files, manifests, open_issues,
    languages, uncommitted_diffs. All are optional and default to empty.
    """

    evidence = evidence or {}
    manifests = evidence.get("manifests") or []
    open_issues = evidence.get("open_issues") or []
    uncommitted_diffs = evidence.get("uncommitted_diffs") or []
    languages = evidence.get("languages") or []
    ratio = _test_ratio(evidence)

    goals: List[dict] = [
        {
            "id": "goal-baseline-preflight",
            "title": "Baseline Health & Fleet Preflight Parity",
            "category": "foundation",
            "priority": "P0",
            "rationale": (
                "Establishes a trustworthy starting point before any other "
                "work begins: confirms `synlynk doctor` passes, the test "
                "runner is green in an isolated worktree, and a runtime "
                "baseline is recorded for regression comparison."
            ),
            "acceptance_criteria": [
                "Run `synlynk doctor` and confirm a clean pass",
                "Confirm the existing test suite passes in a fresh worktree",
                "Record a runtime/performance baseline for comparison",
            ],
            "target_milestone": TARGET_MILESTONE,
        }
    ]

    if ratio < _TEST_RATIO_THRESHOLD:
        goals.append(
            {
                "id": "goal-test-coverage-remediation",
                "title": "High-Risk Test Coverage Remediation",
                "category": "quality",
                "priority": "P0",
                "rationale": (
                    f"Test-to-source ratio is {ratio:.2f}, below the "
                    f"{_TEST_RATIO_THRESHOLD:.2f} safety threshold "
                    f"({len(evidence.get('test_files') or [])} test files vs "
                    f"{len(evidence.get('code_files') or [])} code files). "
                    "Untested modules are the highest-risk surface for "
                    "autonomous changes."
                ),
                "acceptance_criteria": [
                    "AST-inspect modules with zero test coverage",
                    "Add reproduction tests for the highest-risk hotspots",
                    "Raise overall test coverage by at least 15%",
                ],
                "target_milestone": TARGET_MILESTONE,
            }
        )
    else:
        goals.append(
            {
                "id": "goal-regression-hardening",
                "title": "Regression Suite Hardening & CI Acceleration",
                "category": "quality",
                "priority": "P1",
                "rationale": (
                    f"Test-to-source ratio is {ratio:.2f}, already at or above "
                    f"the {_TEST_RATIO_THRESHOLD:.2f} safety threshold, so "
                    "the priority shifts from closing coverage gaps to "
                    "hardening the existing regression suite and keeping CI "
                    "fast."
                ),
                "acceptance_criteria": [
                    "Identify and de-flake the slowest/least reliable tests",
                    "Reduce end-to-end CI wall-clock time",
                    "Document the regression suite's coverage boundaries",
                ],
                "target_milestone": TARGET_MILESTONE,
            }
        )

    goals.append(
        {
            "id": "goal-dependency-modernization",
            "title": "Dependency Modernization & Manifest Audit",
            "category": "maintenance",
            "priority": "P1",
            "rationale": (
                f"Discovered {len(manifests)} manifest(s) across "
                f"{len(languages)} language(s)"
                + (f" with {len(uncommitted_diffs)} uncommitted diff(s)" if uncommitted_diffs else "")
                + "; stale or vulnerable dependencies are a standing risk "
                "that compounds the longer they go unaudited."
            ),
            "acceptance_criteria": [
                "Audit all discovered manifests for outdated/vulnerable pins",
                "Upgrade dependencies with a passing test suite per bump",
                "Record the audit outcome in project-docs/",
            ],
            "target_milestone": TARGET_MILESTONE,
        }
    )

    goals.append(
        {
            "id": "goal-feature-acceleration",
            "title": "Issue Triage & Unattended Milestone Velocity",
            "category": "feature",
            "priority": "P1",
            "rationale": (
                f"{len(open_issues)} open issue(s) discovered; triaging and "
                "sequencing them unblocks unattended milestone velocity "
                "toward the target release."
            ),
            "acceptance_criteria": [
                "Triage all open issues into priority buckets",
                "Dispatch the highest-priority issues as scoped tasks",
                "Track milestone velocity against target_milestone",
            ],
            "target_milestone": TARGET_MILESTONE,
        }
    )

    return goals


def _detect_active_harness() -> Optional[str]:
    """Return the name of an available harness CLI, or None if offline."""

    for name in _KNOWN_HARNESS_CLIS:
        if shutil.which(name):
            return name
    return None


def _run_harness_enrichment(
    harness: str, goals: List[dict], evidence: dict, timeout: float
) -> Optional[dict]:
    """Execute a 1-shot harness refinement pass. Returns a mapping of
    goal id -> refinement fields, or None/raises on any failure."""

    prompt = (
        "Refine these repository goals using the discovered evidence. "
        "Return strict JSON only."
    )
    result = subprocess.run(
        [harness, "--print", prompt],
        input="",
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    import json

    return json.loads(result.stdout)


def _merge_refinements(goals: List[dict], refinements: dict) -> List[dict]:
    merged = []
    for goal in goals:
        refinement = refinements.get(goal["id"]) if refinements else None
        if not refinement:
            merged.append(goal)
            continue
        updated = dict(goal)
        if refinement.get("title"):
            updated["title"] = refinement["title"]
        if refinement.get("acceptance_criteria"):
            updated["acceptance_criteria"] = refinement["acceptance_criteria"]
        if refinement.get("rationale"):
            updated["rationale"] = refinement["rationale"]
        merged.append(updated)
    return merged


def enrich_goals_ambient(
    goals: List[dict],
    evidence: dict,
    timeout: float = 3.0,
    harness_runner: Optional[Callable[[str, List[dict], dict, float], Optional[dict]]] = None,
) -> List[dict]:
    """Non-blocking, best-effort refinement of deterministic goals.

    Fails safe to the original `goals` list unchanged whenever no harness
    CLI is available (offline), the call times out, or any error occurs.
    Never raises.
    """

    harness = _detect_active_harness()
    if harness is None:
        return goals

    runner = harness_runner or _run_harness_enrichment
    try:
        refinements = runner(harness, goals, evidence, timeout)
    except Exception:
        return goals

    if not refinements:
        return goals

    try:
        return _merge_refinements(goals, refinements)
    except Exception:
        return goals
