"""Constitutional Spec Linter Engine and CLI.

Enforces the frontmatter governance contract ratified in dec-9b41a7c3 and dec-4e81b29a:
1. Every spec with status: approved MUST declare:
   - parent_goal: Valid goal_id registered in state.db (goals table)
   - target_release: Valid release tag (e.g. v0.32.0, v0.33.0)
   - decision_id: Valid ratified DECIDE record in project-docs/decisions/
2. Draft specs (status: draft / proposed) are permitted in staging but flagged
   with informational warnings if unanchored.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from synlynk.docgraph import parse_yaml_frontmatter

# Colors for terminal output
_RESET = "\033[0m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_BOLD = "\033[1m"


@dataclass
class SpecLintFinding:
    spec_path: str
    rule: str
    severity: str  # "ERROR" | "WARN" | "INFO"
    message: str
    line: int = 1

    def format_cli(self) -> str:
        color = _RED if self.severity == "ERROR" else (_YELLOW if self.severity == "WARN" else _CYAN)
        return f"  {color}✖ [{self.severity}] [{self.rule}]{_RESET} {self.spec_path}:{self.line} — {self.message}"


@dataclass
class SpecLintResult:
    scanned_count: int = 0
    passed_count: int = 0
    findings: List[SpecLintFinding] = field(default_factory=list)
    errors_count: int = 0
    warnings_count: int = 0

    @property
    def is_valid(self) -> bool:
        return self.errors_count == 0


def load_known_decision_ids(repo_root: str = ".") -> Set[str]:
    """Scan project-docs/decisions/ and extract all declared decision IDs."""
    dec_dir = os.path.join(repo_root, "project-docs", "decisions")
    if not os.path.isdir(dec_dir):
        return set()

    dec_ids: Set[str] = set()
    for root, _, files in os.walk(dec_dir):
        for fname in files:
            if fname.endswith(".md"):
                # Check for decision ID in filename pattern e.g. dec-9b41a7c3
                m_file = re.search(r"(dec-[a-fA-F0-9]{8}|dec-[a-zA-Z0-9]+)", fname)
                if m_file:
                    dec_ids.add(m_file.group(1))

                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                        front, _ = parse_yaml_frontmatter(fh.read(2048))
                        if isinstance(front, dict) and "decision_id" in front:
                            val = str(front["decision_id"]).strip()
                            if val:
                                dec_ids.add(val)
                except Exception:
                    continue
    return dec_ids


def load_known_goal_ids(conn=None, repo_root: Optional[str] = None) -> Set[str]:
    """Load valid goal IDs from canonical state.db goals table."""
    from synlynk.db import _get_db

    own_conn = conn is None
    if own_conn:
        try:
            conn = _get_db()
        except Exception:
            return set()

    try:
        has_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='goals'"
        ).fetchone()
        if not has_table:
            return set()

        rows = conn.execute("SELECT goal_id FROM goals").fetchall()
        return {r[0] for r in rows if r[0]}
    except Exception:
        return set()
    finally:
        if own_conn and conn is not None:
            conn.close()


def lint_spec_file(
    file_path: str,
    repo_root: str = ".",
    known_goals: Optional[Set[str]] = None,
    known_decisions: Optional[Set[str]] = None,
    strict: bool = False,
) -> List[SpecLintFinding]:
    """Lint a single specification file against the constitutional contract."""
    findings: List[SpecLintFinding] = []
    rel_path = os.path.relpath(file_path, repo_root)

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            raw_content = fh.read()
    except Exception as exc:
        findings.append(
            SpecLintFinding(
                spec_path=rel_path,
                rule="FILE_UNREADABLE",
                severity="ERROR",
                message=f"Could not read spec file: {exc}",
            )
        )
        return findings

    front, body = parse_yaml_frontmatter(raw_content)
    if not front:
        findings.append(
            SpecLintFinding(
                spec_path=rel_path,
                rule="MISSING_FRONTMATTER",
                severity="ERROR" if strict else "WARN",
                message="Spec lacks YAML frontmatter ('---' header).",
            )
        )
        return findings

    status = str(front.get("status", "draft")).strip().lower()
    is_approved = status in ("approved", "accepted", "ratified", "completed", "shipped")

    # 1. parent_goal check
    parent_goal = front.get("parent_goal") or front.get("goal")
    if not parent_goal:
        severity = "ERROR" if is_approved else ("WARN" if strict else "INFO")
        findings.append(
            SpecLintFinding(
                spec_path=rel_path,
                rule="MISSING_PARENT_GOAL",
                severity=severity,
                message=f"Spec declares status '{status}' but is missing 'parent_goal' attribute.",
            )
        )
    elif known_goals is not None and len(known_goals) > 0 and str(parent_goal).strip() not in known_goals:
        # Check if it matches goal pattern e.g. goal-xxxx or is unknown
        val = str(parent_goal).strip()
        severity = "ERROR" if is_approved else "WARN"
        findings.append(
            SpecLintFinding(
                spec_path=rel_path,
                rule="UNREGISTERED_GOAL_ID",
                severity=severity,
                message=f"parent_goal '{val}' is not registered in state.db goals table.",
            )
        )

    # 2. target_release check
    target_release = front.get("target_release") or front.get("milestone")
    if not target_release:
        severity = "ERROR" if is_approved else ("WARN" if strict else "INFO")
        findings.append(
            SpecLintFinding(
                spec_path=rel_path,
                rule="MISSING_TARGET_RELEASE",
                severity=severity,
                message=f"Spec declares status '{status}' but is missing 'target_release' attribute.",
            )
        )
    else:
        val = str(target_release).strip()
        if not re.match(r"^v?\d+\.\d+(\.\d+)?(-[a-zA-Z0-9._]+)?$", val):
            findings.append(
                SpecLintFinding(
                    spec_path=rel_path,
                    rule="INVALID_RELEASE_FORMAT",
                    severity="ERROR" if is_approved else "WARN",
                    message=f"target_release '{val}' does not match valid SemVer pattern (e.g. 'v0.32.0').",
                )
            )

    # 3. decision_id check
    decision_id = front.get("decision_id")
    if not decision_id:
        # If approved, must have an authoritative decision
        if is_approved:
            findings.append(
                SpecLintFinding(
                    spec_path=rel_path,
                    rule="MISSING_DECISION_ID",
                    severity="ERROR",
                    message="Approved spec must declare a 'decision_id' linking to a ratified DECIDE record.",
                )
            )
    elif known_decisions is not None and len(known_decisions) > 0:
        val = str(decision_id).strip()
        if val not in known_decisions:
            findings.append(
                SpecLintFinding(
                    spec_path=rel_path,
                    rule="UNRATIFIED_DECISION_ID",
                    severity="ERROR" if is_approved else "WARN",
                    message=f"decision_id '{val}' does not correspond to an existing record in project-docs/decisions/.",
                )
            )

    return findings


# Convenient alias
lint_specification_file = lint_spec_file


def lint_specs(
    specs_dir: Optional[str] = None,
    repo_root: str = ".",
    conn=None,
    strict: bool = False,
) -> SpecLintResult:
    """Scan and lint all specs in docs/superpowers/specs/."""
    if specs_dir is None:
        specs_dir = os.path.join(repo_root, "docs", "superpowers", "specs")

    result = SpecLintResult()
    if not os.path.isdir(specs_dir):
        return result

    known_goals = load_known_goal_ids(conn=conn)
    known_decisions = load_known_decision_ids(repo_root=repo_root)

    for root, dirs, files in os.walk(specs_dir):
        # Skip temporary, archive, or worktree dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("archive", "node_modules")]
        for fname in sorted(files):
            if not fname.endswith(".md") or fname.startswith("."):
                continue

            fpath = os.path.join(root, fname)
            result.scanned_count += 1
            findings = lint_spec_file(
                file_path=fpath,
                repo_root=repo_root,
                known_goals=known_goals,
                known_decisions=known_decisions,
                strict=strict,
            )
            if findings:
                result.findings.extend(findings)
                for f in findings:
                    if f.severity == "ERROR":
                        result.errors_count += 1
                    elif f.severity == "WARN":
                        result.warnings_count += 1
            else:
                result.passed_count += 1

    return result


def cmd_spec_lint(args: argparse.Namespace) -> int:
    """CLI entrypoint for 'synlynk spec lint'."""
    repo_root = getattr(args, "repo_root", ".") or "."
    strict = getattr(args, "strict", False)
    target_spec = getattr(args, "spec_file", None)

    print(f"\n{_BOLD}{_CYAN}▶ Synlynk Constitutional Spec Linter (dec-9b41a7c3){_RESET}\n")

    if target_spec:
        fpath = os.path.join(repo_root, target_spec) if not os.path.isabs(target_spec) else target_spec
        known_goals = load_known_goal_ids()
        known_decisions = load_known_decision_ids(repo_root=repo_root)
        findings = lint_spec_file(
            file_path=fpath,
            repo_root=repo_root,
            known_goals=known_goals,
            known_decisions=known_decisions,
            strict=strict,
        )
        if findings:
            for f in findings:
                print(f.format_cli())
            errs = sum(1 for f in findings if f.severity == "ERROR")
            print(f"\n{_RED}✖ Spec lint failed with {errs} error(s).{_RESET}\n")
            return 1 if errs > 0 else 0
        else:
            print(f"  {_GREEN}✓ Spec satisfies constitutional frontmatter contract.{_RESET}\n")
            return 0

    result = lint_specs(repo_root=repo_root, strict=strict)

    print(f"  Scanned:  {result.scanned_count} specs")
    print(f"  Passed:   {_GREEN}{result.passed_count}{_RESET}")
    print(f"  Warnings: {_YELLOW}{result.warnings_count}{_RESET}")
    print(f"  Errors:   {_RED if result.errors_count > 0 else _GREEN}{result.errors_count}{_RESET}\n")

    if result.findings:
        for f in result.findings:
            if f.severity == "ERROR" or (strict and f.severity == "WARN"):
                print(f.format_cli())
        print()

    if result.is_valid:
        print(f"  {_GREEN}✓ All specifications adhere to the Constitutional Frontmatter Invariant.{_RESET}\n")
        return 0
    else:
        print(f"  {_RED}✖ Spec verification failed. Please fix missing goals, target releases, or decision links.{_RESET}\n")
        return 1
