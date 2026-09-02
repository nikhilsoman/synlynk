"""GOVERNS Backlog Automation — Auto-associate discovered and planned work,
autonomous PM backlog triaging, and living story formation engine.

See docs/superpowers/specs/2026-08-31-governs-backlog-automation-design.md
and docs/superpowers/plans/2026-09-02-pm-backlog-triaging-and-story-formation.md.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import time
from typing import Optional

DEFAULT_ACTIVE_GOALS = [
    {
        "goal_id": "goal-005ea87d",
        "title": "Ephemeral swarm runners, compute dispatch, model registry",
        "keywords": ["swarm", "cloud", "runner", "fly", "k8s", "kubernetes", "pod", "model", "registry", "complexity", "dispatch", "rates", "entitlement"],
    },
    {
        "goal_id": "goal-adb60ccc",
        "title": "Living charter evolution and capability-gated adaptive routing",
        "keywords": ["charter", "adaptive", "routing", "recalibration", "evolution", "living", "capability", "score", "telemetry"],
    },
    {
        "goal_id": "goal-ef42902a",
        "title": "Inter-agent event relay and messaging bus",
        "keywords": ["relay", "messaging", "event", "sse", "json-rpc", "mailbox", "broadcast", "cross-harness", "inter-agent", "channel"],
    },
    {
        "goal_id": "goal-6733bbf1",
        "title": "state.db is sole mutation point for todo/roadmap",
        "keywords": ["state.db", "backlog", "triage", "todo", "roadmap", "pm", "mutation", "database", "sqlite", "ingest", "promote"],
    },
    {
        "goal_id": "goal-0c4e96ff",
        "title": "Grow readership of book manuscript and blog series",
        "keywords": ["blog", "book", "readership", "marketing", "growth", "media", "social", "analytics", "tweet", "changelog", "diagram", "og_card"],
    },
]


def compute_fingerprint(title: str, source_ref: str = "") -> str:
    """Compute a deterministic SHA-256 fingerprint for a discovered item."""
    normalized_title = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    norm_source = (source_ref or "").strip().lower()
    payload = f"{normalized_title}:{norm_source}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _get_connection(db_conn=None):
    if db_conn is not None:
        if isinstance(db_conn, sqlite3.Connection):
            return db_conn
        if callable(db_conn):
            try:
                return db_conn()
            except TypeError:
                return db_conn
        return db_conn
    from synlynk import _get_db
    return _get_db()


def _query_github_open_issues() -> list[dict]:
    """Query open GitHub issues for deduplication."""
    return fetch_open_github_issues(limit=100)


def fetch_open_github_issues(limit: int = 100) -> list[dict]:
    """Fetch open GitHub issues with metadata for backlog ingestion."""
    try:
        res = subprocess.run(
            [
                "gh", "issue", "list",
                "--state", "open",
                "--limit", str(limit),
                "--json", "number,title,body,labels,author,createdAt,updatedAt,url",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(res.stdout.strip() or "[]")
        issues = []
        for item in data:
            num = item.get("number")
            title = item.get("title", "")
            body = item.get("body", "")
            raw_labels = item.get("labels", [])
            labels = [l.get("name", "") if isinstance(l, dict) else str(l) for l in raw_labels]
            author = item.get("author", {})
            author_str = author.get("login", "") if isinstance(author, dict) else str(author or "")
            url = item.get("url", "")
            fp = compute_fingerprint(title, f"issue-{num}" if num else "")
            issues.append({
                "number": num,
                "title": title,
                "body": body,
                "labels": labels,
                "author": author_str,
                "created_at": item.get("createdAt", ""),
                "updated_at": item.get("updatedAt", ""),
                "url": url,
                "fingerprint": fp,
            })
        return issues
    except Exception:
        return []


def _check_github_duplicate(title: str, gh_issues: Optional[list[dict]] = None) -> Optional[int]:
    """Check if an open GitHub issue with matching normalized title already exists."""
    if not title:
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    issues = gh_issues if gh_issues is not None else _query_github_open_issues()
    for iss in issues:
        iss_title = iss.get("title", "")
        norm_iss = re.sub(r"[^a-z0-9]+", " ", iss_title.lower()).strip()
        if norm_iss == normalized:
            return iss.get("number")
    return None


def is_duplicate_issue(
    issue_dict: dict,
    db_conn=None,
    check_closed_prs: bool = True,
) -> tuple[bool, str]:
    """Check whether a GitHub issue is duplicate against state.db stories, backlog_items, or closed PRs/commits."""
    title = issue_dict.get("title", "").strip()
    if not title:
        return True, "empty_title"

    num = issue_dict.get("number") or issue_dict.get("issue_number")
    fp = issue_dict.get("fingerprint") or compute_fingerprint(title, f"issue-{num}" if num else "")
    norm_title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()

    conn = _get_connection(db_conn)
    if conn is not None:
        try:
            # 1. Check backlog_items
            if num:
                row = conn.execute(
                    "SELECT 1 FROM backlog_items WHERE issue_number = ? LIMIT 1", (int(num),)
                ).fetchone()
                if row:
                    return True, "existing_backlog_issue_number"

            row = conn.execute(
                "SELECT 1 FROM backlog_items WHERE fingerprint = ? LIMIT 1", (fp,)
            ).fetchone()
            if row:
                return True, "existing_backlog_fingerprint"

            b_rows = conn.execute("SELECT title FROM backlog_items WHERE title IS NOT NULL").fetchall()
            for (b_title,) in b_rows:
                if re.sub(r"[^a-z0-9]+", " ", (b_title or "").lower()).strip() == norm_title:
                    return True, "existing_backlog_title"
        except Exception:
            pass

        try:
            # 2. Check stories
            if num:
                row = conn.execute(
                    "SELECT 1 FROM stories WHERE gh_issue = ? OR gh_issue = ? LIMIT 1",
                    (str(num), f"#{num}"),
                ).fetchone()
                if row:
                    return True, "existing_story_gh_issue"

            row = conn.execute(
                "SELECT 1 FROM stories WHERE fingerprint = ? LIMIT 1", (fp,)
            ).fetchone()
            if row:
                return True, "existing_story_fingerprint"

            s_rows = conn.execute("SELECT title FROM stories WHERE title IS NOT NULL").fetchall()
            for (s_title,) in s_rows:
                if re.sub(r"[^a-z0-9]+", " ", (s_title or "").lower()).strip() == norm_title:
                    return True, "existing_story_title"
        except Exception:
            pass

    # 3. Check closed / merged PRs & commits
    if check_closed_prs:
        if num:
            try:
                git_proc = subprocess.run(
                    ["git", "log", "-n", "50", "--grep", f"#{num}", "--oneline"],
                    capture_output=True,
                    text=True,
                )
                if git_proc.returncode == 0 and git_proc.stdout.strip():
                    return True, "resolved_in_git_commit"
            except Exception:
                pass

        try:
            gh_proc = subprocess.run(
                ["gh", "pr", "list", "--state", "merged", "--limit", "50", "--json", "number,title,body"],
                capture_output=True,
                text=True,
            )
            if gh_proc.returncode == 0 and gh_proc.stdout.strip():
                merged_prs = json.loads(gh_proc.stdout.strip())
                for pr in merged_prs:
                    pr_title = pr.get("title", "")
                    pr_body = pr.get("body", "")
                    if num and (f"#{num}" in pr_title or f"#{num}" in pr_body or f"fixes #{num}" in pr_body.lower() or f"resolves #{num}" in pr_body.lower()):
                        return True, "resolved_in_merged_pr"
                    if re.sub(r"[^a-z0-9]+", " ", pr_title.lower()).strip() == norm_title:
                        return True, "matched_merged_pr_title"
        except Exception:
            pass

    return False, ""


def check_duplicate(title: str, fingerprint: str = None, db_conn=None, check_gh: bool = False) -> bool:
    """Check whether a work item with this title or fingerprint already exists in state.db or GitHub."""
    conn = _get_connection(db_conn)
    fp = fingerprint or compute_fingerprint(title)
    if conn is not None:
        try:
            row = conn.execute(
                "SELECT 1 FROM stories WHERE fingerprint = ? LIMIT 1", (fp,)
            ).fetchone()
            if row:
                return True

            normalized_title = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
            rows = conn.execute("SELECT title FROM stories WHERE title IS NOT NULL").fetchall()
            for (existing_title,) in rows:
                if re.sub(r"[^a-z0-9]+", " ", (existing_title or "").lower()).strip() == normalized_title:
                    return True
        except Exception:
            pass

    if check_gh:
        if _check_github_duplicate(title) is not None:
            return True

    return False


def _load_active_goals(db_conn=None, active_goals: Optional[list[dict]] = None) -> list[dict]:
    if active_goals:
        return active_goals
    conn = _get_connection(db_conn)
    goals = []
    if conn is not None:
        try:
            rows = conn.execute("SELECT goal_id, outcome, criterion FROM goals WHERE status = 'active'").fetchall()
            for r in rows:
                goals.append({
                    "goal_id": r[0],
                    "title": r[1] or "",
                    "criterion": r[2] or "",
                    "keywords": re.findall(r"\w+", ((r[1] or "") + " " + (r[2] or "")).lower()),
                })
        except Exception:
            pass
    if not goals:
        return DEFAULT_ACTIVE_GOALS
    return goals


def _classify_role_and_stage(title: str, body: str, labels: list[str]) -> tuple[str, str, int]:
    """Returns (role, governs_stage, complexity_tier)."""
    norm_text = (title + " " + body + " " + " ".join(labels)).lower()

    role = "dev"
    for lbl in labels:
        l = lbl.lower()
        if "role:qa" in l or l == "qa":
            role = "qa"
            break
        elif "role:architect" in l or l == "architect":
            role = "architect"
            break
        elif "role:pm" in l or l == "pm":
            role = "pm"
            break
        elif "role:marketing" in l or l == "marketing":
            role = "marketing"
            break
        elif "role:tpm" in l or l == "tpm":
            role = "tpm"
            break
        elif "role:designer" in l or l == "designer":
            role = "designer"
            break
        elif "role:dev" in l:
            role = "dev"
            break
    else:
        if any(w in norm_text for w in ["test fixture", "reproduction test", "flake", "qa gate", "unit test", "regression test", "audit check", "verify test", "test_"]):
            role = "qa"
        elif any(w in norm_text for w in ["architecture", "spec design", "rfb", "rfc", "protocol design", "data model", "ontological"]):
            role = "architect"
        elif any(w in norm_text for w in ["competitive", "market gap", "pricing", "product strategy", "triage backlog", "pm sweep"]):
            role = "pm"
        elif any(w in norm_text for w in ["blog post", "social draft", "marketing", "growth engine", "og card", "svg diagram"]):
            role = "marketing"
        elif any(w in norm_text for w in ["milestone coordination", "sprint timeline", "tpm sweep"]):
            role = "tpm"
        else:
            role = "dev"

    if role == "architect" or any(w in norm_text for w in ["spec", "design", "brainstorm", "visualize"]):
        stage = "visualize"
    elif role == "marketing" or any(w in norm_text for w in ["blog", "docs", "documentation", "readme", "changelog", "notify"]):
        stage = "notify"
    elif any(w in norm_text for w in ["bug", "defect", "fix", "tech-debt", "patch", "repair", "sustain", "clean up"]):
        stage = "sustain"
    elif any(w in norm_text for w in ["release", "deploy", "packaging", "cut version"]):
        stage = "release"
    elif role == "pm" and any(w in norm_text for w in ["goal", "epic", "vision"]):
        stage = "goal"
    else:
        stage = "open"

    if any(w in norm_text for w in ["typo", "doc", "docs", "readme", "comment", "minor", "small", "quick", "one-line", "spelling", "formatting"]):
        tier = 1
    elif any(w in norm_text for w in ["architecture", "overhaul", "engine", "swarm", "protocol", "distributed", "scheduler", "re-architect", "multi-agent", "subsystem", "cross-cutting"]):
        tier = 3
    else:
        tier = 2

    return role, stage, tier


def _extract_or_generate_acceptance_criteria(title: str, body: str, role: str) -> list[str]:
    """Extract markdown checkboxes/bullets or generate testable criteria."""
    criteria = []
    if body:
        boxes = re.findall(r"^[-*]\s*\[[ xX]\]\s*(.+)$", body, flags=re.MULTILINE)
        if boxes:
            criteria.extend([b.strip() for b in boxes if b.strip()])

        if not criteria:
            crit_match = re.search(r"(?:##|###)?\s*Acceptance Criteria:?\s*\n((?:[-*]\s+.+\n?)+)", body, flags=re.IGNORECASE)
            if crit_match:
                bullets = re.findall(r"^[-*]\s+(.+)$", crit_match.group(1), flags=re.MULTILINE)
                criteria.extend([b.strip() for b in bullets if b.strip()])

    if not criteria:
        criteria = [
            f"Implement requirements and logic for '{title}'.",
            f"Add unit/reproduction tests in tests/ verifying correct behavior under {role} charter.",
            "Pass all existing pytest test suite with zero regressions.",
        ]

    return criteria


def synthesize_story_from_issue(
    issue: dict,
    active_goals: Optional[list[dict]] = None,
    db_conn=None,
) -> dict:
    """Synthesize a structured story from a raw GitHub issue dictionary."""
    title = (issue.get("title") or "").strip()
    body = (issue.get("body") or "").strip()
    raw_labels = issue.get("labels", [])
    labels = [l.get("name", "") if isinstance(l, dict) else str(l) for l in raw_labels]
    num = issue.get("number") or issue.get("issue_number")
    fp = issue.get("fingerprint") or compute_fingerprint(title, f"issue-{num}" if num else "")

    role, governs_stage, tier = _classify_role_and_stage(title, body, labels)
    criteria = _extract_or_generate_acceptance_criteria(title, body, role)

    # Match goal
    goals = _load_active_goals(db_conn=db_conn, active_goals=active_goals)
    tokens = set(re.findall(r"\w+", (title + " " + body + " " + " ".join(labels)).lower()))
    best_goal_id = "goal-6733bbf1"
    best_score = -1

    for g in goals:
        g_id = g.get("goal_id", "")
        g_kws = set(g.get("keywords", []))
        if not g_kws:
            g_kws = set(re.findall(r"\w+", (g.get("title", "") + " " + g.get("criterion", "")).lower()))
        score = len(tokens.intersection(g_kws))
        if score > best_score:
            best_score = score
            best_goal_id = g_id

    priority = 2 if tier == 3 else (3 if tier == 2 else 4)
    for lbl in labels:
        l = lbl.lower()
        if "p0" in l or "critical" in l or "urgent" in l:
            priority = 1
            break
        elif "p1" in l:
            priority = 2
            break
        elif "p2" in l:
            priority = 3
            break

    return {
        "title": title,
        "description": body or title,
        "role": role,
        "stage": governs_stage,
        "governs_stage": governs_stage,
        "complexity_tier": tier,
        "acceptance_criteria": criteria,
        "goal_id": best_goal_id,
        "priority": priority,
        "readiness": "ready",
        "gh_issue": str(num) if num else None,
        "issue_number": num,
        "fingerprint": fp,
        "source_type": "github_issue",
        "source_ref": f"gh:#{num}" if num else "",
    }


def ingest_backlog(
    sync_github: bool = False,
    limit: int = 100,
    db_conn=None,
) -> dict:
    """Ingest open GitHub issues into state.db backlog_items with deduplication."""
    issues = fetch_open_github_issues(limit=limit)
    conn = _get_connection(db_conn)
    ingested = []
    duplicates = 0

    for iss in issues:
        is_dup, reason = is_duplicate_issue(iss, db_conn=conn)
        if is_dup:
            duplicates += 1
            continue

        story_meta = synthesize_story_from_issue(iss, db_conn=conn)
        num = iss.get("number")
        item_id = f"backlog-issue-{num}" if num else f"backlog-{story_meta['fingerprint']}"
        author = iss.get("author", "")
        author_str = author.get("login", "") if isinstance(author, dict) else str(author or "")
        raw_labels = iss.get("labels", [])
        labels = [l.get("name", "") if isinstance(l, dict) else str(l) for l in raw_labels]

        if conn is not None:
            try:
                conn.execute(
                    """INSERT INTO backlog_items (
                        item_id, title, body, issue_number, gh_issue,
                        author, labels, fingerprint, role, stage,
                        governs_stage, complexity_tier, goal_id,
                        acceptance_criteria, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'staged')
                    ON CONFLICT(item_id) DO UPDATE SET
                        title=excluded.title,
                        body=excluded.body,
                        updated_at=CURRENT_TIMESTAMP""",
                    (
                        item_id,
                        story_meta["title"],
                        story_meta["description"],
                        num,
                        str(num) if num else None,
                        author_str,
                        json.dumps(labels),
                        story_meta["fingerprint"],
                        story_meta["role"],
                        story_meta["stage"],
                        story_meta["governs_stage"],
                        story_meta["complexity_tier"],
                        story_meta["goal_id"],
                        json.dumps(story_meta["acceptance_criteria"]),
                    ),
                )
                conn.commit()
                ingested.append({
                    "item_id": item_id,
                    "title": story_meta["title"],
                    "issue_number": num,
                    "role": story_meta["role"],
                    "stage": story_meta["stage"],
                    "complexity_tier": story_meta["complexity_tier"],
                    "goal_id": story_meta["goal_id"],
                    "fingerprint": story_meta["fingerprint"],
                })
            except Exception:
                pass
        else:
            ingested.append({
                "item_id": item_id,
                "title": story_meta["title"],
                "issue_number": num,
                "role": story_meta["role"],
                "stage": story_meta["stage"],
                "complexity_tier": story_meta["complexity_tier"],
                "goal_id": story_meta["goal_id"],
                "fingerprint": story_meta["fingerprint"],
            })

    return {
        "fetched": len(issues),
        "ingested": len(ingested),
        "duplicates": duplicates,
        "items": ingested,
    }


def triage_backlog(
    auto_promote: bool = False,
    db_conn=None,
) -> list[dict]:
    """Triage staged backlog items into structured, classified stories."""
    conn = _get_connection(db_conn)
    if conn is None:
        return []

    try:
        rows = conn.execute(
            """SELECT id, item_id, title, body, issue_number, gh_issue,
                      author, labels, fingerprint, role, stage,
                      governs_stage, complexity_tier, goal_id, acceptance_criteria, status
               FROM backlog_items
               WHERE status IN ('staged', 'discovered')
               ORDER BY id ASC"""
        ).fetchall()
    except Exception:
        return []

    triaged_items = []
    for r in rows:
        row_id, item_id, title, body, num, gh_issue, author, labels_raw, fp, role, stage, g_stage, tier, goal_id, crit_raw, status = r
        try:
            labels = json.loads(labels_raw) if labels_raw else []
        except Exception:
            labels = []

        issue_dict = {
            "number": num,
            "title": title,
            "body": body,
            "labels": labels,
            "author": author,
            "fingerprint": fp,
        }
        synthesized = synthesize_story_from_issue(issue_dict, db_conn=conn)

        try:
            conn.execute(
                """UPDATE backlog_items SET
                    role = ?,
                    stage = ?,
                    governs_stage = ?,
                    complexity_tier = ?,
                    goal_id = ?,
                    acceptance_criteria = ?,
                    status = 'triaged',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (
                    synthesized["role"],
                    synthesized["stage"],
                    synthesized["governs_stage"],
                    synthesized["complexity_tier"],
                    synthesized["goal_id"],
                    json.dumps(synthesized["acceptance_criteria"]),
                    row_id,
                ),
            )
            conn.commit()
            triaged_items.append({
                "id": row_id,
                "item_id": item_id,
                "title": synthesized["title"],
                "issue_number": num,
                "role": synthesized["role"],
                "stage": synthesized["stage"],
                "governs_stage": synthesized["governs_stage"],
                "complexity_tier": synthesized["complexity_tier"],
                "goal_id": synthesized["goal_id"],
                "acceptance_criteria": synthesized["acceptance_criteria"],
                "fingerprint": synthesized["fingerprint"],
                "status": "triaged",
            })
        except Exception:
            pass

    if auto_promote:
        auto_promote_backlog(db_conn=conn)

    return triaged_items


def auto_promote_backlog(
    db_conn=None,
    min_tier: int = 1,
) -> list[dict]:
    """Auto-promote triaged backlog items into state.db stories with readiness='ready'."""
    conn = _get_connection(db_conn)
    if conn is None:
        return []

    try:
        rows = conn.execute(
            """SELECT id, item_id, title, body, issue_number, gh_issue,
                      fingerprint, role, stage, governs_stage, complexity_tier,
                      goal_id, acceptance_criteria, status
               FROM backlog_items
               WHERE status IN ('triaged', 'staged') AND complexity_tier >= ?
               ORDER BY complexity_tier DESC, id ASC""",
            (min_tier,),
        ).fetchall()
    except Exception:
        return []

    promoted_stories = []
    for r in rows:
        row_id, item_id, title, body, num, gh_issue, fp, role, stage, g_stage, tier, goal_id, crit_raw, status = r

        existing = False
        try:
            if fp and conn.execute("SELECT 1 FROM stories WHERE fingerprint = ? LIMIT 1", (fp,)).fetchone():
                existing = True
            elif num and conn.execute("SELECT 1 FROM stories WHERE gh_issue = ? OR gh_issue = ? LIMIT 1", (str(num), f"#{num}")).fetchone():
                existing = True
        except Exception:
            pass

        story_id = f"story-{fp[:8]}" if fp else f"story-{hashlib.md5((title or '').encode()).hexdigest()[:8]}"
        priority = 2 if tier == 3 else (3 if tier == 2 else 4)

        if not existing:
            try:
                conn.execute(
                    """INSERT INTO stories (
                        story_id, title, role, stage, governs_stage, status,
                        priority, readiness, fingerprint, source_type, source_ref,
                        gh_issue, goal_id
                    ) VALUES (?, ?, ?, ?, ?, 'open', ?, 'ready', ?, 'backlog_triage', ?, ?, ?)""",
                    (
                        story_id,
                        title,
                        role or "dev",
                        stage or "open",
                        g_stage or "open",
                        priority,
                        fp,
                        f"gh:#{num}" if num else "",
                        str(num) if num else None,
                        goal_id,
                    ),
                )
                if goal_id:
                    conn.execute(
                        "INSERT OR IGNORE INTO goal_contributions (goal_id, story_id) VALUES (?, ?)",
                        (goal_id, story_id),
                    )
                conn.commit()
            except Exception:
                pass

        try:
            conn.execute(
                "UPDATE backlog_items SET status = 'promoted', story_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (story_id, row_id),
            )
            conn.commit()
        except Exception:
            pass

        promoted_stories.append({
            "story_id": story_id,
            "title": title,
            "role": role or "dev",
            "stage": stage or "open",
            "governs_stage": g_stage or "open",
            "complexity_tier": tier,
            "goal_id": goal_id,
            "gh_issue": num,
            "fingerprint": fp,
        })

    return promoted_stories


def _create_github_issue(
    title: str,
    description: str,
    stage: str = "open",
    role: str = "dev",
    source_type: str = "manual",
    parent_issue: Optional[int] = None,
) -> Optional[int]:
    """Create a GitHub issue with GOVERNS labels and optional parent association."""
    labels = [f"governs:{stage}", f"role:{role}"]
    if source_type in ("doctor", "sentinel"):
        labels.append("tech-debt")

    body = description or title
    if parent_issue:
        body = f"Part of #{parent_issue}.\n\n{body}"

    cmd = [
        "gh", "issue", "create",
        "--title", title,
        "--body", body,
    ]
    for label in labels:
        cmd.extend(["--label", label])

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        out = res.stdout.strip()
        match = re.search(r"/issues/(\d+)", out)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


def stage_discovered_work(
    title: str,
    description: str = "",
    role: str = "dev",
    stage: str = "open",
    source_type: str = "manual",
    source_ref: str = "",
    priority: int = 5,
    db_conn=None,
    sync_gh: bool = False,
    parent_issue: Optional[int] = None,
) -> dict:
    """Stage a newly discovered work item into state.db stories table with deduplication."""
    if not title or not title.strip():
        return {"staged": False, "reason": "empty_title"}

    title = title.strip()
    conn = _get_connection(db_conn)
    fp = compute_fingerprint(title, source_ref)

    if check_duplicate(title, fingerprint=fp, db_conn=conn):
        return {"staged": False, "reason": "duplicate", "fingerprint": fp, "title": title}

    story_seed = f"{title}:{time.time()}"
    story_id = f"story-{hashlib.md5(story_seed.encode()).hexdigest()[:8]}"

    gh_issue_num = None
    if sync_gh:
        gh_issue_num = _create_github_issue(
            title=title,
            description=description,
            stage=stage,
            role=role,
            source_type=source_type,
            parent_issue=parent_issue,
        )

    if conn is not None:
        try:
            conn.execute(
                """INSERT INTO stories (
                    story_id, title, role, stage, governs_stage, status,
                    priority, fingerprint, source_type, source_ref, gh_issue
                ) VALUES (?, ?, ?, ?, ?, 'discovered', ?, ?, ?, ?, ?)""",
                (
                    story_id,
                    title,
                    role,
                    stage,
                    stage,
                    priority,
                    fp,
                    source_type,
                    source_ref,
                    str(gh_issue_num) if gh_issue_num else None,
                ),
            )
            conn.commit()
        except Exception as exc:
            return {"staged": False, "reason": str(exc), "fingerprint": fp}

    return {
        "staged": True,
        "story_id": story_id,
        "fingerprint": fp,
        "title": title,
        "role": role,
        "stage": stage,
        "source_type": source_type,
        "source_ref": source_ref,
        "gh_issue": gh_issue_num,
    }


def list_staged_backlog(
    db_conn=None,
    stage: Optional[str] = None,
    unfiled_only: bool = False,
) -> list[dict]:
    """Retrieve staged and discovered work items from state.db."""
    conn = _get_connection(db_conn)
    if conn is None:
        return []

    query = """
        SELECT story_id, title, role, governs_stage, status, priority,
               fingerprint, source_type, source_ref, gh_issue, created_at
        FROM stories
        WHERE (status = 'discovered' OR status = 'open')
    """
    params = []
    if stage:
        query += " AND governs_stage = ?"
        params.append(stage)
    if unfiled_only:
        query += " AND (gh_issue IS NULL OR gh_issue = '')"

    query += " ORDER BY id DESC"

    try:
        rows = conn.execute(query, tuple(params)).fetchall()
        results = []
        for r in rows:
            results.append({
                "story_id": r[0],
                "title": r[1],
                "role": r[2],
                "stage": r[3] or "open",
                "status": r[4],
                "priority": r[5],
                "fingerprint": r[6],
                "source_type": r[7],
                "source_ref": r[8],
                "gh_issue": r[9],
                "created_at": r[10],
            })
        return results
    except Exception:
        return []


def sync_backlog_to_github(
    db_conn=None,
    dry_run: bool = False,
    parent_issue: Optional[int] = None,
    stage: Optional[str] = None,
) -> list[dict]:
    """Synchronize unfiled staged backlog stories to GitHub issues."""
    conn = _get_connection(db_conn)
    unfiled = list_staged_backlog(db_conn=conn, stage=stage, unfiled_only=True)
    synced = []
    gh_issues_cache = _query_github_open_issues()

    for item in unfiled:
        if dry_run:
            synced.append({**item, "action": "dry_run_sync"})
            continue

        existing_issue_num = _check_github_duplicate(item["title"], gh_issues=gh_issues_cache)
        if existing_issue_num:
            if conn is not None:
                try:
                    conn.execute(
                        "UPDATE stories SET gh_issue = ? WHERE story_id = ?",
                        (str(existing_issue_num), item["story_id"]),
                    )
                    conn.commit()
                except Exception:
                    pass
            synced.append({**item, "gh_issue": existing_issue_num, "action": "linked_existing_issue"})
            continue

        issue_num = _create_github_issue(
            title=item["title"],
            description=f"Auto-created from discovered work ({item.get('source_type', 'manual')}: {item.get('source_ref', '')}).",
            stage=item["stage"],
            role=item["role"],
            source_type=item["source_type"],
            parent_issue=parent_issue,
        )
        if issue_num and conn is not None:
            try:
                conn.execute(
                    "UPDATE stories SET gh_issue = ? WHERE story_id = ?",
                    (str(issue_num), item["story_id"]),
                )
                conn.commit()
                synced.append({**item, "gh_issue": issue_num, "action": "created_issue"})
            except Exception:
                pass
        else:
            synced.append({**item, "action": "sync_failed"})

    return synced
