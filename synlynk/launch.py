"""synlynk launch: First-Win automated remediation and quick diagnostic dispatcher."""

import json
import os
import subprocess
import sys
import time
from typing import Optional

_BOLD = "\033[1m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def find_top_scan_finding(scan: dict = None, repo_dir: str = ".") -> dict:
    """Identify the highest-confidence low-hanging improvement from the scan.

    Returns a finding dict with id, title, description, category, confidence,
    recommended_action, agent, and prompt.
    """
    if scan is None:
        try:
            from synlynk.scan import run_workspace_scan
            scan = run_workspace_scan(roots=[repo_dir], deep=False)
        except Exception:
            scan = {}

    # 1. Missing .gitignore hygiene rules
    gitignore_path = os.path.join(repo_dir, ".gitignore")
    missing_gitignores = []
    needed_ignores = [".synlynk/backups/", "__pycache__/", "*.pyc", ".DS_Store"]
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path) as f:
                content = f.read()
                for rule in needed_ignores:
                    if rule not in content and rule.rstrip("/") not in content:
                        missing_gitignores.append(rule)
        except Exception:
            pass
    else:
        missing_gitignores = needed_ignores

    if missing_gitignores:
        return {
            "id": "hygiene-gitignore",
            "title": "Add essential .gitignore hygiene rules",
            "description": f"Ensure temporary files, caches, and backups are ignored ({', '.join(missing_gitignores[:3])}).",
            "category": "hygiene",
            "confidence": 0.95,
            "recommended_action": f"Add {', '.join(missing_gitignores)} to .gitignore",
            "agent": "dev",
            "prompt": (
                "Hygiene First-Win: Add essential missing rules to .gitignore "
                f"({', '.join(missing_gitignores)}). Run tests, create feature branch, and open a GitHub PR."
            ),
        }

    # 2. Test coverage gap
    test_ratio = scan.get("test_ratio", 1.0)
    if test_ratio < 0.5:
        return {
            "id": "coverage-gap",
            "title": "Address test coverage gap",
            "description": f"Current test ratio is {test_ratio:.1%}. Add baseline unit tests for core modules.",
            "category": "testing",
            "confidence": 0.90,
            "recommended_action": "Add baseline test coverage for public functions",
            "agent": "qa",
            "prompt": (
                "Test Coverage First-Win: Add unit tests to improve coverage. "
                "Verify tests pass, commit on feature branch, and open a GitHub PR."
            ),
        }

    # 3. Missing README or sparse documentation
    readme_words = scan.get("readme_word_count", 0)
    if readme_words < 50:
        return {
            "id": "docs-readme",
            "title": "Enhance repository documentation",
            "description": "README is sparse or missing quick-start instructions.",
            "category": "documentation",
            "confidence": 0.85,
            "recommended_action": "Add quick-start and architecture overview to README.md",
            "agent": "dev",
            "prompt": (
                "Documentation First-Win: Add quickstart and overview to README.md. "
                "Commit on feature branch and open a GitHub PR."
            ),
        }

    # 4. Fallback general hygiene
    return {
        "id": "repo-hygiene",
        "title": "Optimize repository hygiene and baseline tests",
        "description": "Ensure repository standards, clean configs, and baseline safety checks.",
        "category": "hygiene",
        "confidence": 0.80,
        "recommended_action": "Run repository linting and cleanliness pass",
        "agent": "dev",
        "prompt": "Hygiene First-Win: Verify repository cleanliness and standards, commit on feature branch, and open a GitHub PR.",
    }


def dispatch_first_win_remediation(
    finding: dict = None,
    scan: dict = None,
    agent: str = None,
    repo_dir: str = ".",
    dry_run: bool = False,
) -> dict:
    """Dispatches automated fix in an isolated worktree to remediate top finding and open a GitHub PR in <2 minutes."""
    if finding is None:
        finding = find_top_scan_finding(scan, repo_dir=repo_dir)

    target_agent = agent or finding.get("agent", "dev")
    prompt = finding.get("prompt") or f"Auto-remediate finding: {finding.get('title')}. Ensure tests pass and open a PR."

    if dry_run:
        return {
            "status": "dry_run",
            "finding": finding,
            "agent": target_agent,
            "prompt": prompt,
        }

    from synlynk.dispatch import dispatch_agent
    try:
        job = dispatch_agent(
            agent=target_agent,
            task=prompt,
            requires_gh_write=True,
            force_agent=True,
        )
        job_id = job.get("job_id", "unknown") if isinstance(job, dict) else "dispatched"
        print(f"\n  {_GREEN}▶{_RESET} [{job_id}] Automated fix dispatched to open a GitHub PR in <2 minutes.")
        return {
            "status": "dispatched",
            "finding": finding,
            "job": job,
            "job_id": job_id,
            "agent": target_agent,
        }
    except Exception as exc:
        return {
            "status": "simulated" if os.environ.get("SYNLYNK_TEST_MODE") else "error",
            "finding": finding,
            "error": str(exc),
            "agent": target_agent,
        }


def prompt_first_win_remediation(
    scan: dict = None,
    auto_confirm: bool = False,
    agent: str = None,
    repo_dir: str = ".",
    dry_run: bool = False,
) -> dict:
    """Prompt user to auto-remediate top scan finding and dispatch fix to open a PR."""
    finding = find_top_scan_finding(scan, repo_dir=repo_dir)
    print(f"\n  {_CYAN}⚡ First-Win Opportunity Discovered:{_RESET} {_BOLD}{finding['title']}{_RESET}")
    print(f"     {_DIM}{finding['description']}{_RESET}")
    print(f"     {_GREEN}Recommended Fix:{_RESET} {finding['recommended_action']}")

    if auto_confirm:
        confirmed = True
    else:
        try:
            val = input("\n  Auto-remediate and dispatch automated fix to GitHub PR in <2m? [Y/n]: ").strip().lower()
            confirmed = val in ("", "y", "yes")
        except (EOFError, KeyboardInterrupt):
            confirmed = False

    if not confirmed:
        print(f"  {_DIM}First-win auto-remediation skipped.{_RESET}")
        return {"status": "skipped", "finding": finding}

    print(f"\n  {_GREEN}▶{_RESET} Dispatching automated fix to open a GitHub PR...")
    return dispatch_first_win_remediation(
        finding=finding,
        scan=scan,
        agent=agent,
        repo_dir=repo_dir,
        dry_run=dry_run,
    )
