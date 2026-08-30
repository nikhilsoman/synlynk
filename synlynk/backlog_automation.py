"""GOVERNS backlog automation: dedup, goal resolution, and filing for
discovered/planned work. See docs/superpowers/specs/2026-08-29-governs-backlog-automation-design.md.
"""

import hashlib
import json
import re
import subprocess


def compute_signal_hash(title: str, source: str) -> str:
    """Stable hash of a normalized title + source, used as the dedup key."""
    normalized = re.sub(r"\s+", " ", title.strip().lower())
    return hashlib.md5(f"{source}:{normalized}".encode()).hexdigest()[:16]


def has_ledger_duplicate(conn, signal_hash: str) -> bool:
    """True if signal_hash already has a backlog_proposals row (filed or declined)."""
    row = conn.execute(
        "SELECT 1 FROM backlog_proposals WHERE signal_hash=? LIMIT 1", (signal_hash,)
    ).fetchone()
    return row is not None


def record_proposal(conn, signal_hash: str, title: str, source: str, status: str,
                     gh_issue_url, story_id, goal_id, goal_match_basis, session_id) -> None:
    """Insert a backlog_proposals ledger row. Caller commits."""
    conn.execute(
        "INSERT INTO backlog_proposals "
        "(signal_hash, title, source, status, gh_issue_url, story_id, goal_id, goal_match_basis, session_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal_hash, title, source, status, gh_issue_url, story_id, goal_id, goal_match_basis, session_id),
    )
    conn.commit()


def search_similar_issues(title: str) -> list:
    """Search open+closed GitHub issues for similar titles via `gh issue list --search`.

    Returns a list of {"title": ..., "url": ...} dicts, or [] on any gh failure.
    """
    result = subprocess.run(
        ["gh", "issue", "list", "--search", title, "--state", "all",
         "--json", "title,url", "--limit", "10"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        return []


def resolve_goal(conn, goal_id: str = None, new_goal_outcome: str = None,
                  new_goal_criterion: str = None) -> tuple:
    """Resolve which goal a story should link to.

    Priority: explicit goal_id > create-new (outcome+criterion given) > no goal.
    The caller (an interactive agent) has already done any "which goal fits best"
    reasoning before calling this — this function only executes the decision.
    Returns (goal_id_or_None, basis_string).
    """
    from synlynk.db import cmd_goal_create

    if goal_id:
        row = conn.execute("SELECT goal_id FROM goals WHERE goal_id=?", (goal_id,)).fetchone()
        if row:
            return goal_id, f"explicit goal_id passed: {goal_id}"
        return None, f"no goal: explicit goal_id {goal_id!r} not found in goals table"

    if new_goal_outcome and new_goal_criterion:
        new_id = cmd_goal_create(new_goal_outcome, new_goal_criterion, role="pm")
        return new_id, f"new goal created: no existing goal matched ({new_goal_outcome!r})"

    return None, "no goal: no goal_id, session goal, or new-goal outcome/criterion given"


def _repo_slug() -> str:
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _create_github_issue(title: str, body: str, parent_issue, labels: str) -> str:
    """Create the issue, then register it as a GitHub sub-issue of parent_issue.
    Returns the new issue's URL, or '' on failure.
    """
    result = subprocess.run(
        ["gh", "issue", "create", "--title", title, "--body", body, "--label", labels],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return ""
    issue_url = result.stdout.strip()
    if not parent_issue:
        return issue_url

    issue_number = issue_url.rstrip("/").rsplit("/", 1)[-1]
    repo = _repo_slug()
    if not repo:
        return issue_url

    view_result = subprocess.run(
        ["gh", "api", f"repos/{repo}/issues/{issue_number}", "--jq", ".id"],
        capture_output=True, text=True,
    )
    if view_result.returncode != 0 or not view_result.stdout.strip():
        return issue_url
    child_db_id = view_result.stdout.strip()

    subprocess.run(
        ["gh", "api", f"repos/{repo}/issues/{parent_issue}/sub_issues",
         "-X", "POST", "-f", f"sub_issue_id={child_db_id}"],
        capture_output=True, text=True,
    )
    return issue_url


def file_backlog_item(conn, title: str, body: str, source: str, session_id: str = None,
                       goal_id: str = None, new_goal_outcome: str = None,
                       new_goal_criterion: str = None, parent_issue=1198,
                       labels: str = "enhancement") -> dict:
    """Dedup (local ledger, then GitHub title search), resolve goal, file the GitHub
    issue + story + ledger row.

    Returns {"status": "filed"|"skipped_duplicate"|"skipped_duplicate_gh",
             "gh_issue_url": str|None, "story_id": str|None}.
    """
    signal_hash = compute_signal_hash(title, source)
    if has_ledger_duplicate(conn, signal_hash):
        return {"status": "skipped_duplicate", "gh_issue_url": None, "story_id": None}

    normalized_title = re.sub(r"\s+", " ", title.strip().lower())
    for hit in search_similar_issues(title):
        hit_title = re.sub(r"\s+", " ", hit.get("title", "").strip().lower())
        if hit_title == normalized_title:
            return {"status": "skipped_duplicate_gh", "gh_issue_url": hit.get("url"), "story_id": None}

    resolved_goal_id, basis = resolve_goal(
        conn, goal_id=goal_id, new_goal_outcome=new_goal_outcome, new_goal_criterion=new_goal_criterion
    )

    gh_issue_url = _create_github_issue(title, body, parent_issue, labels)

    story_id = "backlog-" + hashlib.md5(f"{signal_hash}{gh_issue_url}".encode()).hexdigest()[:8]
    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title, goal_id) VALUES (?, ?, ?)",
        (story_id, title[:100], resolved_goal_id),
    )
    conn.commit()

    record_proposal(
        conn, signal_hash=signal_hash, title=title, source=source, status="filed",
        gh_issue_url=gh_issue_url or None, story_id=story_id, goal_id=resolved_goal_id,
        goal_match_basis=basis, session_id=session_id,
    )
    return {"status": "filed", "gh_issue_url": gh_issue_url or None, "story_id": story_id}
