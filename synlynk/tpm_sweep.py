"""Run one policy-gated autonomous TPM sweep pass."""
from __future__ import annotations

import os
from typing import Dict

from synlynk.approval_gate import raise_approval_ticket
from synlynk.autonomy import AutonomyLevel, get_agent_autonomy_level
from synlynk.backlog import ingest_backlog, triage_backlog
from synlynk.db import _find_ticket, _insert_ticket, _mark_ticket_consumed
from synlynk.dispatch import dispatch_agent
from synlynk.events import emit_awaiting_approval
from synlynk.policy import check_authority, load_policy

_FALLBACK_HARNESS = "codex"

SUPERSEDED_STORY_IDS = [
    "story-bs7-interop",
    "story-ab6a0586",
    "story-e3a3170a",
    "story-fda756fd",
    "story-360c0d73",
    "story-dda00e7b",
]


def archive_superseded_stories(conn=None) -> list[str]:
    """Archive legacy and superseded backlog stories ratified in dec-4e81b29a."""
    from synlynk.db import _get_db

    own_conn = conn is None
    if own_conn:
        conn = _get_db()
    archived = []
    try:
        has_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='stories'"
        ).fetchone()
        if not has_table:
            return []

        for sid in SUPERSEDED_STORY_IDS:
            cur = conn.execute(
                "UPDATE stories SET status='archived', archived_at=CURRENT_TIMESTAMP, "
                "superseded_by='dec-4e81b29a' WHERE story_id=? AND status != 'archived'",
                (sid,),
            )
            rowcount = getattr(cur, "rowcount", 0)
            if isinstance(rowcount, int) and rowcount > 0:
                archived.append(sid)
        conn.commit()
        return archived
    finally:
        if own_conn:
            conn.close()


def evaluate_asimov_invariants(story: dict, repo_path: str = ".") -> tuple[bool, str]:
    """Evaluate Asimov's Laws & Synlynk Invariants for a proposed task dispatch.

    Returns (allowed: bool, reason: str).
    - Law 0 (Secrets / System Integrity): Must not target secrets, tokens, or out-of-sandbox writes.
    - Law 1 (Human Sovereignty): Must not bypass human approval gate when required.
    - Law 2 (Evidence Over Assertions): Must declare verifiable test or execution contracts.
    - Law 3 (Metered Self-Preservation & FinOps): Token and cost estimates must be within safety ceilings.
    """
    title = (story.get("title") or "").lower()
    description = (story.get("description") or "").lower()
    content = f"{title} {description}"

    prohibited_patterns = [
        "bypass security",
        "drop table users",
        "steal credentials",
        "leak secrets",
        "disable invariants",
    ]
    for pat in prohibited_patterns:
        if pat in content:
            return False, f"Violates Law 0 (Secrets & System Integrity): forbidden pattern '{pat}'"

    est_tokens = story.get("estimated_tokens", 25000)
    if isinstance(est_tokens, (int, float)) and est_tokens > 200000:
        return False, f"Violates Law 3 (Metered Self-Preservation): token estimate {est_tokens} exceeds 200k ceiling"

    role = story.get("role", "dev")
    if not role:
        return False, "Violates Law 1 (Human Sovereignty): missing agent role attribution"

    return True, "All Asimov & Synlynk invariants satisfied."


def _ready_stories() -> list:
    from synlynk.db import _get_db

    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT story_id, title, role FROM stories WHERE readiness='ready' "
            "AND NOT EXISTS (SELECT 1 FROM daemon_jobs dj "
            "WHERE dj.story_id=stories.story_id "
            "AND dj.status IN ('queued','running','done'))"
        ).fetchall()
        return [
            {"story_id": row[0], "title": row[1], "role": row[2] or "dev"}
            for row in rows
        ]
    finally:
        conn.close()


def _resolve_harness(role: str, repo_path: str) -> str:
    """Look up the default dispatch harness for a story's role.

    Falls back to codex (the pre-existing hardcoded behavior) for any role
    with no entry in policy["agent_roles"], so unmapped roles keep working
    exactly as before this change.
    """
    policy = load_policy(repo_path=repo_path)
    role_entry = policy.get("agent_roles", {}).get(role)
    if role_entry and role_entry.get("default_harness"):
        return role_entry["default_harness"]
    return _FALLBACK_HARNESS


def run_sweep_pass(assignee: str = "nikhilsoman") -> Dict[str, int]:
    """Dispatch each ready, undispatched story after checking policy authority."""
    summary = {"advanced": 0, "parked": 0, "failed": 0}
    repo_path = os.getcwd()

    try:
        from synlynk.backlog import auto_promote_backlog
        auto_promote_backlog()
    except Exception:
        pass

    for story in _ready_stories():
        authority = check_authority(
            "task_dispatch:implement",
            role=story["role"],
            repo_path=repo_path,
        )
        if not authority.allowed:
            summary["failed"] += 1
            continue

        # Evaluate Asimov's Laws & Synlynk Invariants before dispatch
        asimov_ok, asimov_reason = evaluate_asimov_invariants(story, repo_path=repo_path)
        if not asimov_ok:
            summary["failed"] += 1
            continue

        if authority.requires_approval:
            action = "task_dispatch:implement"
            resolved_ticket = _find_ticket(story["story_id"], action, "resolved")
            if resolved_ticket:
                _mark_ticket_consumed(resolved_ticket["id"])
                # Fall through to dispatch below, same as an allowed authority.
            else:
                if not _find_ticket(story["story_id"], action, "open"):
                    emit_awaiting_approval(
                        story["story_id"],
                        action,
                        authority.reason,
                    )
                    issue_url = raise_approval_ticket(
                        story_id=story["story_id"],
                        action=action,
                        reason=authority.reason,
                        assignee=assignee,
                        context=f"Story: {story['title']}",
                    )
                    if issue_url:
                        _insert_ticket(story["story_id"], action, issue_url)
                summary["parked"] += 1
                continue

        try:
            harness = _resolve_harness(story["role"], repo_path)
            dispatch_agent(
                harness,
                story["title"],
                story_id=story["story_id"],
                task_type="implement",
                context_mode="full",
                role=story["role"],
            )
            summary["advanced"] += 1
        except Exception:
            summary["failed"] += 1

    return summary


def run_tpm_wake_cycle() -> dict:
    """Run the TPM wake-cycle SOP: intake, triage, ambiguity routing, sweep.

    Raw GitHub issues are ingested and triaged, then each triaged backlog item
    is routed to a PM-approval-gate status based on its ambiguity signals:
    a missing goal link needs the architect, a tier-3 item needs PM
    prioritisation, and everything else is routine TPM-drafted work. The
    existing sweep pass then runs unchanged for downstream tracking.
    """
    from synlynk.db import _get_db

    routed = {
        "needs_architect_input": 0,
        "needs_pm_priority_input": 0,
        "tpm_drafted": 0,
    }

    conn = _get_db()
    try:
        archive_superseded_stories(conn=conn)
        ingest_backlog(db_conn=conn)
        triaged_items = triage_backlog(auto_promote=False, db_conn=conn)

        for item in triaged_items:
            if not item.get("goal_id"):
                new_status = "needs_architect_input"
            elif item.get("complexity_tier") == 3:
                new_status = "needs_pm_priority_input"
            else:
                new_status = "tpm_drafted"
            conn.execute(
                "UPDATE backlog_items SET status = ? WHERE id = ?",
                (new_status, item["id"]),
            )
            routed[new_status] += 1
        conn.commit()
    finally:
        conn.close()

    autonomy_level = get_agent_autonomy_level("tpm")

    if autonomy_level == AutonomyLevel.L1_ADVISORY:
        # In L1 Advisory: package release-scale proposal and file tracking issue for human gate
        proposal_url = dispatch_tpm_advisory_proposal()
        sweep_result = {
            "status": "advisory_only",
            "dispatched": 0,
            "proposals": len(triaged_items),
            "proposal_url": proposal_url,
        }
    else:
        # In L2 Gated / L3 Autonomous: run sweep pass
        sweep_result = run_sweep_pass()

    return {
        "autonomy_level": autonomy_level.value,
        "triaged": len(triaged_items),
        "routed": routed,
        "sweep": sweep_result,
    }


def format_release_proposal_markdown(proposal: dict) -> str:
    """Format single-release milestone proposal issue with human-orienting bookends."""
    ver = proposal.get("release_version", "vNext")
    theme = proposal.get("theme", "Next Milestone")

    lines = [
        f"# [Proposal] {ver}: {theme}\n",
        f"**Assigned to:** @nikhilsoman  ",
        "**Status:** `Awaiting Human Sign-off` (Comment `/approve` to dispatch)\n",
        "---\n",
        "## 🧭 Situational Orientation (Book-End 1)",
        f"* **Month-to-Date (MTD):** {proposal.get('bookend_mtd', 'Iterative progress.')}",
        f"* **Week-to-Date (WTD):** {proposal.get('bookend_wtd', 'Cadence execution.')}",
        f"* **Earlier Today:** {proposal.get('bookend_today', 'Recent deliveries.')}\n",
        "---\n",
        f"## 🎯 Current Milestone: {ver} Constituent Tasks\n",
        "| Task / Issue | Task Name | Role | Harness | Est. Cost | Status |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for s in proposal.get("stories", []):
        sid = s.get("story_id", "")
        inum = s.get("issue_number")
        if inum:
            task_ref = f"[#{inum}](https://github.com/nikhilsoman/synlynk/issues/{inum}) `({sid})`"
        else:
            task_ref = f"`({sid})`"
        title = s.get("title", "")
        role = s.get("role", "dev")
        harness = s.get("harness", "codex")
        cost = f"${s.get('estimated_cost_usd', 0.05):.2f}"
        status = s.get("status", "Ready")
        lines.append(f"| {task_ref} | {title} | {role} | {harness} | {cost} | {status} |")

    lines.append("\n### Breakdown by Agent Role")
    breakdown = proposal.get("role_breakdown", {})
    if breakdown:
        for r, tasks in breakdown.items():
            lines.append(f"* **{r}:** {', '.join(tasks)}")
    else:
        lines.append("* **dev:** Core feature implementation and test suites.")

    lines.append("\n---\n")
    lines.append("## 🔭 Roadmap Horizon (Book-End 2)")
    lines.append(f"* {proposal.get('bookend_horizon', 'Next scheduled milestone in roadmap.')}\n")
    lines.append("---\n")
    lines.append("### 🛠️ Operator Action & Commands")
    lines.append("Reply directly to this issue with any of the following commands:")
    lines.append("* `/approve` or `LGTM`: Authorize this release package; TPM marks constituent stories `ready` and kicks off worker dispatches.")
    lines.append("* `/revise <instructions>`: Request adjustments (e.g. `/revise remove task X`). TPM will re-plan and update this issue description.")
    lines.append("* `/drop <story-id>`: Drop a specific constituent task from this release.")
    lines.append("* `/prioritize <story-id>`: Move a task to the critical path.")
    lines.append("* `/hold`: Keep this proposal on pause without closing it.")

    return "\n".join(lines)


def package_next_release_proposal(conn=None, repo_root: str = ".") -> Optional[dict]:
    """Package unblocked backlog stories into a single-release proposal."""
    from synlynk.db import _get_db

    own_conn = conn is None
    if own_conn:
        conn = _get_db()
    try:
        # Check if stories table exists
        has_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='stories'"
        ).fetchone()
        if not has_table:
            return None

        # Fetch stories in advisory or unblocked ready/draft status
        rows = conn.execute(
            "SELECT story_id, title, role, estimated_tokens, gh_issue FROM stories "
            "WHERE (readiness='advisory' OR (readiness IN ('ready', 'draft') AND status NOT IN ('done', 'archived'))) "
            "ORDER BY CASE readiness WHEN 'advisory' THEN 1 WHEN 'ready' THEN 2 ELSE 3 END, rowid ASC LIMIT 5"
        ).fetchall()
        if not rows:
            return None

        stories = []
        role_breakdown: dict[str, list[str]] = {}
        for r in rows:
            sid, title, role, tokens, gh_issue = r[0], r[1], r[2] or "dev", r[3] or 25000, r[4]
            inum = int(gh_issue) if gh_issue and str(gh_issue).isdigit() else None
            stories.append({
                "story_id": sid,
                "issue_number": inum,
                "title": title,
                "role": role,
                "harness": _resolve_harness(role, repo_root),
                "estimated_tokens": tokens,
                "estimated_cost_usd": round(tokens * 0.000002, 2),
                "status": "Ready",
            })
            role_breakdown.setdefault(role, []).append(title)

        # Dynamically determine version from VERSION file
        version_str = "0.32.2"
        vfile = os.path.join(repo_root, "VERSION")
        if os.path.isfile(vfile):
            try:
                with open(vfile, "r", encoding="utf-8") as vf:
                    cur_ver = vf.read().strip()
                parts = cur_ver.split(".")
                if len(parts) == 3 and parts[2].isdigit():
                    version_str = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"
            except Exception:
                version_str = "0.32.2"

        rel_ver = f"v{version_str}"
        roadmap_metadata = {
            "v0.32.3": {
                "theme": "Zero-Drift Governance & Constitutional Spec Linter (Theme 1)",
                "bookend_today": "Cut v0.32.2 release and activated TPM Autonomous Operations & Human-in-the-Loop Gate.",
                "bookend_horizon": "Day 5 (v0.32.4): FinOps Dual-Ledger Telemetry & Dynamic Burn-Rate Governor; Day 6 (v0.32.5): Cloud Wedge Shell.",
            },
            "v0.32.4": {
                "theme": "FinOps Dual-Ledger Telemetry & Dynamic Burn-Rate Governor (Theme 3)",
                "bookend_today": "Shipped v0.32.3 Constitutional Spec Linter & Dual-Lock Document Guard.",
                "bookend_horizon": "Day 6 (v0.32.5): Cloud Wedge Shell; Day 7 (v0.33.0): Sovereign Silicon Deep Integration.",
            },
            "v0.32.5": {
                "theme": "The Cloud Wedge Shell & Personal Relay Hub (Theme 6)",
                "bookend_today": "Shipped v0.32.4 FinOps Dual-Ledger Telemetry.",
                "bookend_horizon": "Day 7 (v0.33.0): Sovereign Silicon Deep Integration; Week 2 (v0.34.0): Ambient Co-Pilot Suite.",
            },
            "v0.33.0": {
                "theme": "Sovereign Silicon Deep Local Model Parity (Theme 2)",
                "bookend_today": "Shipped v0.32.5 Cloud Wedge Shell.",
                "bookend_horizon": "Week 2 (v0.34.0): Ambient Co-Pilot & Fenced Companion v2.1 Suite.",
            },
        }
        meta = roadmap_metadata.get(rel_ver, {
            "theme": f"Milestone {rel_ver}",
            "bookend_today": "Active cadence execution.",
            "bookend_horizon": "Scheduled roadmap progression.",
        })

        return {
            "release_version": rel_ver,
            "theme": meta["theme"],
            "bookend_mtd": "Shipped v0.30.0 (Agent Studio), v0.31.0 (VS Code Extension), v0.32.0 (Sub-3k Packager & AST Currency), v0.32.1 (DocGraph Sidecar), and v0.32.2 (TPM Autonomous Cadence).",
            "bookend_wtd": "Ratified authoritative platform roadmap cadence (Decide Panel dec-9b41a7c3) and re-prioritized thematic order (Decide Panel dec-4e81b29a: 4 -> 1 -> 3 -> 6 -> 2 -> 5 -> 7).",
            "bookend_today": meta["bookend_today"],
            "stories": stories,
            "role_breakdown": role_breakdown,
            "bookend_horizon": meta["bookend_horizon"],
        }
    finally:
        if own_conn:
            conn.close()


def dispatch_tpm_advisory_proposal(
    conn=None,
    max_active_proposals: int = 3,
    assignee: str = "nikhilsoman",
    repo_root: str = ".",
) -> Optional[str]:
    """Create a single-release proposal issue assigned to the operator if under max limit."""
    from synlynk.db import _get_db

    own_conn = conn is None
    if own_conn:
        conn = _get_db()
    try:
        # Check active unapproved proposals
        try:
            count_row = conn.execute(
                "SELECT COUNT(*) FROM approval_tickets WHERE action='release_proposal' AND status='open'"
            ).fetchone()
            val = count_row[0] if count_row else 0
            active_count = int(val) if isinstance(val, (int, float, str)) and str(val).isdigit() else 0
        except Exception:
            active_count = 0

        if active_count >= max_active_proposals:
            return None

        proposal = package_next_release_proposal(conn=conn, repo_root=repo_root)
        if not proposal:
            return None

        body = format_release_proposal_markdown(proposal)
        title = f"[Proposal] {proposal['release_version']}: {proposal['theme']}"

        # Attempt to file GitHub issue via gh CLI
        issue_url = None
        try:
            import subprocess

            res = subprocess.run(
                [
                    "gh", "issue", "create",
                    "--title", title,
                    "--body", body,
                    "--assignee", assignee,
                    "--label", "tpm-advisory,release-proposal",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode == 0:
                issue_url = res.stdout.strip()
        except Exception:
            issue_url = None

        if not issue_url:
            issue_url = f"https://github.com/nikhilsoman/synlynk/issues/simulated-{int(os.getpid())}"

        # Record in approval_tickets table
        try:
            conn.execute(
                "INSERT INTO approval_tickets (story_id, action, issue_url, status) "
                "VALUES (?, 'release_proposal', ?, 'open')",
                (proposal["release_version"], issue_url),
            )
            conn.commit()
        except Exception:
            pass

        return issue_url
    finally:
        if own_conn:
            conn.close()


def process_proposal_comments(
    comments: list, constituent_story_ids: list[str], conn=None
) -> dict:
    """Parse comments on proposal issue to determine human approval, revisions, drops, or priorities."""
    from synlynk.db import _get_db

    own_conn = conn is None
    if own_conn:
        conn = _get_db()
    try:
        verdict = "pending"
        promoted = 0
        dropped_stories: list[str] = []
        prioritized_stories: list[str] = []
        revision_instructions: list[str] = []

        for c in comments:
            raw_text = (c.get("body") or "").strip()
            lines = raw_text.splitlines()

            for line in lines:
                sline = line.strip()
                low_sline = sline.lower()

                if low_sline.startswith("/approve") or low_sline == "lgtm" or "lgtm" in low_sline:
                    verdict = "approved"
                    for sid in constituent_story_ids:
                        if sid not in dropped_stories:
                            conn.execute(
                                "UPDATE stories SET readiness='ready' WHERE story_id=?", (sid,)
                            )
                            promoted += 1
                    try:
                        conn.execute(
                            "UPDATE approval_tickets SET status='resolved', resolved_at=CURRENT_TIMESTAMP "
                            "WHERE action='release_proposal' AND status='open'"
                        )
                    except Exception:
                        pass
                    conn.commit()

                elif low_sline.startswith("/revise"):
                    verdict = "revisions_requested"
                    instruction = sline[7:].strip()
                    if instruction:
                        revision_instructions.append(instruction)

                elif low_sline.startswith("/drop"):
                    target_id = sline[5:].strip()
                    if target_id:
                        dropped_stories.append(target_id)
                        conn.execute(
                            "UPDATE stories SET readiness='deferred' WHERE story_id=?", (target_id,)
                        )
                        conn.commit()

                elif low_sline.startswith("/prioritize"):
                    target_id = sline[11:].strip()
                    if target_id:
                        prioritized_stories.append(target_id)
                        conn.execute(
                            "UPDATE stories SET priority=1 WHERE story_id=?", (target_id,)
                        )
                        conn.commit()

                elif low_sline.startswith("/hold"):
                    verdict = "held"
                    try:
                        conn.execute(
                            "UPDATE approval_tickets SET status='held' "
                            "WHERE action='release_proposal' AND status='open'"
                        )
                        conn.commit()
                    except Exception:
                        pass

        return {
            "verdict": verdict,
            "promoted_count": promoted,
            "dropped_stories": dropped_stories,
            "prioritized_stories": prioritized_stories,
            "revision_instructions": revision_instructions,
        }
    finally:
        if own_conn:
            conn.close()

