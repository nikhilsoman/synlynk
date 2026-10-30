"""GitHub-native sync for roadmap/story/decision rows (gh:#2653 design).

Renders already-authoritative state.db rows onto GitHub Milestones/Issues
(Pattern A: core primitives only, no Projects v2 custom fields -- see the
design spec's "Why Pattern A, not Pattern B" section). github_sync_map is
a cache of GitHub-side facts, never a second source of truth.
"""

import hashlib
import json
import os
import re

from synlynk.gh_shim import run_gh


def _content_hash(fields: dict) -> str:
    """Stable hash of the fields that determine a synced item's rendered content."""
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _gh_api_json(args: list, role: str = "pm", **kwargs):
    """Run ``gh api <args>`` and parse JSON stdout. Raises RuntimeError on failure."""
    env = kwargs.pop("env", None)
    env = dict(env) if env is not None else dict(os.environ)
    env["SYNLYNK_GH_ROLE"] = role
    result = run_gh(["api"] + args, capture_output=True, text=True, env=env, **kwargs)
    if result.returncode != 0:
        raise RuntimeError(f"gh api {args} failed: {result.stderr.strip()}")
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)


_STATUS_LABELS = {"deferred": "status:deferred", "superseded": "status:superseded"}
_CLOSED_STATUSES = {"shipped", "superseded"}
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _render_arc_description(conn, arc_id: int) -> str:
    phases = conn.execute(
        "SELECT phase_title, status FROM roadmap_phases "
        "WHERE arc_version = (SELECT version FROM roadmap_arcs WHERE id=?) "
        "ORDER BY id ASC",
        (arc_id,),
    ).fetchall()
    rollup = _cost_rollup_for_arc(conn, arc_id)
    lines = [f"- [{'x' if status == 'done' else ' '}] {title}" for title, status in phases]
    lines.append("")
    lines.append(
        f"**Cost rollup:** ${rollup['actual_usd']:.2f} actual "
        f"across {rollup['entry_count']} entries "
        f"({rollup['unresolved_count']} unattributed)"
    )
    return "\n".join(lines)


def _arc_sync_fields(conn, arc_id: int) -> dict:
    row = conn.execute(
        "SELECT version, title, status, target_date FROM roadmap_arcs WHERE id=?",
        (arc_id,),
    ).fetchone()
    version, title, status, target_date = row
    return {
        "title": version,
        "state": "closed" if status in _CLOSED_STATUSES else "open",
        "due_on": target_date,
        "description": _render_arc_description(conn, arc_id),
    }


def _find_milestone_by_title(
    owner: str, repo: str, title: str, role: str = "pm"
) -> dict | None:
    """Look up an existing GitHub milestone by exact title match, or None."""
    milestones = _gh_api_json(
        [
            f"repos/{owner}/{repo}/milestones",
            "--method",
            "GET",
            "-fstate=all",
            "-fper_page=100",
        ],
        role=role,
    )
    if not milestones:
        return None
    for milestone in milestones:
        if milestone.get("title") == title:
            return milestone
    return None


def sync_arc(conn, arc_id: int, owner: str, repo: str, role: str = "pm") -> None:
    row = conn.execute(
        "SELECT version, status, is_milestone_eligible FROM roadmap_arcs WHERE id=?",
        (arc_id,),
    ).fetchone()
    version, status, eligible = row
    if not eligible:
        return

    fields = _arc_sync_fields(conn, arc_id)
    new_hash = _content_hash(fields)

    mapped = conn.execute(
        "SELECT github_number, content_hash FROM github_sync_map "
        "WHERE entity_type='roadmap_arc' AND entity_id=?",
        (str(arc_id),),
    ).fetchone()

    if mapped and mapped[1] == new_hash:
        return  # nothing changed since last sync

    payload = {
        "title": fields["title"],
        "state": fields["state"],
        "description": fields["description"],
    }
    if fields["due_on"] and _ISO_DATE_RE.match(fields["due_on"]):
        payload["due_on"] = f"{fields['due_on']}T00:00:00Z"

    if mapped:
        github_number = mapped[0]
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/milestones/{github_number}", "--method", "PATCH"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        node_id = result.get("node_id") if result else None
    else:
        existing = _find_milestone_by_title(owner, repo, fields["title"], role=role)
        if existing is not None:
            github_number = existing["number"]
            result = _gh_api_json(
                [
                    f"repos/{owner}/{repo}/milestones/{github_number}",
                    "--method",
                    "PATCH",
                ]
                + [f"-f{k}={v}" for k, v in payload.items()],
                role=role,
            )
            node_id = result.get("node_id") if result else existing.get("node_id")
        else:
            result = _gh_api_json(
                [f"repos/{owner}/{repo}/milestones", "--method", "POST"]
                + [f"-f{k}={v}" for k, v in payload.items()],
                role=role,
            )
            github_number = result["number"]
            node_id = result.get("node_id")

    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number, github_node_id, content_hash, last_synced_at) "
        "VALUES ('roadmap_arc', ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(entity_type, entity_id) DO UPDATE SET "
        "github_number=excluded.github_number, github_node_id=excluded.github_node_id, "
        "content_hash=excluded.content_hash, last_synced_at=excluded.last_synced_at",
        (str(arc_id), github_number, node_id, new_hash),
    )
    conn.commit()

    label = _STATUS_LABELS.get(status)
    if label:
        try:
            _gh_api_json(
                [
                    f"repos/{owner}/{repo}/issues/{github_number}/labels",
                    "--method",
                    "POST",
                    f"-flabels[]={label}",
                ],
                role=role,
            )
        except RuntimeError:
            pass  # Milestones don't support labels directly on all gh versions; best-effort only


def _cost_rollup_for_arc(conn, arc_id: int) -> dict:
    row = conn.execute(
        "SELECT COALESCE(SUM(actual_usd), 0.0), COUNT(*), "
        "SUM(CASE WHEN estimate_basis='epic_unresolved' THEN 1 ELSE 0 END) "
        "FROM cost_entries WHERE epic_id=?",
        (arc_id,),
    ).fetchone()
    return {
        "actual_usd": row[0] or 0.0,
        "entry_count": row[1] or 0,
        "unresolved_count": row[2] or 0,
    }


def _story_sync_fields(conn, story_id: str) -> dict:
    row = conn.execute(
        "SELECT title, status FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    title, status = row
    body = f"{title or story_id}\n\n<!-- synlynk:story_id={story_id} -->"
    short_title = (title or story_id).splitlines()[0].strip()
    if len(short_title) > 120:
        short_title = short_title[:117] + "..."
    return {
        "title": short_title,
        "state": "closed" if status == "done" else "open",
        "body": body,
    }


def sync_story(
    conn,
    story_id: str,
    owner: str,
    repo: str,
    milestone_number: int | None,
    role: str = "pm",
) -> None:
    fields = _story_sync_fields(conn, story_id)
    new_hash = _content_hash(fields)

    mapped = conn.execute(
        "SELECT github_number, content_hash FROM github_sync_map "
        "WHERE entity_type='story' AND entity_id=?",
        (story_id,),
    ).fetchone()
    if mapped and mapped[1] == new_hash:
        return

    payload = {
        "title": fields["title"],
        "state": fields["state"],
        "body": fields["body"],
    }
    if milestone_number is not None:
        payload["milestone"] = milestone_number

    if mapped:
        github_number = mapped[0]
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/issues/{github_number}", "--method", "PATCH"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        node_id = result.get("node_id") if result else None
    else:
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/issues", "--method", "POST"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        github_number = result["number"]
        node_id = result.get("node_id")
        conn.execute(
            "UPDATE stories SET gh_issue=? WHERE story_id=?",
            (str(github_number), story_id),
        )

    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number, github_node_id, content_hash, last_synced_at) "
        "VALUES ('story', ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(entity_type, entity_id) DO UPDATE SET "
        "github_number=excluded.github_number, github_node_id=excluded.github_node_id, "
        "content_hash=excluded.content_hash, last_synced_at=excluded.last_synced_at",
        (story_id, github_number, node_id, new_hash),
    )
    conn.commit()


def _decision_sync_fields(conn, decision_id: str) -> dict:
    row = conn.execute(
        "SELECT topic, status, synthesis, decision_text FROM decisions WHERE decision_id=?",
        (decision_id,),
    ).fetchone()
    topic, status, synthesis, decision_text = row
    body = (
        f"**Synthesis:** {synthesis}\n\n**Decision:** {decision_text}\n\n"
        f"<!-- synlynk:decision_id={decision_id} -->"
    )
    return {
        "title": topic,
        "state": "closed" if status == "decided" else "open",
        "body": body,
    }


def sync_decision(
    conn, decision_id: str, owner: str, repo: str, role: str = "pm"
) -> None:
    fields = _decision_sync_fields(conn, decision_id)
    new_hash = _content_hash(fields)

    mapped = conn.execute(
        "SELECT github_number, content_hash FROM github_sync_map "
        "WHERE entity_type='decision' AND entity_id=?",
        (decision_id,),
    ).fetchone()
    if mapped and mapped[1] == new_hash:
        return

    payload = {
        "title": fields["title"],
        "state": fields["state"],
        "body": fields["body"],
        "labels[]": "decision",
    }

    if mapped:
        github_number = mapped[0]
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/issues/{github_number}", "--method", "PATCH"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        node_id = result.get("node_id") if result else None
    else:
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/issues", "--method", "POST"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        github_number = result["number"]
        node_id = result.get("node_id")

    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number, github_node_id, content_hash, last_synced_at) "
        "VALUES ('decision', ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(entity_type, entity_id) DO UPDATE SET "
        "github_number=excluded.github_number, github_node_id=excluded.github_node_id, "
        "content_hash=excluded.content_hash, last_synced_at=excluded.last_synced_at",
        (decision_id, github_number, node_id, new_hash),
    )
    conn.commit()
