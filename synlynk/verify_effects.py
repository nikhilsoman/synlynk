"""Pure Effect Verification Engine for dispatched jobs (Invariant 1).

Enforces the three-part invariant:
Succeeded <=> (rc == 0) and EffectVerified(Job) and VerificationPassed(Job)
"""

from dataclasses import dataclass, field
import os
import re
import subprocess
from typing import Any, Dict, List, Optional

from synlynk.jobs import (
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITHOUT_CHANGES,
    STATUS_FAILED_NOOP_DENIED,
    STATUS_FAILED_VERIFICATION,
    STATUS_FAILED,
)
from synlynk.gh_verify import (
    cross_branch_pr_effect_verified,
    gh_write_verified,
    local_commits_pushed,
    github_branch_effect_verified,
)
# PR1 public oracle exports.  The legacy boolean verifier below remains for
# compatibility callers; new reconciliation code uses the pure tri-state API.
from synlynk.job_truth import CompletionDecision, TriState, decide_job_outcome


@dataclass
class EffectVerificationResult:
    verified: bool
    status: str
    files_touched: List[str] = field(default_factory=list)
    diff_bytes: int = 0
    reason: Optional[str] = None
    gh_verified: Optional[bool] = None
    tests_passed: Optional[bool] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


def extract_transcript_gh_evidence(log_text: Optional[str]) -> Dict[str, Any]:
    """Scrape log text for positive GitHub review, merge, PR creation, comment, or close evidence."""
    if not log_text:
        return {}
    res: Dict[str, Any] = {}
    review_match = re.search(r"(?:Approved pull request #(\d+)|gh pr review\s+(\d+)\s+.*--approve)", log_text, re.IGNORECASE)
    if review_match:
        res["review_approved"] = True
        pr_num = review_match.group(1) or review_match.group(2)
        if pr_num:
            res["pr_number"] = pr_num

    merge_match = re.search(r"(?:Merged #(\d+)|Squash and merge pull request #(\d+)|gh pr merge\s+(\d+))", log_text, re.IGNORECASE)
    if merge_match:
        res["pr_merged"] = True
        pr_num = merge_match.group(1) or merge_match.group(2) or merge_match.group(3)
        if pr_num:
            res["pr_number"] = pr_num

    pr_url_match = re.search(r"https://github\.com/[^/]+/[^/]+/pull/(\d+)", log_text)
    if pr_url_match:
        res["pr_created"] = True
        res["pr_number"] = pr_url_match.group(1)
        res["pr_url"] = pr_url_match.group(0)

    issue_comment_url = re.search(
        r"https://github\.com/[^/]+/[^/]+/(?:issues|pull)/(\d+)#issuecomment-(\d+)",
        log_text,
    )
    if issue_comment_url:
        res["comment_posted"] = True
        res["issue_number"] = issue_comment_url.group(1)
        res["comment_id"] = issue_comment_url.group(2)
        res["comment_url"] = issue_comment_url.group(0)

    issue_comment_match = re.search(
        r"(?:commented on (?:issue|pull request) #(\d+)|gh (?:issue|pr) comment\s+(\d+))",
        log_text,
        re.IGNORECASE,
    )
    if issue_comment_match:
        res["comment_posted"] = True
        issue_num = issue_comment_match.group(1) or issue_comment_match.group(2)
        if issue_num and "issue_number" not in res:
            res["issue_number"] = issue_num

    close_match = re.search(
        r"(?:Closed pull request #(\d+)|Closed issue #(\d+)|gh (?:pr|issue) close\s+(\d+))",
        log_text,
        re.IGNORECASE,
    )
    if close_match:
        res["closed"] = True
        close_num = close_match.group(1) or close_match.group(2) or close_match.group(3)
        if close_num:
            res["closed_number"] = close_num

    return res



def _get_worktree_changed_files(
    worktree_path: str,
    base_sha: Optional[str] = None,
    git_state: Optional[dict] = None,
) -> List[str]:
    """Inspect git worktree for all changed files (committed and uncommitted)."""
    if not worktree_path or not os.path.isdir(worktree_path):
        return []
    
    files = set()

    # 0. Pre-computed git_state if supplied. Callers that already diffed
    # against the dispatch base (gh:#2245) put the right names here.
    if git_state:
        for p in git_state.get("changed_files") or []:
            if p:
                files.add(p)
        for p in git_state.get("remote_files_touched") or []:
            if p:
                files.add(p)
        if git_state.get("has_activity") or git_state.get("remote_has_activity") or (git_state.get("commits_ahead", 0) > 0) or git_state.get("dirty"):
            if not files:
                files.add("(git_activity_verified)")
    
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

    # 2. Committed changes since the job's diff base, not an older mainline.
    diff_base = base_sha
    if base_sha:
        try:
            from synlynk.jobs import _resolve_job_diff_base
            diff_base = _resolve_job_diff_base(worktree_path, base_sha) or base_sha
        except Exception:
            diff_base = base_sha
    if diff_base:
        try:
            res = subprocess.run(
                ["git", "-C", worktree_path, "diff", "--name-only", f"{diff_base}..HEAD"],
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
    worktree_branch: Optional[str] = None,
    started_at: Optional[str] = None,
    structured_telemetry: Optional[dict] = None,
    cross_branch_pr: Optional[str] = None,
) -> EffectVerificationResult:
    """Verify that a job with exit code 0 produced real effects before marking succeeded."""
    # Claude/Codex structured terminal events are the completion oracle.  The
    # subprocess exit code is retained for legacy/fallback callers only.
    if structured_telemetry and structured_telemetry.get("available"):
        if structured_telemetry.get("completed") is False:
            return EffectVerificationResult(
                verified=False,
                status=STATUS_FAILED,
                reason=structured_telemetry.get("error") or "Structured harness completion reported failure",
            )
        if structured_telemetry.get("completed") is True:
            exit_code = 0

    if exit_code != 0:
        return EffectVerificationResult(
            verified=False,
            status=STATUS_FAILED,
            reason=f"Job exited with non-zero exit code {exit_code}",
        )

    task_class_norm = (task_class or "mutating").strip().lower()
    gh_kwargs = dict(gh_verify_kwargs or {})
    expect = gh_kwargs.get("expect") or expected_gh_effect
    cross_evidence: Dict[str, Any] = {}
    if cross_branch_pr:
        review_only = task_class_norm == "review" or expect == "review_posted"
        cross = cross_branch_pr_effect_verified(
            cross_branch_pr,
            since=started_at or gh_kwargs.get("since"),
            worktree_branch=worktree_branch,
            expect_author=gh_kwargs.get("expect_author"),
            accept_reviews=True,
            accept_commits=not review_only,
            evidence=cross_evidence,
        )
        if cross is True:
            return EffectVerificationResult(
                verified=True,
                status=STATUS_COMPLETED,
                gh_verified=True,
                evidence=cross_evidence,
            )
        # A recorded cross-branch PR is the primary evidence. Local diff stays
        # in place only when this target is actually the job's own branch, or
        # when no target was recorded. State expectations (merge, pr open)
        # still use the scalar GitHub check below.
        state_expects = {"merged", "pr_open", "created"}
        same_branch = bool(cross_evidence.get("same_branch"))
        if (
            not same_branch
            and expect not in state_expects
            and task_class_norm not in ("gh_write", "review", "github_write")
            and cross is not True
        ):
            return EffectVerificationResult(
                verified=False,
                status=STATUS_FAILED_NOOP_DENIED,
                gh_verified=False,
                reason="Cross-branch PR had no review or commit after dispatch start",
                evidence=cross_evidence,
            )

    # 1. Classification Branch A: GH Write / Review Task
    # A review's durable effect is the remote GitHub review. Review workers
    # are intentionally read-only and may not be able to reach the canonical
    # state DB from their sandbox, so verify GitHub before any worktree checks.
    if task_class_norm in ("gh_write", "review", "github_write"):
        kwargs = dict(gh_verify_kwargs or {})
        log_text = kwargs.pop("log_text", None)
        if expected_gh_effect and "expect" not in kwargs:
            kwargs["expect"] = expected_gh_effect

        evidence = {}
        kwargs.setdefault("evidence", evidence)
        gh_ok = gh_write_verified(**kwargs)

        if not gh_ok and log_text:
            transcript_ev = extract_transcript_gh_evidence(log_text)
            expect_norm = (kwargs.get("expect") or expected_gh_effect or "").strip().lower()
            if (expect_norm in ("review_posted", "review") or task_class_norm == "review" or transcript_ev.get("review_approved")) and transcript_ev.get("review_approved"):
                evidence.update(transcript_ev)
                return EffectVerificationResult(
                    verified=True,
                    status=STATUS_COMPLETED,
                    gh_verified=True,
                    evidence=evidence,
                    reason="GitHub review verified from job transcript confirmation",
                )
            if (expect_norm in ("merged", "merge", "github_pr_merge") or transcript_ev.get("pr_merged")) and transcript_ev.get("pr_merged"):
                evidence.update(transcript_ev)
                return EffectVerificationResult(
                    verified=True,
                    status=STATUS_COMPLETED,
                    gh_verified=True,
                    evidence=evidence,
                    reason="GitHub PR merge verified from job transcript confirmation",
                )
            if (expect_norm in ("pr_open", "created", "github_pr_open") or transcript_ev.get("pr_created")) and transcript_ev.get("pr_created"):
                evidence.update(transcript_ev)
                return EffectVerificationResult(
                    verified=True,
                    status=STATUS_COMPLETED,
                    gh_verified=True,
                    evidence=evidence,
                    reason="GitHub PR creation verified from job transcript confirmation",
                )
            if (expect_norm in ("comment_posted", "comment") or transcript_ev.get("comment_posted")) and transcript_ev.get("comment_posted"):
                evidence.update(transcript_ev)
                return EffectVerificationResult(
                    verified=True,
                    status=STATUS_COMPLETED,
                    gh_verified=True,
                    evidence=evidence,
                    reason="GitHub comment verified from job transcript confirmation",
                )
            if (expect_norm in ("closed", "issue_closed", "pr_closed") or transcript_ev.get("closed")) and transcript_ev.get("closed"):
                evidence.update(transcript_ev)
                return EffectVerificationResult(
                    verified=True,
                    status=STATUS_COMPLETED,
                    gh_verified=True,
                    evidence=evidence,
                    reason="GitHub target close verified from job transcript confirmation",
                )

        if not gh_ok:
            return EffectVerificationResult(
                verified=False,
                status=STATUS_FAILED_NOOP_DENIED,
                gh_verified=False,
                reason="Expected GitHub effect was not verified directly via gh",
                evidence=evidence,
            )
        return EffectVerificationResult(
            verified=True,
            status=STATUS_COMPLETED,
            gh_verified=True,
            evidence=evidence,
        )

    commits_ahead = (git_state or {}).get("commits_ahead", 0)
    if worktree_path and worktree_branch and (commits_ahead or base_sha):
        if not local_commits_pushed(worktree_path, worktree_branch, base_sha):
            if github_branch_effect_verified(worktree_branch, since=started_at) is not True:
                return EffectVerificationResult(
                    verified=False,
                    status="unpushed_branch",
                    reason=f"local commits are not reachable on origin/{worktree_branch}",
                )

    # 2. Classification Branch B: Mutating Task
    if task_class_norm in ("mutating", "code", "mutation", "fix", "feat"):
        files_touched = _get_worktree_changed_files(worktree_path, base_sha, git_state=git_state) if worktree_path else []
        if not files_touched:
            if github_branch_effect_verified(worktree_branch, since=started_at) is True:
                return EffectVerificationResult(
                    verified=True,
                    status=STATUS_COMPLETED,
                    reason=f"GitHub PR exists for {worktree_branch}; local branch was removed after delivery",
                )
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
