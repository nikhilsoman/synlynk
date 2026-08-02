"""synlynk worktree: audit and clean up stale git worktrees/branches."""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class WorktreeEntry:
    path: str
    branch: str
    nested_under: Optional[str] = None


@dataclass
class WorktreeVerdict:
    path: str
    branch: str
    verdict: str  # "safe" | "needs-review" | "unsafe"
    reason: str
    nested_under: Optional[str] = None


def _parse_worktree_porcelain(text: str) -> list:
    """Parses `git worktree list --porcelain` output into raw dicts."""
    entries = []
    current = None
    for line in text.splitlines():
        if line.startswith("worktree "):
            if current is not None:
                entries.append(current)
            current = {"path": line[len("worktree "):].strip(), "branch": None, "bare": False}
        elif current is None:
            continue
        elif line.startswith("branch "):
            ref = line[len("branch "):].strip()
            current["branch"] = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        elif line.startswith("bare"):
            current["bare"] = True
    if current is not None:
        entries.append(current)
    return entries


def _is_subpath(child: str, parent: str) -> bool:
    child_r = os.path.realpath(child)
    parent_r = os.path.realpath(parent)
    return child_r != parent_r and child_r.startswith(parent_r + os.sep)


def _build_worktree_entries(raw_entries: list, main_repo_path: str, cwd_worktree_path: str) -> list:
    """Excludes the main repo checkout and cwd's own worktree, then computes nesting."""
    filtered = []
    for raw in raw_entries:
        path = raw.get("path")
        if not path or raw.get("bare"):
            continue
        if os.path.realpath(path) == os.path.realpath(main_repo_path):
            continue
        if os.path.realpath(path) == os.path.realpath(cwd_worktree_path):
            continue
        filtered.append(WorktreeEntry(path=path, branch=raw.get("branch") or ""))

    for entry in filtered:
        candidates = [other for other in filtered if _is_subpath(entry.path, other.path)]
        if candidates:
            parent = max(candidates, key=lambda o: len(o.path))
            entry.nested_under = parent.path

    return filtered


def _classify_worktree(
    entry: WorktreeEntry,
    worktree_missing: bool,
    is_dirty: bool,
    dirty_summary: str,
    is_ancestor: bool,
    gh_available: bool,
    pr_info,
    net_diff_lines,
    commits_ahead: int,
) -> WorktreeVerdict:
    """Pure classifier — rules 1-3 of the spec's ordered algorithm (dirty
    override → ancestor check → PR state). Takes pre-fetched git/gh signals
    as arguments; does not shell out itself."""
    if worktree_missing:
        return WorktreeVerdict(
            entry.path, entry.branch, "safe",
            "worktree directory missing — stale registration", entry.nested_under,
        )
    if is_dirty:
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            f"dirty: {dirty_summary}", entry.nested_under,
        )
    if is_ancestor:
        return WorktreeVerdict(
            entry.path, entry.branch, "safe",
            "merged, direct ancestor", entry.nested_under,
        )
    if not gh_available:
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            "could not verify PR state — gh unavailable", entry.nested_under,
        )
    if pr_info is None:
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            f"no PR found, {commits_ahead} commits ahead of main", entry.nested_under,
        )

    state = pr_info.get("state")
    number = pr_info.get("number")
    if state == "MERGED":
        return WorktreeVerdict(
            entry.path, entry.branch, "safe", f"PR #{number} merged", entry.nested_under,
        )
    if state == "CLOSED":
        net = net_diff_lines if net_diff_lines is not None else 0
        if net <= 0:
            return WorktreeVerdict(
                entry.path, entry.branch, "safe",
                f"PR #{number} closed, stale — no unique content vs main", entry.nested_under,
            )
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            f"PR #{number} closed, {net} net lines of unmerged content", entry.nested_under,
        )
    if state == "OPEN":
        return WorktreeVerdict(
            entry.path, entry.branch, "unsafe", f"PR #{number} open — active work", entry.nested_under,
        )
    return WorktreeVerdict(
        entry.path, entry.branch, "needs-review",
        f"no PR found, {commits_ahead} commits ahead of main", entry.nested_under,
    )


_VERDICT_RANK = {"safe": 0, "needs-review": 1, "unsafe": 2}


def _apply_nesting_floor(verdicts: list) -> list:
    """Second pass: a nested worktree's verdict can never be better than its
    parent's.

    `needs-review` is the floor unless the parent is `unsafe`.
    """
    by_path = {v.path: v for v in verdicts}
    result = []
    for v in verdicts:
        parent = by_path.get(v.nested_under) if v.nested_under else None
        if parent is None or parent.verdict == "safe":
            result.append(v)
            continue
        floor_verdict = "unsafe" if parent.verdict == "unsafe" else "needs-review"
        if _VERDICT_RANK[floor_verdict] > _VERDICT_RANK[v.verdict]:
            result.append(WorktreeVerdict(
                v.path, v.branch, floor_verdict,
                f"{v.reason}; parent worktree not yet safe", v.nested_under,
            ))
        else:
            result.append(v)
    return result


def _gh_auth_available() -> bool:
    try:
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _git_status_dirty(path: str):
    result = subprocess.run(
        ["git", "status", "--short"], cwd=path, capture_output=True, text=True, timeout=10,
    )
    output = result.stdout.strip()
    if not output:
        return False, ""
    return True, output.splitlines()[0]


def _git_is_ancestor(branch: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, "origin/main"],
        cwd=path, capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0


def _git_commits_ahead(branch: str, path: str) -> int:
    result = subprocess.run(
        ["git", "log", f"origin/main..{branch}", "--oneline"],
        cwd=path, capture_output=True, text=True, timeout=10,
    )
    return len([line for line in result.stdout.splitlines() if line.strip()])


def _git_net_diff_lines(branch: str, path: str) -> int:
    result = subprocess.run(
        ["git", "diff", f"origin/main..{branch}", "--shortstat"],
        cwd=path, capture_output=True, text=True, timeout=10,
    )
    text = result.stdout.strip()
    ins_match = re.search(r"(\d+) insertion", text)
    del_match = re.search(r"(\d+) deletion", text)
    insertions = int(ins_match.group(1)) if ins_match else 0
    deletions = int(del_match.group(1)) if del_match else 0
    return insertions - deletions


def _gh_pr_for_branch(branch: str):
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "all",
            "--search",
            f"head:{branch}",
            "--json",
            "number,state,mergedAt",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except (ValueError, json.JSONDecodeError):
        return None
    return data[0] if data else None


def _gather_worktree_signals(entry: WorktreeEntry, gh_available: bool) -> dict:
    if not os.path.isdir(entry.path):
        return {"worktree_missing": True}
    try:
        is_dirty, dirty_summary = _git_status_dirty(entry.path)
        if is_dirty:
            return {"worktree_missing": False, "is_dirty": True, "dirty_summary": dirty_summary}

        is_ancestor = _git_is_ancestor(entry.branch, entry.path)
        if is_ancestor:
            return {"worktree_missing": False, "is_dirty": False, "is_ancestor": True}

        pr_info = None
        net_diff_lines = None
        if gh_available:
            pr_info = _gh_pr_for_branch(entry.branch)
            if pr_info and pr_info.get("state") == "CLOSED":
                net_diff_lines = _git_net_diff_lines(entry.branch, entry.path)
        commits_ahead = _git_commits_ahead(entry.branch, entry.path)
        return {
            "worktree_missing": False,
            "is_dirty": False,
            "is_ancestor": False,
            "gh_available": gh_available,
            "pr_info": pr_info,
            "net_diff_lines": net_diff_lines,
            "commits_ahead": commits_ahead,
        }
    except (subprocess.SubprocessError, OSError) as exc:
        return {"error": str(exc)}


def _verdict_from_signals(entry: WorktreeEntry, signals: dict, gh_available: bool) -> WorktreeVerdict:
    if signals.get("error"):
        return WorktreeVerdict(entry.path, entry.branch, "needs-review", signals["error"], entry.nested_under)
    return _classify_worktree(
        entry,
        worktree_missing=signals.get("worktree_missing", False),
        is_dirty=signals.get("is_dirty", False),
        dirty_summary=signals.get("dirty_summary", ""),
        is_ancestor=signals.get("is_ancestor", False),
        gh_available=signals.get("gh_available", gh_available),
        pr_info=signals.get("pr_info"),
        net_diff_lines=signals.get("net_diff_lines"),
        commits_ahead=signals.get("commits_ahead", 0),
    )


def _get_repo_root() -> str:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
    return result.stdout.strip()


def _list_worktrees(main_repo_path: str, cwd_worktree_path: str) -> list:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=main_repo_path, capture_output=True, text=True, timeout=10,
    )
    raw = _parse_worktree_porcelain(result.stdout)
    return _build_worktree_entries(raw, main_repo_path, cwd_worktree_path)


def _collect_verdicts(main_repo_path: str, cwd_worktree_path: str) -> list:
    entries = _list_worktrees(main_repo_path, cwd_worktree_path)
    gh_available = _gh_auth_available()
    verdicts = []
    for entry in entries:
        signals = _gather_worktree_signals(entry, gh_available)
        verdicts.append(_verdict_from_signals(entry, signals, gh_available))
    return _apply_nesting_floor(verdicts)


def _format_audit_report(verdicts: list, json_output: bool = False) -> str:
    if json_output:
        payload = [
            {
                "path": v.path,
                "branch": v.branch,
                "verdict": v.verdict,
                "reason": v.reason,
                "nested_under": v.nested_under,
            }
            for v in verdicts
        ]
        return json.dumps(payload, indent=2)

    if not verdicts:
        return "No stale worktrees — nothing to audit."

    safe = [v for v in verdicts if v.verdict == "safe"]
    needs_review = [v for v in verdicts if v.verdict == "needs-review"]
    unsafe = [v for v in verdicts if v.verdict == "unsafe"]

    lines = [
        f"SYNLYNK WORKTREE AUDIT   {len(verdicts)} worktrees checked (excluding main + current session)",
        "",
    ]
    if safe:
        lines.append(f"SAFE ({len(safe)}) — merged/stale, no action needed but removable")
        for v in safe:
            lines.append(f"  {v.branch:<30}  {v.reason}")
        lines.append("")
    if needs_review:
        lines.append(f"NEEDS-REVIEW ({len(needs_review)}) — a human should look")
        for v in needs_review:
            lines.append(f"  {v.branch:<30}  {v.reason}")
        lines.append("")
    if unsafe:
        lines.append(f"UNSAFE ({len(unsafe)}) — active, do not touch")
        for v in unsafe:
            lines.append(f"  {v.branch:<30}  {v.reason}")
        lines.append("")
    if safe:
        lines.append(f"Run `synlynk worktree clean --apply` to remove the {len(safe)} SAFE items")

    return "\n".join(lines).rstrip()


def cmd_worktree_audit(json_output: bool = False) -> str:
    main_repo_path = _get_repo_root()
    cwd_worktree_path = os.getcwd()
    verdicts = _collect_verdicts(main_repo_path, cwd_worktree_path)
    output = _format_audit_report(verdicts, json_output)
    print(output)
    return output


def _nesting_depth(verdict: WorktreeVerdict, by_path: dict) -> int:
    depth = 0
    cur = verdict
    seen = set()
    while cur.nested_under and cur.nested_under in by_path and cur.path not in seen:
        seen.add(cur.path)
        depth += 1
        cur = by_path[cur.nested_under]
    return depth


def cmd_worktree_clean(apply: bool = False, json_output: bool = False) -> str:
    main_repo_path = _get_repo_root()
    cwd_worktree_path = os.getcwd()
    verdicts = _collect_verdicts(main_repo_path, cwd_worktree_path)

    if not apply:
        safe_count = sum(1 for v in verdicts if v.verdict == "safe")
        if json_output:
            payload = {
                "dry_run": True,
                "would_remove": safe_count,
                "items": [
                    {
                        "path": v.path,
                        "branch": v.branch,
                        "verdict": v.verdict,
                        "reason": v.reason,
                        "nested_under": v.nested_under,
                    }
                    for v in verdicts
                ],
            }
            output = json.dumps(payload, indent=2)
        else:
            report = _format_audit_report(verdicts, json_output=False)
            summary = f"[dry-run] would remove {safe_count} worktrees + branches (use --apply)"
            output = f"{report}\n\n{summary}" if report != "No stale worktrees — nothing to audit." else report
        print(output)
        return output

    by_path = {v.path: v for v in verdicts}
    safe_verdicts = [v for v in verdicts if v.verdict == "safe"]
    safe_verdicts.sort(key=lambda v: _nesting_depth(v, by_path), reverse=True)

    result_lines = []
    for v in safe_verdicts:
        wt_status = "removed"
        try:
            result = subprocess.run(
                ["git", "worktree", "remove", "--force", v.path],
                cwd=main_repo_path, capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                wt_status = f"FAILED({result.stderr.strip()[:80]})"
        except (subprocess.SubprocessError, OSError) as exc:
            wt_status = f"FAILED({exc})"

        branch_status = "deleted"
        try:
            result = subprocess.run(
                ["git", "branch", "-D", v.branch],
                cwd=main_repo_path, capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                branch_status = f"FAILED({result.stderr.strip()[:80]})"
        except (subprocess.SubprocessError, OSError) as exc:
            branch_status = f"FAILED({exc})"

        remote_status = "remote-none/skip"
        try:
            result = subprocess.run(
                ["git", "push", "origin", "--delete", v.branch],
                cwd=main_repo_path, capture_output=True, text=True, timeout=15,
            )
            remote_status = "remote-deleted" if result.returncode == 0 else "remote-none/skip"
        except (subprocess.SubprocessError, OSError):
            remote_status = "remote-none/skip"

        result_lines.append(f"{v.branch}   wt={wt_status}   branch={branch_status}   {remote_status}")

    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=main_repo_path, capture_output=True, text=True, timeout=15,
    )

    if json_output:
        output = json.dumps({"applied": True, "results": result_lines}, indent=2)
    else:
        output = "\n".join(result_lines) if result_lines else "No SAFE items to remove."
    print(output)
    return output
