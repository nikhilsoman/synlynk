"""Workspace snapshot for Vizor.

The ecosystem block is the existing ``synlynk status --json`` seam
(``python -m synlynk.cli status --json``). Keep that call; do not add
a second status API."""
import json
import os
import re
import subprocess
import sys
import time
from typing import Optional
from synlynk.observatory import build_job_observatory_snapshot
from synlynk.viz_views import build_workspace_views_snapshot
from synlynk.scan import _query_repo_file_tree
def _pkg():
    """Package namespace tests and the Vizor daemon rebind."""
    import synlynk.viz as viz
    return viz


def load_workspace_sentinel_alerts(sentinel_path: str, *, active_only: bool = False) -> list:
    """Project sentinel.md into the Overview and SSE alert shape.

    The message text is the reproduction record. This function does not write
    the file and does not execute anything inside it.
    """
    from synlynk.sentinel import _iter_sentinel_alerts

    alerts = []
    try:
        parsed = _iter_sentinel_alerts(sentinel_path, active_only=active_only)
    except Exception:
        return []
    for alert in parsed:
        sev = alert.get("original_severity") or alert.get("severity") or "INFO"
        sev_upper = str(sev).strip().upper()
        if sev_upper in ("CRITICAL", "CRIT"):
            severity_out = "CRITICAL"
        elif sev_upper in ("WARNING", "WARN"):
            severity_out = "WARNING"
        else:
            severity_out = "INFO"
        raw_line = alert.get("raw_line") or ""
        alerts.append({
            "ts": alert.get("timestamp") or "",
            "pattern": alert.get("code") or "",
            "severity": severity_out,
            "resolved": "[RESOLVED]" in raw_line or alert.get("code") == "RESOLVED",
            "message": alert.get("message") or "",
            "raw_line": raw_line,
            "occurrences": int(alert.get("occurrences") or 1),
            "first_seen": alert.get("first_seen") or alert.get("timestamp") or "",
            "last_seen": alert.get("last_seen") or alert.get("timestamp") or "",
        })
    return alerts


def load_sentinel_acks(path: str) -> dict:
    """Read the ack sidecar. A missing or corrupt file is an empty ack set.

    Writes land in a later change. This reader must not create the file.
    """
    empty = {"version": 1, "acks": []}
    if not path or not os.path.isfile(path):
        return empty
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        import logging
        logging.getLogger(__name__).info("sentinel acks unreadable: %s", path)
        return {"version": 1, "acks": []}
    if not isinstance(data, dict) or not isinstance(data.get("acks"), list):
        import logging
        logging.getLogger(__name__).info("sentinel acks unreadable: %s", path)
        return {"version": 1, "acks": []}
    result = {"version": 1, "acks": data["acks"]}
    if data.get("slug") is not None:
        result["slug"] = str(data["slug"])
    return result


def save_sentinel_ack(path: str, row: dict, *, slug: str) -> dict:
    """Upsert one ack in a workspace-owned sidecar using atomic replace."""
    data = load_sentinel_acks(path)
    rows = list(data.get("acks") or [])
    kind = str(row.get("kind") or "")

    def _matches(existing: dict) -> bool:
        if str(existing.get("kind") or "") != kind:
            return False
        if kind == "occurrence":
            return list(existing.get("identity") or []) == list(row.get("identity") or [])
        return str(existing.get("code") or "").upper() == str(row.get("code") or "").upper()

    rows = [existing for existing in rows if not _matches(existing)]
    rows.append(dict(row))
    output = {"version": 1, "slug": str(slug), "acks": rows}
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")
    os.replace(temporary, path)
    return output


def raise_sentinel_issue(slug: str, group: dict) -> str:
    """Create one bounded support issue for a sentinel group."""
    code = str(group.get("code") or "UNPARSED").upper()
    count = int(group.get("count") or 1)
    brief = investigate_brief(slug, group)
    raw_lines = [
        str(member.get("raw_line") or "")
        for member in (group.get("members") or [])[:20]
        if member.get("raw_line")
    ]
    body_lines = [
        f"Workspace: {slug}",
        f"Code: {code}",
        f"Severity: {group.get('severity') or 'WARNING'}",
        f"First seen: {group.get('first_seen') or ''}",
        f"Last seen: {group.get('last_seen') or ''}",
        f"Count: {count}",
        "",
        "Sample alerts:",
        *[f"- {line}" for line in raw_lines],
        "",
        "Investigation brief:",
        "```json",
        json.dumps(brief, indent=2),
        "```",
    ]
    env = os.environ.copy()
    env.pop("SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH", None)
    argv = [
        "synlynk", "gh", "--role", "support", "--",
        "issue", "create",
        "--title", f"[support] sentinel: {code} ({count})",
        "--body", "\n".join(body_lines),
    ]
    result = subprocess.run(
        argv, capture_output=True, text=True, check=False, env=env
    )
    if result.returncode != 0:
        raise RuntimeError("gh failed")
    for line in reversed((result.stdout or "").splitlines()):
        candidate = line.strip()
        if candidate.startswith("https://"):
            return candidate
    raise RuntimeError("gh returned no issue URL")


def investigate_brief(slug: str, group: dict) -> dict:
    """Build the bounded, command-free clipboard payload for one group."""
    from synlynk.sentinel import _alert_identity, _extract_sentinel_agent

    code = str(group.get("code") or "UNPARSED").upper()
    members = list(group.get("members") or [])[:20]
    messages = [str(member.get("message") or "") for member in members]
    identities = [list(_alert_identity({
        "severity": member.get("severity"),
        "code": code if code != "UNPARSED" else "",
        "message": member.get("message") or "",
    })) for member in members]
    job_ids = []
    agents = []
    for member in members:
        source = " ".join((
            str(member.get("message") or ""),
            str(member.get("raw_line") or ""),
        ))
        for job_id in re.findall(r"\bjob-[0-9a-f]+\b", source, flags=re.IGNORECASE):
            if job_id not in job_ids and len(job_ids) < 20:
                job_ids.append(job_id)
        agent = _extract_sentinel_agent(str(member.get("raw_line") or ""))
        if agent and agent not in agents and len(agents) < 20:
            agents.append(agent)
    return {
        "slug": str(slug),
        "code": code,
        "severity": str(group.get("severity") or "WARNING").upper(),
        "count": int(group.get("count") or 0),
        "first_seen": str(group.get("first_seen") or ""),
        "last_seen": str(group.get("last_seen") or ""),
        "sample_messages": messages,
        "identities": identities,
        "job_ids": job_ids,
        "agents": agents,
    }


_SEV_RANK = {"CRITICAL": 3, "CRIT": 3, "WARNING": 2, "WARN": 2, "INFO": 1}


def _code_key(alert: dict) -> str:
    code = str(alert.get("pattern") or alert.get("code") or "").strip().upper()
    return code or "UNPARSED"


def _last_seen(alert: dict) -> str:
    return str(alert.get("last_seen") or alert.get("ts") or "")


def group_workspace_sentinel_alerts(alerts, acks=None, *, member_cap: int = 50) -> dict:
    """Split projected alerts into Active groups and Acked groups.

    ``acks`` is the sidecar object ``{"version": 1, "acks": [...]}`` or ``{}``.
    Occurrence / pattern hide rules are applied here so Overview and SSE share one shape.
    """
    from synlynk.sentinel import _alert_identity

    acks = acks or {}
    ack_rows = list(acks.get("acks") or [])
    active_alerts = [a for a in (alerts or []) if not a.get("resolved")]
    buckets = {}
    for alert in active_alerts:
        key = _code_key(alert)
        bucket = buckets.setdefault(key, [])
        bucket.append(alert)

    def _hidden(alert, code):
        identity = list(_alert_identity({
            "severity": alert.get("severity"),
            "code": code if code != "UNPARSED" else "",
            "message": alert.get("message") or "",
        }))
        last = _last_seen(alert)
        for row in ack_rows:
            kind = row.get("kind")
            if kind == "occurrence" and list(row.get("identity") or []) == identity:
                watermark = str(row.get("last_seen_at_ack") or "")
                if not last or last <= watermark:
                    return True
            if kind in ("pattern", "group") and str(row.get("code") or "").upper() == code:
                watermark = str(row.get("last_seen_at_ack") or "")
                if not last or last <= watermark:
                    return True
        return False

    def _pack(code, members, collapsed_default):
        count = sum(int(m.get("occurrences") or 1) for m in members)
        firsts = [m.get("first_seen") or m.get("ts") or "" for m in members]
        lasts = [_last_seen(m) for m in members]
        worst = max(members, key=lambda m: _SEV_RANK.get(str(m.get("severity") or "").upper(), 0))
        shown = members[:member_cap]
        return {
            "code": code,
            "severity": str(worst.get("severity") or "WARNING").upper(),
            "count": count,
            "first_seen": min((x for x in firsts if x), default=""),
            "last_seen": max((x for x in lasts if x), default=""),
            "collapsed": bool(collapsed_default if collapsed_default is not None else count > 3),
            "members": shown,
            "hidden_member_count": max(0, len(members) - len(shown)),
        }

    groups = []
    acked = []
    for code, members in buckets.items():
        visible = [m for m in members if not _hidden(m, code)]
        hidden = [m for m in members if _hidden(m, code)]
        if visible:
            packed = _pack(code, visible, None)
            packed["collapsed"] = packed["count"] > 3
            groups.append(packed)
        if hidden and not visible:
            packed = _pack(code, hidden, True)
            packed["collapsed"] = True
            acked.append(packed)
    groups.sort(key=lambda g: (-_SEV_RANK.get(g["severity"], 0), -g["count"], g["code"]))
    acked.sort(key=lambda g: g["code"])
    return {
        "groups": groups,
        "acked": acked,
        "active_count": sum(g["count"] for g in groups),
        "acked_count": sum(g["count"] for g in acked),
    }


def collect_data(*, db_path: Optional[str] = None) -> dict:
    """Collect workspace-owned goal data from an explicitly scoped ledger.

    Goal reads must not fall back to the process CWD: the Vizor daemon can be
    serving several workspaces while its own CWD is unrelated (and may be
    ``/``).  A missing or unusable path is an empty, safe read.
    """
    if not db_path:
        return {"goals": []}
    try:
        from synlynk import governs_engine

        with _pkg()._open_state_db(db_path=db_path, read_only=True) as conn:
            goals = governs_engine.scoped_goals(conn, status="active")
            product_id = governs_engine.workspace_product_id(conn)
        return {
            "product_id": product_id,
            "goals": [
                {
                    **goal,
                    "id": goal.get("goal_id"),
                }
                for goal in goals
            ]
        }
    except Exception:
        return {"goals": []}

def _load_workspace_repos(config: dict) -> list:
    """Read the multi-repo list from the workspace config, defaulting to the 'default' workspace."""
    ws_name = config.get("workspace_name") or "default"
    ws_config_path = os.path.expanduser(f"~/.synlynk/workspaces/{ws_name}/config.json")
    if not os.path.exists(ws_config_path):
        ws_config_path = os.path.join(".synlynk", "workspaces", ws_name, "config.json")
    try:
        with open(ws_config_path) as f:
            ws_config = json.load(f)
        return ws_config.get("repos", [])
    except Exception:
        return []


def _load_workspace_map() -> dict:
    """Read typed edges between repos from .synlynk/vizor-workspace-map.json."""
    try:
        with open(_pkg().VIZ_WORKSPACE_MAP_PATH) as f:
            data = json.load(f)
        return {"edges": data.get("edges", []), "edge_types": data.get("edge_types", {})}
    except Exception:
        return {"edges": [], "edge_types": {}}


def _repo_github_url(repo_path: str) -> Optional[str]:
    """Derive an https://github.com/<org>/<repo> URL from the repo's origin remote, if any."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        url = result.stdout.strip()
    except Exception:
        return None
    if url.startswith("git@github.com:"):
        slug = url[len("git@github.com:"):]
    elif "github.com/" in url:
        slug = url.split("github.com/", 1)[1]
    else:
        return None
    slug = slug[:-4] if slug.endswith(".git") else slug
    return f"https://github.com/{slug}" if slug else None

def generate_viz_data(db_path: Optional[str] = None) -> dict:
    def _ts() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _workspace_name() -> str:
        try:
            with open(".synlynk/config.json") as f:
                config = json.load(f)
        except Exception:
            config = {}
        return config.get("project_name") or os.path.basename(os.getcwd()) or "workspace"

    def _load_action_history() -> list:
        actions = []
        try:
            with open(".synlynk/events.jsonl") as f:
                for line in f:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict):
                        actions.append(event)
        except (OSError, TypeError):
            pass
        return actions

    def _collect_worktrees() -> dict:
        """Project the worktree audit into the Observatory JSON shape."""
        empty = {
            "items": [],
            "active": 0,
            "safe": 0,
            "needs_review": 0,
            "dirty_orphan": 0,
        }
        try:
            from synlynk.worktree import _collect_verdicts, _get_repo_root

            main_repo_path = _get_repo_root()
            verdicts = _collect_verdicts(main_repo_path, os.getcwd(), gh_available=False)
        except Exception:
            return empty

        items = []
        counts = {key: 0 for key in empty if key != "items"}
        for verdict in verdicts:
            raw_verdict = str(getattr(verdict, "verdict", "") or "")
            reason = str(getattr(verdict, "reason", "") or "")
            if raw_verdict == "safe":
                status = "safe"
            elif raw_verdict == "needs-review":
                status = "needs-review"
            elif any(token in reason.lower() for token in ("dirty", "artifact", "orphan", "missing")):
                status = "dirty-artifact"
            else:
                status = "active"
            counts[{
                "safe": "safe",
                "needs-review": "needs_review",
                "dirty-artifact": "dirty_orphan",
                "active": "active",
            }[status]] += 1
            items.append({
                "path": getattr(verdict, "path", ""),
                "branch": getattr(verdict, "branch", ""),
                "verdict": raw_verdict,
                "status": status,
                "reason": reason,
                "nested_under": getattr(verdict, "nested_under", None),
            })
        return {"items": items, **counts}

    def _base_data() -> dict:
        observatory = build_job_observatory_snapshot()
        observatory["worktrees"] = _collect_worktrees()
        repos = list(workspace_repos)
        for repo in repos:
            repo["active_dream_count"] = active_story_count if len(repos) == 1 else 0
        try:
            views_conn = _pkg()._get_db()
            try:
                file_tree = _query_repo_file_tree(conn=views_conn)
                workspace_views = build_workspace_views_snapshot(views_conn, os.getcwd())
            finally:
                views_conn.close()
        except Exception:
            file_tree = {"name": ".", "dirs": {}, "files": []}
            workspace_views = {
                "product": {"nodes": [], "edges": []},
                "logical": {"nodes": [], "edges": []},
                "infra": {"nodes": [], "edges": []},
            }
        return {
            "workspace": {
                "name": _workspace_name(),
                "updated_at": _ts(),
                "repos": repos,
            },
            "workspace_views": workspace_views,
            "goals": [],
            "spec_verifications": _load_spec_verifications(),
            "dreams": [],
            "costs": {"total_usd": 0.0, "total_usd_estimated": 0.0, "by_agent": {}, "by_stage": {}},
            "agents": {},
            "workspace_agents": _load_workspace_agents(),
            "workspace_map": _load_workspace_map(),
            "file_tree": file_tree,
            "notes": _load_json_optional(_pkg().VIZ_NOTES_PATH, default={}),
            "jobs": observatory.get("jobs", []),
            "actions": _load_action_history(),
            "ecosystem": {},
            "observatory": observatory,
        }

    def _minimal_data() -> dict:
        data = _base_data()
        data["telemetry"] = {"recent": [], "sentinel_alerts": []}
        data["journeys"] = []
        return data

    def _load_json_optional(path: str, default):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return default

    def _load_config() -> dict:
        try:
            with open(".synlynk/config.json") as f:
                return json.load(f)
        except Exception:
            return {}

    def _load_workspace_agents() -> list:
        """Project the durable agent registry into the Vizor data shape."""
        from synlynk import agent_store, charter_schema

        try:
            registry = agent_store.list_agents()
        except Exception:
            return []
        projected = []
        for entry in registry:
            if not isinstance(entry, dict):
                continue
            aliases = entry.get("aliases") or []
            role = next(
                (alias.get("value") for alias in aliases
                 if isinstance(alias, dict) and alias.get("kind") == "role_slug"),
                "",
            )
            if not role:
                continue
            try:
                charter, revision = agent_store.read_charter(entry.get("agent_id", ""))
            except Exception:
                charter, revision = "", 0
            metadata = {}
            body = charter
            if charter.startswith("---\n"):
                _, metadata_text, body = charter.partition("---\n")
                metadata_text, _, body = metadata_text.partition("---\n")
                metadata = charter_schema.parse_frontmatter(metadata_text)
            harnesses = metadata.get("harnesses") or metadata.get("target_harnesses") or []
            if isinstance(harnesses, str):
                harnesses = [item.strip() for item in harnesses.strip("[]").split(",") if item.strip()]
            projected.append({
                "agent_id": entry.get("agent_id", ""),
                "role": role,
                "durability": metadata.get("durability", "dispatch-only"),
                "target_harnesses": list(harnesses) if isinstance(harnesses, list) else [],
                "charter": charter,
                "charter_excerpt": " ".join(body.strip().split())[:220],
                "charter_revision": revision,
                "disabled": bool(entry.get("disabled")),
                "created_at": entry.get("created_at", ""),
            })
        return projected

    def _normalize_stage(name: str) -> str:
        key = (name or "").strip().lower()
        aliases = {
            "dream": "goal",
            "design": "visualize",
            "plan": "open",
            "work": "execute",
            "build": "execute",
            "ship": "release",
            "maintain": "sustain",
            "engage": "execute",
        }
        return aliases.get(key, key)

    _KNOWN_AGENTS = {"claude", "agy", "codex", "grok", "muse"}

    def _looks_like_stage_label(name: str) -> bool:
        # Reject anything that isn't a known agent name — stories.phase is repurposed
        # and often contains stage labels, arc versions, or roadmap cluster names
        return name.lower().strip() not in _KNOWN_AGENTS

    def _empty_agent_bucket() -> dict:
        return {
            "tasks_done": 0,
            "tasks_active": 0,
            "total_usd": 0.0,
            "success_rate": 0.0,
            "alert_count": 0,
        }

    def _read_support_files() -> dict:
        data = _base_data()
        data["telemetry"] = {
            "recent": _load_recent_telemetry(),
            "sentinel_alerts": _load_sentinel_alerts(),
        }
        data["journeys"] = _load_journeys()
        return data

    def _load_recent_telemetry() -> list:
        try:
            with open(".synlynk/telemetry.json") as f:
                rows = json.load(f)
        except Exception:
            return []
        if not isinstance(rows, list):
            return []
        recent = []
        for row in rows[-20:]:
            if not isinstance(row, dict):
                continue
            recent.append({
                "ts": row.get("ts") or row.get("timestamp") or "",
                "agent": row.get("agent") or "",
                "duration_s": float(row.get("duration_s") or 0.0),
                "exit_code": int(row.get("exit_code") or 0),
                "cost_usd": float(row.get("cost_usd") or 0.0),
            })
        return recent

    def _load_sentinel_alerts() -> list:
        return load_workspace_sentinel_alerts(".synlynk/sentinel.md")

    def _load_spec_verifications(limit: int = 20) -> list:
        try:
            rows = _pkg()._get_db().execute(
                "SELECT payload_json FROM events "
                "WHERE event_type='spec_verified' ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        except Exception:
            return []
        verifications = []
        for (payload_json,) in rows:
            try:
                payload = json.loads(payload_json)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                verifications.append(payload)
        return verifications

    def _load_journeys() -> list:
        journeys_dir = os.path.join("docs", "journeys")
        if not os.path.isdir(journeys_dir):
            return []
        journeys = []
        for filename in sorted(os.listdir(journeys_dir)):
            if not filename.endswith(".md"):
                continue
            path = os.path.join(journeys_dir, filename)
            try:
                with open(path) as f:
                    lines = f.read().splitlines()
            except Exception:
                continue
            name = None
            current_step = None
            steps = []
            for line in lines:
                if name is None and line.startswith("# "):
                    name = line[2:].strip()
                    continue
                if line.startswith("## "):
                    if current_step:
                        steps.append(current_step)
                    current_step = {
                        "screen": line[3:].strip(),
                        "route": "",
                        "desc": "",
                        "agent": "",
                        "stage": "",
                    }
                    continue
                if current_step and ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip().lower()
                    value = value.strip()
                    if key in current_step:
                        current_step[key] = value
            if current_step:
                steps.append(current_step)
            if name is not None:
                journeys.append({"id": os.path.splitext(filename)[0], "name": name, "steps": steps})
        return journeys

    def _get_latest_capability_agent(conn, story_id: str) -> str:
        try:
            row = conn.execute(
                "SELECT agent FROM capability_ratings WHERE story_id=? ORDER BY ts DESC, id DESC LIMIT 1",
                (story_id,),
            ).fetchone()
        except Exception:
            return ""
        return row[0] if row and row[0] else ""

    def _story_cost_actual(conn, story_id: str) -> float:
        try:
            rows = conn.execute(
                "SELECT COALESCE(SUM(total_cost_usd), 0) FROM cost_entries WHERE notes LIKE ?",
                (f"%{story_id}%",),
            ).fetchone()
        except Exception:
            return 0.0
        return float(rows[0] or 0.0) if rows else 0.0

    def _dream_cost_breakdown(conn, dream_id: str) -> tuple:
        try:
            rows = conn.execute(
                "SELECT COALESCE(SUM(total_cost_usd), 0), cost_source FROM cost_entries "
                "WHERE notes LIKE ? GROUP BY cost_source",
                (f"%{dream_id}%",),
            ).fetchall()
        except Exception:
            return 0.0, 0.0
        total = 0.0
        prov_estimated = 0.0
        for amount, cost_source in rows:
            amount = float(amount or 0.0)
            total += amount
            if cost_source != "actual":
                prov_estimated += amount
        return total, prov_estimated

    def _story_cost_est(tokens) -> Optional[float]:
        if tokens is None:
            return None
        try:
            return float(tokens) / 1000.0 * 0.003
        except Exception:
            return None

    def _stage_order_key(row) -> int:
        try:
            return int(row[0])
        except Exception:
            return 0

    from synlynk import uxcore

    config = _load_config()
    workspace_repos = [
        {**repo, "github_url": _repo_github_url(repo["path"])}
        for repo in _load_workspace_repos(config)
    ]
    active_story_count = 0

    try:
        conn = (
            _pkg()._open_state_db(db_path=db_path, read_only=True)
            if db_path
            else _pkg()._get_db()
        )
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        db_path = None
        try:
            row = conn.execute("PRAGMA database_list").fetchone()
            db_path = row[2] if row else None
        except Exception:
            pass
    except Exception:
        return _minimal_data()

    if len(workspace_repos) == 1:
        try:
            active_story_count = conn.execute(
                "SELECT COUNT(*) FROM stories WHERE status = 'active'"
            ).fetchone()[0]
        except Exception:
            active_story_count = 0

    required_tables = {"roadmap_arcs", "roadmap_phases", "stories", "cost_entries"}
    if not required_tables.issubset(tables):
        try:
            conn.close()
        except Exception:
            pass
        return _minimal_data()
    data = _read_support_files()

    try:
        conn.close()
    except Exception:
        pass

    original_uxcore_get_db = uxcore._get_db
    if db_path:
        # db_path came from the already-selected connection above. Re-open it
        # through the central resolver in read-only mode so Vizor never
        # discovers or mutates a second ledger.
        uxcore._get_db = lambda: _pkg()._open_state_db(db_path=db_path, read_only=True)
    else:
        uxcore._get_db = _pkg()._get_db
    try:
        costs = uxcore.get_costs()
        dreams_typed = uxcore.get_gantt_data()
        fleet = uxcore.get_fleet_state()
    except uxcore.UxCoreError:
        return _minimal_data()
    finally:
        uxcore._get_db = original_uxcore_get_db

    data["costs"] = {
        "total_usd": costs.total_usd,
        "total_usd_estimated": costs.total_usd_estimated,
        "by_agent": costs.by_agent,
        "by_stage": costs.by_stage,
    }
    data["agents"] = {
        agent: {
            "tasks_done": bucket.tasks_done,
            "tasks_active": bucket.tasks_active,
            "total_usd": bucket.total_usd,
            "success_rate": bucket.success_rate,
            "alert_count": bucket.alert_count,
        }
        for agent, bucket in fleet.items()
    }
    data["releases"] = [
        {
            "id": dream.id,
            "name": dream.name,
            "status": dream.status,
            "cost_total": dream.cost_total,
            "cost_total_estimated": dream.cost_total_estimated,
            "cost_est": dream.cost_est,
            "target_date": getattr(dream, "target_date", None),
            "goal_id": getattr(dream, "goal_id", None),
            "goal_outcome": getattr(dream, "goal_outcome", None),
            "stages": [
                {
                    "key": stage.key,
                    "status": stage.status,
                    "agents": stage.agents,
                    "start_frac": stage.start_frac,
                    "width_frac": stage.width_frac,
                    "cost_actual": stage.cost_actual,
                    "cost_est": stage.cost_est,
                    "tasks": [
                        {
                            "id": task.id,
                            "name": task.name,
                            "agent": task.agent,
                            "status": task.status,
                            "cost_est": task.cost_est,
                            "cost_actual": task.cost_actual,
                            "cost_prov_estimated": task.cost_prov_estimated,
                            "note": data["notes"].get(task.id)
                            if isinstance(data["notes"], dict)
                            else None,
                        }
                        for task in stage.tasks
                    ],
                }
                for stage in dream.stages
            ],
        }
        for dream in dreams_typed
    ]
    data["dreams"] = data["releases"]

    data["goals"] = collect_data(db_path=db_path).get("goals", [])

    ecosystem = {}
    try:
        import subprocess
        import sys

        python_bin = sys.executable or "python3"
        res = subprocess.run(
            [python_bin, "-m", "synlynk.cli", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if res.returncode == 0:
            ecosystem = json.loads(res.stdout)
    except Exception:
        pass
    data["ecosystem"] = ecosystem

    try:
        conn.close()
    except Exception:
        pass
    return data

