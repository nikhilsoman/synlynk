"""Pure Effect Verification Engine for dispatched jobs (Invariant 1).

Enforces the three-part invariant:
Succeeded <=> (rc == 0) and EffectVerified(Job) and VerificationPassed(Job)
"""

from dataclasses import dataclass, field
import os
import subprocess
from typing import Any, Dict, List, Optional

from synlynk.jobs import (
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITHOUT_CHANGES,
    STATUS_FAILED_NOOP_DENIED,
    STATUS_FAILED_VERIFICATION,
    STATUS_FAILED,
)
from synlynk.gh_verify import gh_write_verified


@dataclass
class EffectVerificationResult:
    verified: bool
    status: str
    files_touched: List[str] = field(default_factory=list)
    diff_bytes: int = 0
    reason: Optional[str] = None
    gh_verified: Optional[bool] = None
    tests_passed: Optional[bool] = None


def _get_worktree_changed_files(
    worktree_path: str,
    base_sha: Optional[str] = None,
    git_state: Optional[dict] = None,
) -> List[str]:
    """Inspect git worktree for all changed files (committed and uncommitted)."""
    if not worktree_path or not os.path.isdir(worktree_path):
        return []
    
    files = set()

    # 0. Pre-computed git_state if supplied
    if git_state:
        for p in git_state.get("changed_files") or []:
            if p:
                files.add(p)
        for p in git_state.get("remote_files_touched") or []:
            if p:
                files.add(p)
    
    # 1. Uncommitted changes (working copy & untracked)
    try:
        res = subprocess.run(
            ["git", "-C", worktree_path, "status", "--short"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Git status format: XY <path> or XY <path1> -> <path2>
                parts = line.split(None, 1)
                if len(parts) >= 2:
                    path_part = parts[1]
                    if " -> " in path_part:
                        path_part = path_part.split(" -> ")[-1]
                    files.add(path_part.strip('\"\''))
    except Exception:
        pass

    # 2. Committed changes since base_sha
    if base_sha:
        try:
            res = subprocess.run(
                ["git", "-C", worktree_path, "diff", "--name-only", f"{base_sha}..HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    p = line.strip()
                    if p:
                        files.add(p.strip('\"\''))
        except Exception:
            pass

    return sorted(list(files))


def verify_job_effects(
    worktree_path: Optional[str] = None,
    base_sha: Optional[str] = None,
    task_class: str = "mutating",
    expected_gh_effect: Optional[str] = None,
    verification_cmd: Optional[str] = None,
    receipt_path: Optional[str] = None,
    gh_verify_kwargs: Optional[Dict[str, Any]] = None,
    git_state: Optional[dict] = None,
    exit_code: int = 0,
) -> EffectVerificationResult:
    """Verify that a job with exit code 0 produced real effects before marking succeeded."""
    if exit_code != 0:
        return EffectVerificationResult(
            verified=False,
            status=STATUS_FAILED,
            reason=f"Job exited with non-zero exit code {exit_code}",
        )

    task_class_norm = (task_class or "mutating").strip().lower()

    # 1. Classification Branch A: Mutating Task
    if task_class_norm in ("mutating", "code", "mutation", "fix", "feat"):
        files_touched = _get_worktree_changed_files(worktree_path, base_sha, git_state=git_state) if worktree_path else []
        if not files_touched:
            return EffectVerificationResult(
                verified=False,
                status=STATUS_COMPLETED_WITHOUT_CHANGES,
                files_touched=[],
                reason="Zero git diff and zero files touched for mutating task",
            )
        
        # If verification command provided, execute it
        if verification_cmd:
            try:
                cmd_cwd = worktree_path if (worktree_path and os.path.isdir(worktree_path)) else None
                cmd_res = subprocess.run(
                    verification_cmd,
                    shell=True,
                    cwd=cmd_cwd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if cmd_res.returncode != 0:
                    return EffectVerificationResult(
                        verified=False,
                        status=STATUS_FAILED_VERIFICATION,
                        files_touched=files_touched,
                        tests_passed=False,
                        reason=f"Verification command failed with exit code {cmd_res.returncode}: {cmd_res.stderr.strip() or cmd_res.stdout.strip()}",
                    )
            except Exception as e:
                return EffectVerificationResult(
                    verified=False,
                    status=STATUS_FAILED_VERIFICATION,
                    files_touched=files_touched,
                    tests_passed=False,
                    reason=f"Verification command raised exception: {e}",
                )

        return EffectVerificationResult(
            verified=True,
            status=STATUS_COMPLETED,
            files_touched=files_touched,
            tests_passed=True if verification_cmd else None,
        )

    # 2. Classification Branch B: GH Write / Review Task
    elif task_class_norm in ("gh_write", "review", "github_write"):
        kwargs = dict(gh_verify_kwargs or {})
        if expected_gh_effect and "expect" not in kwargs:
            kwargs["expect"] = expected_gh_effect
        
        gh_ok = gh_write_verified(**kwargs)
        if not gh_ok:
            return EffectVerificationResult(
                verified=False,
                status=STATUS_FAILED_NOOP_DENIED,
                gh_verified=False,
                reason="Expected GitHub effect was not verified",
            )
        return EffectVerificationResult(
            verified=True,
            status=STATUS_COMPLETED,
            gh_verified=True,
        )

    # 3. Classification Branch C: Analysis / Read-Only Task
    elif task_class_norm in ("analysis", "read_only", "readonly", "probe", "audit"):
        if receipt_path:
            if not os.path.exists(receipt_path) or os.path.getsize(receipt_path) == 0:
                return EffectVerificationResult(
                    verified=False,
                    status=STATUS_COMPLETED_WITHOUT_CHANGES,
                    reason=f"Analysis receipt missing or empty: {receipt_path}",
                )
        return EffectVerificationResult(
            verified=True,
            status=STATUS_COMPLETED,
        )

    # Fallback default
    return EffectVerificationResult(
        verified=True,
        status=STATUS_COMPLETED,
    )
