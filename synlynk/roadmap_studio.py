"""Vizor Roadmap Studio: ticket-scoped read/write operations over approval_tickets.

Visualizes and drives the existing TPM-sweep release-proposal mechanism
(synlynk/tpm_sweep.py) as a drag/drop board. Four of the six writes here
delegate to shared helpers extracted from tpm_sweep.process_proposal_comments()
so the GitHub-comment path and this Vizor path can't drift apart; reorder and
pin are net-new (no comment-grammar equivalent existed for them).

See docs/superpowers/specs/2026-11-15-roadmap-studio-visual-proposal-ui-design.md.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any, Optional

from synlynk.board import _columns, _open_product_db
from synlynk.maintainer import load_maintainer_proposals
from synlynk.tpm_sweep import _apply_approve, _apply_drop, _apply_hold

logger = logging.getLogger(__name__)

RELEASE_PROPOSAL_ACTION = "release_proposal"


def _conn(conn: Optional[sqlite3.Connection], repo_path: str) -> tuple[sqlite3.Connection, bool]:
    if conn is not None:
        return conn, False
    opened, _slug = _open_product_db(repo_path, migrate=False)
    return opened, True


def _ticket_row(conn: sqlite3.Connection, ticket_id: int) -> dict:
    if not isinstance(ticket_id, int) or isinstance(ticket_id, bool):
        raise ValueError("ticket_id must be an integer")
    row = conn.execute(
        "SELECT id, story_id, status, constituent_story_ids FROM approval_tickets WHERE id=? AND action=?",
        (ticket_id, RELEASE_PROPOSAL_ACTION),
    ).fetchone()
    if row is None:
        raise KeyError(f"release_proposal ticket not found: {ticket_id}")
    return dict(row)


def _constituent_ids(ticket_row: dict) -> list[str]:
    raw = ticket_row.get("constituent_story_ids")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(sid) for sid in parsed] if isinstance(parsed, list) else []


def _version_sort_key(version_str: str) -> tuple:
    cleaned = (version_str or "").lstrip("v")
    parts = []
    for p in cleaned.split("."):
        try:
            parts.append((0, int(p)))
        except ValueError:
            parts.append((1, str(p)))
    return tuple(parts)


def normalize_proposal_for_studio(raw: dict, default_source: str = "tpm") -> dict:
    """Shared card-rendering schema (DECIDE panel defect #4, 2026-11-24;
    validation boundary added per re-review defect #4, same day; fixed
    per re-review round 2 conditions 4-5, same day).

    Maps a TPM story row (from the `stories` table) or a Task 6
    maintainer-proposal dict (from load_maintainer_proposals()) onto one
    consistent shape so synlynk/viz/roadmap_studio.py's cardHtml JS never
    special-cases the source. Every key below is always present with a
    defined default -- never absent, never None where a string/list is
    expected -- so the JS template never reads `undefined`.

    Each field's *raw* shape is checked before any coercion runs (round-2
    condition 4). The earlier version called `list(raw.get("tier_provenance")
    or [])` unconditionally -- if a producer passed a non-empty string
    there, `or []` never triggers (a non-empty string is truthy) and
    `list("abc")` silently becomes `['a', 'b', 'c']`, which then looks
    like a valid list of strings to a check that only runs after the
    coercion. Checking `isinstance(..., list)` first, before touching the
    value, catches that instead of laundering it into a technically-valid
    shape.

    On an invalid field, only *that* field falls back to its default --
    not just `severity` (round-2 condition 5) -- and a warning is logged
    each time, so a malformed producer is visible in logs rather than
    silently degraded.
    """
    from synlynk.proposal_schema import VALID_SEVERITIES

    story_id = raw.get("story_id") or raw.get("proposal_id") or ""
    title = raw.get("title") or raw.get("story_id") or raw.get("proposal_id") or "Untitled"
    source = raw.get("source") or default_source

    severity = raw.get("severity")
    if not isinstance(severity, str) or severity not in VALID_SEVERITIES:
        if severity is not None:
            logger.warning(
                "normalize_proposal_for_studio: invalid severity %r for story_id=%r, falling back to 'normal'",
                severity, story_id,
            )
        severity = "normal"

    github_issue = raw.get("github_issue")
    if github_issue is None:
        github_issue = raw.get("gh_issue")
    if github_issue is not None and not isinstance(github_issue, int):
        logger.warning(
            "normalize_proposal_for_studio: invalid github_issue %r for story_id=%r, falling back to None",
            github_issue, story_id,
        )
        github_issue = None

    tier_provenance = raw.get("tier_provenance")
    if not isinstance(tier_provenance, list) or not all(isinstance(x, str) for x in tier_provenance):
        if tier_provenance is not None:
            logger.warning(
                "normalize_proposal_for_studio: invalid tier_provenance %r for story_id=%r, falling back to []",
                tier_provenance, story_id,
            )
        tier_provenance = []

    return {
        "story_id": str(story_id),
        "title": str(title),
        "source": str(source),
        "severity": severity,
        "github_issue": github_issue,
        "tier_provenance": tier_provenance,
    }


def studio_data(repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None) -> dict:
    """Return open/held release_proposal tickets (with resolved constituent stories), the
    backlog pool, and pending maintainer proposals (DECIDE panel defect #4, 2026-11-24:
    this is the function /api/roadmap_studio actually serves, so normalization and the
    maintainer-proposal merge both happen here, not in the viz/ render-shell module)."""
    active_conn, owns = _conn(conn, repo_path)
    try:
        ticket_rows = active_conn.execute(
            "SELECT id, story_id AS release_version, issue_url, status, constituent_story_ids, theme "
            "FROM approval_tickets WHERE action=? AND status IN ('open','held')",
            (RELEASE_PROPOSAL_ACTION,),
        ).fetchall()

        claimed: set[str] = set()
        tickets = []
        for row in ticket_rows:
            row_dict = dict(row)
            story_ids = _constituent_ids(row_dict)
            claimed.update(story_ids)
            stories = []
            if story_ids:
                placeholders = ",".join("?" for _ in story_ids)
                story_rows = active_conn.execute(
                    f"SELECT story_id, title, role, estimated_tokens, gh_issue, readiness, status, "
                    f"priority, proposal_order FROM stories WHERE story_id IN ({placeholders}) "
                    f"ORDER BY proposal_order ASC NULLS LAST, rowid ASC",
                    story_ids,
                ).fetchall()
                stories = [normalize_proposal_for_studio(dict(r)) for r in story_rows]
            tickets.append(
                {
                    "id": row_dict["id"],
                    "release_version": row_dict["release_version"],
                    "issue_url": row_dict["issue_url"],
                    "status": row_dict["status"],
                    "theme": row_dict.get("theme"),
                    "stories": stories,
                }
            )

        tickets.sort(key=lambda t: _version_sort_key(t.get("release_version") or ""))

        backlog_rows = active_conn.execute(
            "SELECT story_id, title, role, estimated_tokens, gh_issue FROM stories "
            "WHERE (readiness='advisory' OR (readiness IN ('ready','draft') AND status NOT IN ('done','archived')))"
        ).fetchall()
        backlog = [normalize_proposal_for_studio(dict(r)) for r in backlog_rows if r["story_id"] not in claimed]

        maintainer_proposals = [
            normalize_proposal_for_studio(raw, default_source="maintainer")
            for raw in load_maintainer_proposals(repo_root=repo_path)
        ]

        return {"tickets": tickets, "backlog": backlog, "maintainer_proposals": maintainer_proposals}
    finally:
        if owns:
            active_conn.close()



def approve_ticket(ticket_id: int, repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None) -> dict:
    active_conn, owns = _conn(conn, repo_path)
    try:
        ticket_row = _ticket_row(active_conn, ticket_id)
        constituent_story_ids = _constituent_ids(ticket_row)
        promoted = _apply_approve(active_conn, constituent_story_ids, [], ticket_id=ticket_id)
        return {"ok": True, "ticket_id": ticket_id, "promoted_count": promoted}
    finally:
        if owns:
            active_conn.close()


def hold_ticket(ticket_id: int, repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None) -> dict:
    active_conn, owns = _conn(conn, repo_path)
    try:
        _ticket_row(active_conn, ticket_id)
        _apply_hold(active_conn, ticket_id=ticket_id)
        return {"ok": True, "ticket_id": ticket_id}
    finally:
        if owns:
            active_conn.close()


def revise_ticket(
    ticket_id: int, instructions: str, repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None
) -> dict:
    """Mirror process_proposal_comments()'s /revise: return the instruction, persist nothing.

    See the spec's confirmed finding (grep -n revision_instructions synlynk/tpm_sweep.py) that
    today's /revise instruction is never written to any table or column on the comment path either.
    """
    active_conn, owns = _conn(conn, repo_path)
    try:
        _ticket_row(active_conn, ticket_id)
        return {"ok": True, "ticket_id": ticket_id, "instructions": instructions, "persisted": False}
    finally:
        if owns:
            active_conn.close()


def drop_story(story_id: str, repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None) -> dict:
    active_conn, owns = _conn(conn, repo_path)
    try:
        if not story_id or not isinstance(story_id, str):
            raise ValueError("story_id is required")
        if active_conn.execute("SELECT 1 FROM stories WHERE story_id=?", (story_id,)).fetchone() is None:
            raise KeyError(f"story not found: {story_id}")
        _apply_drop(active_conn, story_id)
        return {"ok": True, "story_id": story_id}
    finally:
        if owns:
            active_conn.close()


def reorder_stories(
    ticket_id: int, ordered_story_ids: list[str], repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None
) -> dict:
    """Write sequential proposal_order for ordered_story_ids, scoped to ticket_id's own constituents.

    Rejects (does not silently ignore) any story_id not a member of this ticket's
    constituent_story_ids — the proposal_order scoping invariant from the spec.
    """
    active_conn, owns = _conn(conn, repo_path)
    try:
        ticket_row = _ticket_row(active_conn, ticket_id)
        members = set(_constituent_ids(ticket_row))
        for story_id in ordered_story_ids:
            if story_id not in members:
                raise ValueError(f"story_id {story_id!r} is not a constituent of ticket {ticket_id}")
        for index, story_id in enumerate(ordered_story_ids):
            active_conn.execute("UPDATE stories SET proposal_order=? WHERE story_id=?", (index, story_id))
        active_conn.commit()
        return {"ok": True, "ticket_id": ticket_id, "ordered_story_ids": list(ordered_story_ids)}
    finally:
        if owns:
            active_conn.close()


def pin_story(
    ticket_id: int, story_id: str, repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None
) -> dict:
    """Append story_id into ticket's constituent_story_ids JSON column if not already present.

    Allowed to push the ticket past package_next_release_proposal()'s 5-story cap — this is a
    deliberate manual override, per the spec. Returns over_cap so the UI can show a non-blocking
    warning badge; package_next_release_proposal() itself is untouched.
    """
    active_conn, owns = _conn(conn, repo_path)
    try:
        if not story_id or not isinstance(story_id, str):
            raise ValueError("story_id is required")
        ticket_row = _ticket_row(active_conn, ticket_id)
        if active_conn.execute("SELECT 1 FROM stories WHERE story_id=?", (story_id,)).fetchone() is None:
            raise KeyError(f"story not found: {story_id}")
        members = _constituent_ids(ticket_row)
        if story_id not in members:
            members.append(story_id)
            active_conn.execute(
                "UPDATE approval_tickets SET constituent_story_ids=? WHERE id=?",
                (json.dumps(members), ticket_id),
            )
            active_conn.commit()
        return {"ok": True, "ticket_id": ticket_id, "story_id": story_id, "over_cap": len(members) > 5}
    finally:
        if owns:
            active_conn.close()
