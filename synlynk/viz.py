"""BS-21 Vizor: local browser dashboard generator and server."""
import html
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from typing import Dict, Optional, Tuple

from synlynk import _get_db, _query_repo_file_tree

_open_state_db = _get_db
from synlynk.observatory import (
    build_job_observatory_snapshot,
    write_observatory_snapshot,
)
from synlynk.viz_views import build_workspace_views_snapshot
from synlynk import vizor_daemon

VIZ_CACHE_DIR = ".synlynk/viz-cache"
VIZ_NOTES_PATH = ".synlynk/viz-notes.json"
VIZ_META_PATH = ".synlynk/viz-meta.json"
VIZ_WORKSPACE_MAP_PATH = ".synlynk/vizor-workspace-map.json"
DEFAULT_PORT = 8721
_KNOWN_AGENTS = {"claude", "agy", "codex", "grok", "muse"}


def _live_js(port: int) -> str:
    from synlynk.local_http_auth import ensure_local_token

    token_js = json.dumps(ensure_local_token())
    return f"""
<script>
(function() {{
  const PORT = {port};
  window.VIZOR_TOKEN = {token_js};
  window.vizorAuthHeaders = function(extra) {{
    const headers = {{'X-Synlynk-Token': window.VIZOR_TOKEN || ''}};
    if (extra) {{
      Object.keys(extra).forEach(function(k) {{ headers[k] = extra[k]; }});
    }}
    return headers;
  }};
  let lastUpdated = null;

  async function checkManifest() {{
    try {{
      const r = await fetch('/manifest.json?_=' + Date.now(), {{ headers: window.vizorAuthHeaders() }});
      if (!r.ok) return;
      const m = await r.json();
      if (lastUpdated === null) {{
        lastUpdated = m.updated_at;
        return;
      }}
      if (m.updated_at !== lastUpdated) {{
        lastUpdated = m.updated_at;
        fireNotification(m.updated_at);
        showReloadBanner(m.updated_at);
      }}
    }} catch (e) {{}}
  }}

  function fireNotification(updatedAt) {{
    if (Notification.permission !== 'granted') return;
    new Notification('synlynk viz updated', {{
      body: `Workspace snapshot refreshed at ${{new Date(updatedAt).toLocaleTimeString()}}`,
      tag: 'vizor-refresh',
    }});
  }}

  function showReloadBanner(updatedAt) {{
    const existing = document.getElementById('vizor-reload-banner');
    if (existing) existing.remove();
    const banner = document.createElement('div');
    banner.id = 'vizor-reload-banner';
    banner.style.cssText = `position:fixed;top:0;left:0;right:0;z-index:9999;background:#0d9e87;color:#fff;font-family:SF Mono,monospace;font-size:12px;padding:8px 16px;display:flex;align-items:center;gap:12px;`;
    banner.innerHTML = `<span>✦ Vizor updated at ${{new Date(updatedAt).toLocaleTimeString()}}</span>
      <button onclick="location.reload()" style="background:rgba(255,255,255,0.2);border:none;color:#fff;padding:3px 10px;border-radius:4px;cursor:pointer">↺ Reload</button>
      <button onclick="this.parentElement.remove()" style="background:none;border:none;color:#fff;cursor:pointer;margin-left:auto;font-size:16px">✕</button>`;
    document.body.prepend(banner);
  }}

  document.addEventListener('click', function requestOnce() {{
    if (Notification.permission === 'default') Notification.requestPermission();
    document.removeEventListener('click', requestOnce);
  }}, {{ once: true }});

  setInterval(checkManifest, 60000);
  checkManifest();
}})();
</script>
""".replace("\n", " ")


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
        with open(VIZ_WORKSPACE_MAP_PATH) as f:
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


def generate_viz_data() -> dict:
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
            views_conn = _get_db()
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
            "notes": _load_json_optional(VIZ_NOTES_PATH, default={}),
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
        sentinel_path = ".synlynk/sentinel.md"
        from synlynk.sentinel import _iter_sentinel_alerts
        alerts = []
        try:
            for alert in _iter_sentinel_alerts(sentinel_path, active_only=False):
                sev = alert.get("original_severity") or alert.get("severity") or "INFO"
                sev_upper = str(sev).strip().upper()
                if sev_upper in ("CRITICAL", "CRIT"):
                    severity_out = "CRITICAL"
                elif sev_upper in ("WARNING", "WARN"):
                    severity_out = "WARNING"
                else:
                    severity_out = "INFO"
                alerts.append({
                    "ts": alert.get("timestamp") or "",
                    "pattern": alert.get("code") or "",
                    "severity": severity_out,
                    "resolved": "[RESOLVED]" in alert.get("raw_line", "") or alert.get("code") == "RESOLVED",
                    "message": alert.get("message") or "",
                })
        except Exception:
            pass
        return alerts

    def _load_spec_verifications(limit: int = 20) -> list:
        try:
            rows = _get_db().execute(
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
        conn = _get_db()
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
        uxcore._get_db = lambda: _open_state_db(db_path=db_path, read_only=True)
    else:
        uxcore._get_db = _get_db
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

    try:
        conn = _get_db()
        goal_rows = conn.execute(
            "SELECT goal_id, outcome, criterion, deadline, status FROM goals WHERE status='active' "
            "ORDER BY created_at DESC"
        ).fetchall()
        goals = [
            {"id": r[0], "outcome": r[1], "criterion": r[2], "deadline": r[3], "status": r[4]}
            for r in goal_rows
        ]
        conn.close()
    except Exception:
        goals = []
    data["goals"] = goals

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


def _compute_underused_feature_banner(data: dict) -> Optional[str]:
    jobs = data.get("jobs", [])
    if not isinstance(jobs, list) or len(jobs) < 10:
        return None

    approve_kill_used = any(
        isinstance(job, dict)
        and str(job.get("status") or "").strip().lower() in {"approved", "killed"}
        for job in jobs
    )
    if not approve_kill_used:
        for action in data.get("actions", []):
            if not isinstance(action, dict):
                continue
            if action.get("action") not in {"approve_pr", "kill_job"}:
                continue
            result = action.get("result")
            if not isinstance(result, dict) or result.get("ok", True):
                approve_kill_used = True
                break
    if approve_kill_used:
        return None
    return f"You've dispatched {len(jobs)} jobs but never used approve/kill -- try it"


def generate_overview_html(data: dict, port: int) -> str:
    """Generate the per-workspace Overview canvas (overview.html)."""
    workspace = data.get("workspace") or {}
    workspace_name = str(workspace.get("name") or "workspace")
    updated_at = str(workspace.get("updated_at") or "")

    # 1. Active sentinel alerts
    sentinel_alerts = [
        a for a in data.get("telemetry", {}).get("sentinel_alerts", [])
        if not a.get("resolved")
    ]
    alerts_html = ""
    if sentinel_alerts:
        alert_rows = []
        for a in sentinel_alerts[:6]:
            sev = str(a.get("severity") or "WARNING").upper()
            sev_class = "sev-crit" if sev in ("CRITICAL", "CRIT") else "sev-warn"
            pattern = a.get("pattern")
            raw_msg = a.get("message") or "Sentinel alert active"
            msg = f"{pattern}: {raw_msg}" if pattern and not raw_msg.startswith(str(pattern)) else raw_msg
            ts = a.get("ts") or ""
            alert_rows.append(
                f'<div class="alert-item {sev_class}">'
                f'<span class="alert-pill">{html.escape(sev)}</span>'
                f'<span class="alert-msg">{html.escape(msg)}</span>'
                f'<span class="alert-ts">{html.escape(ts)}</span>'
                f'</div>'
            )
        alerts_html = f"""
        <div class="alerts-banner">
          <div class="alerts-header">
            <span class="alerts-icon">⚠️</span>
            <span class="alerts-title">Active Sentinel Alerts ({len(sentinel_alerts)})</span>
          </div>
          <div class="alerts-list">
            {"".join(alert_rows)}
          </div>
        </div>
        """

    # 2. Stat Cards Data
    goals = data.get("goals") or []
    active_goals_count = len([g for g in goals if g.get("status") == "active" or not g.get("status")])

    open_stories_count = 0
    total_stories_count = 0
    done_stories_count = 0
    for dream in data.get("dreams") or []:
        for stage in dream.get("stages") or []:
            for task in stage.get("tasks") or []:
                total_stories_count += 1
                st = str(task.get("status") or "").lower()
                if st in ("done", "completed", "resolved", "merged"):
                    done_stories_count += 1
                elif st in ("active", "ready", "open", "in_progress", "todo", "in progress"):
                    open_stories_count += 1
    if open_stories_count == 0 and total_stories_count == 0:
        repos = workspace.get("repos") or []
        if repos and isinstance(repos[0], dict):
            open_stories_count = int(repos[0].get("active_dream_count") or 0)

    jobs = data.get("jobs") or []
    running_jobs_count = len([j for j in jobs if str(j.get("status") or "").lower() in ("running", "active", "dispatched")])

    costs = data.get("costs") or {}
    total_burn = float(costs.get("total_usd") or 0.0)

    # 3. Goal Progress Rollup
    goal_cards = []
    if goals:
        for g in goals[:6]:
            gid = g.get("id") or "goal"
            outcome = g.get("outcome") or g.get("name") or gid
            criterion = g.get("criterion") or ""
            pct = int((done_stories_count / total_stories_count) * 100) if total_stories_count > 0 else 0
            crit_html = f'<div class="goal-criterion">{html.escape(criterion)}</div>' if criterion else ''
            goal_cards.append(f"""
            <div class="goal-item">
              <div class="goal-top">
                <span class="goal-badge">{html.escape(gid)}</span>
                <span class="goal-outcome">{html.escape(outcome)}</span>
                <span class="goal-pct">{pct}%</span>
              </div>
              {crit_html}
              <div class="progress-bar-bg">
                <div class="progress-bar-fill" style="width: {pct}%;"></div>
              </div>
            </div>
            """)
    else:
        goal_cards.append("""
        <div class="empty-hint">
          No active goals in state.db. Run <code>synlynk goal create</code> to define an outcome.
        </div>
        """)
    goals_html = "\n".join(goal_cards)

    # 4. Recent / Active Jobs Feed
    job_rows = []
    if jobs:
        for j in jobs[:6]:
            jid = j.get("job_id") or j.get("id") or "job"
            agent = j.get("agent") or j.get("harness") or "agent"
            task_desc = j.get("task_description") or j.get("task") or j.get("branch") or jid
            st = str(j.get("status") or "completed").lower()
            pr_url = j.get("pr_url") or j.get("pr") or ""

            if st in ("running", "active"):
                st_badge = '<span class="status-chip running">● running</span>'
            elif "pr" in st or pr_url:
                st_badge = '<span class="status-chip pr-open">✓ PR open</span>'
            elif st in ("failed", "error"):
                st_badge = '<span class="status-chip failed">✕ failed</span>'
            else:
                st_badge = '<span class="status-chip done">✓ completed</span>'

            pr_link_html = f'<a href="{html.escape(pr_url)}" target="_blank" class="job-link">PR ↗</a>' if pr_url else ""

            job_rows.append(f"""
            <div class="job-row">
              <span class="job-id">{html.escape(jid)}</span>
              <span class="agent-chip agent-{html.escape(agent.lower())}">{html.escape(agent)}</span>
              <span class="job-desc" title="{html.escape(task_desc)}">{html.escape(task_desc)}</span>
              {st_badge}
              {pr_link_html}
            </div>
            """)
    else:
        job_rows.append("""
        <div class="empty-hint">
          No recent jobs dispatched. Dispatches from <code>synlynk dispatch</code> will appear here.
        </div>
        """)
    jobs_html = "\n".join(job_rows)

    style = """
    :root {
      --bg: #0d0f14; --bg2: #13171f; --bg3: #1a202c;
      --border: #1e2430; --border2: #2d3748;
      --text: #f3f4f6; --text2: #9ca3af; --text3: #6b7280;
      --accent: #0d9e87; --accent-bg: rgba(13,158,135,0.15); --accent-dim: #14b8a6;
      --shadow: 0 4px 16px rgba(0,0,0,0.25);
      --font-mono: 'SF Mono', 'JetBrains Mono', monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    [data-theme="light"] {
      --bg: #f8fafc; --bg2: #ffffff; --bg3: #f1f5f9;
      --border: #e2e8f0; --border2: #cbd5e1;
      --text: #0f172a; --text2: #475569; --text3: #94a3b8;
      --accent: #0d9e87; --accent-bg: #e6f7f4; --accent-dim: #0b7a60;
      --shadow: 0 2px 10px rgba(0,0,0,0.06);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      padding: 24px 32px 48px;
      line-height: 1.5;
      font-size: 13px;
    }
    a { color: inherit; text-decoration: none; }
    .overview-container { max-width: 1200px; margin: 0 auto; }
    .overview-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .overview-title { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
    .overview-sub { font-size: 13px; color: var(--text2); margin-top: 2px; }
    .overview-meta { display: flex; align-items: center; gap: 10px; font-size: 12px; color: var(--text3); }
    .status-pill {
      background: var(--accent-bg);
      color: var(--accent-dim);
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 11px;
    }

    /* Sentinel Banner */
    .alerts-banner {
      background: rgba(245, 158, 11, 0.1);
      border: 1px solid rgba(245, 158, 11, 0.3);
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 24px;
    }
    .alerts-header { display: flex; align-items: center; gap: 8px; font-weight: 600; color: #f59e0b; margin-bottom: 8px; }
    .alerts-list { display: flex; flex-direction: column; gap: 6px; }
    .alert-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      padding: 4px 8px;
      border-radius: 4px;
      background: var(--bg2);
    }
    .alert-item.sev-crit { border-left: 3px solid #ef4444; }
    .alert-item.sev-warn { border-left: 3px solid #f59e0b; }
    .alert-pill { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; background: rgba(0,0,0,0.2); }
    .alert-msg { flex: 1; word-break: break-word; }
    .alert-ts { color: var(--text3); font-size: 11px; font-family: var(--font-mono); }

    /* Stat Cards Row */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .stat-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px 20px;
      transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .stat-card:hover { border-color: var(--accent); transform: translateY(-1px); }
    .stat-label { font-size: 12px; color: var(--text2); font-weight: 500; }
    .stat-value { font-size: 26px; font-weight: 700; margin: 4px 0 2px; color: var(--text); }
    .text-accent { color: var(--accent-dim); }
    .stat-foot { font-size: 11px; color: var(--text3); }

    /* Section Cards */
    .sections-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
      gap: 20px;
      margin-bottom: 24px;
    }
    @media (max-width: 900px) {
      .sections-grid { grid-template-columns: 1fr; }
    }
    .section-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px;
    }
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border);
    }
    .section-title { font-size: 15px; font-weight: 600; }
    .section-link { font-size: 12px; color: var(--accent); font-weight: 500; }
    .section-link:hover { text-decoration: underline; }

    /* Goals Rollup */
    .goals-list { display: flex; flex-direction: column; gap: 12px; }
    .goal-item {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
    }
    .goal-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
    .goal-badge {
      font-size: 11px;
      font-family: var(--font-mono);
      background: var(--bg3);
      color: var(--accent);
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 600;
    }
    .goal-outcome { font-weight: 600; font-size: 13px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .goal-pct { font-size: 12px; font-weight: 700; color: var(--accent-dim); }
    .goal-criterion { font-size: 12px; color: var(--text2); margin-bottom: 8px; line-height: 1.35; }
    .progress-bar-bg { height: 6px; background: var(--bg3); border-radius: 3px; overflow: hidden; }
    .progress-bar-fill { height: 100%; background: var(--accent); border-radius: 3px; transition: width 0.3s ease; }

    /* Jobs Feed */
    .jobs-list { display: flex; flex-direction: column; gap: 8px; }
    .job-row {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 12px;
      padding: 8px 12px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
    }
    .job-id { font-family: var(--font-mono); font-size: 11px; color: var(--text3); }
    .agent-chip {
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;
      background: var(--bg3);
      color: var(--text2);
    }
    .agent-codex { background: rgba(16,163,127,0.15); color: #10a37f; }
    .agent-agy { background: rgba(66,133,244,0.15); color: #4285f4; }
    .agent-claude { background: rgba(13,158,135,0.15); color: #0d9e87; }
    .agent-grok { background: rgba(255,255,255,0.1); color: var(--text); }
    .job-desc { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
    .status-chip { font-size: 11px; font-weight: 600; padding: 2px 6px; border-radius: 4px; }
    .status-chip.running { background: rgba(13,158,135,0.15); color: var(--accent-dim); }
    .status-chip.pr-open { background: rgba(59,130,246,0.15); color: #60a5fa; }
    .status-chip.done { background: rgba(34,197,94,0.15); color: #22c55e; }
    .status-chip.failed { background: rgba(239,68,68,0.15); color: #ef4444; }
    .job-link { font-size: 11px; color: var(--accent); font-weight: 600; }
    .job-link:hover { text-decoration: underline; }

    /* Category Shortcuts Grid */
    .shortcuts-section { margin-top: 12px; }
    .shortcuts-title { font-size: 15px; font-weight: 600; margin-bottom: 14px; }
    .shortcuts-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
    }
    .cat-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      display: flex;
      flex-direction: column;
    }
    .cat-card-header {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--accent);
      margin-bottom: 12px;
    }
    .cat-card-links { display: flex; flex-direction: column; gap: 8px; }
    .cat-link {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 6px;
      background: var(--bg);
      border: 1px solid var(--border);
      font-size: 12px;
      color: var(--text);
      transition: all 0.15s ease;
    }
    .cat-link:hover {
      border-color: var(--accent);
      color: var(--accent);
      transform: translateX(2px);
    }
    .link-icon { font-size: 13px; width: 16px; text-align: center; }

    .empty-hint {
      text-align: center;
      padding: 24px 16px;
      color: var(--text3);
      font-size: 12px;
      background: var(--bg);
      border-radius: 6px;
      border: 1px dashed var(--border);
    }
    """

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="system">
<head>
  <meta charset="utf-8">
  <title>{html.escape(workspace_name)} — Workspace Overview</title>
  <style>{style}</style>
</head>
<body>
  <div class="overview-container">
    <div class="overview-header">
      <div>
        <h1 class="overview-title">{html.escape(workspace_name)}</h1>
        <div class="overview-sub">Workspace Overview & Operational Health</div>
      </div>
      <div class="overview-meta">
        <span class="status-pill">● Active</span>
        <span class="meta-time">Updated {html.escape(updated_at)}</span>
      </div>
    </div>

    {alerts_html}

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Active Goals</div>
        <div class="stat-value">{active_goals_count}</div>
        <div class="stat-foot">Sovereign GOVERNS goals</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Open Stories</div>
        <div class="stat-value">{open_stories_count}</div>
        <div class="stat-foot">Ready & in-flight tasks</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Jobs Running</div>
        <div class="stat-value text-accent">{running_jobs_count}</div>
        <div class="stat-foot">Autonomous dispatches</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Burn (7d)</div>
        <div class="stat-value">${total_burn:.2f}</div>
        <div class="stat-foot">Fleet AI spend</div>
      </div>
    </div>

    <div class="sections-grid">
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">Goal Progress Rollup</div>
          <a href="gantt.html" class="section-link">View in Gantt →</a>
        </div>
        <div class="goals-list">
          {goals_html}
        </div>
      </div>

      <div class="section-card">
        <div class="section-header">
          <div class="section-title">Recent / Active Dispatches</div>
          <a href="observatory.html" class="section-link">Observatory →</a>
        </div>
        <div class="jobs-list">
          {jobs_html}
        </div>
      </div>
    </div>

    <div class="shortcuts-section">
      <div class="shortcuts-title">Jump to a View</div>
      <div class="shortcuts-grid">
        <div class="cat-card">
          <div class="cat-card-header">STATUS</div>
          <div class="cat-card-links">
            <a href="board.html" class="cat-link"><span class="link-icon">▦</span> Board</a>
            <a href="gantt.html" class="cat-link"><span class="link-icon">📅</span> Gantt</a>
          </div>
        </div>
        <div class="cat-card">
          <div class="cat-card-header">TOPOLOGIES</div>
          <div class="cat-card-links">
            <a href="tube.html" class="cat-link"><span class="link-icon">🚇</span> Architect Map</a>
            <a href="infra.html" class="cat-link"><span class="link-icon">⚙️</span> Infra View</a>
          </div>
        </div>
        <div class="cat-card">
          <div class="cat-card-header">PROJECTIONS</div>
          <div class="cat-card-links">
            <a href="product.html" class="cat-link"><span class="link-icon">🗺</span> Product View</a>
            <a href="logical.html" class="cat-link"><span class="link-icon">🧩</span> Logical View</a>
            <a href="world.html" class="cat-link"><span class="link-icon">🌐</span> World View</a>
          </div>
        </div>
        <div class="cat-card">
          <div class="cat-card-header">TELEMETRY</div>
          <div class="cat-card-links">
            <a href="effort.html" class="cat-link"><span class="link-icon">💰</span> Effort & Cost</a>
            <a href="efficiency.html" class="cat-link"><span class="link-icon">📊</span> Efficiency</a>
            <a href="observatory.html" class="cat-link"><span class="link-icon">◉</span> Observatory</a>
            <a href="roles.html" class="cat-link"><span class="link-icon">🤖</span> Agent Roles</a>
          </div>
        </div>
      </div>
    </div>
  </div>
  {_live_js(port)}
</body>
</html>"""


def generate_activity_stream_html(data: dict, port: int) -> str:
    """Generate the cross-workspace Activity Stream canvas (activity.html)."""
    workspace = data.get("workspace") or {}
    workspace_name = str(workspace.get("name") or "workspace")
    updated_at = str(workspace.get("updated_at") or "")

    # Collect and normalize events
    events = []

    # 1. From actions / events.jsonl
    for act in data.get("actions") or []:
        if not isinstance(act, dict):
            continue
        action_name = str(act.get("action") or act.get("event") or "event")
        ts = str(act.get("ts") or act.get("timestamp") or "")
        actor = str(act.get("user") or act.get("actor") or act.get("agent") or "system")
        summary = str(act.get("summary") or act.get("message") or act.get("description") or f"Action {action_name} executed by {actor}")
        ev_type = "story" if "story" in action_name else ("goal" if "goal" in action_name else ("pr" if "pr" in action_name else "job"))
        events.append({
            "workspace": workspace_name,
            "type": ev_type,
            "ts": ts,
            "title": f"Action <b>{action_name}</b> by @{actor}",
            "summary": summary,
            "links": [("Board", "board.html"), ("Gantt", "gantt.html")],
        })

    # 2. From jobs
    for j in data.get("jobs") or []:
        if not isinstance(j, dict):
            continue
        jid = j.get("job_id") or j.get("id") or "job"
        agent = j.get("agent") or j.get("harness") or "agent"
        task_desc = j.get("task_description") or j.get("task") or j.get("branch") or jid
        st = str(j.get("status") or "completed").lower()
        pr_url = j.get("pr_url") or j.get("pr") or ""
        ts = str(j.get("created_at") or j.get("updated_at") or "")
        links = [("Observatory", "observatory.html")]
        if pr_url:
            links.append(("GitHub PR", pr_url))
        events.append({
            "workspace": workspace_name,
            "type": "job",
            "ts": ts,
            "title": f"Dispatch <b>{jid}</b> on agent <b>{agent}</b> ({st})",
            "summary": task_desc,
            "links": links,
        })

    # 3. From goals
    for g in data.get("goals") or []:
        if not isinstance(g, dict):
            continue
        gid = g.get("id") or "goal"
        outcome = g.get("outcome") or g.get("name") or gid
        crit = g.get("criterion") or ""
        events.append({
            "workspace": workspace_name,
            "type": "goal",
            "ts": "",
            "title": f"Goal <b>{gid}</b> updated",
            "summary": f"{outcome} — {crit}" if crit else outcome,
            "links": [("Gantt", "gantt.html")],
        })

    # 4. From dreams / stories
    for dream in data.get("dreams") or []:
        for stage in dream.get("stages") or []:
            for task in stage.get("tasks") or []:
                tid = task.get("id") or "task"
                tname = task.get("name") or tid
                tstatus = task.get("status") or "active"
                agent = task.get("agent") or "agent"
                events.append({
                    "workspace": workspace_name,
                    "type": "story",
                    "ts": "",
                    "title": f"Story <b>{tid}</b> ({tstatus})",
                    "summary": f"{tname} — assigned to {agent}",
                    "links": [("Board", "board.html"), ("Gantt", "gantt.html")],
                })

    # If events is empty, add placeholder
    if not events:
        events.append({
            "workspace": workspace_name,
            "type": "goal",
            "ts": updated_at,
            "title": f"Workspace <b>{workspace_name}</b> initialized",
            "summary": "Vizor multi-workspace monitoring active. Autonomous events will stream here in real time.",
            "links": [("Overview", "overview.html"), ("Board", "board.html")],
        })

    workspaces = sorted(list({e["workspace"] for e in events if e.get("workspace")}))
    event_types = ["goal", "story", "epic", "pr", "job"]

    cards_html = []
    for idx, e in enumerate(events):
        ws = e.get("workspace") or workspace_name
        ev_type = e.get("type") or "story"
        title = e.get("title") or ""
        summary = e.get("summary") or ""
        ts = e.get("ts") or ""
        links = e.get("links") or []
        rendered_links = []
        for label, href in links:
            target_attr = ' target="_blank"' if href.startswith("http") else ""
            rendered_links.append(
                f'<a href="{html.escape(href)}"{target_attr} class="event-link">🔗 {html.escape(label)}</a>'
            )
        links_html = "".join(rendered_links)

        cards_html.append(f"""
        <div class="activity-card" data-workspace="{html.escape(ws)}" data-type="{html.escape(ev_type)}" style="{'display: flex;' if idx < 15 else 'display: none;'}">
          <div class="card-top">
            <div class="card-tags">
              <span class="tag-ws">{html.escape(ws)}</span>
              <span class="tag-type tag-{html.escape(ev_type)}">· {html.escape(ev_type)}</span>
            </div>
            {f'<div class="card-time">{html.escape(ts)}</div>' if ts else ''}
          </div>
          <div class="card-title">{title}</div>
          <div class="card-summary">{html.escape(summary)}</div>
          <div class="card-links">{links_html}</div>
        </div>
        """)

    stream_html = "\n".join(cards_html)

    style = """
    :root {
      --bg: #0d0f14; --bg2: #13171f; --bg3: #1a202c;
      --border: #1e2430; --border2: #2d3748;
      --text: #f3f4f6; --text2: #9ca3af; --text3: #6b7280;
      --accent: #0d9e87; --accent-bg: rgba(13,158,135,0.15); --accent-dim: #14b8a6;
      --font-mono: 'SF Mono', 'JetBrains Mono', monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    [data-theme="light"] {
      --bg: #f8fafc; --bg2: #ffffff; --bg3: #f1f5f9;
      --border: #e2e8f0; --border2: #cbd5e1;
      --text: #0f172a; --text2: #475569; --text3: #94a3b8;
      --accent: #0d9e87; --accent-bg: #e6f7f4; --accent-dim: #0b7a60;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      padding: 24px 32px 48px;
      line-height: 1.5;
      font-size: 13px;
    }
    a { color: inherit; text-decoration: none; }
    .stream-container { max-width: 900px; margin: 0 auto; }
    .stream-header {
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .stream-title { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
    .stream-sub { font-size: 13px; color: var(--text2); margin-top: 2px; }

    /* Filters Bar */
    .filters-bar {
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px 18px;
      margin-bottom: 24px;
    }
    .filter-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .filter-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text3); width: 80px; }
    .filter-chip {
      background: var(--bg);
      border: 1px solid var(--border);
      color: var(--text2);
      font-size: 11px;
      font-weight: 500;
      padding: 4px 10px;
      border-radius: 6px;
      cursor: pointer;
      user-select: none;
      transition: all 0.15s ease;
    }
    .filter-chip:hover { border-color: var(--accent); color: var(--text); }
    .filter-chip.active { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }

    /* Activity Cards */
    .stream-feed { display: flex; flex-direction: column; gap: 12px; }
    .activity-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px 20px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      transition: border-color 0.15s ease;
    }
    .activity-card:hover { border-color: var(--accent); }
    .card-top { display: flex; justify-content: space-between; align-items: center; }
    .card-tags { display: flex; align-items: center; gap: 6px; font-size: 12px; }
    .tag-ws { font-weight: 700; color: var(--accent); }
    .tag-type { color: var(--text3); text-transform: lowercase; }
    .card-time { font-size: 11px; color: var(--text3); font-family: var(--font-mono); }
    .card-title { font-size: 13px; color: var(--text); }
    .card-summary { font-size: 12px; color: var(--text2); line-height: 1.4; }
    .card-links { display: flex; align-items: center; gap: 12px; margin-top: 4px; padding-top: 8px; border-top: 1px solid var(--border); }
    .event-link { font-size: 11px; color: var(--accent); font-weight: 500; }
    .event-link:hover { text-decoration: underline; }

    .load-more-btn {
      width: 100%;
      padding: 12px;
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text2);
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      margin-top: 20px;
      transition: all 0.15s ease;
    }
    .load-more-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--bg3); }
    """

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="system">
<head>
  <meta charset="utf-8">
  <title>synlynk Vizor — Activity Stream</title>
  <style>{style}</style>
</head>
<body>
  <div class="stream-container">
    <div class="stream-header">
      <h1 class="stream-title">Activity Stream</h1>
      <div class="stream-sub">Real-time cross-workspace events, dispatches, and governance updates</div>
    </div>

    <div class="filters-bar">
      <div class="filter-group">
        <span class="filter-label">Workspace:</span>
        <button class="filter-chip active" data-filter-group="ws" data-filter="all" onclick="toggleFilter(this)">All</button>
        {"".join(f'<button class="filter-chip" data-filter-group="ws" data-filter="{html.escape(w)}" onclick="toggleFilter(this)">{html.escape(w)}</button>' for w in workspaces)}
      </div>
      <div class="filter-group">
        <span class="filter-label">Type:</span>
        <button class="filter-chip active" data-filter-group="type" data-filter="all" onclick="toggleFilter(this)">All Types</button>
        {"".join(f'<button class="filter-chip" data-filter-group="type" data-filter="{html.escape(t)}" onclick="toggleFilter(this)">{html.escape(t.capitalize())}</button>' for t in event_types)}
      </div>
    </div>

    <div class="stream-feed" id="stream-feed">
      {stream_html}
    </div>

    <button type="button" class="load-more-btn" id="load-more" onclick="loadMore()">Load More Activity</button>
  </div>

  <script>
    let visibleCount = 15;
    let selectedWs = 'all';
    let selectedType = 'all';

    function toggleFilter(btn) {{
      const group = btn.dataset.filterGroup;
      const val = btn.dataset.filter;
      document.querySelectorAll(`.filter-chip[data-filter-group="${{group}}"]`).forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (group === 'ws') selectedWs = val;
      if (group === 'type') selectedType = val;
      applyFilters();
    }}

    function applyFilters() {{
      const cards = document.querySelectorAll('.activity-card');
      let shown = 0;
      cards.forEach(card => {{
        const cardWs = card.dataset.workspace;
        const cardType = card.dataset.type;
        const wsMatch = selectedWs === 'all' || cardWs === selectedWs;
        const typeMatch = selectedType === 'all' || cardType === selectedType;
        if (wsMatch && typeMatch && shown < visibleCount) {{
          card.style.display = 'flex';
          shown++;
        }} else {{
          card.style.display = 'none';
        }}
      }});
      const loadBtn = document.getElementById('load-more');
      if (loadBtn) {{
        loadBtn.style.display = (shown >= cards.length || shown === 0) ? 'none' : 'block';
      }}
    }}

    function loadMore() {{
      visibleCount += 15;
      applyFilters();
    }}
  </script>
  {_live_js(port)}
</body>
</html>"""


def generate_index_html(data: dict, port: int) -> str:
    """Generate the master Vizor shell with two-tier accordion and location breadcrumbs."""
    workspace = data.get("workspace") or {}
    workspace_name = str(workspace.get("name") or "workspace")
    updated_at = str(workspace.get("updated_at") or "")

    # Calculate open stories count for active workspace
    open_stories = 0
    for dream in data.get("dreams") or []:
        for stage in dream.get("stages") or []:
            for task in stage.get("tasks") or []:
                st = str(task.get("status") or "").lower()
                if st in ("active", "ready", "open", "in_progress", "todo", "in progress"):
                    open_stories += 1
    if open_stories == 0:
        repos = workspace.get("repos") or []
        if repos and isinstance(repos[0], dict):
            open_stories = int(repos[0].get("active_dream_count") or 0)

    # Registered workspaces for accordion
    try:
        from synlynk.state_registry import _read_unlocked, registry_path
        rpath = registry_path()
        reg_products = _read_unlocked(rpath).get("products", {}) if rpath.exists() else {}
        other_slugs = [s for s in sorted(reg_products.keys()) if s != workspace_name]
    except Exception:
        other_slugs = []

    other_ws_html = "".join(f"""
        <details name="workspace" class="ws-accordion">
          <summary class="ws-summary" onclick="window.location.href='/w/{html.escape(s)}/index.html';">
            <span class="ws-chevron">▸</span>
            <span class="ws-name">{html.escape(s)}</span>
          </summary>
        </details>
    """ for s in other_slugs)

    style_content = """
    :root {
      --bg:        #f6f8fa;  --bg2: #ffffff; --bg3: #eaeef2;
      --border:    #d1d5db;  --border2: #e8ebee;
      --text:      #1f2328;  --text2: #57606a; --text3: #8b949e;
      --accent:    #0d9e87;  --accent-bg: #e6f7f4; --accent-dim: #c0ede6;
      --shadow:    0 2px 12px rgba(0,0,0,.10);

      --s-dream-bg:#ede9fe; --s-dream-bd:#c4b5fd; --s-dream-tx:#6d28d9;
      --s-plan-bg: #dbeafe; --s-plan-bd: #93c5fd; --s-plan-tx: #1d4ed8;
      --s-work-bg: #dcfce7; --s-work-bd: #86efac; --s-work-tx: #15803d;
      --s-ship-bg: #ffedd5; --s-ship-bd: #fdba74; --s-ship-tx: #c2410c;
      --s-maint-bg:#e0e7ff; --s-maint-bd:#a5b4fc; --s-maint-tx:#4338ca;
      --s-engage-bg:#fce7f3;--s-engage-bd:#f9a8d4;--s-engage-tx:#be185d;

      --ag-claude-bg:#e6f7f4;--ag-claude-bd:#0d9e87;--ag-claude-tx:#0d9e87;
      --ag-agy-bg:  #e8f0fe;--ag-agy-bd:  #4285f4;--ag-agy-tx:  #1a56c7;
      --ag-codex-bg:#e6f4f0;--ag-codex-bd:#10a37f;--ag-codex-tx:#0b7a60;
      --ag-grok-bg: #f0f0f0;--ag-grok-bd: #666;   --ag-grok-tx: #333;
      --ag-muse-bg: #fdf2f8;--ag-muse-bd: #db2777;--ag-muse-tx: #9d174d;
    }
    [data-theme="dark"] {
      --bg:#0d0f14; --bg2:#0a0c10; --bg3:#13171f;
      --border:#1e2430; --border2:#13171f;
      --text:#c9d1d9; --text2:#8b949e; --text3:#4a5568;
      --accent:#3de0c0; --accent-bg:#0d2137; --accent-dim:#0a3050;
      --shadow: 0 2px 20px rgba(0,0,0,.5);

      --s-dream-bg:#2d1f5e;--s-dream-bd:#4a3f80;--s-dream-tx:#a78bfa;
      --s-plan-bg: #1e3a5a;--s-plan-bd: #3a6090;--s-plan-tx: #60a5fa;
      --s-work-bg: #1a4a2e;--s-work-bd: #2a7040;--s-work-tx: #4ade80;
      --s-ship-bg: #5a3a00;--s-ship-bd: #8a5a00;--s-ship-tx: #fb923c;
      --s-maint-bg:#1e2a4a;--s-maint-bd:#3a4a80;--s-maint-tx:#818cf8;
      --s-engage-bg:#3a1a3a;--s-engage-bd:#6a2a6a;--s-engage-tx:#f472b6;

      --ag-claude-bg:#0d2a2a;--ag-claude-bd:#3de0c0;--ag-claude-tx:#3de0c0;
      --ag-agy-bg:  #0d1a3a;--ag-agy-bd:  #4285f4;--ag-agy-tx:  #4285f4;
      --ag-codex-bg:#0a1f18;--ag-codex-bd:#10a37f;--ag-codex-tx:#10a37f;
      --ag-grok-bg: #1a1a1a;--ag-grok-bd: #e0e0e0;--ag-grok-tx: #e0e0e0;
      --ag-muse-bg: #2e081d;--ag-muse-bd: #f472b6;--ag-muse-tx: #f472b6;
    }

    * { box-sizing:border-box; margin:0; padding:0; }
    html, body { height:100%; }
    body {
      display:flex;
      height:100vh;
      margin:0;
      overflow:hidden;
      font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 'SF Mono', monospace;
      background:var(--bg);
      color:var(--text);
      font-size:13px;
      transition:background .2s,color .2s;
    }
    a { color:inherit; text-decoration:none; }
    button { font:inherit; }

    .shell {
      display:flex;
      height:100vh;
      width:100%;
      overflow:hidden;
    }
    .sidenav {
      width:260px;
      min-width:260px;
      flex-shrink:0;
      background:var(--bg2);
      border-right:1px solid var(--border);
      display:flex;
      flex-direction:column;
      overflow:hidden;
    }
    .nav-header {
      padding:14px 16px;
      border-bottom:1px solid var(--border);
      display:flex;
      align-items:center;
      justify-content:space-between;
    }
    .nav-brand {
      display:flex;
      align-items:center;
      gap:8px;
    }
    .logo-badge {
      background:var(--accent);
      color:#fff;
      font-weight:800;
      font-size:11px;
      padding:3px 6px;
      border-radius:4px;
      letter-spacing:.5px;
    }
    .brand-title {
      font-size:14px;
      font-weight:700;
      color:var(--text);
      letter-spacing:-.3px;
    }
    .nav-section {
      flex:1;
      overflow-y:auto;
      padding:8px 0;
    }

    /* Accordion Styles */
    .tier-accordion {
      margin-bottom:2px;
      border-bottom:1px solid var(--border2);
    }
    .tier-summary {
      display:flex;
      align-items:center;
      gap:8px;
      padding:10px 14px;
      font-weight:700;
      font-size:11px;
      letter-spacing:.8px;
      cursor:pointer;
      user-select:none;
    }
    .tier-summary::-webkit-details-marker { display:none; }
    .tier-personal > .tier-summary {
      background:rgba(13,158,135,0.12);
      color:var(--accent);
    }
    .tier-team > .tier-summary, .tier-enterprise > .tier-summary {
      background:rgba(59,130,246,0.10);
      color:#60a5fa;
    }
    .tier-chevron { font-size:10px; width:12px; }
    .stub-badge {
      margin-left:auto;
      font-size:9px;
      font-weight:500;
      opacity:.75;
      padding:1px 5px;
      border-radius:4px;
      background:rgba(255,255,255,0.08);
    }
    .stub-panel {
      padding:16px 14px;
      background:var(--bg3);
      color:var(--text2);
      text-align:center;
      font-size:11px;
      border-top:1px solid var(--border);
    }
    .stub-icon { font-size:18px; margin-bottom:4px; }
    .stub-sub { font-size:10px; color:var(--text3); margin-top:4px; }

    .tier-content {
      background:var(--bg2);
    }

    /* Workspace Accordion */
    .ws-accordion {
      border-bottom:1px solid var(--border);
    }
    .ws-summary {
      display:flex;
      align-items:center;
      gap:6px;
      padding:8px 14px;
      font-size:12px;
      font-weight:600;
      cursor:pointer;
      background:var(--bg3);
      color:var(--text);
    }
    .ws-summary::-webkit-details-marker { display:none; }
    .ws-chevron { font-size:9px; width:10px; color:var(--text3); }
    .ws-name { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .count-badge {
      font-size:10px;
      font-weight:700;
      background:var(--accent-bg);
      color:var(--accent);
      padding:1px 6px;
      border-radius:8px;
    }
    .ws-content {
      padding:4px 0 8px;
    }

    .nav-category-header {
      font-size:10px;
      font-weight:700;
      text-transform:uppercase;
      letter-spacing:.8px;
      color:var(--text3);
      padding:8px 16px 4px;
    }
    .nav-link {
      padding:6px 12px 6px 20px;
      display:flex;
      align-items:center;
      gap:8px;
      cursor:pointer;
      border-radius:5px;
      margin:1px 8px;
      color:var(--text2);
      font-size:12px;
      line-height:1.2;
      user-select:none;
    }
    .nav-link:hover { background:var(--bg3); color:var(--text); }
    .nav-link.active { background:var(--accent-bg); color:var(--accent); font-weight:600; }
    .nav-icon { width:16px; text-align:center; flex-shrink:0; font-size:12px; }
    .nav-label { white-space:nowrap; }

    .nav-footer {
      border-top:1px solid var(--border);
      padding:10px 14px;
      background:var(--bg2);
    }
    .theme-sw { display:flex; gap:4px; margin-bottom:8px; }
    .theme-btn {
      flex:1;
      padding:4px 0;
      border-radius:5px;
      font-size:10px;
      text-align:center;
      cursor:pointer;
      border:1px solid var(--border);
      color:var(--text3);
      background:transparent;
    }
    .theme-btn:hover { border-color:var(--accent); color:var(--accent); }
    .theme-btn.active { background:var(--accent-bg); border-color:var(--accent); color:var(--accent); font-weight:700; }

    .avatar-row {
      display:flex;
      align-items:center;
      gap:8px;
    }
    .avatar {
      width:22px;
      height:22px;
      border-radius:50%;
      background:linear-gradient(135deg,var(--accent),#0b7a60);
      display:flex;
      align-items:center;
      justify-content:center;
      font-size:10px;
      font-weight:800;
      color:#fff;
      flex-shrink:0;
    }
    .avatar-name {
      font-size:11px;
      color:var(--text2);
      flex:1;
      min-width:0;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap;
    }

    /* Main Area */
    .main {
      flex:1;
      display:flex;
      flex-direction:column;
      overflow:hidden;
      min-width:0;
    }
    .main-topbar {
      background:var(--bg2);
      border-bottom:1px solid var(--border);
      padding:8px 20px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      min-height:42px;
    }
    .breadcrumbs {
      display:flex;
      align-items:center;
      gap:6px;
      font-size:12px;
      color:var(--text2);
    }
    .crumb-link { color:var(--text2); font-weight:500; }
    .crumb-link:hover { color:var(--accent); text-decoration:underline; }
    .crumb-sep { color:var(--text3); font-size:11px; }
    .crumb-cat { color:var(--text3); font-weight:600; text-transform:uppercase; font-size:11px; letter-spacing:.5px; }
    .crumb-current { color:var(--text); font-weight:600; }

    .corner-actions {
      display:flex;
      align-items:center;
      gap:8px;
    }
    .corner-btn {
      background:transparent;
      border:1px solid var(--border);
      border-radius:6px;
      padding:4px 8px;
      cursor:pointer;
      color:var(--text2);
      display:flex;
      align-items:center;
      justify-content:center;
      transition:all 0.15s ease;
    }
    .corner-btn:hover { border-color:var(--accent); color:var(--accent); background:var(--bg3); }
    .corner-link {
      font-size:11px;
      font-weight:600;
      color:var(--accent);
      padding:4px 8px;
      border-radius:6px;
      background:var(--accent-bg);
      border:1px solid var(--accent);
    }
    .corner-link:hover { opacity:0.9; }

    iframe#view-frame {
      flex:1;
      border:none;
      width:100%;
      background:var(--bg);
    }
    .status-bar {
      background:var(--bg2);
      border-top:1px solid var(--border);
      padding:5px 20px;
      display:flex;
      align-items:center;
      gap:10px;
      font-size:11px;
      color:var(--text3);
      flex-shrink:0;
      min-height:28px;
    }
    .status-dot { color:var(--accent); }
    .status-workspace { color:var(--text2); font-weight:600; }
    .status-updated { margin-left:auto; }
    """

    meta_json = json.dumps({"port": port, "updated_at": updated_at})
    avatar_label = (workspace_name[:1] or "S").upper()

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Shell</title>
<script>window.VIZOR_META = {meta_json};</script>
<style>{style_content}</style>
</head>
<body>
<div class="shell">
  <aside class="sidenav">
    <div class="nav-header">
      <div class="nav-brand">
        <span class="logo-badge">VIZOR</span>
        <span class="brand-title">synlynk</span>
      </div>
    </div>
    <div class="nav-section">
      <!-- Tier 1: Personal -->
      <details name="tier1" class="tier-accordion tier-personal" open>
        <summary class="tier-summary">
          <span class="tier-chevron">▾</span>
          <span>PERSONAL</span>
        </summary>
        <div class="tier-content">
          <!-- Active Workspace -->
          <details name="workspace" class="ws-accordion" open>
            <summary class="ws-summary">
              <span class="ws-chevron">▾</span>
              <span class="ws-name">{html.escape(workspace_name)}</span>
              <span class="count-badge">{open_stories}</span>
            </summary>
            <div class="ws-content">
              <a class="nav-link active" href="overview.html" data-view="overview" data-cat="Overview" data-label="Overview">
                <span class="nav-icon">📊</span>
                <span class="nav-label">Overview</span>
              </a>

              <div class="nav-category-header">STATUS</div>
              <a class="nav-link" href="board.html" data-view="board" data-cat="STATUS" data-label="Board">
                <span class="nav-icon">▦</span>
                <span class="nav-label">Board</span>
              </a>
              <a class="nav-link" href="gantt.html" data-view="gantt" data-cat="STATUS" data-label="Gantt">
                <span class="nav-icon">📅</span>
                <span class="nav-label">Gantt</span>
              </a>

              <div class="nav-category-header">TOPOLOGIES</div>
              <a class="nav-link" href="tube.html" data-view="tube" data-cat="TOPOLOGIES" data-label="Architect Map">
                <span class="nav-icon">🚇</span>
                <span class="nav-label">Architect Map</span>
              </a>
              <a class="nav-link" href="infra.html" data-view="infra" data-cat="TOPOLOGIES" data-label="Infra View">
                <span class="nav-icon">⚙️</span>
                <span class="nav-label">Infra View</span>
              </a>

              <div class="nav-category-header">PROJECTIONS</div>
              <a class="nav-link" href="product.html" data-view="product" data-cat="PROJECTIONS" data-label="Product View">
                <span class="nav-icon">🗺</span>
                <span class="nav-label">Product View</span>
              </a>
              <a class="nav-link" href="logical.html" data-view="logical" data-cat="PROJECTIONS" data-label="Logical View">
                <span class="nav-icon">🧩</span>
                <span class="nav-label">Logical View</span>
              </a>
              <a class="nav-link" href="world.html" data-view="world" data-cat="PROJECTIONS" data-label="World View">
                <span class="nav-icon">🌐</span>
                <span class="nav-label">World View</span>
              </a>

              <div class="nav-category-header">TELEMETRY</div>
              <a class="nav-link" href="effort.html" data-view="effort" data-cat="TELEMETRY" data-label="Effort & Cost">
                <span class="nav-icon">💰</span>
                <span class="nav-label">Effort & Cost</span>
              </a>
              <a class="nav-link" href="efficiency.html" data-view="efficiency" data-cat="TELEMETRY" data-label="Efficiency">
                <span class="nav-icon">📊</span>
                <span class="nav-label">Efficiency</span>
              </a>
              <a class="nav-link" href="observatory.html" data-view="observatory" data-cat="TELEMETRY" data-label="Observatory">
                <span class="nav-icon">◉</span>
                <span class="nav-label">Observatory</span>
              </a>
              <a class="nav-link" href="roles.html" data-view="roles" data-cat="TELEMETRY" data-label="Agent Roles">
                <span class="nav-icon">🤖</span>
                <span class="nav-label">Agent Roles</span>
              </a>
            </div>
          </details>
          {other_ws_html}
        </div>
      </details>

      <!-- Tier 1: Team Stub -->
      <details name="tier1" class="tier-accordion tier-team">
        <summary class="tier-summary">
          <span class="tier-chevron">▸</span>
          <span>TEAM</span>
          <span class="stub-badge">Coming soon</span>
        </summary>
        <div class="stub-panel">
          <div class="stub-icon">🚧</div>
          <div>Team workspaces aren't set up yet.</div>
          <div class="stub-sub">Coming soon — invite teammates and share workspace views.</div>
        </div>
      </details>

      <!-- Tier 1: Enterprise Stub -->
      <details name="tier1" class="tier-accordion tier-enterprise">
        <summary class="tier-summary">
          <span class="tier-chevron">▸</span>
          <span>ENTERPRISE</span>
          <span class="stub-badge">Coming soon</span>
        </summary>
        <div class="stub-panel">
          <div class="stub-icon">🏢</div>
          <div>Enterprise workspaces coming soon.</div>
          <div class="stub-sub">Coming soon — SSO, audit logs, and fleet-wide policies.</div>
        </div>
      </details>
    </div>

    <div class="nav-footer">
      <div class="theme-sw">
        <button class="theme-btn" type="button" data-theme-mode="light">☀ Light</button>
        <button class="theme-btn" type="button" data-theme-mode="dark">☾ Dark</button>
        <button class="theme-btn active" type="button" data-theme-mode="system">⊙ System</button>
      </div>
      <div class="avatar-row">
        <div class="avatar">{html.escape(avatar_label)}</div>
        <div class="avatar-name">{html.escape(workspace_name)}</div>
      </div>
    </div>
  </aside>

  <main class="main">
    <header class="main-topbar">
      <nav class="breadcrumbs" id="breadcrumbs">
        <a class="crumb-link" href="activity.html" onclick="return setView('activity', 'activity.html', 'Personal', 'Activity Stream');">Personal</a>
        <span class="crumb-sep" id="crumb-sep-ws">›</span>
        <a class="crumb-link" href="overview.html" id="crumb-ws" onclick="return setView('overview', 'overview.html', '', 'Overview');">{html.escape(workspace_name)}</a>
        <span class="crumb-sep" id="crumb-sep-cat" style="display:none;">›</span>
        <span class="crumb-cat" id="crumb-cat" style="display:none;"></span>
        <span class="crumb-sep" id="crumb-sep-view" style="display:none;">›</span>
        <span class="crumb-current" id="crumb-view" style="display:none;"></span>
      </nav>
      <div class="corner-actions">
        <button class="corner-btn" type="button" title="Settings — GitHub & Harness Connections (Sub-project 2)" onclick="alert('Settings section coming in Sub-project 2 (GitHub OAuth, Provider connections, Backup/Restore)');">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
        </button>
        <button class="corner-btn" type="button" title="Guided Walkthrough (Sub-project 4)" onclick="alert('FTUE Guided Walkthrough coming in Sub-project 4');">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
        </button>
        <a href="/" class="corner-link" title="Workspace Hub">Hub ↗</a>
      </div>
    </header>

    <iframe id="view-frame" src="overview.html" title="Synlynk Vizor view"></iframe>
    <div class="status-bar">
      <span class="status-dot">●</span>
      <span>local</span>
      <span>·</span>
      <span>offline-ready</span>
      <span>·</span>
      <span class="status-workspace">{html.escape(workspace_name)}</span>
      <span>·</span>
      <span class="status-updated">updated {html.escape(updated_at)}</span>
    </div>
  </main>
</div>

<script>
(function() {{
  const themeKey = 'vizor-theme';
  const themeButtons = Array.from(document.querySelectorAll('.theme-btn'));
  const viewFrame = document.getElementById('view-frame');
  const navLinks = Array.from(document.querySelectorAll('.nav-link'));

  function resolveTheme(theme) {{
    if (theme === 'system') {{
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }}
    return theme || 'light';
  }}

  function syncThemeButtons(theme) {{
    themeButtons.forEach((btn) => {{
      btn.classList.toggle('active', btn.dataset.themeMode === theme);
    }});
  }}

  function applyTheme(theme) {{
    const resolved = resolveTheme(theme);
    document.documentElement.setAttribute('data-theme', resolved);
    syncThemeButtons(theme);
  }}

  function setView(viewId, viewSrc, category, label) {{
    if (viewSrc && viewFrame) {{
      viewFrame.src = viewSrc;
    }}
    navLinks.forEach((link) => {{
      link.classList.toggle('active', link.dataset.view === viewId);
    }});

    const sepWs = document.getElementById('crumb-sep-ws');
    const wsEl = document.getElementById('crumb-ws');
    const sepCat = document.getElementById('crumb-sep-cat');
    const catEl = document.getElementById('crumb-cat');
    const sepView = document.getElementById('crumb-sep-view');
    const viewEl = document.getElementById('crumb-view');

    if (viewId === 'activity') {{
      if (sepWs) sepWs.style.display = 'none';
      if (wsEl) wsEl.style.display = 'none';
      if (sepCat) sepCat.style.display = 'inline';
      if (catEl) {{ catEl.style.display = 'inline'; catEl.textContent = 'ACTIVITY STREAM'; }}
      if (sepView) sepView.style.display = 'none';
      if (viewEl) viewEl.style.display = 'none';
    }} else if (viewId === 'overview') {{
      if (sepWs) sepWs.style.display = 'inline';
      if (wsEl) wsEl.style.display = 'inline';
      if (sepCat) sepCat.style.display = 'none';
      if (catEl) catEl.style.display = 'none';
      if (sepView) sepView.style.display = 'none';
      if (viewEl) viewEl.style.display = 'none';
    }} else {{
      if (sepWs) sepWs.style.display = 'inline';
      if (wsEl) wsEl.style.display = 'inline';
      if (sepCat) sepCat.style.display = 'inline';
      if (catEl) {{ catEl.style.display = 'inline'; catEl.textContent = category || ''; }}
      if (sepView) sepView.style.display = 'inline';
      if (viewEl) {{ viewEl.style.display = 'inline'; viewEl.textContent = label || ''; }}
    }}
    return false;
  }}

  window.setView = setView;

  const storedTheme = localStorage.getItem(themeKey) || 'system';
  applyTheme(storedTheme);

  themeButtons.forEach((btn) => {{
    btn.addEventListener('click', () => {{
      const theme = btn.dataset.themeMode || 'system';
      localStorage.setItem(themeKey, theme);
      applyTheme(theme);
    }});
  }});

  window.addEventListener('storage', (e) => {{
    if (e.key === themeKey) {{
      applyTheme(e.newValue || 'system');
    }}
  }});

  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
  if (prefersDark && typeof prefersDark.addEventListener === 'function') {{
    prefersDark.addEventListener('change', () => {{
      if ((localStorage.getItem(themeKey) || 'system') === 'system') {{
        applyTheme('system');
      }}
    }});
  }}

  navLinks.forEach((link) => {{
    link.addEventListener('click', (event) => {{
      event.preventDefault();
      const viewId = link.dataset.view || 'overview';
      const viewSrc = link.getAttribute('href') || 'overview.html';
      const category = link.dataset.cat || '';
      const label = link.dataset.label || '';
      setView(viewId, viewSrc, category, label);
    }});
  }});

  setView('overview', 'overview.html', '', 'Overview');
}})();
</script>
{_live_js(port)}
</body>
</html>"""


_GANTT_STYLE = """
/* ══════════════════════════════════════════════
   THEME TOKENS
══════════════════════════════════════════════ */
:root {
  --bg:        #f6f8fa;  --bg2: #ffffff; --bg3: #eaeef2;
  --border:    #d1d5db;  --border2: #e8ebee;
  --text:      #1f2328;  --text2: #57606a; --text3: #8b949e;
  --accent:    #0d9e87;  --accent-bg: #e6f7f4; --accent-dim: #c0ede6;
  --shadow:    0 2px 12px rgba(0,0,0,.10);

  --s-dream-bg:#ede9fe; --s-dream-bd:#c4b5fd; --s-dream-tx:#6d28d9;
  --s-plan-bg: #dbeafe; --s-plan-bd: #93c5fd; --s-plan-tx: #1d4ed8;
  --s-work-bg: #dcfce7; --s-work-bd: #86efac; --s-work-tx: #15803d;
  --s-ship-bg: #ffedd5; --s-ship-bd: #fdba74; --s-ship-tx: #c2410c;
  --s-maint-bg:#e0e7ff; --s-maint-bd:#a5b4fc; --s-maint-tx:#4338ca;
  --s-engage-bg:#fce7f3;--s-engage-bd:#f9a8d4;--s-engage-tx:#be185d;

  --ag-claude-bg:#e6f7f4;--ag-claude-bd:#0d9e87;--ag-claude-tx:#0d9e87;
  --ag-agy-bg:  #e8f0fe;--ag-agy-bd:  #4285f4;--ag-agy-tx:  #1a56c7;
  --ag-codex-bg:#e6f4f0;--ag-codex-bd:#10a37f;--ag-codex-tx:#0b7a60;
  --ag-grok-bg: #f0f0f0;--ag-grok-bd: #666;   --ag-grok-tx: #333;
}
[data-theme="dark"] {
  --bg:#0d0f14; --bg2:#0a0c10; --bg3:#13171f;
  --border:#1e2430; --border2:#13171f;
  --text:#c9d1d9; --text2:#8b949e; --text3:#4a5568;
  --accent:#3de0c0; --accent-bg:#0d2137; --accent-dim:#0a3050;
  --shadow: 0 2px 20px rgba(0,0,0,.5);

  --s-dream-bg:#2d1f5e;--s-dream-bd:#4a3f80;--s-dream-tx:#a78bfa;
  --s-plan-bg: #1e3a5a;--s-plan-bd: #3a6090;--s-plan-tx: #60a5fa;
  --s-work-bg: #1a4a2e;--s-work-bd: #2a7040;--s-work-tx: #4ade80;
  --s-ship-bg: #5a3a00;--s-ship-bd: #8a5a00;--s-ship-tx: #fb923c;
  --s-maint-bg:#1e2a4a;--s-maint-bd:#3a4a80;--s-maint-tx:#818cf8;
  --s-engage-bg:#3a1a3a;--s-engage-bd:#6a2a6a;--s-engage-tx:#f472b6;

  --ag-claude-bg:#0d2a2a;--ag-claude-bd:#3de0c0;--ag-claude-tx:#3de0c0;
  --ag-agy-bg:  #0d1a3a;--ag-agy-bd:  #4285f4;--ag-agy-tx:  #4285f4;
  --ag-codex-bg:#0a1f18;--ag-codex-bd:#10a37f;--ag-codex-tx:#10a37f;
  --ag-grok-bg: #1a1a1a;--ag-grok-bd: #e0e0e0;--ag-grok-tx: #e0e0e0;
}

* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:'SF Mono','JetBrains Mono',monospace; background:var(--bg); color:var(--text); font-size:13px; transition:background .2s,color .2s; padding:20px 24px 48px; }

.content { width:100%; max-width:100%; }
.ws-header { display:flex;align-items:center;gap:12px;margin-bottom:16px; }
.ws-title { font-size:17px;font-weight:700;color:var(--text); }
.ws-sub { font-size:12px;color:var(--text3);margin-top:2px; }
.ws-chip { background:var(--accent-bg);color:var(--accent);border:1px solid var(--accent-dim);border-radius:12px;font-size:11px;padding:3px 10px; }
.toolbar { display:flex;align-items:center;gap:8px;margin-bottom:12px; }
.lbl { font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.8px; }
.chip { padding:3px 9px;border-radius:10px;font-size:11px;border:1px solid var(--border);color:var(--text2);cursor:pointer;background:transparent;font-family:inherit; }
.chip.on { background:var(--accent-bg);border-color:var(--accent);color:var(--accent); }
.sp { flex:1; }
.zbtn { padding:4px 9px;border-radius:5px;font-size:11px;background:var(--bg3);border:1px solid var(--border);color:var(--text2);cursor:pointer;font-family:inherit; }

/* ══ AGENT AVATARS ══════════════════════════════ */
.aa { width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:9px;font-weight:800;flex-shrink:0;border:1.5px solid;cursor:default;position:relative; }
.aa.sm { width:16px;height:16px;font-size:7px;border-width:1px; }
.aa.lg { width:24px;height:24px;font-size:10px; }
.aa-claude{background:var(--ag-claude-bg);border-color:var(--ag-claude-bd);color:var(--ag-claude-tx);}
.aa-agy   {background:var(--ag-agy-bg);   border-color:var(--ag-agy-bd);   color:var(--ag-agy-tx);   }
.aa-codex {background:var(--ag-codex-bg); border-color:var(--ag-codex-bd); color:var(--ag-codex-tx); font-size:8px;}
.aa-grok  {background:var(--ag-grok-bg);  border-color:var(--ag-grok-bd);  color:var(--ag-grok-tx);  }
.aa-stack { display:flex;align-items:center;gap:3px; }
.aa[title]:hover::after { content:attr(title);position:absolute;bottom:26px;left:50%;transform:translateX(-50%);background:var(--bg3);color:var(--text);padding:3px 7px;border-radius:4px;font-size:10px;white-space:nowrap;border:1px solid var(--border);z-index:200;pointer-events:none; }

/* ══ SVG PENCIL NOTE ICON ═══════════════════════ */
.pencil-wrap {
  opacity:0; position:absolute; top:5px; right:6px;
  cursor:pointer; z-index:20; transition:opacity .15s;
  width:18px; height:18px; display:flex; align-items:center; justify-content:center;
}
.editable:hover .pencil-wrap { opacity:1; }
.pencil-wrap.note-info   { opacity:1; }
.pencil-wrap.note-action { opacity:1; }
.pencil-wrap.note-urgent { opacity:1; }
.pencil-wrap.note-done   { opacity:1; }
.pencil-wrap svg { width:16px;height:16px;transition:transform .15s; }
.pencil-wrap:hover svg { transform:scale(1.15); }
.pencil-wrap.note-none   svg { color:#9ca3af; }
.pencil-wrap.note-info   svg { color:#3b82f6; }
.pencil-wrap.note-action svg { color:#f59e0b; }
.pencil-wrap.note-urgent svg { color:#ef4444; }
.pencil-wrap.note-done   svg { color:#22c55e; }

.note-chip { display:inline-flex;align-items:center;gap:3px;border-radius:4px;font-size:10px;padding:2px 6px;cursor:pointer;margin-left:6px;border:1px solid; }
.note-chip.nc-info   { background:#eff6ff;border-color:#93c5fd;color:#1d4ed8; }
.note-chip.nc-action { background:#fefce8;border-color:#fcd34d;color:#92400e; }
.note-chip.nc-urgent { background:#fef2f2;border-color:#fca5a5;color:#dc2626; }
[data-theme="dark"] .note-chip.nc-info   { background:#0d1a3a;border-color:#4285f4;color:#60a5fa; }
[data-theme="dark"] .note-chip.nc-action { background:#2d2500;border-color:#f59e0b;color:#fbbf24; }
[data-theme="dark"] .note-chip.nc-urgent { background:#3a1a1a;border-color:#f85149;color:#f85149; }

.pencil-icon { display:block; }

/* ══ NOTE MODAL ══════════════════════════════════ */
.ov { display:none;position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:999; }
.ov.open { display:block; }
.note-modal { display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:18px;width:400px;z-index:1000;box-shadow:var(--shadow); }
.note-modal.open { display:block; }
.nm-title { font-size:12px;color:var(--text2);margin-bottom:10px; }
.note-modal textarea { width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:6px;color:var(--text);font-family:inherit;font-size:12px;padding:8px 10px;resize:none;outline:none;height:80px; }
.note-modal textarea:focus { border-color:var(--accent); }
.ac-row { display:flex;align-items:center;gap:7px;margin-top:10px; }
.ac-lbl { font-size:11px;color:var(--text3); }
.ac { padding:3px 9px;border-radius:10px;font-size:11px;border:1px solid var(--border);color:var(--text2);cursor:pointer;background:transparent;font-family:inherit; }
.ac:hover { border-color:var(--accent);color:var(--accent); }
.ac.on { border-color:#f0883e;color:#f0883e;background:#fff7ed; }
[data-theme="dark"] .ac.on { background:#2d1a00; }
.nm-footer { display:flex;justify-content:flex-end;gap:8px;margin-top:12px; }
.btn { padding:6px 14px;border-radius:5px;cursor:pointer;font-family:inherit;font-size:12px;border:1px solid; }
.btn-cancel { background:transparent;border-color:var(--border);color:var(--text2); }
.btn-save { background:var(--accent-bg);border-color:var(--accent);color:var(--accent); }

/* ══ GANTT ═══════════════════════════════════════ */
.gw { overflow-x:auto; }
.gantt { min-width:960px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;overflow:hidden; }

.gh { display:grid;grid-template-columns:260px repeat(10,1fr);border-bottom:1px solid var(--border);background:var(--bg3); }
.ghl { padding:7px 14px;font-size:11px;color:var(--text3);border-right:1px solid var(--border);text-transform:uppercase;letter-spacing:.5px; }
.gwk { padding:7px 4px;font-size:10px;color:var(--text3);text-align:center;border-right:1px solid var(--border2); }
.gwk.now { color:var(--accent);font-weight:700; }

/* Dream row */
.drow { display:grid;grid-template-columns:260px 1fr;border-bottom:1px solid var(--border);background:var(--bg2);transition:background .15s; }
.drow:hover { background:var(--bg3); }
.drow.exp { background:var(--bg3); }
.dlbl { padding:9px 14px;border-right:1px solid var(--border);display:flex;flex-direction:column;justify-content:center;gap:5px;position:relative;cursor:pointer;min-height:52px; }
.dtop { display:flex;align-items:center;gap:7px; }
.darr { font-size:11px;color:var(--text3);transition:transform .25s; }
.exp .darr { transform:rotate(90deg);color:var(--accent); }
.dname { font-size:12px;color:var(--text);font-weight:600; }
.dbot { display:flex;align-items:center;gap:8px; }
.dcost { font-size:10px; }
.dcost.ok { color:#16a34a; }
.dcost.over { color:#dc2626; }
.dcost.na { color:var(--text3); }
.dbars { position:relative;height:52px;display:flex;align-items:center; }

/* Stage bars — OVERVIEW */
.sb {
  position:absolute; height:28px; border-radius:5px;
  display:flex;align-items:center;padding:0 8px;
  font-size:10px;font-weight:600;gap:5px;
  cursor:pointer;transition:filter .15s,box-shadow .2s;border:1px solid;white-space:nowrap;
}
.sb:hover { filter:brightness(.92); box-shadow: 0 2px 8px rgba(0,0,0,.12); }
[data-theme="dark"] .sb:hover { filter:brightness(1.2); }
.sb.dim { opacity:.3;cursor:default; }
.sb.dim:hover { filter:none;box-shadow:none; }
.sb.sel { box-shadow:0 0 0 2px var(--accent), 0 2px 8px rgba(0,0,0,.12); }

.sb-dream {background:var(--s-dream-bg);border-color:var(--s-dream-bd);color:var(--s-dream-tx);}
.sb-plan  {background:var(--s-plan-bg); border-color:var(--s-plan-bd); color:var(--s-plan-tx); }
.sb-work  {background:var(--s-work-bg); border-color:var(--s-work-bd); color:var(--s-work-tx); }
.sb-ship  {background:var(--s-ship-bg); border-color:var(--s-ship-bd); color:var(--s-ship-tx); }
.sb-maint {background:var(--s-maint-bg);border-color:var(--s-maint-bd);color:var(--s-maint-tx);}
.sb-engage{background:var(--s-engage-bg);border-color:var(--s-engage-bd);color:var(--s-engage-tx);}

.sb.live { background-size:200% 100%;animation:sh 2s infinite; }
.sb-plan.live { background:linear-gradient(90deg,var(--s-plan-bg),#bfdbfe,var(--s-plan-bg));background-size:200% 100%; }
.sb-work.live { background:linear-gradient(90deg,var(--s-work-bg),#bbf7d0,var(--s-work-bg));background-size:200% 100%; }
[data-theme="dark"] .sb-plan.live { background:linear-gradient(90deg,#1e3a5a,#2e5a8a,#1e3a5a);background-size:200% 100%; }
[data-theme="dark"] .sb-work.live { background:linear-gradient(90deg,#1a4a2e,#2a6a3e,#1a4a2e);background-size:200% 100%; }
@keyframes sh { 0%{background-position:200% 0}100%{background-position:-200% 0} }

.bar-agents .aa { width:13px;height:13px;font-size:7px;border-width:1px; }
.today-ln { position:absolute;top:0;bottom:0;width:2px;background:var(--accent);opacity:.5;pointer-events:none;z-index:5; }
.today-ln::before { content:'today';position:absolute;top:2px;left:4px;font-size:9px;color:var(--accent);white-space:nowrap; }

/* ══ DRILL-DOWN SECTION ══════════════════════════ */
.drill {
  max-height:0; overflow:hidden;
  border-left:3px solid var(--accent);
  background:var(--bg);
  transition:max-height .35s cubic-bezier(.4,0,.2,1);
  border-bottom:0px solid var(--border);
}
.drill.open {
  max-height:600px;
  border-bottom:1px solid var(--border);
}

.drill-header {
  display:flex;align-items:center;gap:10px;
  padding:8px 14px;border-bottom:1px solid var(--border2);
  background:var(--bg2);
}
.stage-pill { padding:3px 10px;border-radius:10px;font-size:11px;font-weight:700;border:1px solid; }
.drill-ttl { font-size:12px;color:var(--text2); }
.drill-close { margin-left:auto;color:var(--text3);cursor:pointer;font-size:14px;padding:0 4px; }
.drill-close:hover { color:var(--text); }

/* Zoomed timeline header */
.zoom-grid { display:grid;border-bottom:1px solid var(--border2);background:var(--bg3); }
.zoom-lbl { padding:6px 14px;font-size:11px;color:var(--text3);border-right:1px solid var(--border2);font-style:italic; }
.zoom-col { padding:6px 4px;font-size:10px;color:var(--accent);text-align:center;border-right:1px solid var(--border2);font-weight:700; }

/* Task rows in zoomed view */
.trow { display:grid;border-bottom:1px solid var(--border2);background:var(--bg);min-height:48px;transition:background .15s; }
.trow:last-child { border-bottom:none; }
.trow:hover { background:var(--bg3); }

.tlbl {
  padding:7px 14px;border-right:1px solid var(--border2);
  display:flex;align-items:center;gap:8px;position:relative;
  overflow:hidden;
}
.tname { font-size:12px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;text-align:right; }

/* Zoomed task bar */
.tbars { position:relative;display:flex;align-items:center; }
.tb {
  position:absolute; border-radius:5px;
  display:flex;align-items:center;padding:0 8px;
  font-size:10px;font-weight:600;border:1px solid;
  transition:filter .15s,box-shadow .15s;
  overflow:hidden; white-space:nowrap; height:30px;
}
.tb:hover { filter:brightness(.95);box-shadow:0 2px 8px rgba(0,0,0,.1); }
[data-theme="dark"] .tb:hover { filter:brightness(1.15); }
.tb-name { flex:1;overflow:hidden;text-overflow:ellipsis; }
.tb-right { display:flex;align-items:center;gap:5px;margin-left:auto;flex-shrink:0;padding-left:6px; }
.tb-cost { font-size:10px;opacity:.8; }

/* Task status variants */
.tb-done   { background:var(--bg3);border-color:var(--border);color:var(--text3); }
.tb-active { background:var(--s-work-bg);border-color:var(--s-work-bd);color:var(--s-work-tx);animation:sh 2s infinite; }
.tb-active { background:linear-gradient(90deg,var(--s-work-bg),#bbf7d0,var(--s-work-bg));background-size:200% 100%; }
[data-theme="dark"] .tb-active { background:linear-gradient(90deg,#1a4a2e,#2a6a3e,#1a4a2e);background-size:200% 100%; }
.tb-queued { background:var(--bg3);border-color:var(--border);color:var(--text3);opacity:.55; }
.tb-blocked{ background:#fef2f2;border-color:#fca5a5;color:#dc2626; }

/* Status dot */
.st-dot { width:7px;height:7px;border-radius:50%;flex-shrink:0; }
.st-dot.done    { background:#16a34a; }
.st-dot.active  { background:var(--s-work-tx);animation:pulse 1.5s infinite; }
.st-dot.queued  { background:var(--text3); }
.st-dot.blocked { background:#dc2626; }
@keyframes pulse { 0%,100%{opacity:1}50%{opacity:.3} }

/* ══ LEGEND + SUMMARY ════════════════════════════ */
.legend { display:flex;align-items:center;gap:12px;margin-top:14px;flex-wrap:wrap; }
.li { display:flex;align-items:center;gap:5px;font-size:11px;color:var(--text3); }
.ld { width:10px;height:10px;border-radius:3px;border:1px solid; }
.lsep { color:var(--border); }
.al-row { display:flex;align-items:center;gap:14px;margin-top:8px; }
.ali { display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text3); }

/* Note icon state legend */
.ni-legend { display:flex;align-items:center;gap:12px;margin-top:8px; }
.nil { display:flex;align-items:center;gap:5px;font-size:11px;color:var(--text3); }

.srow { display:flex;gap:10px;margin-top:18px; }
.sc { flex:1;background:var(--bg2);border:1px solid var(--border);border-radius:7px;padding:11px 13px;position:relative; }
.sc .sl { font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.5px; }
.sc .sv { font-size:20px;font-weight:700;color:var(--text);margin:4px 0 2px; }
.sc .ss { font-size:11px;color:var(--text3); }
.sc.teal .sv { color:var(--accent); }
.sc.blue .sv { color:#1d4ed8; }[data-theme="dark"] .sc.blue .sv { color:#60a5fa; }
.sc.org  .sv { color:#c2410c; }[data-theme="dark"] .sc.org  .sv { color:#fb923c; }
.sc.purp .sv { color:#6d28d9; }[data-theme="dark"] .sc.purp .sv { color:#a78bfa; }
.wow { display:inline-block;margin-top:4px;background:var(--s-work-bg);color:var(--s-work-tx);border:1px solid var(--s-work-bd);border-radius:10px;font-size:10px;padding:2px 8px; }

/* Goals Panel Styles */
.goals-panel {
  max-height: 0;
  overflow: hidden;
  border-left: 3px solid var(--accent);
  background: var(--bg);
  transition: max-height .35s cubic-bezier(.4,0,.2,1);
  border-bottom: 0px solid var(--border);
  margin-top: 15px;
  border-radius: 4px;
}
.goals-panel.open {
  max-height: 600px;
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  background: var(--bg2);
}
.goals-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border2);
  background: var(--bg3);
}
.goals-ttl {
  font-weight: 700;
  font-size: 13px;
  color: var(--text);
}
.goals-close {
  margin-left: auto;
  color: var(--text3);
  cursor: pointer;
  font-size: 12px;
}
.goals-close:hover {
  color: var(--text);
}
.goals-body {
  padding: 8px 0;
}
.goal-item {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border2);
  gap: 12px;
}
.goal-item:last-child {
  border-bottom: none;
}
.goal-content {
  flex: 1;
}
.goal-outcome {
  font-weight: bold;
  color: var(--text);
  font-size: 13px;
}
.goal-criterion {
  font-size: 11px;
  color: var(--text2);
  margin-top: 2px;
}
.goal-deadline {
  font-size: 11px;
  color: var(--text3);
  margin-left: 10px;
  white-space: nowrap;
}
.goal-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
  background: var(--bg3);
  color: var(--text2);
  border: 1px solid var(--border);
}
.goal-badge.active {
  background: var(--accent-bg);
  color: var(--accent);
  border-color: var(--accent-dim);
}
.empty-state {
  padding: 18px 14px;
  color: var(--text3);
  font-size: 12px;
  text-align: center;
}
.empty-state code {
  background: var(--bg3);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: inherit;
}
/* ══ SECTION DIVIDERS & COLLAPSIBLE CONTROLS ══════════════ */
.section-divider { margin: 16px 0 10px; }
.section-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; background: var(--bg3); border: 1px solid var(--border);
  border-radius: 6px; cursor: pointer; user-select: none; transition: background .15s;
}
.section-header:hover { background: var(--border2); }
.section-title { display: flex; align-items: center; gap: 10px; font-size: 12px; font-weight: 700; color: var(--text); }
.section-chevron { font-size: 10px; color: var(--text3); transition: transform .2s; }
.section-header.collapsed .section-chevron { transform: rotate(-90deg); }
.section-badge { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px; text-transform: uppercase; }
.active-badge { background: rgba(13,158,135,0.15); color: #0d9e87; border: 1px solid rgba(13,158,135,0.3); }
.planned-badge { background: rgba(59,130,246,0.12); color: #3b82f6; border: 1px solid rgba(59,130,246,0.3); }
.completed-badge { background: rgba(100,116,139,0.15); color: var(--text3); border: 1px solid var(--border); }
.section-count { font-size: 11px; color: var(--text3); font-weight: normal; }
.section-hint { font-size: 11px; color: var(--text3); }
.section-content { transition: max-height .3s ease; }
.section-content.collapsed { display: none; }
.goal-pill { background: rgba(99,102,241,0.12); color: #6366f1; border: 1px solid rgba(99,102,241,0.3); font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 600; display: inline-flex; align-items: center; gap: 3px; max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pivot-controls { display: flex; align-items: center; background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 2px; }
.pivot-btn { padding: 4px 12px; border-radius: 4px; font-size: 11px; font-family: inherit; border: none; background: transparent; color: var(--text2); cursor: pointer; transition: all .15s; }
.pivot-btn.active { background: var(--accent); color: #fff; font-weight: 700; }
"""


def generate_gantt_html(data: dict, port: int) -> str:
    data_json = json.dumps(data)

    script_content = """
const PORT = __PORT__;
const NOTE_STATE_CLASS = { none:'note-none', info:'note-info', action:'note-action', urgent:'note-urgent', done:'note-done' };
const STAGE_CLASS = {
  goal:'goal',
  open:'open',
  visualize:'visualize',
  execute:'execute',
  release:'release',
  notify:'notify',
  sustain:'sustain',
};
const STAGE_ICON = {
  goal:'◆ Goal',
  open:'○ Open',
  visualize:'◌ Visualize',
  execute:'⚙ Execute',
  release:'▲ Release',
  notify:'✉ Notify',
  sustain:'↺ Sustain',
};
const STAGE_STYLE = {
  goal:'background:#dbeafe;border-color:#93c5fd;color:#1d4ed8',
  open:'background:#ede9fe;border-color:#c4b5fd;color:#6d28d9',
  visualize:'background:#e6f7f4;border-color:#c0ede6;color:#0d9e87',
  execute:'background:#dcfce7;border-color:#86efac;color:#15803d',
  release:'background:#fef3c7;border-color:#fde68a;color:#d97706',
  notify:'background:#ffe4e6;border-color:#fda4af;color:#be123c',
  sustain:'background:#f3f4f6;border-color:#d1d5db;color:#6b7280',
};
const releases = Array.isArray(window.VIZOR_DATA && (window.VIZOR_DATA.releases || window.VIZOR_DATA.dreams)) ? (window.VIZOR_DATA.releases || window.VIZOR_DATA.dreams) : [];
const dreams = releases; // Backwards compatibility alias
const goals = Array.isArray(window.VIZOR_DATA && window.VIZOR_DATA.goals) ? window.VIZOR_DATA.goals : [];
const specVerifications = Array.isArray(window.VIZOR_DATA && window.VIZOR_DATA.spec_verifications) ? window.VIZOR_DATA.spec_verifications : [];
const VERDICT_BADGE = {
  fulfilled: 'background:#dcfce7;border-color:#86efac;color:#15803d',
  partial: 'background:#fef3c7;border-color:#fde68a;color:#d97706',
  diverged: 'background:#ffe4e6;border-color:#fda4af;color:#be123c',
};
const notes = (window.VIZOR_DATA && window.VIZOR_DATA.notes && typeof window.VIZOR_DATA.notes === 'object') ? window.VIZOR_DATA.notes : {};
let openDrills = {};
let currentNoteTarget = null;
let currentPivot = safeStorageGet('vizor-gantt-pivot', 'release');
let sectionStates = {
  active: safeStorageGet('vizor-gantt-sec-active', 'open') === 'open',
  planned: safeStorageGet('vizor-gantt-sec-planned', 'open') === 'open',
  completed: safeStorageGet('vizor-gantt-sec-completed', 'collapsed') === 'open',
};

function escapeHtml(value) {
  return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function safeStorageGet(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value === null ? fallback : value;
  } catch (err) {
    return fallback;
  }
}

function safeStorageSet(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (err) {}
}

function setTheme(t) {
  const resolved = t === 'system' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : t;
  document.documentElement.setAttribute('data-theme', resolved);
  document.querySelectorAll('.theme-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('btn-' + t)?.classList.add('active');
  safeStorageSet('vizor-theme', t);
}

function toggleSection(secKey) {
  sectionStates[secKey] = !sectionStates[secKey];
  safeStorageSet('vizor-gantt-sec-' + secKey, sectionStates[secKey] ? 'open' : 'collapsed');
  const header = document.getElementById('sec-hdr-' + secKey);
  const content = document.getElementById('sec-cnt-' + secKey);
  if (header && content) {
    if (sectionStates[secKey]) {
      header.classList.remove('collapsed');
      content.classList.remove('collapsed');
      const hint = header.querySelector('.section-hint');
      if (hint) hint.textContent = 'Click to collapse';
    } else {
      header.classList.add('collapsed');
      content.classList.add('collapsed');
      const hint = header.querySelector('.section-hint');
      if (hint) hint.textContent = 'Click to expand';
    }
  }
}

function setPivot(pivot) {
  currentPivot = pivot;
  safeStorageSet('vizor-gantt-pivot', pivot);
  document.getElementById('pivot-release-btn')?.classList.toggle('active', pivot === 'release');
  document.getElementById('pivot-goal-btn')?.classList.toggle('active', pivot === 'goal');
  renderTimeline();
}

function classForStage(stageKey) {
  const key = String(stageKey || '').trim().toLowerCase();
  return STAGE_CLASS[key] || 'open';
}

function iconForStage(stageKey) {
  const key = String(stageKey || '').trim().toLowerCase();
  return STAGE_ICON[key] || (stageKey ? escapeHtml(stageKey) : '○ Open');
}

function noteStateClass(state) {
  return NOTE_STATE_CLASS[state || 'none'] || NOTE_STATE_CLASS.none;
}

function noteData(targetId) {
  return notes[targetId] || (window.VIZOR_DATA && window.VIZOR_DATA.notes && window.VIZOR_DATA.notes[targetId]) || null;
}

function setNoteButtons(tags) {
  const wanted = new Set((tags || []).map(t => String(t).trim().toLowerCase()));
  document.querySelectorAll('.ac').forEach(btn => {
    const tag = String(btn.getAttribute('data-tag') || '').trim().toLowerCase();
    btn.classList.toggle('on', wanted.has(tag));
  });
}

function noteTagsFromButtons() {
  return Array.from(document.querySelectorAll('.ac.on')).map(btn => btn.getAttribute('data-tag') || btn.textContent.trim()).filter(Boolean);
}

function updateNoteIcon(targetId, state) {
  const el = document.querySelector('[data-note-target="' + CSS.escape(targetId) + '"]');
  if (!el) return;
  Object.values(NOTE_STATE_CLASS).forEach(cls => el.classList.remove(cls));
  el.classList.add(noteStateClass(state));
}

function openNote(targetId, targetLabel) {
  currentNoteTarget = targetId;
  const existing = noteData(targetId);
  document.getElementById('nt').innerHTML = 'Note on <strong>' + escapeHtml(targetLabel || targetId) + '</strong>';
  document.getElementById('ntxt').value = existing && typeof existing.text === 'string' ? existing.text : '';
  setNoteButtons(existing && Array.isArray(existing.tags) ? existing.tags : []);
  document.getElementById('nm').classList.add('open');
  document.getElementById('ov').classList.add('open');
  document.getElementById('ntxt').focus();
}

function openNoteFromEl(el) {
  openNote(el.getAttribute('data-note-target'), el.getAttribute('data-note-label'));
}

function closeNote() {
  document.getElementById('nm').classList.remove('open');
  document.getElementById('ov').classList.remove('open');
  currentNoteTarget = null;
}

async function saveNote() {
  if (!currentNoteTarget) return;
  const text = document.getElementById('ntxt').value || '';
  const tags = noteTagsFromButtons();
  const existing = noteData(currentNoteTarget);
  const derivedState = existing && existing.state ? existing.state : ((text || tags.length) ? 'info' : null);
  const response = await fetch('/note', {
    method: 'POST',
    headers: window.vizorAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ id: currentNoteTarget, text, tags, state: derivedState }),
  });
  if (!response.ok) throw new Error('note save failed');
  notes[currentNoteTarget] = { text, tags, state: derivedState };
  if (window.VIZOR_DATA && window.VIZOR_DATA.notes) {
    window.VIZOR_DATA.notes[currentNoteTarget] = notes[currentNoteTarget];
  }
  updateNoteIcon(currentNoteTarget, derivedState);
  closeNote();
}

function renderTask(task, releaseId, stageKey, index, total) {
  const status = String(task.status || 'queued').trim().toLowerCase();
  const tbClass = status === 'done' ? 'tb-done' : status === 'active' ? 'tb-active' : status === 'blocked' ? 'tb-blocked' : 'tb-queued';
  const dotClass = status === 'done' ? 'done' : status === 'active' ? 'active' : status === 'blocked' ? 'blocked' : 'queued';
  const note = task.note || null;
  const noteClass = noteStateClass(note && note.state);
  const leftPct = total > 0 ? ((index / total) * 100).toFixed(1) : '0.0';
  const widthPct = total > 0 ? ((0.85 / total) * 100).toFixed(1) : '100.0';
  const agent = String(task.agent || '').trim().toLowerCase();
  const agentClass = agent === 'agy' ? 'aa-agy' : agent === 'codex' ? 'aa-codex' : agent === 'grok' ? 'aa-grok' : 'aa-claude';
  const agentLabel = agent === 'codex' ? 'Co' : agent === 'grok' ? 'G' : agent === 'claude' ? 'C' : 'A';
  return `
    <div class="trow editable" style="grid-template-columns:260px repeat(${total || 1}, 1fr)" title="ID: ${escapeHtml(task.id)}">
      <div class="tlbl">
        <div class="aa ${agentClass}" title="${escapeHtml(task.agent || 'agent')}">${agentLabel}</div>
        <div class="tname">${escapeHtml(task.name || 'Task')}</div>
        <div class="pencil-wrap ${noteClass}" data-note-target="${escapeHtml(task.id)}" data-note-label="${escapeHtml(task.name || task.id)}" onclick="openNoteFromEl(this);event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div>
      </div>
      <div class="tbars" style="grid-column:2/span ${total || 1}">
        <div class="tb ${tbClass}" style="left:${leftPct}%;width:${widthPct}%">
          <div class="st-dot ${dotClass}"></div>
          <span class="tb-name">${escapeHtml(task.name || 'Task')}</span>
          <div class="tb-right">
            <div class="aa sm ${agentClass}" title="${escapeHtml(task.agent || 'agent')}">${agentLabel}</div>
            <span class="tb-cost">${escapeHtml(status)}${note && note.text ? ' · note' : ''}</span>
          </div>
        </div>
      </div>
    </div>`;
}

function renderDrill(releaseId, stageKey) {
  const rel = releases.find(d => d.id === releaseId);
  const stage = rel && Array.isArray(rel.stages) ? rel.stages.find(s => s.key === stageKey) : null;
  const dr = document.getElementById('drill-' + releaseId);
  if (!dr) return;
  if (!stage) {
    dr.innerHTML = `<div style="padding:12px 14px;font-size:11px;color:var(--text3)">No tasks defined. <span style="color:var(--accent);cursor:pointer">📝 Add note</span></div>`;
    return;
  }

  const tasks = Array.isArray(stage.tasks) ? stage.tasks : [];
  const total = Math.max(tasks.length, 1);
  const gridCols = `260px repeat(${total}, 1fr)`;
  const headerCols = tasks.map((task, idx) => `<div class="zoom-col">${escapeHtml(task.name || ('Task ' + (idx + 1)))}</div>`).join('');
  const taskRows = tasks.map((task, idx) => renderTask(task, releaseId, stageKey, idx, total)).join('');
  const pillKey = classForStage(stageKey);
  const lastLabel = tasks.length > 1 ? tasks[tasks.length - 1].name : '';
  dr.innerHTML = `
    <div class="drill-header">
      <div class="stage-pill" style="${STAGE_STYLE[pillKey] || STAGE_STYLE.plan}">${escapeHtml(iconForStage(stageKey))} stage</div>
      <div class="drill-ttl">${escapeHtml(releaseId.toUpperCase())} — ${tasks.length} task${tasks.length !== 1 ? 's' : ''} · zoomed to stage window</div>
      <div class="drill-close" onclick="closeDrill('${escapeHtml(releaseId)}')">✕ collapse</div>
    </div>
    <div class="zoom-grid" style="grid-template-columns:${gridCols}">
      <div class="zoom-lbl">↳ zoomed: ${escapeHtml(stage.key || stageKey)}${lastLabel ? ' → ' + escapeHtml(lastLabel) : ''}</div>
      ${headerCols}
    </div>
    ${taskRows}`;
}

function zoomStage(releaseId, stageKey, barEl) {
  const dr = document.getElementById('drill-' + releaseId);
  const drow = document.getElementById('drow-' + releaseId);
  if (!dr || !drow) return;
  if (openDrills[releaseId] === stageKey) {
    closeDrill(releaseId);
    return;
  }
  if (openDrills[releaseId]) {
    const prevBar = document.getElementById('sb-' + releaseId + '-' + openDrills[releaseId]);
    if (prevBar) prevBar.classList.remove('sel');
  }
  renderDrill(releaseId, stageKey);
  dr.classList.add('open');
  drow.classList.add('exp');
  if (barEl) barEl.classList.add('sel');
  openDrills[releaseId] = stageKey;
}

function closeDrill(releaseId) {
  const dr = document.getElementById('drill-' + releaseId);
  const drow = document.getElementById('drow-' + releaseId);
  dr?.classList.remove('open');
  drow?.classList.remove('exp');
  if (openDrills[releaseId]) {
    const prevBar = document.getElementById('sb-' + releaseId + '-' + openDrills[releaseId]);
    if (prevBar) prevBar.classList.remove('sel');
  }
  delete openDrills[releaseId];
}

function toggleDrill(releaseId) {
  if (openDrills[releaseId]) {
    closeDrill(releaseId);
    return;
  }
  const rel = releases.find(d => d.id === releaseId);
  if (!rel || !Array.isArray(rel.stages) || !rel.stages.length) return;
  const activeStage = rel.stages.find(s => String(s.status || '').toLowerCase() === 'active') || rel.stages[0];
  const barEl = document.getElementById('sb-' + releaseId + '-' + activeStage.key);
  zoomStage(releaseId, activeStage.key, barEl);
}

function renderRelease(release) {
  const stages = Array.isArray(release.stages) ? release.stages : [];
  const note = release.note || noteData(release.id);
  const noteClass = noteStateClass(note && note.state);
  const taskCount = stages.reduce((sum, stage) => sum + (Array.isArray(stage.tasks) ? stage.tasks.length : 0), 0);
  const status = String(release.status || 'planned').trim().toLowerCase();
  const statusClass = (status === 'done' || status === 'shipped') ? 'ok' : (status === 'blocked' ? 'over' : 'na');
  const stageAgents = stages[0] && Array.isArray(stages[0].agents) ? stages[0].agents : [];
  const agentsHtml = stageAgents.slice(0, 4).map(agent => {
    const a = String(agent || '').trim().toLowerCase();
    const agentClass = a === 'agy' ? 'aa-agy' : a === 'codex' ? 'aa-codex' : a === 'grok' ? 'aa-grok' : 'aa-claude';
    const agentLabel = a === 'codex' ? 'Co' : a === 'grok' ? 'G' : a === 'claude' ? 'C' : 'A';
    return `<div class="aa ${agentClass}" title="${escapeHtml(agent)}">${agentLabel}</div>`;
  }).join('');
  const barHtml = stages.map(stage => {
    const cls = classForStage(stage.key);
    const live = String(stage.status || '').toLowerCase() === 'active' ? 'live' : 'dim';
    const left = Number(stage.start_frac || 0) * 100;
    const width = Number(stage.width_frac || 0) * 100;
    const agentHtml = Array.isArray(stage.agents) && stage.agents.length ? `<div class="bar-agents">${stage.agents.map(agent => {
      const a = String(agent || '').trim().toLowerCase();
      const agentClass = a === 'agy' ? 'aa-agy' : a === 'codex' ? 'aa-codex' : a === 'grok' ? 'aa-grok' : 'aa-claude';
      const agentLabel = a === 'codex' ? 'Co' : a === 'grok' ? 'G' : a === 'claude' ? 'C' : 'A';
      return `<div class="aa ${agentClass}">${agentLabel}</div>`;
    }).join('')}</div>` : '';
    return `<div class="sb sb-${cls} ${live}" id="sb-${release.id}-${stage.key}" style="left:${left}%;width:${width}%" onclick="zoomStage('${escapeHtml(release.id)}','${escapeHtml(stage.key)}',this)">${escapeHtml(iconForStage(stage.key))}${agentHtml}</div>`;
  }).join('');

  const goalBadge = release.goal_id ? `<span class="goal-pill" title="Goal: ${escapeHtml(release.goal_outcome || release.goal_id)}">🎯 ${escapeHtml(release.goal_id)}</span>` : '';
  const targetDateHtml = release.target_date ? `<span style="font-size:10px;color:var(--text3);margin-left:4px;">📅 ${escapeHtml(release.target_date)}</span>` : '';

  return `
      <div class="drow" id="drow-${release.id}">
        <div class="dlbl editable" onclick="toggleDrill('${escapeHtml(release.id)}')">
          <div class="dtop"><span class="darr">▶</span><div class="dname">${escapeHtml(release.id)} · ${escapeHtml(release.name || release.id)}</div>
            ${goalBadge}
            <span class="note-chip nc-${noteClass.replace('note-', '') === 'none' ? 'info' : noteClass.replace('note-', '')}" style="display:${noteClass === 'note-none' ? 'none' : 'inline-flex'}" onclick="openNote('${escapeHtml(release.id)}','${escapeHtml(release.name || release.id)}');event.stopPropagation()">✎ note</span>
          </div>
          <div class="dbot"><div class="aa-stack">${agentsHtml}</div><span class="dcost ${statusClass}">${escapeHtml(release.status || 'planned')}${taskCount ? ' · ' + taskCount + ' tasks' : ''}</span>${targetDateHtml}</div>
          <div class="pencil-wrap ${noteClass}" data-note-target="${escapeHtml(release.id)}" data-note-label="${escapeHtml(release.name || release.id)}" onclick="openNoteFromEl(this);event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div>
        </div>
        <div class="dbars">
          <div class="today-ln" style="left:19%"></div>
          ${barHtml}
        </div>
      </div>
      <div class="drill" id="drill-${release.id}"></div>`;
}

// Backwards compatibility alias
const renderDream = renderRelease;

function renderGoal(goal) {
  const deadlineHtml = goal.deadline ? `<span class="goal-deadline">📅 ${escapeHtml(goal.deadline)}</span>` : '';
  const status = String(goal.status || 'active').trim().toLowerCase();
  const badgeClass = status === 'active' ? 'active' : '';
  return `
    <div class="goal-item">
      <div class="goal-content">
        <div class="goal-outcome">${escapeHtml(goal.outcome)}</div>
        <div class="goal-criterion">${escapeHtml(goal.criterion)}</div>
      </div>
      ${deadlineHtml}
      <div class="goal-badge ${badgeClass}">${escapeHtml(status)}</div>
    </div>`;
}

function toggleGoalsPanel() {
  const panel = document.getElementById('goals-panel');
  if (!panel) return;
  panel.classList.toggle('open');
}

function renderGoals() {
  const goalCount = document.getElementById('goal-count');
  const goalSub = document.getElementById('goal-sub');
  const goalsBody = document.getElementById('goals-body');

  const activeCount = goals.filter(g => String(g.status || '').toLowerCase() === 'active').length;
  const totalCount = goals.length;

  if (goalCount) goalCount.textContent = String(activeCount);
  if (goalSub) goalSub.textContent = activeCount + ' active / of ' + totalCount + ' goals';

  if (!goalsBody) return;

  if (!goals.length) {
    goalsBody.innerHTML = `
      <div class="empty-state">
        <p class="empty-state-desc" style="padding: 12px 14px; font-size: 11px; color: var(--text3); margin: 0;">
          No active goals yet. Add a goal using: <code>synlynk goal create --outcome "..." --criterion "..."</code>
        </p>
      </div>`;
    return;
  }

  goalsBody.innerHTML = goals.map(renderGoal).join('');
}

function renderVerifiedEntry(entry) {
  const verdict = String(entry.verdict || 'unknown').trim().toLowerCase();
  const badgeStyle = VERDICT_BADGE[verdict] || 'background:#f3f4f6;border-color:#d1d5db;color:#6b7280';
  return `
    <div class="goal-item">
      <div class="goal-content">
        <div class="goal-outcome">PR #${escapeHtml(entry.pr_number ?? '—')} · ${escapeHtml(entry.spec_path || 'Unknown spec')}</div>
        <div class="goal-criterion">${escapeHtml(entry.rationale || 'No rationale provided')}</div>
      </div>
      <div class="goal-badge" style="${badgeStyle}">${escapeHtml(verdict)}</div>
    </div>`;
}

function toggleVerifiedPanel() {
  const panel = document.getElementById('spec-verifications-panel');
  if (!panel) return;
  panel.classList.toggle('open');
}

function renderVerified() {
  const count = document.getElementById('spec-verified-count');
  const sub = document.getElementById('spec-verified-sub');
  const body = document.getElementById('spec-verifications-body');
  if (count) count.textContent = String(specVerifications.length);
  if (sub) sub.textContent = specVerifications.length + ' verified PR' + (specVerifications.length === 1 ? '' : 's');
  if (!body) return;
  body.innerHTML = specVerifications.length
    ? specVerifications.map(renderVerifiedEntry).join('')
    : '<div class="empty-state"><p class="empty-state-desc" style="padding: 12px 14px; font-size: 11px; color: var(--text3); margin: 0;">No verified PRs yet.</p></div>';
}

function renderByRelease() {
  const body = document.getElementById('gantt-body');
  if (!body) return;
  if (!releases.length) {
    body.innerHTML = "<p class='empty-state'>No Releases found in state db</p>";
    return;
  }
  const activeList = [];
  const plannedList = [];
  const completedList = [];

  releases.forEach(r => {
    const s = String(r.status || '').trim().toLowerCase();
    if (s === 'shipped' || s === 'done' || s === 'completed' || s === 'resolved') {
      completedList.push(r);
    } else if (s === 'active' || s === 'in_progress') {
      activeList.push(r);
    } else {
      plannedList.push(r);
    }
  });

  const activeOpen = sectionStates.active;
  const plannedOpen = sectionStates.planned;
  const completedOpen = sectionStates.completed;

  let html = '';

  if (activeList.length > 0) {
    html += `
      <div class="section-divider">
        <div class="section-header ${activeOpen ? '' : 'collapsed'}" id="sec-hdr-active" onclick="toggleSection('active')">
          <div class="section-title">
            <span class="section-chevron">▼</span>
            <span class="section-badge active-badge">● Active</span>
            <span>In-Progress Releases & Milestones</span>
            <span class="section-count">(${activeList.length})</span>
          </div>
          <div class="section-hint">${activeOpen ? 'Click to collapse' : 'Click to expand'}</div>
        </div>
        <div class="section-content ${activeOpen ? '' : 'collapsed'}" id="sec-cnt-active">
          ${activeList.map(renderRelease).join('')}
        </div>
      </div>`;
  }

  if (plannedList.length > 0) {
    html += `
      <div class="section-divider">
        <div class="section-header ${plannedOpen ? '' : 'collapsed'}" id="sec-hdr-planned" onclick="toggleSection('planned')">
          <div class="section-title">
            <span class="section-chevron">▼</span>
            <span class="section-badge planned-badge">○ Planned</span>
            <span>Upcoming Releases & Arcs</span>
            <span class="section-count">(${plannedList.length})</span>
          </div>
          <div class="section-hint">${plannedOpen ? 'Click to collapse' : 'Click to expand'}</div>
        </div>
        <div class="section-content ${plannedOpen ? '' : 'collapsed'}" id="sec-cnt-planned">
          ${plannedList.map(renderRelease).join('')}
        </div>
      </div>`;
  }

  if (completedList.length > 0) {
    html += `
      <div class="section-divider">
        <div class="section-header ${completedOpen ? '' : 'collapsed'}" id="sec-hdr-completed" onclick="toggleSection('completed')">
          <div class="section-title">
            <span class="section-chevron">▼</span>
            <span class="section-badge completed-badge">✓ Shipped</span>
            <span>Completed Historical Releases</span>
            <span class="section-count">(${completedList.length})</span>
          </div>
          <div class="section-hint">${completedOpen ? 'Click to collapse' : 'Click to expand'}</div>
        </div>
        <div class="section-content ${completedOpen ? '' : 'collapsed'}" id="sec-cnt-completed">
          ${completedList.map(renderRelease).join('')}
        </div>
      </div>`;
  }

  body.innerHTML = html || "<p class='empty-state'>No Releases found in state db</p>";
}

function renderByGoal() {
  const body = document.getElementById('gantt-body');
  if (!body) return;
  if (!goals.length) {
    body.innerHTML = "<p class='empty-state'>No active goals defined. Create one via <code>synlynk goal create</code></p>";
    return;
  }
  let html = '';
  goals.forEach(goal => {
    const linkedReleases = releases.filter(r => r.goal_id === goal.id || (r.goal_outcome && r.goal_outcome === goal.outcome));
    const deadlineHtml = goal.deadline ? `<span style="font-size:11px;color:var(--text3);margin-left:8px;">📅 ${escapeHtml(goal.deadline)}</span>` : '';
    html += `
      <div class="section-divider">
        <div class="section-header">
          <div class="section-title">
            <span class="section-badge active-badge">🎯 Goal</span>
            <span>${escapeHtml(goal.outcome)}</span>
            <span class="section-count">(${linkedReleases.length} linked release${linkedReleases.length !== 1 ? 's' : ''})</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            ${deadlineHtml}
            <span class="goal-badge active">${escapeHtml(goal.status || 'active')}</span>
          </div>
        </div>
        <div class="section-content">
          ${linkedReleases.length ? linkedReleases.map(renderRelease).join('') : `<div style="padding:10px 14px;font-size:11px;color:var(--text3);font-style:italic;">No releases linked to this goal yet.</div>`}
        </div>
      </div>`;
  });
  body.innerHTML = html;
}

function renderTimeline() {
  const wsSub = document.getElementById('ws-sub');
  const releaseCount = document.getElementById('dream-count');
  const releaseSub = document.getElementById('dream-sub');
  const statusWorkspaces = document.getElementById('status-workspaces');

  if (!releases.length) {
    const body = document.getElementById('gantt-body');
    if (body) body.innerHTML = "<p class='empty-state'>No Releases found in state db</p>";
    if (wsSub) wsSub.textContent = '0 Releases · no stage data';
    if (releaseCount) releaseCount.textContent = '0';
    if (releaseSub) releaseSub.textContent = '0 stages';
    if (statusWorkspaces) statusWorkspaces.textContent = '0 releases';
    renderGoals();
    renderVerified();
    return;
  }

  const releaseCountValue = releases.length;
  const stageCountValue = releases.reduce((sum, rel) => sum + (Array.isArray(rel.stages) ? rel.stages.length : 0), 0);
  const activeReleases = releases.filter(rel => {
    const s = String(rel.status || '').toLowerCase();
    return s === 'active' || s === 'in_progress';
  }).length;

  if (currentPivot === 'goal') {
    renderByGoal();
  } else {
    renderByRelease();
  }

  if (wsSub) wsSub.textContent = releaseCountValue + ' Releases · click any stage bar to zoom in';
  if (releaseCount) releaseCount.textContent = String(releaseCountValue);
  if (releaseSub) releaseSub.textContent = stageCountValue + ' stages · ' + activeReleases + ' active';
  if (statusWorkspaces) statusWorkspaces.textContent = releaseCountValue + ' releases';
  renderGoals();
  renderVerified();

  const firstRel = releases[0];
  const firstStage = firstRel && Array.isArray(firstRel.stages) ? (firstRel.stages.find(s => String(s.status || '').toLowerCase() === 'active') || firstRel.stages[0]) : null;
  if (firstRel && firstStage) {
    const barEl = document.getElementById('sb-' + firstRel.id + '-' + firstStage.key);
    if (barEl) zoomStage(firstRel.id, firstStage.key, barEl);
  }
}

// Backwards compatibility
function renderDreams() {
  renderTimeline();
}

setTheme(safeStorageGet('vizor-theme', 'light'));
renderTimeline();
""".replace("__PORT__", str(port))

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Gantt Timeline</title>
<script>window.VIZOR_DATA = {data_json};</script>
<style>
{_GANTT_STYLE}
</style>
</head>
<body>

<div class="ov" id="ov" onclick="closeNote()"></div>
<div class="note-modal" id="nm">
  <div class="nm-title" id="nt">Note on <strong>—</strong></div>
  <textarea placeholder="Add a note or instruction for next Vizor run…" id="ntxt"></textarea>
  <div class="ac-row">
    <span class="ac-lbl">Action:</span>
    <button class="ac" data-tag="Redo stage" onclick="this.classList.toggle('on')">↺ Redo stage</button>
    <button class="ac" data-tag="Reassign agent" onclick="this.classList.toggle('on')">⇄ Reassign agent</button>
    <button class="ac" data-tag="Defer" onclick="this.classList.toggle('on')">⏸ Defer</button>
  </div>
  <div class="nm-footer">
    <button class="btn btn-cancel" onclick="closeNote()">Cancel</button>
    <button class="btn btn-save" onclick="saveNote()">Save note</button>
  </div>
</div>

<svg style="display:none"><symbol id="pencil-svg" viewBox="0 0 16 16">
  <polygon points="2,14 3.5,10 12,1.5 14.5,4 6,12.5" fill="currentColor" opacity=".85"/>
  <polygon points="2,14 3.5,10 5.5,12" fill="currentColor"/>
  <rect x="12.2" y="0.5" width="2.5" height="3" rx=".5" fill="currentColor" opacity=".6"/>
  <line x1="4.5" y1="11" x2="12.5" y2="3" stroke="white" stroke-width=".7" opacity=".3"/>
</symbol></svg>

<div class="content">
  <div class="ws-header">
    <div>
      <div class="ws-title">{html.escape(str(data.get("workspace", {}).get("name", "workspace")))}</div>
      <div class="ws-sub" id="ws-sub">Loading timeline…</div>
    </div>
    <div style="display:flex;align-items:center;gap:10px;margin-left:auto;">
      <div class="pivot-controls">
        <button id="pivot-release-btn" class="pivot-btn active" onclick="setPivot('release')">By Release</button>
        <button id="pivot-goal-btn" class="pivot-btn" onclick="setPivot('goal')">By Goal</button>
      </div>
      <div class="ws-chip">● live</div>
    </div>
  </div>
  <div class="toolbar">
    <span class="lbl">Filter:</span>
    <button class="chip on">All</button><button class="chip">In Progress</button><button class="chip">Ships soon</button>
    <div class="sp"></div>
    <button class="zbtn">← 4w</button>
    <button class="zbtn" style="border-color:var(--accent);color:var(--accent)">10w ✓</button>
    <button class="zbtn">26w →</button>
  </div>

  <div class="gw"><div class="gantt" id="gantt">
    <div class="gh" id="gantt-header">
      <div class="ghl">Release / Epic</div>
      <div class="gwk">Goal</div><div class="gwk">Open</div>
      <div class="gwk">Visualize</div><div class="gwk now">Execute ▾</div>
      <div class="gwk">Release</div><div class="gwk">Notify</div>
      <div class="gwk">Sustain</div><div class="gwk">QA Gate</div>
      <div class="gwk">Target</div><div class="gwk">Review</div>
    </div>
    <div id="gantt-body"></div>
  </div></div>

  <div class="legend">
    <div class="li"><div class="ld" style="background:#dbeafe;border-color:#93c5fd"></div>◆ Goal</div>
    <div class="li"><div class="ld" style="background:#ede9fe;border-color:#c4b5fd"></div>○ Open</div>
    <div class="li"><div class="ld" style="background:#e6f7f4;border-color:#c0ede6"></div>◌ Visualize</div>
    <div class="li"><div class="ld" style="background:#dcfce7;border-color:#86efac"></div>⚙ Execute</div>
    <div class="li"><div class="ld" style="background:#fef3c7;border-color:#fde68a"></div>▲ Release</div>
    <div class="li"><div class="ld" style="background:#ffe4e6;border-color:#fda4af"></div>✉ Notify</div>
    <div class="li"><div class="ld" style="background:#f3f4f6;border-color:#d1d5db"></div>↺ Sustain</div>
    <span class="lsep">|</span><div class="li" style="font-style:italic">~ animated = in progress</div>
  </div>
  <div class="ni-legend">
    <span class="lbl">Note icons:</span>
    <div class="nil"><svg width="14" height="14" style="color:#9ca3af"><use href="#pencil-svg"/></svg> no note</div>
    <div class="nil"><svg width="14" height="14" style="color:#3b82f6"><use href="#pencil-svg"/></svg> has note</div>
    <div class="nil"><svg width="14" height="14" style="color:#f59e0b"><use href="#pencil-svg"/></svg> action tagged</div>
    <div class="nil"><svg width="14" height="14" style="color:#ef4444"><use href="#pencil-svg"/></svg> urgent / overrun</div>
    <div class="nil"><svg width="14" height="14" style="color:#22c55e"><use href="#pencil-svg"/></svg> resolved</div>
  </div>
  <div class="al-row">
    <span class="lbl">Agents:</span>
    <div class="ali"><div class="aa aa-claude">C</div>Claude</div>
    <div class="ali"><div class="aa aa-agy">A</div>Agy</div>
    <div class="ali"><div class="aa aa-codex">Co</div>Codex</div>
    <div class="ali"><div class="aa aa-grok">G</div>Grok</div>
  </div>

  <div class="srow">
    <div class="sc teal editable"><div class="sl">Releases tracked</div><div class="sv" id="dream-count">0</div><div class="ss" id="dream-sub">0 stages</div><div class="wow">⚡ live</div><div class="pencil-wrap note-none" onclick="openNote('summary','Summary');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
    <div class="sc blue editable"><div class="sl">Active agents</div><div class="sv">3</div><div class="aa-stack" style="margin-top:6px"><div class="aa aa-agy">A</div><div class="aa aa-codex">Co</div><div class="aa aa-grok">G</div></div><div class="pencil-wrap note-none" onclick="openNote('agents','Agents');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
    <div class="sc org editable"><div class="sl">Total spend</div><div class="sv">$28.50</div><div class="ss">of ~$71 · 40% in</div><div class="pencil-wrap note-none" onclick="openNote('cost','Total spend');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
    <div class="sc purp editable"><div class="sl">Next ship</div><div class="sv">Jul 24</div><div class="ss">Module Extraction → main</div><div class="pencil-wrap note-none" onclick="openNote('ship','Next ship');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
    <div class="sc teal editable" onclick="toggleGoalsPanel()" style="cursor:pointer;"><div class="sl">Business Goals</div><div class="sv" id="goal-count">0</div><div class="ss" id="goal-sub">0 active</div><div class="pencil-wrap note-none" onclick="openNote('goals','Business Goals');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
    <div class="sc teal editable" onclick="toggleVerifiedPanel()" style="cursor:pointer;"><div class="sl">Spec Verified</div><div class="sv" id="spec-verified-count">0</div><div class="ss" id="spec-verified-sub">0 verified PRs</div></div>
  </div>

  <div class="goals-panel" id="goals-panel">
    <div class="goals-header">
      <div class="goals-ttl">🎯 Business Goals</div>
      <div class="goals-close" onclick="toggleGoalsPanel()">✕ collapse</div>
    </div>
    <div class="goals-body" id="goals-body"></div>
  </div>
  <div class="goals-panel" id="spec-verifications-panel">
    <div class="goals-header">
      <div class="goals-ttl">✅ Spec Verified</div>
      <div class="goals-close" onclick="toggleVerifiedPanel()">✕ collapse</div>
    </div>
    <div class="goals-body" id="spec-verifications-body"></div>
  </div>
</div>

<script>
{script_content}
</script>
{_live_js(port)}
</body>
</html>"""


_ARCHITECT_MAP_JS = """
let amZoomScale = 1.0;
let amPanX = 0, amPanY = 0;

function amApplyTransform() {
  const vp = document.getElementById('am-canvas-viewport');
  if (vp) {
    vp.setAttribute('transform', 'translate(' + amPanX + ',' + amPanY + ') scale(' + amZoomScale + ')');
  }
  const details = document.querySelectorAll('.am-cluster-detail');
  details.forEach(d => {
    d.style.display = amZoomScale < 0.65 ? 'none' : 'block';
  });
}

function amZoomIn() {
  amZoomScale = Math.min(amZoomScale * 1.25, 3.0);
  amApplyTransform();
}

function amZoomOut() {
  amZoomScale = Math.max(amZoomScale / 1.25, 0.4);
  amApplyTransform();
}

function amZoomReset() {
  amZoomScale = 1.0;
  amPanX = 0;
  amPanY = 0;
  amApplyTransform();
}

function layoutGraph(nodes, edges) {
  const W = 900, H = 620, ITER = 200;
  const positions = {};
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1);
    positions[n.id] = { x: W / 2 + 260 * Math.cos(angle), y: H / 2 + 220 * Math.sin(angle) };
  });
  for (let iter = 0; iter < ITER; iter++) {
    nodes.forEach(a => {
      let fx = 0, fy = 0;
      nodes.forEach(b => {
        if (a.id === b.id) return;
        const dx = positions[a.id].x - positions[b.id].x;
        const dy = positions[a.id].y - positions[b.id].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const repel = 4000 / (dist * dist);
        fx += (dx / dist) * repel;
        fy += (dy / dist) * repel;
      });
      edges.forEach(e => {
        if (e.from !== a.id && e.to !== a.id) return;
        const otherId = e.from === a.id ? e.to : e.from;
        if (!positions[otherId]) return;
        const dx = positions[otherId].x - positions[a.id].x;
        const dy = positions[otherId].y - positions[a.id].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const attract = dist * 0.01;
        fx += (dx / dist) * attract;
        fy += (dy / dist) * attract;
      });
      positions[a.id].x = Math.min(W - 70, Math.max(70, positions[a.id].x + fx));
      positions[a.id].y = Math.min(H - 40, Math.max(40, positions[a.id].y + fy));
    });
  }
  return positions;
}

function renderGraph() {
  const svg = document.getElementById('am-svg');
  if (!svg) return;
  const nodes = window.ARCHITECT_NODES || [];
  const edges = window.ARCHITECT_EDGES || [];
  const edgeTypes = window.ARCHITECT_EDGE_TYPES || {};
  const isMultiRepo = nodes.length > 1;
  const pos = layoutGraph(nodes, edges);
  let markup = '<g id="am-canvas-viewport" transform="translate(' + amPanX + ',' + amPanY + ') scale(' + amZoomScale + ')">';

  edges.forEach(e => {
    const a = pos[e.from], b = pos[e.to];
    if (!a || !b) return;
    const color = (edgeTypes[e.type] || {}).color || '#0d9e87';
    const edgeLabel = (edgeTypes[e.type] || {}).label || e.type || 'api-bridge';
    if (isMultiRepo) {
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      markup += '<g class="am-bridge-group">' +
        '<line class="am-edge am-bridge-edge" x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y + '" stroke="' + color + '" stroke-width="2.5" stroke-dasharray="6,4"></line>' +
        '<rect x="' + (mx - 40) + '" y="' + (my - 10) + '" width="80" height="20" rx="4" fill="#ffffff" stroke="' + color + '" stroke-width="1"></rect>' +
        '<text class="am-bridge-label" x="' + mx + '" y="' + (my + 4) + '" text-anchor="middle" font-size="10" fill="' + color + '" font-weight="600">' + edgeLabel + '</text>' +
        '</g>';
    } else {
      markup += '<line class="am-edge" x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y + '" stroke="' + color + '"></line>';
    }
  });

  nodes.forEach(n => {
    const p = pos[n.id];
    if (!p) return;
    const label = String(n.label || n.id || '');
    if (isMultiRepo) {
      const w = 220, h = 120;
      const stack = (n.stack_labels || []).join(', ');
      markup += '<g class="am-cluster am-cluster-repo am-repo-box" data-repo="' + n.id + '" transform="translate(' + (p.x - w / 2) + ',' + (p.y - h / 2) + ')" onclick="openDrawer(\\'' + n.id + '\\')">' +
        '<rect class="am-cluster-bg" width="' + w + '" height="' + h + '" rx="10"></rect>' +
        '<rect class="am-cluster-header" width="' + w + '" height="32" rx="10"></rect>' +
        '<rect y="22" width="' + w + '" height="10" class="am-cluster-header"></rect>' +
        '<text class="am-cluster-title" x="12" y="21">📦 ' + label + '</text>' +
        '<text class="am-cluster-detail" x="12" y="55">Stack: ' + (stack || 'general') + '</text>' +
        '<text class="am-cluster-detail" x="12" y="75">Active stories: ' + (n.active_dream_count || 0) + '</text>' +
        '<g class="am-node" transform="translate(12, 86)">' +
        '<rect width="' + (w - 24) + '" height="24" rx="4" fill="#ffffff" stroke="#94a3b8" stroke-width="1"></rect>' +
        '<text x="' + ((w - 24) / 2) + '" y="16" text-anchor="middle" font-size="10" fill="#334155">Inspect Repo →</text>' +
        '</g>' +
        '</g>';
    } else {
      const w = Math.max(90, label.length * 7 + 20);
      markup += '<g class="am-node" transform="translate(' + (p.x - w / 2) + ',' + (p.y - 18) + ')" onclick="openDrawer(\\'' + n.id + '\\')">' +
        '<rect width="' + w + '" height="36" rx="8"></rect>' +
        '<text x="' + (w / 2) + '" y="22" text-anchor="middle">' + label + '</text>' +
        '</g>';
    }
  });

  markup += '</g>';
  svg.innerHTML = markup;
  amApplyTransform();
}

function setArchitectView(view) {
  document.querySelectorAll('.am-tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
  const kv = document.getElementById('am-knowledge-view');
  if (kv) kv.classList.toggle('active', view === 'knowledge');
  const gv = document.getElementById('am-graph-view');
  if (gv) gv.classList.toggle('active', view === 'graph');
  const tv = document.getElementById('am-tree-view');
  if (tv) tv.classList.toggle('active', view === 'tree');
  if (view === 'tree' && !window._treeRendered) {
    renderTree();
    window._treeRendered = true;
  }
  fetch('/architect-map/view-pref', {
    method: 'POST',
    headers: window.vizorAuthHeaders ? window.vizorAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
    body: JSON.stringify({ view: view }),
  }).catch(() => {});
}

let currentDrawerNode = null;

function openDrawer(nodeId) {
  const node = (window.ARCHITECT_NODES || []).find(n => n.id === nodeId);
  if (!node) return;
  currentDrawerNode = node;
  document.getElementById('am-drawer-title').textContent = node.label;
  const stack = (node.stack_labels || []).join(', ') || 'unlabeled';
  document.getElementById('am-drawer-body').innerHTML =
    '<div>Path: <code>' + node.path + '</code></div>' +
    '<div>Stack: ' + stack + '</div>' +
    '<div>Active dreams: ' + (node.active_dream_count || 0) + '</div>';
  const githubLink = document.getElementById('am-drawer-github');
  if (node.github_url) {
    githubLink.href = node.github_url;
    githubLink.style.display = 'block';
  } else {
    githubLink.style.display = 'none';
  }
  document.getElementById('am-drawer').classList.add('open');
  document.getElementById('am-ov').classList.add('open');
}

function closeDrawer() {
  document.getElementById('am-drawer').classList.remove('open');
  document.getElementById('am-ov').classList.remove('open');
  currentDrawerNode = null;
}

async function drawerDispatch() {
  if (!currentDrawerNode) return;
  const task = prompt('Task to dispatch in ' + currentDrawerNode.label + ':');
  if (!task) return;
  await fetch('/dispatch', {
    method: 'POST',
    headers: window.vizorAuthHeaders ? window.vizorAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_path: currentDrawerNode.path, task: task }),
  });
  closeDrawer();
}

function drawerJumpGantt() {
  if (!currentDrawerNode) return;
  window.top.postMessage({ type: 'vizor-navigate', view: 'gantt', repo: currentDrawerNode.id }, '*');
}

function renderTreeNode(node) {
  let html = '';
  const dirNames = Object.keys(node.dirs || {}).sort();
  dirNames.forEach(name => {
    html += '<details class="am-tree-dir" open><summary>📁 ' + name + '</summary>' + renderTreeNode(node.dirs[name]) + '</details>';
  });
  (node.files || []).slice().sort((a, b) => a.name.localeCompare(b.name)).forEach(f => {
    html += '<div class="am-tree-file">📄 ' + f.name + ' <span style="color:#94a3b8">(' + f.symbol_count + ')</span></div>';
  });
  return html;
}

function renderTree() {
  const root = document.getElementById('am-tree-root');
  if (!root) return;
  const tree = window.ARCHITECT_FILE_TREE || { dirs: {}, files: [] };
  root.innerHTML = renderTreeNode(tree) || '<div class="am-tree-file">No scan data yet — run <code>synlynk scan --deep</code>.</div>';
}

function filterKgSearch(query) {
  const q = (query || '').toLowerCase().trim();
  const frame = document.getElementById('am-graphify-frame');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'search', query: q }, '*');
    } catch (_) {}
  }
}

function toggleAmKgDropdown(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('am-kg-dropdown-menu');
  if (menu) menu.classList.toggle('open');
}

document.addEventListener('click', function(e) {
  if (!e.target.closest('.am-dropdown')) {
    const menus = document.querySelectorAll('.am-dropdown-menu');
    menus.forEach(m => m.classList.remove('open'));
  }
});

function filterAmKgCommunities(query) {
  const q = (query || '').toLowerCase().trim();
  const items = document.querySelectorAll('.am-community-item');
  items.forEach(item => {
    const text = item.textContent.toLowerCase();
    item.style.display = !q || text.includes(q) ? 'flex' : 'none';
  });
}

function selectAllAmCommunities(enable) {
  const checkboxes = document.querySelectorAll('.am-community-checkbox');
  checkboxes.forEach(cb => {
    cb.checked = enable;
  });
  updateAmKgSelectedCount();
  const frame = document.getElementById('am-graphify-frame');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'filter-communities-batch', allEnabled: enable }, '*');
    } catch (_) {}
  }
}

function toggleAmCommunityFilter(cb) {
  const comm = cb.dataset.comm;
  const isChecked = cb.checked;
  updateAmKgSelectedCount();
  const frame = document.getElementById('am-graphify-frame');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'filter-community', community: comm, enabled: isChecked }, '*');
    } catch (_) {}
  }
}

function updateAmKgSelectedCount() {
  const checkboxes = document.querySelectorAll('.am-community-checkbox');
  const checked = document.querySelectorAll('.am-community-checkbox:checked');
  const countEl = document.getElementById('am-kg-selected-count');
  if (countEl) {
    if (checked.length === checkboxes.length) {
      countEl.textContent = 'All (' + checkboxes.length + ')';
    } else {
      countEl.textContent = checked.length + ' / ' + checkboxes.length;
    }
  }
}

function applyTheme(theme) {
  if (!theme) return;
  const resolved = theme === 'system'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : theme;
  document.documentElement.setAttribute('data-theme', resolved);
  const frame = document.querySelector('iframe');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'theme-change', theme: resolved }, '*');
    } catch (_) {}
  }
}

window.addEventListener('message', function(e) {
  if (!e.data) return;
  if (e.data.type === 'theme-change' || e.data.theme) {
    applyTheme(e.data.theme || e.data);
  } else if (e.data.type === 'lod-status-update') {
    const chip = document.getElementById('am-kg-status-chip') || document.querySelector('.am-kg-chip');
    if (chip && e.data.visibleCount !== undefined) {
      chip.textContent = e.data.visibleCount + ' of ' + e.data.totalCount + ' Clusters Visible (Level ' + e.data.level + ': ≥' + e.data.minDegree + ' conns)';
    }
  }
});

try {
  const savedTheme = localStorage.getItem('vizor-theme');
  if (savedTheme) applyTheme(savedTheme);
} catch (_) {}

const svgEl = document.getElementById('am-svg');
if (svgEl) {
  let isDragging = false;
  let startX = 0, startY = 0;
  svgEl.addEventListener('wheel', function(e) {
    e.preventDefault();
    if (e.deltaY < 0) {
      amZoomScale = Math.min(amZoomScale * 1.1, 3.0);
    } else {
      amZoomScale = Math.max(amZoomScale / 1.1, 0.4);
    }
    amApplyTransform();
  }, { passive: false });
  svgEl.addEventListener('mousedown', function(e) {
    if (e.target.closest('.am-node') || e.target.closest('.am-cluster')) return;
    isDragging = true;
    startX = e.clientX - amPanX;
    startY = e.clientY - amPanY;
  });
  window.addEventListener('mousemove', function(e) {
    if (!isDragging) return;
    amPanX = e.clientX - startX;
    amPanY = e.clientY - startY;
    amApplyTransform();
  });
  window.addEventListener('mouseup', function() {
    isDragging = false;
  });
}

function triggerAmKgRefresh(btn) {
  if (!btn) btn = document.getElementById('am-kg-refresh-btn');
  const chip = document.getElementById('am-kg-status-chip') || document.querySelector('.am-kg-chip');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '🔄 Refreshing...';
  }
  if (chip) chip.textContent = '⏳ Extracting AST Knowledge Graph...';

  const pathParts = window.location.pathname.split('/');
  let refreshUrl = '/api/graph/refresh';
  if (pathParts[1] === 'w' && pathParts[2]) {
    refreshUrl = '/w/' + encodeURIComponent(pathParts[2]) + '/api/graph/refresh';
  }

  fetch(refreshUrl, {
    method: 'POST',
    headers: window.vizorAuthHeaders ? window.vizorAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  })
  .then(res => {
    if (!res.ok) throw new Error('Refresh failed with status ' + res.status);
    return res.json();
  })
  .then(data => {
    if (btn) {
      btn.textContent = '✓ Refreshed';
      setTimeout(() => { btn.textContent = '🔄 Refresh Graph'; btn.disabled = false; }, 2000);
    }
    if (chip) chip.textContent = '✓ Graph Refreshed';
    const iframe = document.getElementById('am-graphify-frame') || document.querySelector('iframe');
    if (iframe) {
      iframe.src = iframe.src;
    }
  })
  .catch(err => {
    console.error(err);
    if (btn) {
      btn.textContent = '✗ Failed';
      setTimeout(() => { btn.textContent = '🔄 Refresh Graph'; btn.disabled = false; }, 2500);
    }
    if (chip) chip.textContent = '✗ Extraction Failed';
  });
}

function triggerGraphRefresh(el) {
  if (el) el.textContent = '[Refreshing...]';
  const pathParts = window.location.pathname.split('/');
  let refreshUrl = '/api/graph/refresh';
  if (pathParts[1] === 'w' && pathParts[2]) {
    refreshUrl = '/w/' + encodeURIComponent(pathParts[2]) + '/api/graph/refresh';
  }
  fetch(refreshUrl, {
    method: 'POST',
    headers: window.vizorAuthHeaders ? window.vizorAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  })
  .then(res => {
    if (!res.ok) throw new Error('Refresh failed with status ' + res.status);
    return res.json();
  })
  .then(data => {
    if (el) el.textContent = '[Refreshed ✓]';
    setTimeout(() => { location.reload(); }, 600);
  })
  .catch(err => {
    if (el) el.textContent = '[Refresh Failed ✗]';
    console.error(err);
  });
}

function openKgSourceDrawer(filePath, startLine, endLine) {
  if (!filePath) return;
  const drawer = document.getElementById('kg-source-drawer');
  const ov = document.getElementById('kg-source-ov');
  const title = document.getElementById('kg-source-title');
  const badge = document.getElementById('kg-source-badge');
  const code = document.getElementById('kg-source-code');
  if (!drawer || !code) return;

  title.textContent = filePath;
  badge.textContent = startLine && endLine ? 'L' + startLine + '-' + endLine : '';
  code.textContent = 'Loading source code...';
  drawer.classList.add('open');
  if (ov) ov.classList.add('open');

  let url = '/api/source?file=' + encodeURIComponent(filePath);
  if (startLine) url += '&start=' + startLine;
  if (endLine) url += '&end=' + endLine;

  fetch(url)
    .then(r => r.json())
    .then(res => {
      if (res.status === 'ok') {
        code.textContent = res.content || '[Empty content]';
      } else {
        code.textContent = 'Error: ' + (res.error || 'Failed to load source');
      }
    })
    .catch(err => {
      code.textContent = 'Failed to fetch source: ' + err.message;
    });
}

function closeKgSourceDrawer() {
  const drawer = document.getElementById('kg-source-drawer');
  const ov = document.getElementById('kg-source-ov');
  if (drawer) drawer.classList.remove('open');
  if (ov) ov.classList.remove('open');
}

function toggleAmKindFilter(el) {
  const frame = document.getElementById('am-graphify-frame');
  if (!frame || !frame.contentWindow) return;
  const container = document.getElementById('am-kg-kind-filters');
  if (!container) return;
  const checked = Array.from(container.querySelectorAll('input:checked')).map(cb => cb.value);
  frame.contentWindow.postMessage({ type: 'filter-kind-l0', kinds: checked }, '*');
}

function resetInspectMode() {
  const frame = document.getElementById('am-graphify-frame');
  if (frame && frame.contentWindow) {
    frame.contentWindow.postMessage({ type: 'reset-inspect' }, '*');
  }
}

window.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeKgSourceDrawer();
    closeDrawer();
    resetInspectMode();
  }
});

window.addEventListener('message', function(e) {
  if (!e.data || typeof e.data !== 'object') return;
  if (e.data.type === 'open-source-drawer') {
    openKgSourceDrawer(e.data.file, e.data.start_line, e.data.end_line);
  }
});

renderGraph();
"""

_ARCHITECT_MAP_STYLE = """
body { margin:0; font-family:'SF Mono',monospace; background:#f6f8fa; color:#1f2328; }
.am-header { display:flex; justify-content:space-between; align-items:center; padding:14px 20px; border-bottom:1px solid #d1d5db; }
.am-header h1 { font-size:15px; margin:0; }
.am-switcher { display:flex; gap:6px; }
.am-tab { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; font-family:inherit; }
.am-tab.active { background:#0d9e87; color:#fff; border-color:#0d9e87; }
.am-legend { display:flex; gap:14px; padding:8px 20px; font-size:11px; }
.legend-item { display:flex; align-items:center; gap:5px; }
.legend-dot { width:9px; height:9px; border-radius:50%; display:inline-block; }
.am-view { display:none; padding:10px 20px; }
.am-view.active { display:block; }
.am-node { cursor:pointer; }
.am-node rect { fill:#fff; stroke:#334155; stroke-width:1.5; }
.am-node text { font-size:11px; font-family:inherit; }
.am-edge { stroke-width:2; fill:none; }
.ov { display:none; position:fixed; inset:0; background:rgba(0,0,0,.35); z-index:999; }
.ov.open { display:block; }
.am-drawer { position:fixed; top:0; right:-360px; width:340px; height:100%; background:#fff; box-shadow:-2px 0 12px rgba(0,0,0,.15); z-index:1000; transition:right .2s ease; padding:16px; box-sizing:border-box; }
.am-drawer.open { right:0; }
.am-drawer-header { display:flex; justify-content:space-between; align-items:center; font-size:13px; font-weight:bold; margin-bottom:12px; }
.am-drawer-header button { background:none; border:none; cursor:pointer; font-size:14px; }
.am-drawer-body { font-size:12px; line-height:1.6; margin-bottom:16px; }
.am-drawer-actions { display:flex; flex-direction:column; gap:8px; }
.btn { background:#0d9e87; color:#fff; border:none; border-radius:5px; padding:7px 10px; font-size:12px; cursor:pointer; text-align:center; text-decoration:none; font-family:inherit; }
.am-tree { font-size:12px; }
.am-tree-dir > summary { cursor:pointer; padding:2px 0; }
.am-tree-file { padding:2px 0 2px 18px; color:#475569; }
.am-stale-banner { background:#fffbeb; border:1px solid #f59e0b; color:#b45309; padding:8px 16px; margin:8px 20px; border-radius:6px; font-size:12px; font-weight:500; display:flex; align-items:center; gap:8px; }
.am-zoom-controls { position:absolute; top:20px; right:30px; display:flex; gap:6px; z-index:10; }
.am-zoom-btn { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:6px 10px; font-size:12px; cursor:pointer; font-family:inherit; box-shadow:0 1px 3px rgba(0,0,0,0.1); }
.am-zoom-btn:hover { background:#f3f4f6; }
.am-cluster-repo { cursor:pointer; }
.am-cluster-bg { fill:#f8fafc; stroke:#64748b; stroke-width:1.5; }
.am-cluster-header { fill:#e2e8f0; }
.am-cluster-title { font-size:12px; font-weight:bold; fill:#0f172a; }
.am-cluster-detail { font-size:11px; fill:#475569; }
.am-bridge-edge { stroke-dasharray:6,4; }
.am-bridge-label { font-size:10px; font-weight:600; }
.am-kg-topbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; flex-wrap:wrap; }
.am-kg-controls { display:flex; align-items:center; gap:10px; flex:1; }
.am-dropdown { position:relative; display:inline-block; }
.am-dropdown-btn { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:6px 12px; font-size:12px; font-family:inherit; cursor:pointer; display:flex; align-items:center; gap:6px; box-shadow:0 1px 2px rgba(0,0,0,0.05); }
.am-dropdown-btn:hover { background:#f3f4f6; }
.am-dropdown-menu { display:none; position:absolute; top:100%; left:0; margin-top:4px; width:340px; max-height:400px; background:#fff; border:1px solid #d1d5db; border-radius:8px; box-shadow:0 10px 25px rgba(0,0,0,0.15); z-index:100; flex-direction:column; box-sizing:border-box; }
.am-dropdown-menu.open { display:flex; }
.am-dropdown-header { padding:8px 10px; border-bottom:1px solid #e5e7eb; }
.am-dropdown-header input { width:100%; box-sizing:border-box; padding:5px 8px; font-size:12px; border:1px solid #d1d5db; border-radius:4px; outline:none; font-family:inherit; }
.am-dropdown-actions { display:flex; justify-content:space-between; padding:6px 10px; border-bottom:1px solid #e5e7eb; font-size:11px; }
.am-dropdown-actions a { color:#0d9e87; text-decoration:none; cursor:pointer; font-weight:500; }
.am-dropdown-actions a:hover { text-decoration:underline; }
.am-dropdown-list { overflow-y:auto; padding:6px 10px; max-height:280px; }
.am-community-item { user-select:none; }
.am-search-input { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:6px 10px; font-size:12px; font-family:inherit; width:220px; outline:none; box-shadow:0 1px 2px rgba(0,0,0,0.05); }
.am-search-input:focus { border-color:#0d9e87; }
.am-kg-chip { font-size:11px; color:#64748b; background:#f1f5f9; padding:4px 8px; border-radius:6px; border:1px solid #e2e8f0; white-space:nowrap; }
.am-kg-canvas-full { width:100%; height:720px; border:1px solid #d1d5db; border-radius:8px; overflow:hidden; position:relative; background:#fff; }

[data-theme="dark"] body { background:#0d0f14; color:#c9d1d9; }
[data-theme="dark"] .am-header { border-bottom-color:#1e2430; }
[data-theme="dark"] .am-tab { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-tab.active { background:#0d9e87; color:#fff; border-color:#0d9e87; }
[data-theme="dark"] .am-drawer { background:#0a0c10; color:#c9d1d9; box-shadow:-2px 0 20px rgba(0,0,0,.5); }
[data-theme="dark"] .am-node rect { fill:#13171f; stroke:#38bdf8; }
[data-theme="dark"] .am-node text { fill:#c9d1d9; }
[data-theme="dark"] .am-tree-file { color:#8b949e; }
[data-theme="dark"] .am-stale-banner { background:#451a03; border-color:#78350f; color:#fbbf24; }
[data-theme="dark"] .am-zoom-btn { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-zoom-btn:hover { background:#1e2430; }
[data-theme="dark"] .am-cluster-bg { fill:#13171f; stroke:#334155; }
[data-theme="dark"] .am-cluster-header { fill:#1e2430; }
[data-theme="dark"] .am-cluster-title { fill:#38bdf8; }
[data-theme="dark"] .am-cluster-detail { fill:#8b949e; }
.am-btn-action { background:#fff; border:1px solid #d1d5db; border-radius:6px; padding:6px 12px; font-size:12px; font-family:inherit; cursor:pointer; display:inline-flex; align-items:center; gap:6px; box-shadow:0 1px 2px rgba(0,0,0,0.05); transition:all .15s ease; color:#1e293b; }
.am-btn-action:hover { background:#f1f5f9; border-color:#94a3b8; }
.am-btn-action:disabled { opacity:0.6; cursor:not-allowed; }
.kg-source-drawer { position:fixed; top:0; right:-520px; width:500px; height:100%; background:#fff; box-shadow:-4px 0 20px rgba(0,0,0,.2); z-index:1100; transition:right .25s ease-in-out; display:flex; flex-direction:column; box-sizing:border-box; }
.kg-source-drawer.open { right:0; }
.kg-source-header { padding:12px 16px; border-bottom:1px solid #e2e8f0; display:flex; justify-content:space-between; align-items:center; background:#f8fafc; font-weight:600; font-size:13px; }
.kg-source-title { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:380px; }
.kg-source-badge { font-size:10px; background:#e2e8f0; color:#475569; padding:2px 6px; border-radius:4px; margin-left:6px; font-weight:normal; }
.kg-source-close { background:none; border:none; font-size:16px; cursor:pointer; color:#64748b; }
.kg-source-close:hover { color:#0f172a; }
.kg-source-body { flex:1; overflow:auto; padding:12px 16px; font-family:'SF Mono',monospace; font-size:12px; line-height:1.5; background:#ffffff; }
.kg-source-pre { margin:0; tab-size:4; white-space:pre; }
.am-kg-kind-filters { display:flex; align-items:center; gap:6px; }
.am-kind-chip { display:inline-flex; align-items:center; gap:4px; font-size:11px; padding:3px 8px; border-radius:12px; border:1px solid #d1d5db; background:#fff; cursor:pointer; user-select:none; }
.am-kind-chip:hover { background:#f1f5f9; }
.am-kind-chip input { margin:0; cursor:pointer; }
[data-theme="dark"] .kg-source-drawer { background:#0d1117; border-left:1px solid #30363d; color:#c9d1d9; box-shadow:-4px 0 20px rgba(0,0,0,.6); }
[data-theme="dark"] .kg-source-header { background:#161b22; border-bottom-color:#30363d; color:#c9d1d9; }
[data-theme="dark"] .kg-source-badge { background:#30363d; color:#8b949e; }
[data-theme="dark"] .kg-source-body { background:#0d1117; color:#c9d1d9; }
[data-theme="dark"] .am-kind-chip { background:#161b22; border-color:#30363d; color:#c9d1d9; }
[data-theme="dark"] .am-kind-chip:hover { background:#21262d; }
[data-theme="dark"] .am-dropdown-btn { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-dropdown-btn:hover { background:#1e2430; }
[data-theme="dark"] .am-dropdown-menu { background:#0a0c10; border-color:#1e2430; color:#c9d1d9; box-shadow:0 10px 25px rgba(0,0,0,0.5); }
[data-theme="dark"] .am-dropdown-header { border-bottom-color:#1e2430; }
[data-theme="dark"] .am-dropdown-header input { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-dropdown-actions { border-bottom-color:#1e2430; }
[data-theme="dark"] .am-search-input { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-kg-chip { background:#13171f; border-color:#1e2430; color:#8b949e; }
[data-theme="dark"] .am-btn-action { background:#13171f; border-color:#1e2430; color:#c9d1d9; }
[data-theme="dark"] .am-btn-action:hover { background:#1e2430; border-color:#334155; }
[data-theme="dark"] .am-kg-canvas-full { border-color:#1e2430; background:#0d0f14; }
"""


def generate_architect_map_html(data: dict, port: int) -> str:
    """Generate the Architect Map view shell."""
    import json
    from synlynk.viz_views import derive_canonical_community_names

    workspace = data.get("workspace", {})
    workspace_name = str(workspace.get("name") or "workspace")
    updated_at = workspace.get("updated_at", "")
    repos = workspace.get("repos") or []
    workspace_map = data.get("workspace_map") or {"edges": [], "edge_types": {}}
    edges = workspace_map.get("edges", [])
    edge_types = workspace_map.get("edge_types", {})

    if not repos:
        repos = [{"path": os.getcwd(), "name": workspace_name, "stack_labels": [], "github_url": None}]

    nodes_json = json.dumps([
        {
            "id": r["name"],
            "label": r["name"],
            "path": r.get("path", ""),
            "stack_labels": r.get("stack_labels", []),
            "github_url": r.get("github_url"),
            "active_dream_count": r.get("active_dream_count", 0),
        }
        for r in repos
    ])
    edges_json = json.dumps(edges)
    edge_types_json = json.dumps(edge_types)
    file_tree_json = json.dumps(data.get("file_tree") or {"name": ".", "dirs": {}, "files": []})

    legend_html = "".join(
        f'<div class="legend-item"><span class="legend-dot" style="background:{html.escape(et.get("color", "#94a3b8"))}"></span>{html.escape(et.get("label", key))}</div>'
        for key, et in edge_types.items()
    )

    style_content = _ARCHITECT_MAP_STYLE
    json_data = json.dumps(data)
    live_js_html = _live_js(port)

    is_monorepo = len(repos) <= 1

    is_stale = bool(data.get("discovery", {}).get("knowledge_graph", {}).get("stale"))
    if not is_stale:
        is_stale = bool((data.get("workspace_views") or {}).get("logical", {}).get("stale"))

    staleness_banner_html = ""
    if is_stale:
        staleness_banner_html = (
            '<div class="am-stale-banner" id="graph-stale-banner">'
            '<span>⚠️ Graph Stale (differs from HEAD commit) — '
            '<a href="#" onclick="triggerGraphRefresh(this); return false;" style="color:#b45309;text-decoration:underline;">[Refresh Index]</a></span>'
            '</div>'
        )

    if is_monorepo:
        logical_nodes = (data.get("workspace_views") or {}).get("logical", {}).get("nodes") or []
        comm_names = derive_canonical_community_names(logical_nodes)

        communities: Dict[Any, int] = {}
        for n in logical_nodes:
            comm = n.get("community")
            if comm is None:
                try:
                    attrs = json.loads(n.get("attrs_json") or "{}")
                    comm = attrs.get("community")
                except Exception:
                    pass
            if comm is not None:
                communities[comm] = communities.get(comm, 0) + 1

        community_colors = [
            "#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899",
            "#06b6d4", "#6366f1", "#14b8a6", "#f97316", "#84cc16"
        ]
        if communities:
            sorted_comms = sorted(communities.items(), key=lambda x: x[1], reverse=True)
            communities_html = "".join(
                f'<label class="am-community-item" style="display:flex; align-items:center; gap:8px; padding:4px 0; font-size:12px; cursor:pointer;">'
                f'<input type="checkbox" class="am-community-checkbox" checked data-comm="{html.escape(str(cid))}" onchange="toggleAmCommunityFilter(this)">'
                f'<span class="legend-dot" style="background:{community_colors[i % len(community_colors)]}; width:10px; height:10px; border-radius:50%; display:inline-block; flex-shrink:0;"></span>'
                f'<span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="{html.escape(comm_names.get(cid, f"Community {cid}"))}">{html.escape(comm_names.get(cid, f"Community {cid}"))} ({count})</span>'
                f'</label>'
                for i, (cid, count) in enumerate(sorted_comms)
            )
        else:
            communities_html = '<div style="font-size:11px; color:#64748b;">No Community clusters detected. Run <code>synlynk scan --deep</code>.</div>'

        switcher_html = """    <button class="am-tab active" data-view="knowledge" onclick="setArchitectView('knowledge')">Knowledge Graph</button>
    <button class="am-tab" data-view="tree" onclick="setArchitectView('tree')">File Tree</button>"""

        total_symbols = len(logical_nodes)
        num_clusters = len(communities)
        views_html = f"""{staleness_banner_html}
<div id="am-knowledge-view" class="am-view active">
  <div class="am-kg-topbar">
    <div class="am-kg-controls">
      <div class="am-dropdown">
        <button type="button" class="am-dropdown-btn" onclick="toggleAmKgDropdown(event)">
          <span>🌐 Communities: <strong id="am-kg-selected-count">All ({num_clusters})</strong></span>
          <span style="font-size:9px; color:#64748b;">▼</span>
        </button>
        <div class="am-dropdown-menu" id="am-kg-dropdown-menu">
          <div class="am-dropdown-header">
            <input type="text" placeholder="Filter communities..." oninput="filterAmKgCommunities(this.value)">
          </div>
          <div class="am-dropdown-actions">
            <a onclick="selectAllAmCommunities(true)">Select All</a>
            <a onclick="selectAllAmCommunities(false)">Deselect All</a>
          </div>
          <div class="am-dropdown-list" id="am-communities-list">
            {communities_html}
          </div>
        </div>
      </div>
      <input type="text" id="am-kg-search" class="am-search-input" placeholder="🔍 Search symbols..." oninput="filterKgSearch(this.value)">
      <div class="am-kg-kind-filters" id="am-kg-kind-filters">
        <label class="am-kind-chip"><input type="checkbox" checked value="Service Class" onchange="toggleAmKindFilter(this)"> Services</label>
        <label class="am-kind-chip"><input type="checkbox" checked value="Module Cluster" onchange="toggleAmKindFilter(this)"> Modules</label>
        <label class="am-kind-chip"><input type="checkbox" checked value="CLI Handler" onchange="toggleAmKindFilter(this)"> Handlers</label>
        <label class="am-kind-chip"><input type="checkbox" checked value="Test Suite" onchange="toggleAmKindFilter(this)"> Tests</label>
      </div>
      <span class="am-kg-chip" id="am-kg-status-chip">{num_clusters} Clusters · {total_symbols} AST Symbols</span>
      <button type="button" id="am-kg-refresh-btn" class="am-btn-action" onclick="triggerAmKgRefresh(this)" title="Re-extract AST Knowledge Graph">🔄 Refresh Graph</button>
    </div>
  </div>
  <div class="am-kg-canvas-full">
    <iframe id="am-graphify-frame" src="graphify.html" width="100%" height="100%" style="border:none;" title="Graphify Knowledge Graph"></iframe>
  </div>
</div>
<div id="am-tree-view" class="am-view">
  <div id="am-tree-root" class="am-tree"></div>
</div>"""
    else:
        switcher_html = """    <button class="am-tab active" data-view="graph" onclick="setArchitectView('graph')">Clustered Canvas</button>
    <button class="am-tab" data-view="tree" onclick="setArchitectView('tree')">File Tree</button>"""

        views_html = f"""{staleness_banner_html}
<div class="am-legend">{legend_html}</div>
<div id="am-graph-view" class="am-view active" style="position:relative;">
  <div class="am-zoom-controls">
    <button type="button" class="am-zoom-btn" onclick="amZoomIn()" title="Zoom In">➕</button>
    <button type="button" class="am-zoom-btn" onclick="amZoomOut()" title="Zoom Out">➖</button>
    <button type="button" class="am-zoom-btn" onclick="amZoomReset()" title="Reset LOD Zoom">⊙ Reset</button>
  </div>
  <svg id="am-svg" width="100%" height="680" style="background:#fff; border-radius:8px; border:1px solid #d1d5db;"></svg>
</div>
<div id="am-tree-view" class="am-view">
  <div id="am-tree-root" class="am-tree"></div>
</div>"""

    template = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Architect Map</title>
<style>
__STYLE_CONTENT__
</style>
</head>
<body>
<div class="am-header">
  <h1>Architect Map — __WORKSPACE_NAME__</h1>
  <div class="am-switcher">
__SWITCHER_HTML__
  </div>
</div>
__VIEWS_HTML__
<div class="ov" id="am-ov" onclick="closeDrawer()"></div>
<div class="am-drawer" id="am-drawer">
  <div class="am-drawer-header">
    <span id="am-drawer-title">—</span>
    <button onclick="closeDrawer()">✕</button>
  </div>
  <div class="am-drawer-body" id="am-drawer-body"></div>
  <div class="am-drawer-actions">
    <button class="btn" onclick="drawerDispatch()">Dispatch to this repo</button>
    <button class="btn" onclick="drawerJumpGantt()">Jump to Gantt view</button>
    <a class="btn" id="am-drawer-github" href="#" target="_blank" rel="noopener">Open on GitHub</a>
  </div>
</div>
<div class="ov" id="kg-source-ov" onclick="closeKgSourceDrawer()"></div>
<div class="kg-source-drawer" id="kg-source-drawer">
  <div class="kg-source-header">
    <div class="kg-source-title"><span id="kg-source-title">—</span><span class="kg-source-badge" id="kg-source-badge"></span></div>
    <button class="kg-source-close" onclick="closeKgSourceDrawer()">✕</button>
  </div>
  <div class="kg-source-body">
    <pre class="kg-source-pre"><code id="kg-source-code">Loading...</code></pre>
  </div>
</div>
<script>
window.VIZOR_DATA = __JSON_DATA__;
window.ARCHITECT_NODES = __NODES_JSON__;
window.ARCHITECT_EDGES = __EDGES_JSON__;
window.ARCHITECT_EDGE_TYPES = __EDGE_TYPES_JSON__;
window.ARCHITECT_FILE_TREE = __FILE_TREE_JSON__;
window.VIZOR_PORT = __PORT__;
__ARCHITECT_MAP_JS__
</script>
__LIVE_JS_HTML__
</body>
</html>"""
    return (
        template
        .replace("__STYLE_CONTENT__", style_content)
        .replace("__WORKSPACE_NAME__", html.escape(workspace_name))
        .replace("__SWITCHER_HTML__", switcher_html)
        .replace("__VIEWS_HTML__", views_html)
        .replace("__JSON_DATA__", json_data)
        .replace("__NODES_JSON__", nodes_json)
        .replace("__EDGES_JSON__", edges_json)
        .replace("__EDGE_TYPES_JSON__", edge_types_json)
        .replace("__FILE_TREE_JSON__", file_tree_json)
        .replace("__PORT__", str(port))
        .replace("__ARCHITECT_MAP_JS__", _ARCHITECT_MAP_JS)
        .replace("__LIVE_JS_HTML__", live_js_html)
    )


_BS6_VIEW_JS = """
function bs6LayoutGraph(nodes, edges) {
  const W = 900, H = 620, ITER = 200;
  const positions = {};
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1);
    positions[n.id] = { x: W / 2 + 260 * Math.cos(angle), y: H / 2 + 220 * Math.sin(angle) };
  });
  for (let iter = 0; iter < ITER; iter++) {
    nodes.forEach(a => {
      let fx = 0, fy = 0;
      nodes.forEach(b => {
        if (a.id === b.id) return;
        const dx = positions[a.id].x - positions[b.id].x;
        const dy = positions[a.id].y - positions[b.id].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const repel = 4000 / (dist * dist);
        fx += (dx / dist) * repel;
        fy += (dy / dist) * repel;
      });
      edges.forEach(e => {
        if (e.from_id !== a.id && e.to_id !== a.id) return;
        const otherId = e.from_id === a.id ? e.to_id : e.from_id;
        if (!positions[otherId]) return;
        const dx = positions[otherId].x - positions[a.id].x;
        const dy = positions[otherId].y - positions[a.id].y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const attract = dist * 0.01;
        fx += (dx / dist) * attract;
        fy += (dy / dist) * attract;
      });
      positions[a.id].x = Math.min(W - 70, Math.max(70, positions[a.id].x + fx));
      positions[a.id].y = Math.min(H - 40, Math.max(40, positions[a.id].y + fy));
    });
  }
  return positions;
}

function bs6RenderGraph() {
  const svg = document.getElementById('bs6-svg');
  if (!svg) return;
  const nodes = window.BS6_NODES || [];
  const edges = window.BS6_EDGES || [];
  const pos = bs6LayoutGraph(nodes, edges);
  let markup = '';
  edges.forEach(e => {
    const a = pos[e.from_id], b = pos[e.to_id];
    if (!a || !b) return;
    markup += '<line class="am-edge" x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y + '" stroke="#94a3b8"></line>';
  });
  nodes.forEach(n => {
    const p = pos[n.id];
    if (!p) return;
    const label = String(n.label || n.id || '');
    const w = Math.max(90, label.length * 7 + 20);
    let strokeColor = '#334155';
    let community = n.community;
    if (community === undefined && n.attrs_json) {
      try { community = JSON.parse(n.attrs_json).community; } catch (e) {}
    }
    const communityColors = ['#0d9e87', '#3b82f6', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#10b981'];
    if (community !== undefined && community !== null) {
      let idx = Number(community);
      if (!Number.isFinite(idx)) {
        let hash = 0;
        const str = String(community);
        for (let i = 0; i < str.length; i++) {
          hash = (hash * 31 + str.charCodeAt(i)) | 0;
        }
        idx = Math.abs(hash);
      } else {
        idx = Math.abs(Math.floor(idx));
      }
      strokeColor = communityColors[idx % communityColors.length];
    }
    markup += '<g class="am-node" transform="translate(' + (p.x - w / 2) + ',' + (p.y - 18) + ')" onclick="bs6OpenDrawer(\\'' + n.id + '\\')">' +
      '<rect width="' + w + '" height="36" rx="8" stroke="' + strokeColor + '" stroke-width="1.8"></rect>' +
      '<text x="' + (w / 2) + '" y="22" text-anchor="middle">' + label + '</text>' +
      '</g>';
  });
  svg.innerHTML = markup;
}

function bs6OpenDrawer(nodeId) {
  const node = (window.BS6_NODES || []).find(n => n.id === nodeId);
  if (!node) return;
  document.getElementById('am-drawer-title').textContent = node.label;
  let attrs = {};
  try { attrs = JSON.parse(node.attrs_json || '{}'); } catch (e) {}
  const attrLines = Object.keys(attrs).map(k => '<div>' + k + ': <code>' + attrs[k] + '</code></div>').join('');
  document.getElementById('am-drawer-body').innerHTML =
    '<div>Kind: ' + (node.kind || '') + '</div>' +
    '<div>Source: <code>' + (node.source_path || '') + '</code></div>' +
    '<div>Provenance: ' + (node.provenance || '') + '</div>' +
    attrLines;
  document.getElementById('am-drawer').classList.add('open');
  document.getElementById('am-ov').classList.add('open');
}

function bs6CloseDrawer() {
  document.getElementById('am-drawer').classList.remove('open');
  document.getElementById('am-ov').classList.remove('open');
}

function setLogicalView(view) {
  document.querySelectorAll('.am-tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
  const iv = document.getElementById('bs6-interactive-view');
  if (iv) iv.classList.toggle('active', view === 'vis');
  const gv = document.getElementById('bs6-graph-view');
  if (gv) gv.classList.toggle('active', view === 'svg');
}

function toggleAmKgDropdown(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('bs6-kg-dropdown-menu');
  if (menu) menu.classList.toggle('open');
}

document.addEventListener('click', function(e) {
  if (!e.target.closest('.am-dropdown')) {
    const menus = document.querySelectorAll('.am-dropdown-menu');
    menus.forEach(m => m.classList.remove('open'));
  }
});

function filterAmKgCommunities(query) {
  const q = (query || '').toLowerCase().trim();
  const items = document.querySelectorAll('.am-community-item');
  items.forEach(item => {
    const text = item.textContent.toLowerCase();
    item.style.display = !q || text.includes(q) ? 'flex' : 'none';
  });
}

function selectAllAmCommunities(enable) {
  const checkboxes = document.querySelectorAll('.am-community-checkbox');
  checkboxes.forEach(cb => {
    cb.checked = enable;
  });
  updateAmKgSelectedCount();
  const frame = document.getElementById('bs6-graphify-frame');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'filter-communities-batch', allEnabled: enable }, '*');
    } catch (_) {}
  }
}

function toggleAmCommunityFilter(cb) {
  const comm = cb.dataset.comm;
  const isChecked = cb.checked;
  updateAmKgSelectedCount();
  const frame = document.getElementById('bs6-graphify-frame');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'filter-community', community: comm, enabled: isChecked }, '*');
    } catch (_) {}
  }
}

function updateAmKgSelectedCount() {
  const checkboxes = document.querySelectorAll('.am-community-checkbox');
  const checked = document.querySelectorAll('.am-community-checkbox:checked');
  const countEl = document.getElementById('bs6-kg-selected-count');
  if (countEl) {
    if (checked.length === checkboxes.length) {
      countEl.textContent = 'All (' + checkboxes.length + ')';
    } else {
      countEl.textContent = checked.length + ' / ' + checkboxes.length;
    }
  }
}

function bs6ToggleCommFilter(cb) {
  toggleAmCommunityFilter(cb);
}

function bs6FilterSearch(query) {
  const q = (query || '').toLowerCase().trim();
  const frame = document.getElementById('bs6-graphify-frame');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'search', query: q }, '*');
    } catch (_) {}
  }
  const nodes = document.querySelectorAll('#bs6-svg .am-node');
  nodes.forEach(n => {
    const text = (n.textContent || '').toLowerCase();
    n.style.opacity = !q || text.includes(q) ? '1' : '0.2';
  });
}

function applyTheme(theme) {
  if (!theme) return;
  const resolved = theme === 'system'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : theme;
  document.documentElement.setAttribute('data-theme', resolved);
  const frame = document.querySelector('iframe');
  if (frame && frame.contentWindow) {
    try {
      frame.contentWindow.postMessage({ type: 'theme-change', theme: resolved }, '*');
    } catch (_) {}
  }
}

window.addEventListener('message', function(e) {
  if (!e.data) return;
  if (e.data.type === 'theme-change' || e.data.theme) {
    applyTheme(e.data.theme || e.data);
  } else if (e.data.type === 'lod-status-update') {
    const chip = document.getElementById('bs6-kg-status-chip') || document.querySelector('.am-kg-chip');
    if (chip && e.data.visibleCount !== undefined) {
      chip.textContent = e.data.visibleCount + ' of ' + e.data.totalCount + ' Clusters Visible (Level ' + e.data.level + ': ≥' + e.data.minDegree + ' conns)';
    }
  }
});

function triggerBs6KgRefresh(btn) {
  if (!btn) btn = document.getElementById('bs6-kg-refresh-btn');
  const chip = document.getElementById('bs6-kg-status-chip') || document.querySelector('.am-kg-chip');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '🔄 Refreshing...';
  }
  if (chip) chip.textContent = '⏳ Extracting AST Knowledge Graph...';

  const pathParts = window.location.pathname.split('/');
  let refreshUrl = '/api/graph/refresh';
  if (pathParts[1] === 'w' && pathParts[2]) {
    refreshUrl = '/w/' + encodeURIComponent(pathParts[2]) + '/api/graph/refresh';
  }

  fetch(refreshUrl, {
    method: 'POST',
    headers: window.vizorAuthHeaders ? window.vizorAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  })
  .then(res => {
    if (!res.ok) throw new Error('Refresh failed with status ' + res.status);
    return res.json();
  })
  .then(data => {
    if (btn) {
      btn.textContent = '✓ Refreshed';
      setTimeout(() => { btn.textContent = '🔄 Refresh Graph'; btn.disabled = false; }, 2000);
    }
    if (chip) chip.textContent = '✓ Graph Refreshed';
    const iframe = document.getElementById('bs6-graphify-frame') || document.querySelector('iframe');
    if (iframe) {
      iframe.src = iframe.src;
    }
  })
  .catch(err => {
    console.error(err);
    if (btn) {
      btn.textContent = '✗ Failed';
      setTimeout(() => { btn.textContent = '🔄 Refresh Graph'; btn.disabled = false; }, 2500);
    }
    if (chip) chip.textContent = '✗ Extraction Failed';
  });
}

function triggerGraphRefresh(el) {
  if (el) el.textContent = '[Refreshing...]';
  const pathParts = window.location.pathname.split('/');
  let refreshUrl = '/api/graph/refresh';
  if (pathParts[1] === 'w' && pathParts[2]) {
    refreshUrl = '/w/' + encodeURIComponent(pathParts[2]) + '/api/graph/refresh';
  }
  fetch(refreshUrl, {
    method: 'POST',
    headers: window.vizorAuthHeaders ? window.vizorAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  })
  .then(res => {
    if (!res.ok) throw new Error('Refresh failed with status ' + res.status);
    return res.json();
  })
  .then(data => {
    if (el) el.textContent = '[Refreshed ✓]';
    setTimeout(() => { location.reload(); }, 600);
  })
  .catch(err => {
    if (el) el.textContent = '[Refresh Failed ✗]';
    console.error(err);
  });
}

function openKgSourceDrawer(filePath, startLine, endLine) {
  if (!filePath) return;
  const drawer = document.getElementById('kg-source-drawer');
  const ov = document.getElementById('kg-source-ov');
  const title = document.getElementById('kg-source-title');
  const badge = document.getElementById('kg-source-badge');
  const code = document.getElementById('kg-source-code');
  if (!drawer || !code) return;

  title.textContent = filePath;
  badge.textContent = startLine && endLine ? 'L' + startLine + '-' + endLine : '';
  code.textContent = 'Loading source code...';
  drawer.classList.add('open');
  if (ov) ov.classList.add('open');

  let url = '/api/source?file=' + encodeURIComponent(filePath);
  if (startLine) url += '&start=' + startLine;
  if (endLine) url += '&end=' + endLine;

  fetch(url)
    .then(r => r.json())
    .then(res => {
      if (res.status === 'ok') {
        code.textContent = res.content || '[Empty content]';
      } else {
        code.textContent = 'Error: ' + (res.error || 'Failed to load source');
      }
    })
    .catch(err => {
      code.textContent = 'Failed to fetch source: ' + err.message;
    });
}

function closeKgSourceDrawer() {
  const drawer = document.getElementById('kg-source-drawer');
  const ov = document.getElementById('kg-source-ov');
  if (drawer) drawer.classList.remove('open');
  if (ov) ov.classList.remove('open');
}

function toggleAmKindFilter(el) {
  const frame = document.getElementById('bs6-graphify-frame') || document.getElementById('am-graphify-frame') || document.querySelector('iframe');
  if (!frame || !frame.contentWindow) return;
  const container = document.getElementById('bs6-kg-kind-filters') || document.getElementById('am-kg-kind-filters') || document.querySelector('.am-kg-kind-filters');
  if (!container) return;
  const checked = Array.from(container.querySelectorAll('input:checked')).map(cb => cb.value);
  frame.contentWindow.postMessage({ type: 'filter-kind-l0', kinds: checked }, '*');
}

function resetInspectMode() {
  const frame = document.getElementById('bs6-graphify-frame') || document.getElementById('am-graphify-frame') || document.querySelector('iframe');
  if (frame && frame.contentWindow) {
    frame.contentWindow.postMessage({ type: 'reset-inspect' }, '*');
  }
}

window.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeKgSourceDrawer();
    if (typeof closeDrawer === 'function') closeDrawer();
    if (typeof bs6CloseDrawer === 'function') bs6CloseDrawer();
    resetInspectMode();
  }
});

window.addEventListener('message', function(e) {
  if (!e.data || typeof e.data !== 'object') return;
  if (e.data.type === 'open-source-drawer') {
    openKgSourceDrawer(e.data.file, e.data.start_line, e.data.end_line);
  }
});

try {
  const savedTheme = localStorage.getItem('vizor-theme');
  if (savedTheme) applyTheme(savedTheme);
} catch (_) {}

bs6RenderGraph();
"""


def _generate_bs6_view_html(data: dict, port: int, view_key: str, view_title: str) -> str:
    """Shared self-contained node/edge SVG view renderer for the BS-6 Product/Logical/Infra views."""
    from synlynk.viz_views import derive_canonical_community_names

    workspace = data.get("workspace", {})
    workspace_name = str(workspace.get("name") or "workspace")
    workspace_views = data.get("workspace_views") or {}
    view_data = workspace_views.get(view_key) or {"nodes": [], "edges": []}
    nodes = view_data.get("nodes") or []
    edges = view_data.get("edges") or []

    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)
    live_js_html = _live_js(port)

    kind_counts: Dict[str, int] = {}
    for n in nodes:
        kind = str(n.get("kind") or "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    legend_html = "".join(
        f'<div class="legend-item"><span class="legend-dot"></span>{html.escape(kind.title())} ({count})</div>'
        for kind, count in sorted(kind_counts.items())
    )

    is_stale = bool(view_data.get("stale"))
    if not is_stale and view_key == "logical":
        is_stale = bool(data.get("discovery", {}).get("knowledge_graph", {}).get("stale"))
        if not is_stale:
            for n in nodes:
                try:
                    attrs = json.loads(n.get("attrs_json") or "{}")
                    if attrs.get("stale"):
                        is_stale = True
                        break
                except Exception:
                    pass

    staleness_banner_html = ""
    if is_stale:
        staleness_banner_html = (
            '<div class="am-stale-banner" id="graph-stale-banner">'
            '<span>⚠️ Graph Stale (differs from HEAD commit) — '
            '<a href="#" onclick="triggerGraphRefresh(this); return false;" style="color:#b45309;text-decoration:underline;">[Refresh]</a></span>'
            '</div>'
        )

    switcher_html = ""
    if view_key == "logical":
        switcher_html = """  <div class="am-switcher">
    <button class="am-tab active" data-view="vis" onclick="setLogicalView('vis')">Interactive Canvas</button>
    <button class="am-tab" data-view="svg" onclick="setLogicalView('svg')">AST Projection</button>
  </div>"""

        comm_names = derive_canonical_community_names(nodes)
        communities: Dict[Any, int] = {}
        for n in nodes:
            comm = n.get("community")
            if comm is None:
                try:
                    attrs = json.loads(n.get("attrs_json") or "{}")
                    comm = attrs.get("community")
                except Exception:
                    pass
            if comm is not None:
                communities[comm] = communities.get(comm, 0) + 1

        community_colors = [
            "#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899",
            "#06b6d4", "#6366f1", "#14b8a6", "#f97316", "#84cc16"
        ]
        if communities:
            sorted_comms = sorted(communities.items(), key=lambda x: x[1], reverse=True)
            comm_items = "".join(
                f'<label class="am-community-item" style="display:flex; align-items:center; gap:8px; padding:4px 0; font-size:12px; cursor:pointer;">'
                f'<input type="checkbox" class="am-community-checkbox" checked data-comm="{html.escape(str(cid))}" onchange="toggleAmCommunityFilter(this)">'
                f'<span class="legend-dot" style="background:{community_colors[i % len(community_colors)]}; width:10px; height:10px; border-radius:50%; display:inline-block; flex-shrink:0;"></span>'
                f'<span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="{html.escape(comm_names.get(cid, f"Community {cid}"))}">{html.escape(comm_names.get(cid, f"Community {cid}"))} ({count})</span>'
                f'</label>'
                for i, (cid, count) in enumerate(sorted_comms)
            )
        else:
            comm_items = '<div style="font-size:11px; color:#64748b;">No Community clusters detected. Run <code>synlynk scan --deep</code>.</div>'

        num_clusters = len(communities)
        total_symbols = len(nodes)
        main_views_html = f"""
<div id="bs6-interactive-view" class="am-view active">
  <div class="am-kg-topbar">
    <div class="am-kg-controls">
      <div class="am-dropdown">
        <button type="button" class="am-dropdown-btn" onclick="toggleAmKgDropdown(event)">
          <span>🌐 Communities: <strong id="bs6-kg-selected-count">All ({num_clusters})</strong></span>
          <span style="font-size:9px; color:#64748b;">▼</span>
        </button>
        <div class="am-dropdown-menu" id="bs6-kg-dropdown-menu">
          <div class="am-dropdown-header">
            <input type="text" placeholder="Filter communities..." oninput="filterAmKgCommunities(this.value)">
          </div>
          <div class="am-dropdown-actions">
            <a onclick="selectAllAmCommunities(true)">Select All</a>
            <a onclick="selectAllAmCommunities(false)">Deselect All</a>
          </div>
          <div class="am-dropdown-list" id="bs6-communities-list">
            {comm_items}
          </div>
        </div>
      </div>
      <input type="text" id="bs6-search" class="am-search-input" placeholder="🔍 Search symbols..." oninput="bs6FilterSearch(this.value)">
      <div class="am-kg-kind-filters" id="bs6-kg-kind-filters">
        <label class="am-kind-chip"><input type="checkbox" checked value="Service Class" onchange="toggleAmKindFilter(this)"> Services</label>
        <label class="am-kind-chip"><input type="checkbox" checked value="Module Cluster" onchange="toggleAmKindFilter(this)"> Modules</label>
        <label class="am-kind-chip"><input type="checkbox" checked value="CLI Handler" onchange="toggleAmKindFilter(this)"> Handlers</label>
        <label class="am-kind-chip"><input type="checkbox" checked value="Test Suite" onchange="toggleAmKindFilter(this)"> Tests</label>
      </div>
      <span class="am-kg-chip" id="bs6-kg-status-chip">{num_clusters} Clusters · {total_symbols} AST Symbols</span>
      <button type="button" id="bs6-kg-refresh-btn" class="am-btn-action" onclick="triggerBs6KgRefresh(this)" title="Re-extract AST Knowledge Graph">🔄 Refresh Graph</button>
    </div>
  </div>
  <div class="am-kg-canvas-full">
    <iframe id="bs6-graphify-frame" src="graphify.html" width="100%" height="100%" style="border:none;" title="Graphify Knowledge Graph"></iframe>
  </div>
</div>
<div id="bs6-graph-view" class="am-view">
  <div class="am-legend">{legend_html}</div>
  <svg id="bs6-svg" width="100%" height="640"></svg>
</div>
"""
    else:
        main_views_html = f"""
<div class="am-legend">{legend_html}</div>
<div id="bs6-graph-view" class="am-view active">
  <svg id="bs6-svg" width="100%" height="640"></svg>
</div>
"""

    template = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — __VIEW_TITLE__</title>
<style>
__STYLE_CONTENT__
</style>
</head>
<body>
<div class="am-header">
  <h1>__VIEW_TITLE__ — __WORKSPACE_NAME__</h1>
__SWITCHER_HTML__
</div>
__STALENESS_BANNER__
__MAIN_VIEWS__
<div class="ov" id="am-ov" onclick="bs6CloseDrawer()"></div>
<div class="am-drawer" id="am-drawer">
  <div class="am-drawer-header">
    <span id="am-drawer-title">—</span>
    <button onclick="bs6CloseDrawer()">✕</button>
  </div>
  <div class="am-drawer-body" id="am-drawer-body"></div>
</div>
<div class="ov" id="kg-source-ov" onclick="closeKgSourceDrawer()"></div>
<div class="kg-source-drawer" id="kg-source-drawer">
  <div class="kg-source-header">
    <div class="kg-source-title"><span id="kg-source-title">—</span><span class="kg-source-badge" id="kg-source-badge"></span></div>
    <button class="kg-source-close" onclick="closeKgSourceDrawer()">✕</button>
  </div>
  <div class="kg-source-body">
    <pre class="kg-source-pre"><code id="kg-source-code">Loading...</code></pre>
  </div>
</div>
<script>
window.BS6_NODES = __NODES_JSON__;
window.BS6_EDGES = __EDGES_JSON__;
window.VIZOR_PORT = __PORT__;
__BS6_VIEW_JS__
</script>
__LIVE_JS_HTML__
</body>
</html>"""
    return (
        template
        .replace("__STYLE_CONTENT__", _ARCHITECT_MAP_STYLE)
        .replace("__VIEW_TITLE__", html.escape(view_title))
        .replace("__WORKSPACE_NAME__", html.escape(workspace_name))
        .replace("__SWITCHER_HTML__", switcher_html)
        .replace("__STALENESS_BANNER__", staleness_banner_html)
        .replace("__MAIN_VIEWS__", main_views_html)
        .replace("__NODES_JSON__", nodes_json)
        .replace("__EDGES_JSON__", edges_json)
        .replace("__PORT__", str(port))
        .replace("__BS6_VIEW_JS__", _BS6_VIEW_JS)
        .replace("__LIVE_JS_HTML__", live_js_html)
    )


def generate_product_html(data: dict, port: int) -> str:
    return _generate_bs6_view_html(data, port, "product", "Product View")


def generate_logical_html(data: dict, port: int) -> str:
    return _generate_bs6_view_html(data, port, "logical", "Logical View")


def generate_infra_html(data: dict, port: int) -> str:
    return _generate_bs6_view_html(data, port, "infra", "Infra View")


def generate_world_html(data: dict, port: int) -> str:
    return _generate_bs6_view_html(data, port, "world", "World View (Ecosystem Radar)")



def generate_journeys_html(data: dict, port: int) -> str:
    data_json = json.dumps(data)
    live_js_block = _live_js(port)
    html_template = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — User Journeys</title>
<style>
/* ══════════════════════════════════════════════
   THEME TOKENS
   ══════════════════════════════════════════════ */
:root {
  --bg:        #f6f8fa;  --bg2: #ffffff; --bg3: #eaeef2;
  --border:    #d1d5db;  --border2: #e8ebee;
  --text:      #1f2328;  --text2: #57606a; --text3: #8b949e;
  --accent:    #0d9e87;  --accent-bg: #e6f7f4; --accent-dim: #c0ede6;
  --shadow:    0 2px 12px rgba(0,0,0,.10);

  /* Stage colors: design/blue, plan/purple, build/teal, ship/green, sustain/amber */
  --s-design-bg:  #dbeafe; --s-design-bd:  #93c5fd; --s-design-tx:  #1d4ed8;
  --s-plan-bg:    #ede9fe; --s-plan-bd:    #c4b5fd; --s-plan-tx:    #6d28d9;
  --s-build-bg:   #e6f7f4; --s-build-bd:   #c0ede6; --s-build-tx:   #0d9e87;
  --s-ship-bg:    #dcfce7; --s-ship-bd:    #86efac; --s-ship-tx:    #15803d;
  --s-sustain-bg: #fef3c7; --s-sustain-bd: #fde68a; --s-sustain-tx: #d97706;

  --ag-claude-bg:#e6f7f4;--ag-claude-bd:#0d9e87;--ag-claude-tx:#0d9e87;
  --ag-agy-bg:  #e8f0fe;--ag-agy-bd:  #4285f4;--ag-agy-tx:  #1a56c7;
  --ag-codex-bg:#e6f4f0;--ag-codex-bd:#10a37f;--ag-codex-tx:#0b7a60;
  --ag-grok-bg: #f0f0f0;--ag-grok-bd: #666;   --ag-grok-tx: #333;
  --ag-muse-bg: #fdf2f8;--ag-muse-bd: #db2777;--ag-muse-tx: #9d174d;
}
[data-theme="dark"] {
  --bg:#0d0f14; --bg2:#0a0c10; --bg3:#13171f;
  --border:#1e2430; --border2:#13171f;
  --text:#c9d1d9; --text2:#8b949e; --text3:#4a5568;
  --accent:#3de0c0; --accent-bg:#0d2137; --accent-dim:#0a3050;
  --shadow: 0 2px 20px rgba(0,0,0,.5);

  --s-design-bg:  #1e3a5a; --s-design-bd:  #3a6090; --s-design-tx:  #60a5fa;
  --s-plan-bg:    #2d1f5e; --s-plan-bd:    #4a3f80; --s-plan-tx:    #a78bfa;
  --s-build-bg:   #0d2a2a; --s-build-bd:   #1f4d45; --s-build-tx:   #3de0c0;
  --s-ship-bg:    #1a4a2e; --s-ship-bd:    #2a7040; --s-ship-tx:    #4ade80;
  --s-sustain-bg: #451a03; --s-sustain-bd: #78350f; --s-sustain-tx: #fbbf24;

  --ag-claude-bg:#0d2a2a;--ag-claude-bd:#3de0c0;--ag-claude-tx:#3de0c0;
  --ag-agy-bg:  #0d1a3a;--ag-agy-bd:  #4285f4;--ag-agy-tx:  #4285f4;
  --ag-codex-bg:#0a1f18;--ag-codex-bd:#10a37f;--ag-codex-tx:#10a37f;
  --ag-grok-bg: #1a1a1a;--ag-grok-bd: #e0e0e0;--ag-grok-tx: #e0e0e0;
  --ag-muse-bg: #2e081d;--ag-muse-bd: #f472b6;--ag-muse-tx: #f472b6;
}

* { box-sizing:border-box; margin:0; padding:0; }
body {
  font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background:var(--bg);
  color:var(--text);
  font-size:13px;
  transition:background .2s,color .2s;
  overflow:hidden;
}

/* Split Pane Layout */
.split-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}
.left-panel {
  width: 280px;
  min-width: 200px;
  max-width: 500px;
  background: var(--bg2);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}
.resizer {
  width: 5px;
  background: transparent;
  cursor: col-resize;
  position: relative;
  z-index: 10;
  flex-shrink: 0;
  transition: background 0.15s;
}
.resizer:hover, .resizer.dragging {
  background: var(--accent);
}
.right-panel {
  flex: 1;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Left Panel Header & Rows */
.panel-header {
  padding: 16px;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
  font-weight: 750;
  color: var(--text);
  background: var(--bg2);
}
.journey-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.journey-row {
  padding: 12px 16px;
  cursor: pointer;
  color: var(--text2);
  font-weight: 500;
  border-bottom: 1px solid var(--border2);
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.journey-row:hover {
  background: var(--bg3);
  color: var(--text);
}
.journey-row.active {
  background: var(--accent-bg);
  color: var(--accent);
  border-left: 3px solid var(--accent);
  padding-left: 13px;
}
.journey-steps-count {
  font-size: 10px;
  background: var(--bg3);
  color: var(--text3);
  padding: 2px 6px;
  border-radius: 8px;
  font-family: 'SF Mono', 'JetBrains Mono', monospace;
}
.journey-row.active .journey-steps-count {
  background: var(--accent-dim);
  color: var(--accent);
}

/* FTUE Notice Banner */
.ftue-notice {
  background: var(--accent-bg);
  border-bottom: 1px solid var(--accent-dim);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  z-index: 5;
  animation: slideDown 0.3s ease;
}
@keyframes slideDown {
  from { transform: translateY(-100%); }
  to { transform: translateY(0); }
}
.notice-text {
  color: var(--accent);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
}
.close-notice-btn {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  opacity: 0.7;
  transition: opacity 0.15s;
}
.close-notice-btn:hover {
  opacity: 1;
}

/* Right Panel Content Header & Flow */
.right-header {
  padding: 16px 24px;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  min-height: 53px;
  display: flex;
  align-items: center;
}
.right-header-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
.flow-viewport {
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 40px 24px;
  display: flex;
  align-items: center;
  background: var(--bg);
}
.flow-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* Cards & Arrows */
.step-card {
  width: 200px;
  min-height: 120px;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: var(--shadow);
  transition: transform 0.2s, box-shadow 0.2s;
  flex-shrink: 0;
}
.step-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 16px rgba(0,0,0,.12);
}
[data-theme="dark"] .step-card:hover {
  box-shadow: 0 4px 20px rgba(0,0,0,.4);
}
.step-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.3;
}
.step-route {
  font-family: 'SF Mono', 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--text3);
  background: var(--bg3);
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.step-desc {
  font-size: 11px;
  color: var(--text2);
  line-height: 1.4;
  flex: 1;
  word-break: break-word;
}
.step-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
  flex-shrink: 0;
}

/* Stage Badge Pill Styles */
.stage-pill {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 12px;
  border: 1px solid;
  letter-spacing: 0.5px;
}
.st-design { background: var(--s-design-bg); border-color: var(--s-design-bd); color: var(--s-design-tx); }
.st-plan { background: var(--s-plan-bg); border-color: var(--s-plan-bd); color: var(--s-plan-tx); }
.st-build { background: var(--s-build-bg); border-color: var(--s-build-bd); color: var(--s-build-tx); }
.st-ship { background: var(--s-ship-bg); border-color: var(--s-ship-bd); color: var(--s-ship-tx); }
.st-sustain { background: var(--s-sustain-bg); border-color: var(--s-sustain-bd); color: var(--s-sustain-tx); }
.st-unknown { background: var(--bg3); border-color: var(--border); color: var(--text3); }

/* Agent Avatar Badges */
.aa {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 800;
  flex-shrink: 0;
  border: 1.5px solid;
  cursor: default;
}
.aa-claude { background: var(--ag-claude-bg); border-color: var(--ag-claude-bd); color: var(--ag-claude-tx); }
.aa-agy    { background: var(--ag-agy-bg);    border-color: var(--ag-agy-bd);    color: var(--ag-agy-tx);    }
.aa-codex  { background: var(--ag-codex-bg);  border-color: var(--ag-codex-bd);  color: var(--ag-codex-tx);  font-size: 8px; }
.aa-grok   { background: var(--ag-grok-bg);   border-color: var(--ag-grok-bd);   color: var(--ag-grok-tx);   }
.aa-muse   { background: var(--ag-muse-bg);   border-color: var(--ag-muse-bd);   color: var(--ag-muse-tx);   }
.aa-unknown { background: var(--bg3); border-color: var(--border); color: var(--text3); }

.flow-arrow {
  font-size: 20px;
  color: var(--text3);
  user-select: none;
  font-weight: bold;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
}

/* Empty State Styles */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 40px;
  text-align: center;
  color: var(--text2);
  background: var(--bg);
}
.empty-state-icon {
  font-size: 40px;
  margin-bottom: 16px;
  opacity: 0.6;
}
.empty-state-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--text);
}
.empty-state-desc {
  font-size: 12px;
  max-width: 480px;
  line-height: 1.6;
  color: var(--text3);
  background: var(--bg2);
  border: 1px solid var(--border);
  padding: 16px;
  border-radius: 8px;
  font-family: 'SF Mono', 'JetBrains Mono', monospace;
  text-align: left;
}
</style>
</head>
<body>

<header style="height:44px;padding:0 20px;display:flex;align-items:center;gap:20px;background:var(--bg2);border-bottom:1px solid var(--border);flex-shrink:0;font-size:13px;font-family:inherit">
  <span style="font-weight:700;color:var(--text)">🗺 User Journeys</span>
  <span style="color:var(--text3)">Screen-by-screen flows from docs/journeys/</span>
</header>
<div id="app-container" style="height: calc(100vh - 44px); width: 100vw; display: flex; flex-direction: column;"></div>

<script>
window.VIZOR_DATA = {{data_json}};
</script>
<script>
function setTheme(t) {
  const resolved = t === 'system' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : t;
  document.documentElement.setAttribute('data-theme', resolved);
}
setTheme(localStorage.getItem('vizor-theme') || 'system');
window.addEventListener('storage', (e) => {
  if (e.key === 'vizor-theme') {
    setTheme(e.newValue);
  }
});

let selectedJourneyId = null;

function getAgentDetails(name) {
  const n = (name || '').trim().toLowerCase();
  if (n.startsWith('claude')) return { cls: 'aa-claude', lbl: 'C' };
  if (n.startsWith('agy')) return { cls: 'aa-agy', lbl: 'A' };
  if (n.startsWith('codex')) return { cls: 'aa-codex', lbl: 'Cx' };
  if (n.startsWith('grok')) return { cls: 'aa-grok', lbl: 'G' };
  if (!n) return null;
  return { cls: 'aa-unknown', lbl: n.charAt(0).toUpperCase() };
}

function getStageClass(stage) {
  const s = (stage || '').trim().toLowerCase();
  if (s === 'design') return 'st-design';
  if (s === 'plan') return 'st-plan';
  if (s === 'build') return 'st-build';
  if (s === 'ship') return 'st-ship';
  if (s === 'sustain') return 'st-sustain';
  return 'st-unknown';
}

function dismissNotice() {
  const notice = document.getElementById('ftue-notice');
  if (notice) {
    notice.style.display = 'none';
  }
}

function selectJourney(id) {
  selectedJourneyId = id;
  
  // Highlight row
  document.querySelectorAll('.journey-row').forEach(row => {
    if (row.getAttribute('data-id') === id) {
      row.classList.add('active');
    } else {
      row.classList.remove('active');
    }
  });

  const journey = window.VIZOR_DATA.journeys.find(j => j.id === id);
  if (!journey) return;

  // Render header
  const header = document.getElementById('right-header-title');
  if (header) {
    header.textContent = journey.name;
  }

  // Render flow
  const viewport = document.getElementById('flow-viewport');
  if (!viewport) return;

  if (!journey.steps || journey.steps.length === 0) {
    viewport.innerHTML = '<div class="empty-state"><div class="empty-state-title">No steps defined for this journey</div></div>';
    return;
  }

  let html = '<div class="flow-row">';
  journey.steps.forEach((step, idx) => {
    const stageCls = getStageClass(step.stage);
    const stageLabel = step.stage || 'unknown';
    const agent = getAgentDetails(step.agent);
    
    let agentHtml = '';
    if (agent) {
      agentHtml = `<div class="aa ${agent.cls}" title="Agent: ${step.agent}">${agent.lbl}</div>`;
    }

    html += `
      <div class="step-card">
        <div class="step-name">${step.screen || 'Screen'}</div>
        <div class="step-route" title="${step.route || ''}">${step.route || '/'}</div>
        <div class="step-desc">${step.desc || ''}</div>
        <div class="step-footer">
          <div class="stage-pill ${stageCls}">${stageLabel}</div>
          ${agentHtml}
        </div>
      </div>
    `;

    if (idx < journey.steps.length - 1) {
      html += '<div class="flow-arrow">→</div>';
    }
  });
  html += '</div>';
  viewport.innerHTML = html;
}

function initApp() {
  const container = document.getElementById('app-container');
  const data = window.VIZOR_DATA;

  if (!data || !data.journeys || data.journeys.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🗺️</div>
        <div class="empty-state-title">User Journeys</div>
        <div class="empty-state-desc">No journeys found. Create docs/journeys/ with .md files, each starting with a # H1 title. Steps use ## Screen Name headings with route:, desc:, agent:, stage: key-value lines.</div>
      </div>
    `;
    return;
  }

  let leftRowsHtml = '';
  data.journeys.forEach(j => {
    const stepCount = j.steps ? j.steps.length : 0;
    leftRowsHtml += `
      <div class="journey-row" data-id="${j.id}" onclick="selectJourney('${j.id}')">
        <span>${j.name}</span>
        <span class="journey-steps-count">${stepCount} step${stepCount !== 1 ? 's' : ''}</span>
      </div>
    `;
  });

  const showFTUE = data.workspace && data.workspace.vizor_second_view === 'tube';
  const noticeStyle = showFTUE ? 'display: flex;' : 'display: none;';

  container.innerHTML = `
    <div class="split-container">
      <div class="left-panel" id="left-panel">
        <div class="panel-header">User Journeys</div>
        <div class="journey-list">${leftRowsHtml}</div>
      </div>
      <div class="resizer" id="resizer"></div>
      <div class="right-panel" id="right-panel">
        <div class="ftue-notice" id="ftue-notice" style="${noticeStyle}">
          <span class="notice-text">Your workspace is configured for the Architect Map as the primary structural view. User Journeys is available if your project has UX screens.</span>
          <button class="close-notice-btn" onclick="dismissNotice()">✕</button>
        </div>
        <div class="right-header">
          <div class="right-header-title" id="right-header-title">Select a Journey</div>
        </div>
        <div class="flow-viewport" id="flow-viewport"></div>
      </div>
    </div>
  `;

  const resizer = document.getElementById('resizer');
  const leftPanel = document.getElementById('left-panel');
  let isDragging = false;

  resizer.addEventListener('mousedown', (e) => {
    isDragging = true;
    resizer.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const newWidth = e.clientX;
    if (newWidth >= 200 && newWidth <= 500) {
      leftPanel.style.width = `${newWidth}px`;
    }
  });

  document.addEventListener('mouseup', () => {
    if (isDragging) {
      isDragging = false;
      resizer.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
  });

  if (data.journeys.length > 0) {
    selectJourney(data.journeys[0].id);
  }
}

initApp();
</script>
{_live_js(port)}
</body>
</html>"""
    return html_template.replace("{{data_json}}", data_json).replace("{_live_js(port)}", live_js_block)


def _viz_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _fmt_usd(value) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


def _fmt_pct(value: float) -> str:
    try:
        return f"{float(value):.0f}%"
    except Exception:
        return "0%"


def _svg_text(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _stage_color(key: str) -> str:
    stage = (key or "").strip().lower()
    return {
        "goal": "#7b8cff",
        "open": "#60a5fa",
        "visualize": "#f39c6b",
        "execute": "#1a9e5c",
        "release": "#0d9e87",
        "notify": "#fbbf24",
        "sustain": "#888888",
    }.get(stage, "#0d9e87")


def generate_effort_html(data: dict, port: int) -> str:
    costs = data.get("costs") or {}
    dreams = list(data.get("dreams") or [])
    by_agent = dict(costs.get("by_agent") or {})
    by_stage = dict(costs.get("by_stage") or {})
    total_usd = float(costs.get("total_usd") or 0.0)
    total_usd_estimated = float(costs.get("total_usd_estimated") or 0.0)

    def _bucket_total(bucket) -> float:
        if isinstance(bucket, dict):
            return float(bucket.get("actual", 0.0)) + float(bucket.get("estimated", 0.0))
        return float(bucket or 0.0)

    def _bucket_estimated(bucket) -> float:
        if isinstance(bucket, dict):
            return float(bucket.get("estimated", 0.0))
        return 0.0

    data_json = _viz_json(data)

    if total_usd == 0:
        return f"""<!doctype html>
<html lang="en" data-theme="system">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Effort & Cost</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f7fb;
      --bg-accent: linear-gradient(180deg, #ffffff 0%, #eef3fb 100%);
      --panel: rgba(255,255,255,0.92);
      --panel-border: rgba(15, 23, 42, 0.10);
      --text: #142033;
      --muted: #64748b;
      --shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
      --card: #ffffff;
      --card-border: rgba(15, 23, 42, 0.08);
      --teal: #0d9e87;
      --blue: #3b7dd8;
      --green: #1a9e5c;
      --gray: #888888;
      --red: #e05;
      --stage-design: #f39c6b;
      --stage-plan: #7b8cff;
      --stage-build: #1a9e5c;
      --stage-ship: #0d9e87;
      --stage-sustain: #888888;
    }}
    [data-theme="dark"] {{
      color-scheme: dark;
      --bg: #0b1220;
      --bg-accent: linear-gradient(180deg, #111a2e 0%, #0b1220 100%);
      --panel: rgba(15, 23, 42, 0.92);
      --panel-border: rgba(148, 163, 184, 0.18);
      --text: #e5edf8;
      --muted: #94a3b8;
      --shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
      --card: rgba(15, 23, 42, 0.92);
      --card-border: rgba(148, 163, 184, 0.16);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--bg-accent);
    }}
    .shell {{ display: grid; place-items: center; min-height: 100vh; padding: 32px; }}
    .empty {{
      width: min(860px, 100%);
      border: 1px solid var(--panel-border);
      border-radius: 24px;
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 36px;
    }}
    h1 {{ margin: 0 0 12px; font-size: 30px; letter-spacing: -0.03em; }}
    p {{ margin: 0; color: var(--muted); font-size: 16px; line-height: 1.6; }}
  </style>
</head>
<body>
  <script>window.VIZOR_DATA = {data_json}; function checkManifest() {{ return window.VIZOR_DATA; }}</script>
  <header style="height:44px;padding:0 20px;display:flex;align-items:center;gap:20px;background:#fff;border-bottom:1px solid rgba(15,23,42,.10);flex-shrink:0;font-size:13px;font-family:inherit">
    <span style="font-weight:700;color:#142033">💰 Effort & Cost</span>
    <span style="color:#64748b">Spend by dream, agent, and stage</span>
  </header>
  <main class="shell">
    <section class="empty">
      <h1>Effort & Cost</h1>
      <p>No cost data yet. Cost entries are recorded automatically on each synlynk exec run.</p>
    </section>
  </main>
  {_live_js(port)}
</body>
</html>"""

    dreams_sorted = sorted(dreams, key=lambda d: float(d.get("cost_total") or 0.0), reverse=True)
    max_dream_cost = max([float(d.get("cost_total") or 0.0) for d in dreams_sorted] + [0.0]) or 1.0
    dreams_in_flight = sum(1 for dream in dreams_sorted if (dream.get("status") or "") == "active")
    over_budget = sum(
        1
        for dream in dreams_sorted
        if dream.get("cost_est") is not None and float(dream.get("cost_total") or 0.0) > float(dream.get("cost_est") or 0.0)
    )
    top_agent = max(by_agent.items(), key=lambda item: _bucket_total(item[1]))[0] if by_agent else "—"

    def build_summary_cards() -> str:
        est_pct = (total_usd_estimated / total_usd * 100.0) if total_usd else 0.0
        cards = [
            ("Total Spend", _fmt_usd(total_usd)),
            ("Dreams In Flight", str(dreams_in_flight)),
            ("Over Budget", str(over_budget)),
            ("Top Agent", _svg_text(top_agent)),
            ("~Estimated", f"{_fmt_usd(total_usd_estimated)} ({_fmt_pct(est_pct)})"),
        ]
        return "".join(
            f'<div class="stat"><span>{label}</span><strong>{value}</strong></div>'
            for label, value in cards
        )

    def render_bar_chart(rows, title, value_key, color_fn, label_fn, empty_text, max_value=None, estimated_key=None) -> str:
        rows = list(rows)
        row_count = max(len(rows), 1)
        svg_height = 54 + row_count * 30
        max_value = max_value or max([float(row.get(value_key) or 0.0) for row in rows] + [0.0]) or 1.0
        svg_rows = []
        if rows:
            for idx, row in enumerate(rows):
                value = float(row.get(value_key) or 0.0)
                estimated_val = float(row.get(estimated_key) or 0.0) if estimated_key else 0.0
                actual_val = max(value - estimated_val, 0.0)
                y = 18 + idx * 30
                bar_color = color_fn(row, value)
                label = label_fn(row, value)
                actual_width = (actual_val / max_value) * 380 if max_value else 0.0
                bar_svg = f'<rect x="110" y="{y}" width="{actual_width:.2f}" height="18" rx="9" fill="{bar_color}"></rect>'
                if estimated_val > 0:
                    est_width = (estimated_val / max_value) * 380 if max_value else 0.0
                    bar_svg += (
                        f'<rect x="{110 + actual_width:.2f}" y="{y}" width="{est_width:.2f}" '
                        f'height="18" fill="{bar_color}" fill-opacity="0.4"></rect>'
                    )
                svg_rows.append(
                    f'<text x="0" y="{y + 7}" class="y-label">{_svg_text(row.get("label") or row.get("name") or row.get("key") or "")}</text>'
                    f'{bar_svg}'
                    f'<text x="495" y="{y + 7}" text-anchor="end" class="value-label">{_svg_text(label)}</text>'
                )
        else:
            svg_rows.append(f'<text x="250" y="42" text-anchor="middle" class="empty-label">{_svg_text(empty_text)}</text>')

        return f"""
        <section class="panel">
          <div class="panel-head">
            <h2>{_svg_text(title)}</h2>
          </div>
          <svg viewBox="0 0 500 {svg_height}" aria-label="{_svg_text(title)}">
            {''.join(svg_rows)}
          </svg>
        </section>
        """

    dream_rows = [
        {
            "label": dream.get("name") or dream.get("id") or "Unnamed dream",
            "name": dream.get("name") or dream.get("id") or "Unnamed dream",
            "value": float(dream.get("cost_total") or 0.0),
            "estimated": float(dream.get("cost_total_estimated") or 0.0),
            "cost_est": dream.get("cost_est"),
            "cost_total": float(dream.get("cost_total") or 0.0),
        }
        for dream in dreams_sorted
    ]

    agent_rows = []
    for agent, bucket in sorted(by_agent.items(), key=lambda item: _bucket_total(item[1]), reverse=True):
        total = _bucket_total(bucket)
        if total <= 0:
            continue
        agent_rows.append({
            "label": agent, "name": agent, "value": total, "spend": total,
            "estimated": _bucket_estimated(bucket),
        })

    stage_rows = []
    for stage, bucket in sorted(by_stage.items(), key=lambda item: _bucket_total(item[1]), reverse=True):
        total = _bucket_total(bucket)
        if total <= 0:
            continue
        stage_rows.append({
            "label": stage, "name": stage, "value": total, "spend": total,
            "estimated": _bucket_estimated(bucket),
        })

    def dream_color(row, value):
        est = row.get("cost_est")
        if est is not None and value > float(est or 0.0):
            return "#e05"
        return "#0d9e87"

    def dream_label(row, value):
        est = row.get("cost_est")
        prov_estimated = row.get("estimated") or 0.0
        base = _fmt_usd(value)
        if prov_estimated > 0:
            base = f"{base} (est: {_fmt_usd(prov_estimated)})"
        if est is None:
            return base
        return f"{base} / est {_fmt_usd(est)}"

    def agent_color(row, value):
        agent = (row.get("label") or "").strip().lower()
        return {
            "claude": "#0d9e87",
            "agy": "#3b7dd8",
            "codex": "#1a9e5c",
            "grok": "#888888",
        }.get(agent, "#0d9e87")

    def agent_label(row, value):
        pct = (value / total_usd * 100.0) if total_usd else 0.0
        base = f"{_fmt_usd(value)} ({_fmt_pct(pct)})"
        prov_estimated = row.get("estimated") or 0.0
        if prov_estimated > 0:
            base = f"{base} (est: {_fmt_usd(prov_estimated)})"
        return base

    def stage_label(row, value):
        pct = (value / total_usd * 100.0) if total_usd else 0.0
        base = f"{_fmt_usd(value)} ({_fmt_pct(pct)})"
        prov_estimated = row.get("estimated") or 0.0
        if prov_estimated > 0:
            base = f"{base} (est: {_fmt_usd(prov_estimated)})"
        return base

    def stage_color(row, value):
        return _stage_color(row.get("label") or row.get("name") or "")

    return f"""<!doctype html>
<html lang="en" data-theme="system">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Effort & Cost</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f7fb;
      --bg-accent: linear-gradient(180deg, #ffffff 0%, #eef3fb 100%);
      --panel: rgba(255,255,255,0.92);
      --panel-border: rgba(15, 23, 42, 0.10);
      --text: #142033;
      --muted: #64748b;
      --shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
      --card: #ffffff;
      --card-border: rgba(15, 23, 42, 0.08);
      --teal: #0d9e87;
      --blue: #3b7dd8;
      --green: #1a9e5c;
      --gray: #888888;
      --red: #e05;
      --stage-design: #f39c6b;
      --stage-plan: #7b8cff;
      --stage-build: #1a9e5c;
      --stage-ship: #0d9e87;
      --stage-sustain: #888888;
    }}
    [data-theme="dark"] {{
      color-scheme: dark;
      --bg: #0b1220;
      --bg-accent: linear-gradient(180deg, #111a2e 0%, #0b1220 100%);
      --panel: rgba(15, 23, 42, 0.92);
      --panel-border: rgba(148, 163, 184, 0.18);
      --text: #e5edf8;
      --muted: #94a3b8;
      --shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
      --card: rgba(15, 23, 42, 0.92);
      --card-border: rgba(148, 163, 184, 0.16);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--bg-accent);
    }}
    .wrap {{
      width: min(1320px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }}
    .hero {{
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 24px;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0;
      font-size: 30px;
      letter-spacing: -0.04em;
    }}
    .subtle {{ color: var(--muted); margin-top: 6px; font-size: 14px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
    .stat, .panel {{
      border: 1px solid var(--card-border);
      background: var(--card);
      border-radius: 22px;
      box-shadow: var(--shadow);
    }}
    .stat {{
      padding: 18px 18px 16px;
      min-height: 102px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .stat span {{ color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .stat strong {{ font-size: 28px; line-height: 1.1; letter-spacing: -0.04em; }}
    .panel {{
      padding: 18px 18px 8px;
      margin-top: 16px;
    }}
    .panel-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 8px;
    }}
    .panel h2 {{
      margin: 0;
      font-size: 18px;
      letter-spacing: -0.02em;
    }}
    svg {{
      width: 100%;
      display: block;
      overflow: visible;
      font-size: 12px;
    }}
    .y-label {{ fill: var(--text); font-size: 12px; dominant-baseline: middle; }}
    .value-label {{ fill: var(--muted); font-size: 12px; dominant-baseline: middle; }}
    .empty-label {{ fill: var(--muted); font-size: 14px; dominant-baseline: middle; }}
    @media (max-width: 980px) {{
      .summary {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    }}
    @media (max-width: 700px) {{
      .wrap {{ width: min(100vw - 20px, 100%); }}
      .summary {{ grid-template-columns: 1fr; }}
      .hero {{ flex-direction: column; align-items: start; }}
    }}
  </style>
</head>
<body>
  <script>window.VIZOR_DATA = {data_json}; function checkManifest() {{ return window.VIZOR_DATA; }}</script>
  <main class="wrap">
    <header class="hero">
      <div>
        <h1>Effort & Cost</h1>
        <div class="subtle">Workspace spend, dream overruns, and agent allocation at a glance. Faded segments indicate estimated (non-structural) cost.</div>
      </div>
    </header>
    <section class="summary">{build_summary_cards()}</section>
    {render_bar_chart(
        dream_rows,
        "By Dream",
        "value",
        dream_color,
        dream_label,
        "No dreams found",
        max_dream_cost,
        estimated_key="estimated",
    )}
    {render_bar_chart(
        agent_rows,
        "By Agent",
        "value",
        agent_color,
        agent_label,
        "No agent spend yet",
        estimated_key="estimated",
    )}
    {render_bar_chart(
        stage_rows,
        "By Stage",
        "value",
        stage_color,
        stage_label,
        "No stage spend yet",
        estimated_key="estimated",
    )}
  </main>
  {_live_js(port)}
</body>
</html>"""


def generate_efficiency_html(data: dict, port: int) -> str:
    import html
    import json
    import math

    def get_capability_level(cycle_cap: dict, agent: str, cycle: str) -> str:
        c_key = cycle.lower()
        a_key = agent.lower()
        if c_key in cycle_cap and isinstance(cycle_cap[c_key], dict):
            sub = cycle_cap[c_key]
            if a_key in sub:
                return sub[a_key]
            for k, v in sub.items():
                if k.lower() == a_key:
                    return v
        if a_key in cycle_cap and isinstance(cycle_cap[a_key], dict):
            sub = cycle_cap[a_key]
            if c_key in sub:
                return sub[c_key]
            for k, v in sub.items():
                if k.lower() == c_key:
                    return v
        return "none"

    def _money(value) -> str:
        try:
            return f"${float(value):.2f}"
        except Exception:
            return "$0.00"

    def _rate(value) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.0

    def _avatar(name: str) -> Tuple[str, str]:
        key = (name or "").strip().lower()
        if key.startswith("claude"):
            return "C", "claude"
        if key.startswith("agy"):
            return "A", "agy"
        if key.startswith("codex"):
            return "Co", "codex"
        if key.startswith("grok"):
            return "G", "grok"
        if not name:
            return "?", "unknown"
        return (name.strip()[:2] if len(name.strip()) > 1 else name.strip()[0]).upper(), "unknown"

    def _dot_class(rate: float, alert_count: int) -> str:
        if rate >= 0.9 and alert_count == 0:
            return "dot-good"
        if 0.7 <= rate < 0.9 or alert_count == 1:
            return "dot-warn"
        return "dot-bad"

    def _bar_class(rate: float) -> str:
        if rate >= 0.9:
            return "bar-good"
        if rate >= 0.7:
            return "bar-warn"
        return "bar-bad"

    def _pattern_class(pattern: str) -> str:
        mapping = {
            "FLATLINE": "pattern-flatline",
            "SUCCESS_LOOP": "pattern-success-loop",
            "COST_SPIKE": "pattern-cost-spike",
            "QUOTA_EXHAUSTED": "pattern-quota-exhausted",
        }
        return mapping.get((pattern or "").upper(), "pattern-unknown")

    agents = data.get("agents") or {}
    telemetry = data.get("telemetry") or {}
    sentinel_alerts = telemetry.get("sentinel_alerts") or []
    recent_runs = telemetry.get("recent") or []
    json_data = json.dumps(data, ensure_ascii=False)

    try:
        from synlynk.status import TIER1_CAPACITY
    except ImportError:
        TIER1_CAPACITY = {
            "claude": {"ctx_window_tokens": 200_000, "read_budget_tokens": 750_000, "write_budget_tokens": 32_000, "tool_budget_count": 200},
            "agy": {"ctx_window_tokens": 1_000_000, "read_budget_tokens": 900_000, "write_budget_tokens": 65_000, "tool_budget_count": 500},
            "codex": {"ctx_window_tokens": 128_000, "read_budget_tokens": 110_000, "write_budget_tokens": 16_000, "tool_budget_count": 128},
            "grok": {"ctx_window_tokens": 131_000, "read_budget_tokens": 115_000, "write_budget_tokens": 16_000, "tool_budget_count": 100},
        }

    eco = data.get("ecosystem", {})
    is_placeholder = not bool(eco)

    if is_placeholder:
        efficiency = 1.0
        fleet_attached = 0
        fleet_total = 0
        dispatch_mode = "—"
        agents_data = {}
        cycle_cap = {
            "goal": {"claude": "full", "agy": "partial", "codex": "none", "grok": "none"},
            "open": {"claude": "full", "agy": "none", "codex": "none", "grok": "none"},
            "visualize": {"claude": "full", "agy": "partial", "codex": "full", "grok": "partial"},
            "execute": {"claude": "full", "agy": "partial", "codex": "partial", "grok": "none"},
            "release": {"claude": "full", "agy": "partial", "codex": "partial", "grok": "partial"},
            "notify": {"claude": "full", "agy": "partial", "codex": "none", "grok": "partial"},
            "sustain": {"claude": "full", "agy": "partial", "codex": "partial", "grok": "partial"},
        }
        capacity = TIER1_CAPACITY
        sentinels_active = 0
    else:
        efficiency = eco.get("headless_efficiency", 1.0)
        fleet = eco.get("fleet", {})
        fleet_attached = fleet.get("attached", 0)
        fleet_total = fleet.get("total", 0)
        dispatch_mode = fleet.get("dispatch_mode", "—")
        agents_data = eco.get("agents", {})
        cycle_cap = eco.get("cycle_capability", {})
        capacity = eco.get("capacity", {}) or TIER1_CAPACITY
        sentinels_active = eco.get("sentinels_active", 0)

    style_content = """
    :root {
      --bg:#f6f8fa; --bg2:#ffffff; --bg3:#eaeef2;
      --border:#d1d5db; --border2:#e8ebee;
      --text:#1f2328; --text2:#57606a; --text3:#8b949e;
      --accent:#0d9e87; --accent-bg:#e6f7f4; --accent-dim:#c0ede6;
      --shadow:0 2px 12px rgba(0,0,0,.10);

      --ag-claude-bg:#e6f7f4; --ag-claude-bd:#0d9e87; --ag-claude-tx:#0d9e87;
      --ag-agy-bg:#e8f0fe; --ag-agy-bd:#4285f4; --ag-agy-tx:#1a56c7;
      --ag-codex-bg:#e6f4f0; --ag-codex-bd:#10a37f; --ag-codex-tx:#0b7a60;
      --ag-grok-bg:#f0f0f0; --ag-grok-bd:#666; --ag-grok-tx:#333;
      --ag-muse-bg:#fdf2f8; --ag-muse-bd:#db2777; --ag-muse-tx:#9d174d;
      --ok:#16a34a; --warn:#d97706; --bad:#dc2626;
    }
    [data-theme="dark"] {
      --bg:#0d1117; --bg2:#161b22; --bg3:#0d1117;
      --border:#30363d; --border2:#30363d;
      --text:#c9d1d9; --text2:#8b949e; --text3:#4a5568;
      --accent:#58a6ff; --accent-bg:#0d2137; --accent-dim:#0a3050;
      --shadow:0 2px 20px rgba(0,0,0,.5);

      --ag-claude-bg:#0d2a2a; --ag-claude-bd:#3de0c0; --ag-claude-tx:#3de0c0;
      --ag-agy-bg:#0d1a3a; --ag-agy-bd:#4285f4; --ag-agy-tx:#4285f4;
      --ag-codex-bg:#0a1f18; --ag-codex-bd:#10a37f; --ag-codex-tx:#10a37f;
      --ag-grok-bg:#1a1a1a; --ag-grok-bd:#e0e0e0; --ag-grok-tx:#e0e0e0;
      --ag-muse-bg:#2e081d; --ag-muse-bd:#f472b6; --ag-muse-tx:#f472b6;
      --ok:#3fb950; --warn:#f0883e; --bad:#f85149;
    }
    * { box-sizing:border-box; margin:0; padding:0; }
    body {
      font-family:'SF Mono','JetBrains Mono',monospace;
      background: radial-gradient(circle at top, rgba(13,158,135,.10), transparent 36%), var(--bg);
      color:var(--text);
      font-size:13px;
      transition:background .2s,color .2s;
      min-height:100vh;
      padding:20px;
    }
    .page {
      max-width:1280px;
      margin:0 auto;
      display:flex;
      flex-direction:column;
      gap:18px;
    }
    .hero {
      display:flex;
      align-items:end;
      justify-content:space-between;
      gap:16px;
    }
    .title {
      font-size:20px;
      font-weight:800;
      letter-spacing:-0.02em;
    }
    .subtitle {
      margin-top:4px;
      color:var(--text2);
      font-size:12px;
      line-height:1.4;
    }
    .meta-chip {
      align-self:flex-start;
      padding:5px 10px;
      border-radius:999px;
      border:1px solid var(--border);
      background:var(--bg2);
      color:var(--text2);
      font-size:11px;
      white-space:nowrap;
    }
    .section {
      background:var(--bg2);
      border:1px solid var(--border);
      border-radius:16px;
      box-shadow:var(--shadow);
      overflow:hidden;
    }
    .section-head {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      padding:14px 16px;
      border-bottom:1px solid var(--border2);
      background:linear-gradient(180deg, rgba(13,158,135,.06), transparent);
    }
    .section-title {
      font-size:13px;
      font-weight:800;
      letter-spacing:.02em;
      text-transform:uppercase;
      color:var(--text);
    }
    .section-note {
      color:var(--text3);
      font-size:11px;
    }
    .cards-grid {
      display:grid;
      grid-template-columns:repeat(2, minmax(0, 1fr));
      gap:14px;
      padding:16px;
    }
    .cards-grid.single {
      grid-template-columns:1fr;
    }
    .agent-card {
      position:relative;
      background:linear-gradient(180deg, rgba(255,255,255,.75), rgba(255,255,255,0));
      border:1px solid var(--border2);
      border-radius:14px;
      padding:16px 16px 14px;
      min-height:168px;
      overflow:hidden;
    }
    [data-theme="dark"] .agent-card {
      background:linear-gradient(180deg, rgba(255,255,255,.02), rgba(255,255,255,0));
    }
    .agent-card::before {
      content:'';
      position:absolute;
      inset:0;
      border-radius:14px;
      pointer-events:none;
      background:linear-gradient(135deg, rgba(13,158,135,.08), transparent 42%);
      opacity:.7;
    }
    .traffic-dot {
      position:absolute;
      top:14px;
      right:14px;
      width:12px;
      height:12px;
      border-radius:50%;
      border:2px solid var(--bg2);
      box-shadow:0 0 0 1px rgba(0,0,0,.06);
      z-index:1;
    }
    .dot-good { background:var(--ok); }
    .dot-warn { background:var(--warn); }
    .dot-bad { background:var(--bad); }
    .agent-head {
      display:flex;
      align-items:center;
      gap:12px;
      position:relative;
      z-index:1;
      margin-bottom:12px;
      padding-right:20px;
    }
    .avatar-badge {
      width:34px;
      height:34px;
      border-radius:50%;
      display:flex;
      align-items:center;
      justify-content:center;
      font-weight:800;
      font-size:11px;
      letter-spacing:.02em;
      color:#fff;
      flex-shrink:0;
    }
    .agent-claude { background:linear-gradient(135deg, var(--ag-claude-bd), var(--ag-claude-tx)); }
    .agent-agy { background:linear-gradient(135deg, var(--ag-agy-bd), var(--ag-agy-tx)); }
    .agent-codex { background:linear-gradient(135deg, var(--ag-codex-bd), var(--ag-codex-tx)); }
    .agent-grok { background:linear-gradient(135deg, var(--ag-grok-bd), var(--ag-grok-tx)); }
    .agent-muse { background:linear-gradient(135deg, var(--ag-muse-bd), var(--ag-muse-tx)); }
    .agent-unknown { background:linear-gradient(135deg, var(--accent), #0b7a60); }
    .agent-name {
      font-size:15px;
      font-weight:800;
      color:var(--text);
      line-height:1.2;
    }
    .agent-metrics {
      display:flex;
      flex-direction:column;
      gap:10px;
      position:relative;
      z-index:1;
    }
    .agent-counts {
      color:var(--text2);
      font-size:12px;
    }
    .agent-spend {
      font-size:12px;
      color:var(--text);
      font-weight:700;
    }
    .alert-count {
      color:var(--bad);
      font-size:12px;
      font-weight:700;
    }
    .rate-wrap {
      margin-top:2px;
    }
    .rate-label-row {
      display:flex;
      align-items:center;
      justify-content:space-between;
      margin-bottom:6px;
      font-size:11px;
      color:var(--text2);
    }
    .rate-track {
      width:100%;
      height:10px;
      background:var(--bg3);
      border:1px solid var(--border);
      border-radius:999px;
      overflow:hidden;
    }
    .rate-fill {
      height:100%;
      border-radius:999px;
    }
    .bar-good { background:linear-gradient(90deg, #22c55e, #16a34a); }
    .bar-warn { background:linear-gradient(90deg, #f59e0b, #d97706); }
    .bar-bad { background:linear-gradient(90deg, #ef4444, #dc2626); }
    .timeline-list {
      display:flex;
      flex-direction:column;
      gap:10px;
      padding:14px 16px 16px;
      max-height:280px;
      overflow:auto;
    }
    .timeline-row {
      display:grid;
      grid-template-columns:160px minmax(0, 1fr) auto;
      gap:10px;
      align-items:center;
      padding:10px 12px;
      border:1px solid var(--border2);
      border-radius:12px;
      background:var(--bg);
    }
    .timeline-ts {
      color:var(--text2);
      font-size:11px;
      white-space:nowrap;
    }
    .badge {
      display:inline-flex;
      align-items:center;
      justify-content:center;
      padding:4px 8px;
      border-radius:999px;
      font-size:10px;
      font-weight:800;
      letter-spacing:.02em;
      white-space:nowrap;
    }
    .pattern-flatline { background:#fee2e2; color:#b91c1c; border:1px solid #fecaca; }
    .pattern-success-loop { background:#ffedd5; color:#c2410c; border:1px solid #fed7aa; }
    .pattern-cost-spike { background:#fef3c7; color:#a16207; border:1px solid #fde68a; }
    .pattern-quota-exhausted { background:#e5e7eb; color:#4b5563; border:1px solid #d1d5db; }
    .pattern-unknown { background:var(--bg3); color:var(--text2); border:1px solid var(--border); }
    [data-theme="dark"] .pattern-flatline { background:#2a1212; color:#fca5a5; border-color:#4c1d1d; }
    [data-theme="dark"] .pattern-success-loop { background:#2a1b12; color:#fdba74; border-color:#4a2a16; }
    [data-theme="dark"] .pattern-cost-spike { background:#2a2412; color:#fde68a; border-color:#4a4016; }
    [data-theme="dark"] .pattern-quota-exhausted { background:#1f2937; color:#d1d5db; border-color:#374151; }
    .resolved-badge {
      background:rgba(22,163,74,.12);
      color:var(--ok);
      border:1px solid rgba(22,163,74,.22);
    }
    .timeline-row .resolved-badge {
      justify-self:end;
    }
    .runs-table-wrap {
      padding:0 16px 16px;
    }
    table.runs-table {
      width:100%;
      border-collapse:separate;
      border-spacing:0;
      overflow:hidden;
      border:1px solid var(--border2);
      border-radius:12px;
      background:var(--bg);
    }
    .runs-table th,
    .runs-table td {
      padding:11px 12px;
      border-bottom:1px solid var(--border2);
      text-align:left;
      font-size:12px;
      vertical-align:middle;
    }
    .runs-table th {
      color:var(--text2);
      font-size:10px;
      text-transform:uppercase;
      letter-spacing:.08em;
      background:var(--bg3);
    }
    .runs-table tr:last-child td {
      border-bottom:none;
    }
    .run-agent {
      display:flex;
      align-items:center;
      gap:8px;
    }
    .run-duration,
    .run-cost {
      white-space:nowrap;
      font-variant-numeric:tabular-nums;
    }
    .exit-ok {
      color:var(--ok);
      font-weight:800;
      white-space:nowrap;
    }
    .exit-bad {
      color:var(--bad);
      font-weight:800;
      white-space:nowrap;
    }
    .empty-state {
      min-height:60vh;
      display:flex;
      align-items:center;
      justify-content:center;
      text-align:center;
      padding:24px;
      font-size:14px;
      font-weight:700;
      color:var(--text2);
    }
    .empty-state span {
      display:inline-block;
      max-width:560px;
      line-height:1.6;
      border:1px solid var(--border);
      background:var(--bg2);
      border-radius:16px;
      padding:18px 20px;
      box-shadow:var(--shadow);
    }
    @media (max-width: 900px) {
      .cards-grid,
      .cards-grid.single {
        grid-template-columns:1fr;
      }
      .timeline-row {
        grid-template-columns:1fr;
      }
      .timeline-row .resolved-badge {
        justify-self:start;
      }
      .runs-table-wrap {
        overflow:auto;
      }
      .runs-table {
        min-width:680px;
      }
    }
    .number-font {
      font-family: system-ui, monospace;
    }
    .label-font {
      font-family: sans-serif;
    }
    .eco-top-row {
      display: flex;
      flex-wrap: wrap;
      gap: 18px;
      margin-bottom: 18px;
    }
    .eco-banner-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      flex: 1;
      min-width: 280px;
      box-shadow: var(--shadow);
      position: relative;
    }
    .efficiency-num {
      font-size: 48px;
      font-weight: 800;
      color: var(--accent);
      line-height: 1;
      margin-bottom: 8px;
    }
    .efficiency-title {
      font-size: 14px;
      font-weight: 700;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .efficiency-sub {
      font-size: 11px;
      color: var(--text2);
      margin-top: 4px;
    }
    .fleet-header-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      flex: 1;
      min-width: 280px;
      box-shadow: var(--shadow);
    }
    .fleet-title {
      font-size: 14px;
      font-weight: 700;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 16px;
    }
    .fleet-status-row {
      display: flex;
      gap: 12px;
    }
    .fleet-pill {
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid var(--border);
      background: var(--bg3);
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .dispatch-mode-pill {
      color: var(--accent);
      border-color: var(--accent);
    }
    .attached-badge {
      color: var(--ok);
      border-color: var(--ok);
    }
    .eco-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin-bottom: 18px;
    }
    .cap-table, .matrix-table {
      width: 100%;
      border-collapse: collapse;
    }
    .cap-table th, .cap-table td,
    .matrix-table th, .matrix-table td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border2);
      vertical-align: middle;
    }
    .cap-table th, .matrix-table th {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text2);
      font-weight: 700;
      background: var(--bg3);
      padding: 8px 12px;
    }
    .cap-table td, .matrix-table td {
      background: var(--bg2);
    }
    .cap-agent-name, .matrix-agent-name {
      font-size: 13px;
      font-weight: 700;
      color: var(--text);
    }
    .cap-cell {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .cap-num {
      font-size: 12px;
      font-weight: 700;
      color: var(--text);
    }
    .cap-bar-track {
      width: 100%;
      height: 4px;
      background: var(--bg3);
      border-radius: 2px;
      overflow: hidden;
      border: 1px solid var(--border);
    }
    .cap-bar-fill {
      height: 100%;
      background: var(--accent);
      border-radius: 2px;
      transition: width 0.3s ease;
    }
    .matrix-table th, .matrix-table td {
      text-align: center;
    }
    .matrix-table th:first-child, .matrix-table td:first-child {
      text-align: left;
    }
    .matrix-circle-container {
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .skeleton-text {
      color: var(--text3) !important;
    }
    .skeleton-fill {
      background: var(--border) !important;
      opacity: 0.5;
    }
    .skeleton-pulse::after {
      content: "";
      position: absolute;
      top: 0; right: 0; bottom: 0; left: 0;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent);
      animation: skeleton-pulse-anim 1.5s infinite;
      pointer-events: none;
    }
    @keyframes skeleton-pulse-anim {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(100%); }
    }
    .rwt-section { margin-top: 10px; display: flex; flex-direction: column; gap: 4px; }
    .rwt-row { display: flex; align-items: center; gap: 6px; }
    .rwt-label { font-size: 10px; font-weight: 700; color: var(--text3); width: 10px; }
    .rwt-track { flex: 1; height: 5px; background: var(--bg3); border-radius: 3px; overflow: hidden; }
    .rwt-fill { height: 100%; background: var(--accent); border-radius: 3px; }
    .rwt-fill.rwt-write { background: var(--ag-agy-bd); }
    .rwt-fill.rwt-tool { background: var(--ag-codex-bd); }
    .rwt-val { font-size: 10px; color: var(--text3); width: 36px; text-align: right; }
    .cycle-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .cycle-table th, .cycle-table td { padding: 7px 12px; border-bottom: 1px solid var(--border2); text-align: center; }
    .cycle-table th { font-weight: 700; color: var(--text2); background: var(--bg3); }
    .cycle-table td:first-child { text-align: left; }
    .cap-full { background: rgba(22,163,74,.12); color: var(--ok); font-weight: 600; border-radius: 4px; padding: 1px 6px; }
    .cap-partial { background: rgba(217,119,6,.12); color: var(--warn); border-radius: 4px; padding: 1px 6px; }
    .cap-none { color: var(--text3); }
    """

    cycles_list = ["goal", "open", "visualize", "execute", "release", "notify", "sustain"]
    cards_html = []
    for name, stats in agents.items():
        rate = _rate(stats.get("success_rate"))
        alerts = int(stats.get("alert_count") or 0)
        initials, avatar_class = _avatar(name)
        dot_class = _dot_class(rate, alerts)
        bar_class = _bar_class(rate)
        alert_html = f'<div class="alert-count">{alerts} sentinel alerts</div>' if alerts > 0 else ""

        # Get capacity data safely
        clean_name = (name or "").strip().lower()
        agent_cap = capacity.get(clean_name) or capacity.get(name) or TIER1_CAPACITY.get(clean_name) or {}
        baseline_cap = TIER1_CAPACITY.get(clean_name) or {}
        if not baseline_cap:
            baseline_cap = {"read_budget_tokens": 1, "write_budget_tokens": 1, "tool_budget_count": 1}

        read_budget = agent_cap.get("read_budget_tokens", 0)
        write_budget = agent_cap.get("write_budget_tokens", 0)
        tool_budget = agent_cap.get("tool_budget_count", 0)

        base_read = baseline_cap.get("read_budget_tokens", 1) or 1
        base_write = baseline_cap.get("write_budget_tokens", 1) or 1
        base_tool = baseline_cap.get("tool_budget_count", 1) or 1

        if is_placeholder:
            read_pct = 100.0
            write_pct = 100.0
            tool_pct = 100.0
            read_budget_k = base_read // 1000
            write_budget_k = base_write // 1000
            tool_budget = base_tool
        else:
            read_pct = (read_budget / base_read) * 100 if base_read else 0.0
            write_pct = (write_budget / base_write) * 100 if base_write else 0.0
            tool_pct = (tool_budget / base_tool) * 100 if base_tool else 0.0
            read_budget_k = read_budget // 1000
            write_budget_k = write_budget // 1000

        rwt_html = f"""
            <div class="rwt-section">
              <div class="rwt-row">
                <span class="rwt-label">R</span>
                <div class="rwt-track"><div class="rwt-fill" style="width:{read_pct:.0f}%"></div></div>
                <span class="rwt-val">{read_budget_k}k</span>
              </div>
              <div class="rwt-row">
                <span class="rwt-label">W</span>
                <div class="rwt-track"><div class="rwt-fill rwt-write" style="width:{write_pct:.0f}%"></div></div>
                <span class="rwt-val">{write_budget_k}k</span>
              </div>
              <div class="rwt-row">
                <span class="rwt-label">T</span>
                <div class="rwt-track"><div class="rwt-fill rwt-tool" style="width:{tool_pct:.0f}%"></div></div>
                <span class="rwt-val">{tool_budget}</span>
              </div>
            </div>
        """.strip()

        # Radar heptagon SVG
        angles = [270, 321.4, 12.9, 64.3, 115.7, 167.1, 218.6]
        cycles_order = cycles_list

        outer_points = []
        for deg in angles:
            rad = math.radians(deg)
            x = 40 + 32 * math.cos(rad)
            y = 40 + 32 * math.sin(rad)
            outer_points.append(f"{x:.1f},{y:.1f}")
        outer_points_str = " ".join(outer_points)

        score_points = []
        for i, cycle in enumerate(cycles_order):
            support = get_capability_level(cycle_cap, clean_name, cycle)
            if support == "full":
                score = 1.0
            elif support == "partial":
                score = 0.5
            else:
                score = 0.0
            deg = angles[i]
            rad = math.radians(deg)
            r = 32 * score
            x = 40 + r * math.cos(rad)
            y = 40 + r * math.sin(rad)
            score_points.append((x, y))
        score_points_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in score_points)

        axis_lines_html = []
        for i in range(len(cycles_list)):
            rad = math.radians(angles[i])
            x_outer = 40 + 32 * math.cos(rad)
            y_outer = 40 + 32 * math.sin(rad)
            axis_lines_html.append(
                f'<line x1="40" y1="40" x2="{x_outer:.1f}" y2="{y_outer:.1f}" stroke="var(--border)" stroke-width="0.5" stroke-dasharray="2,2" />'
            )
        axis_lines_str = "\n".join(axis_lines_html)

        dots_html = []
        for x, y in score_points:
            dots_html.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="var(--ag-{avatar_class}-bd, var(--accent))" />')
        dots_str = "\n".join(dots_html)

        radar_svg_html = f"""
            <div class="radar-container" style="display: flex; justify-content: center; margin-top: 10px;">
              <svg width="80" height="80" viewBox="0 0 80 80" style="overflow: visible;">
                <polygon points="{outer_points_str}" fill="none" stroke="var(--border)" stroke-width="1" />
                {axis_lines_str}
                <polygon points="{score_points_str}" fill="var(--ag-{avatar_class}-bd, var(--accent))" fill-opacity="0.4" stroke="var(--ag-{avatar_class}-bd, var(--accent))" stroke-width="1.5" />
                {dots_str}
              </svg>
            </div>
        """.strip()

        cards_html.append(
            f"""
        <div class="agent-card">
          <span class="traffic-dot {dot_class}"></span>
          <div class="agent-head">
            <div class="avatar-badge agent-{avatar_class}">{html.escape(initials)}</div>
            <div class="agent-name">{html.escape(str(name))}</div>
          </div>
          <div class="agent-metrics">
            <div class="agent-counts">{int(stats.get("tasks_done") or 0)} done · {int(stats.get("tasks_active") or 0)} active</div>
            <div class="agent-spend">Total spend: {_money(stats.get("total_usd"))}</div>
            {alert_html}
            <div class="rate-wrap">
              <div class="rate-label-row">
                <span>Success rate</span>
                <span>{rate * 100:.0f}%</span>
              </div>
              <div class="rate-track">
                <div class="rate-fill {bar_class}" style="width:{rate * 100:.0f}%"></div>
              </div>
            </div>
            {rwt_html}
            {radar_svg_html}
          </div>
        </div>
            """.rstrip()
        )

    if not cards_html:
        cards_html.append(
            '<div style="grid-column: 1 / -1; text-align: center; color: var(--text3); padding: 32px 16px;" class="label-font">'
            'No agent telemetry recorded yet. Run synlynk exec or synlynk launch to populate.</div>'
        )

    sorted_alerts = sorted(
        [alert for alert in sentinel_alerts if isinstance(alert, dict)],
        key=lambda alert: str(alert.get("ts") or ""),
        reverse=True,
    )
    timeline_html = []
    for alert in sorted_alerts:
        pattern = str(alert.get("pattern") or "")
        resolved = bool(alert.get("resolved"))
        resolved_html = '<span class="badge resolved-badge">[RESOLVED] ✓</span>' if resolved else ""
        timeline_html.append(
            f"""
        <div class="timeline-row">
          <div class="timeline-ts">{html.escape(str(alert.get("ts") or ""))}</div>
          <span class="badge {_pattern_class(pattern)}">{html.escape(pattern or "UNKNOWN")}</span>
          {resolved_html}
        </div>
            """.rstrip()
        )
    if not timeline_html:
        timeline_html.append(
            """
        <div class="timeline-row">
          <div class="timeline-ts">No sentinel alerts</div>
          <span class="badge pattern-unknown">-</span>
          <span class="badge resolved-badge" style="visibility:hidden;">[RESOLVED] ✓</span>
        </div>
            """.rstrip()
        )

    recent_runs = telemetry.get("recent") or []
    recent_rows = list((recent_runs or [])[-10:])[::-1]
    runs_html = []
    for row in recent_rows:
        agent_name = str(row.get("agent") or "")
        initials, avatar_class = _avatar(agent_name)
        exit_code = int(row.get("exit_code") or 0)
        duration = float(row.get("duration_s") or 0.0)
        runs_html.append(
            f"""
        <tr>
          <td>{html.escape(str(row.get("ts") or ""))}</td>
          <td>
            <div class="run-agent">
              <span class="avatar-badge agent-{avatar_class}">{html.escape(initials)}</span>
              <span>{html.escape(agent_name or "unknown")}</span>
            </div>
          </td>
          <td class="run-duration">{duration:.0f}s</td>
          <td class="run-cost">{_money(row.get("cost_usd"))}</td>
          <td class="{ 'exit-ok' if exit_code == 0 else 'exit-bad' }">{'✓' if exit_code == 0 else '✗'} {exit_code}</td>
        </tr>
            """.rstrip()
        )
    if not runs_html:
        runs_html.append(
            """
        <tr>
          <td colspan="5" style="color:var(--text2);">No recent runs</td>
        </tr>
            """.rstrip()
        )

    # 1. Headless efficiency banner HTML
    efficiency_val = efficiency
    if is_placeholder:
        eff_banner_html = f"""
      <div class="eco-banner-card skeleton-pulse">
        <div class="efficiency-num number-font skeleton-text">—x</div>
        <div class="efficiency-title label-font">headless efficiency</div>
        <div class="efficiency-sub label-font">vs. interactive baseline (no probe run yet)</div>
      </div>
        """
    else:
        eff_banner_html = f"""
      <div class="eco-banner-card">
        <div class="efficiency-num number-font">{efficiency_val:.1f}x</div>
        <div class="efficiency-title label-font">headless efficiency</div>
        <div class="efficiency-sub label-font">vs. interactive baseline</div>
      </div>
        """

    # 2. Fleet header HTML
    if is_placeholder:
        fleet_html = f"""
      <div class="fleet-header-card skeleton-pulse">
        <div class="fleet-title label-font">Fleet Status</div>
        <div class="fleet-status-row">
          <span class="fleet-pill label-font skeleton-text" style="border-color: var(--border); color: var(--text3);">Mode: —</span>
          <span class="fleet-pill label-font skeleton-text" style="border-color: var(--border); color: var(--text3);">— attached</span>
        </div>
      </div>
        """
    else:
        fleet_html = f"""
      <div class="fleet-header-card">
        <div class="fleet-title label-font">Fleet Status</div>
        <div class="fleet-status-row">
          <span class="fleet-pill dispatch-mode-pill label-font">Mode: <span class="number-font">{html.escape(str(dispatch_mode))}</span></span>
          <span class="fleet-pill attached-badge label-font"><span class="number-font">{int(fleet_attached)}/{int(fleet_total)}</span> attached</span>
        </div>
      </div>
        """

    eco_top_html = f"""
    <div class="eco-top-row">
      {eff_banner_html}
      {fleet_html}
    </div>
    """

    # 3. Capacity table HTML
    agents_list = ["claude", "agy", "codex", "grok"]
    
    def _to_k(tokens) -> str:
        try:
            return f"{int(tokens) // 1000}K"
        except Exception:
            return "0K"

    max_r = max((capacity.get(a, {}).get("read_budget_tokens", 0) for a in agents_list), default=1)
    max_w = max((capacity.get(a, {}).get("write_budget_tokens", 0) for a in agents_list), default=1)
    max_t = max((capacity.get(a, {}).get("tool_budget_count", 0) for a in agents_list), default=1)
    max_ctx = max((capacity.get(a, {}).get("ctx_window_tokens", 0) for a in agents_list), default=1)

    capacity_rows = []
    for agent in agents_list:
        cap = capacity.get(agent, {})
        r_val = cap.get("read_budget_tokens", 0)
        w_val = cap.get("write_budget_tokens", 0)
        t_val = cap.get("tool_budget_count", 0)
        ctx_val = cap.get("ctx_window_tokens", 0)

        r_pct = (r_val / max_r) * 100 if max_r else 0
        w_pct = (w_val / max_w) * 100 if max_w else 0
        t_pct = (t_val / max_t) * 100 if max_t else 0
        ctx_pct = (ctx_val / max_ctx) * 100 if max_ctx else 0

        if is_placeholder:
            r_str, w_str, t_str, ctx_str = "—", "—", "—", "—"
            r_pct, w_pct, t_pct, ctx_pct = 0, 0, 0, 0
            text_cls = "skeleton-text"
            fill_cls = "skeleton-fill"
        else:
            r_str = _to_k(r_val)
            w_str = _to_k(w_val)
            t_str = str(t_val)
            ctx_str = _to_k(ctx_val)
            text_cls = ""
            fill_cls = ""

        capacity_rows.append(f"""
        <tr>
          <td class="cap-agent-name label-font">{html.escape(agent)}</td>
          <td>
            <div class="cap-cell">
              <div class="cap-num number-font {text_cls}">{r_str}</div>
              <div class="cap-bar-track">
                <div class="cap-bar-fill {fill_cls}" style="width: {r_pct:.1f}%"></div>
              </div>
            </div>
          </td>
          <td>
            <div class="cap-cell">
              <div class="cap-num number-font {text_cls}">{w_str}</div>
              <div class="cap-bar-track">
                <div class="cap-bar-fill {fill_cls}" style="width: {w_pct:.1f}%"></div>
              </div>
            </div>
          </td>
          <td>
            <div class="cap-cell">
              <div class="cap-num number-font {text_cls}">{t_str}</div>
              <div class="cap-bar-track">
                <div class="cap-bar-fill {fill_cls}" style="width: {t_pct:.1f}%"></div>
              </div>
            </div>
          </td>
          <td>
            <div class="cap-cell">
              <div class="cap-num number-font {text_cls}">{ctx_str}</div>
              <div class="cap-bar-track">
                <div class="cap-bar-fill {fill_cls}" style="width: {ctx_pct:.1f}%"></div>
              </div>
            </div>
          </td>
        </tr>
        """)

    capacity_table_html = f"""
    <section class="section">
      <div class="section-head">
        <div class="section-title label-font">Capacity Table</div>
        <div class="section-note label-font">Relative to max value in each column.</div>
      </div>
      <div style="padding: 16px; overflow-x: auto;">
        <table class="cap-table">
          <thead>
            <tr>
              <th class="label-font">Agent</th>
              <th class="label-font">R (Read)</th>
              <th class="label-font">W (Write)</th>
              <th class="label-font">T (Tools)</th>
              <th class="label-font">CTX (Context)</th>
            </tr>
          </thead>
          <tbody>
            {''.join(capacity_rows)}
          </tbody>
        </table>
      </div>
    </section>
    """

    # 4. Cycle matrix HTML
    def _matrix_svg(support: str) -> str:
        s = (support or "").strip().lower()
        if s == "full":
            return (
                '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<circle cx="8" cy="8" r="7" fill="#3fb950" stroke="#3fb950" stroke-width="2"/>'
                '</svg>'
            )
        elif s == "partial":
            return (
                '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<circle cx="8" cy="8" r="7" stroke="#f0883e" stroke-width="2"/>'
                '<path d="M8 1a7 7 0 0 1 0 14V1z" fill="#f0883e"/>'
                '</svg>'
            )
        else:
            return (
                '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<circle cx="8" cy="8" r="7" stroke="#30363d" stroke-width="2"/>'
                '</svg>'
            )

    matrix_rows = []
    for agent in agents_list:
        tds = []
        for cycle in cycles_list:
            support = get_capability_level(cycle_cap, agent, cycle)
            tds.append(f"""
          <td>
            <div class="matrix-circle-container">
              {_matrix_svg(support)}
            </div>
          </td>
            """)
        matrix_rows.append(f"""
        <tr>
          <td class="matrix-agent-name label-font">{html.escape(agent)}</td>
          {''.join(tds)}
        </tr>
        """)

    matrix_table_html = f"""
    <section class="section">
      <div class="section-head">
        <div class="section-title label-font">Cycle Capability Matrix</div>
        <div class="section-note label-font">Support mapping across GOVERNS cycles.</div>
      </div>
      <div style="padding: 16px; overflow-x: auto;">
        <table class="matrix-table">
          <thead>
            <tr>
              <th class="label-font">Agent</th>
              <th class="label-font">Goal</th>
              <th class="label-font">Open</th>
              <th class="label-font">Visualize</th>
              <th class="label-font">Execute</th>
              <th class="label-font">Release</th>
              <th class="label-font">Notify</th>
              <th class="label-font">Sustain</th>
            </tr>
          </thead>
          <tbody>
            {''.join(matrix_rows)}
          </tbody>
        </table>
      </div>
    </section>
    """

    eco_grid_html = f"""
    <div class="eco-grid">
      {capacity_table_html}
      {matrix_table_html}
    </div>
    """

    # 5. Cycle capability matrix section
    matrix_rows_new = []
    cycle_emojis = {
        "goal": "🎯 Goal",
        "open": "📂 Open",
        "visualize": "🧭 Visualize",
        "execute": "⚙️ Execute",
        "release": "🚀 Release",
        "notify": "✉️ Notify",
        "sustain": "🔧 Sustain",
    }
    matrix_agents = ["claude", "agy", "codex", "grok"]
    for cycle in cycles_list:
        row_tds = [f"<td>{cycle_emojis.get(cycle, cycle)}</td>"]
        for agent in matrix_agents:
            support = get_capability_level(cycle_cap, agent, cycle)
            support_lower = support.lower()
            row_tds.append(f'<td><span class="cap-{support_lower}">{support_lower}</span></td>')
        matrix_rows_new.append(f"<tr>{''.join(row_tds)}</tr>")
    new_matrix_table_html = f"""
    <section class="section">
      <div class="section-head">
        <div class="section-title">Cycle Capability Matrix</div>
        <div class="section-note">full / partial / none per agent per 7-stage GOVERNS cycle.</div>
      </div>
      <table class="cycle-table">
        <thead><tr><th>Cycle</th><th>Claude</th><th>Agy</th><th>Codex</th><th>Grok</th></tr></thead>
        <tbody>
          {"".join(matrix_rows_new)}
        </tbody>
      </table>
    </section>
    """

    grid_class = "cards-grid single" if len(agents) == 1 else "cards-grid"
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Efficiency Report Card</title>
<script>window.VIZOR_DATA = {json_data};</script>
<script>
  (function() {{
    const theme = localStorage.getItem('vizor-theme') || 'system';
    let actualTheme = theme;
    if (theme === 'system') {{
      actualTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }}
    document.documentElement.setAttribute('data-theme', actualTheme);
  }})();
</script>
<style>{style_content}</style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <div>
        <div class="title">Efficiency Report Card</div>
        <div class="subtitle">Per-agent throughput, spend, success rate, and sentinel health.</div>
      </div>
      <div class="meta-chip">{html.escape(str(data.get("workspace", {}).get("name", "workspace")))} · {len(agents)} agent{'' if len(agents) == 1 else 's'}</div>
    </div>

    {eco_top_html}

    {eco_grid_html}

    <section class="section">
      <div class="section-head">
        <div class="section-title">Agent Cards</div>
        <div class="section-note">Traffic-light status uses success rate and sentinel alert count.</div>
      </div>
      <div class="{grid_class}">
        {''.join(cards_html)}
      </div>
    </section>

    {new_matrix_table_html}

    <section class="section">
      <div class="section-head">
        <div class="section-title">Sentinel Timeline</div>
        <div class="section-note">Newest first.</div>
      </div>
      <div class="timeline-list">
        {''.join(timeline_html)}
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div class="section-title">Recent Runs</div>
        <div class="section-note">Last 10 telemetry rows.</div>
      </div>
      <div class="runs-table-wrap">
        <table class="runs-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Agent</th>
              <th>Duration</th>
              <th>Cost</th>
              <th>Exit</th>
            </tr>
          </thead>
          <tbody>
            {''.join(runs_html)}
          </tbody>
        </table>
      </div>
    </section>
  </div>
  {_live_js(port)}
</body>
</html>"""
    return html_out


def generate_observatory_html(snapshot: dict) -> str:
    snapshot = snapshot or {}
    write_observatory_snapshot(snapshot)

    def _money(value) -> str:
        try:
            return f"${float(value or 0.0):.2f}"
        except Exception:
            return "—"

    def _tokens(input_tokens, output_tokens) -> str:
        try:
            total = int(input_tokens or 0) + int(output_tokens or 0)
        except Exception:
            return "—"
        return f"{total/1000:.1f}k" if total >= 1000 else str(total)

    def _age(seconds) -> str:
        try:
            seconds = int(seconds or 0)
        except Exception:
            return "—"
        minutes, secs = divmod(max(0, seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes:02d}m"
        if minutes:
            return f"{minutes}m {secs:02d}s"
        return f"{secs}s"

    def _render_job(job: dict) -> str:
        stage = html.escape(str(job.get("stage") or job.get("status") or "unknown"))
        repo = html.escape(str(job.get("repo") or "unknown"))
        job_id = html.escape(str(job.get("id") or "—"))
        short_id = job_id[-8:] if len(job_id) > 8 else job_id
        agent = html.escape(str(job.get("agent") or "—"))
        return f"""
          <div class="obs-job" data-stage="{stage}" data-repo="{repo}">
            <div class="obs-job-id">{short_id}</div>
            <div class="obs-job-agent">{agent}</div>
            <div class="obs-job-stage">{stage}</div>
            <div class="obs-job-age">{html.escape(_age(job.get("runtime_seconds")))}</div>
            <div class="obs-job-cost">{html.escape(_money(job.get("cost_usd")))}</div>
            <div class="obs-job-tokens">{html.escape(_tokens(job.get("input_tokens"), job.get("output_tokens")))}</div>
          </div>
        """.strip()

    def _render_repo(repo: dict) -> str:
        repo_name = html.escape(str(repo.get("repo") or "unknown"))
        rollups = repo.get("rollups") or {}
        jobs = repo.get("jobs") or []
        job_cards = "\n".join(_render_job(job) for job in jobs)
        if not job_cards:
            job_cards = '<div class="obs-empty">No jobs</div>'
        return f"""
        <section class="obs-repo">
          <header class="obs-repo-header">
            <div>
              <div class="obs-repo-title">{repo_name}</div>
              <div class="obs-repo-meta">{len(jobs)} jobs · {_money(rollups.get("total_cost"))} · {rollups.get("active_count", 0)} active</div>
            </div>
          </header>
          <div class="obs-job-grid">
            <div class="obs-job-head">
              <span>job</span><span>agent</span><span>stage</span><span>age</span><span>cost</span><span>tokens</span>
            </div>
            {job_cards}
          </div>
        </section>
        """.strip()

    def _worktree_model(value) -> tuple:
        if isinstance(value, list):
            items = value
            counts = {"active": 0, "safe": 0, "needs_review": 0, "dirty_orphan": 0}
            for item in items:
                status = str(item.get("status") or item.get("verdict") or "active").lower()
                if status in ("needs-review", "needs_review"):
                    counts["needs_review"] += 1
                elif status == "safe":
                    counts["safe"] += 1
                elif status in ("dirty-artifact", "dirty", "orphan"):
                    counts["dirty_orphan"] += 1
                else:
                    counts["active"] += 1
            return items, counts
        value = value if isinstance(value, dict) else {}
        return value.get("items") or [], {
            "active": int(value.get("active", 0) or 0),
            "safe": int(value.get("safe", 0) or 0),
            "needs_review": int(value.get("needs_review", 0) or 0),
            "dirty_orphan": int(value.get("dirty_orphan", 0) or 0),
        }

    def _worktree_status(item: dict) -> str:
        status = str(item.get("status") or item.get("verdict") or "active").lower()
        if status in ("needs-review", "needs_review"):
            return "needs-review"
        if status == "safe":
            return "safe"
        if status in ("dirty-artifact", "dirty", "orphan"):
            return "dirty-artifact"
        return "active"

    worktree_items, worktree_counts = _worktree_model(snapshot.get("worktrees"))
    worktree_rows = []
    for item in worktree_items:
        status = _worktree_status(item)
        label = {"active": "ACTIVE", "safe": "SAFE", "needs-review": "NEEDS-REVIEW", "dirty-artifact": "DIRTY-ARTIFACT"}[status]
        p_path = html.escape(str(item.get("path") or ""))
        prune_btn = f' <button class="wt-prune" data-path="{p_path}">Prune</button>' if status == "safe" else ""
        worktree_rows.append(
            f'<tr><td><code>{html.escape(str(item.get("branch") or "—"))}</code></td>'
            f'<td class="wt-path">{html.escape(str(item.get("path") or "—"))}</td>'
            f'<td><span class="wt-pill wt-{status}">{label}</span></td>'
            f'<td>{html.escape(str(item.get("reason") or "—"))}</td>'
            f'<td><button class="wt-inspect" data-path="{p_path}">Inspect</button>'
            f'{prune_btn}</td></tr>'
        )
    worktree_html = f'''<!-- Worktree Lifecycle & Fleet Health -->
    <section class="wt-panel" id="worktree-lifecycle">
      <header class="wt-header"><div><div class="wt-kicker">Fleet health</div><h2>Worktree Lifecycle &amp; Fleet Health</h2></div>
        <button class="wt-clean" id="wt-clean">Clean Safe Worktrees</button></header>
      <div class="wt-metrics">
        <div class="wt-metric"><span>Active Working</span><strong>{worktree_counts["active"]}</strong></div>
        <div class="wt-metric wt-safe"><span>Safe to Prune</span><strong>{worktree_counts["safe"]}</strong></div>
        <div class="wt-metric wt-review"><span>Needs Review</span><strong>{worktree_counts["needs_review"]}</strong></div>
        <div class="wt-metric wt-dirty"><span>Dirty / Orphan</span><strong>{worktree_counts["dirty_orphan"]}</strong></div>
      </div>
      <div class="wt-table-wrap"><table class="wt-table"><thead><tr><th>Branch</th><th>Path</th><th>Status</th><th>Reason</th><th></th></tr></thead>
        <tbody>{''.join(worktree_rows) or '<tr><td colspan="5" class="obs-empty">No auxiliary worktrees found.</td></tr>'}</tbody></table></div>
      <div class="wt-result" id="wt-result" aria-live="polite"></div>
    </section>'''

    repos = snapshot.get("repos") or []
    rollups = snapshot.get("rollups") or {}
    repo_cards = "\n".join(_render_repo(repo) for repo in repos)
    if not repo_cards:
        repo_cards = '<div class="obs-empty-state">No live jobs in this workspace.</div>'

    snapshot_json = json.dumps(snapshot).replace("</", "<\\/")
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Observatory</title>
<style>
:root {{
  --bg: #0b1020;
  --panel: rgba(12, 18, 35, 0.82);
  --panel-2: rgba(18, 24, 45, 0.9);
  --line: rgba(255,255,255,0.08);
  --text: #e7edf8;
  --muted: #9aa7bd;
  --accent: #47d7b1;
  --accent-2: #7aa8ff;
  --shadow: 0 24px 80px rgba(0,0,0,.45);
  --running: #47d7b1;
  --queued: #7aa8ff;
  --failed: #ff7a90;
  --done: #9ca3af;
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; min-height: 100%; background: radial-gradient(circle at top, #18213d 0%, var(--bg) 44%, #05070f 100%); color: var(--text); font-family: "SF Mono", "JetBrains Mono", monospace; }}
body {{ padding: 24px; }}
.obs-shell {{ max-width: 1400px; margin: 0 auto; }}
.obs-hero {{
  display: flex; justify-content: space-between; align-items: flex-end; gap: 18px;
  margin-bottom: 18px; padding: 18px 20px; border: 1px solid var(--line);
  border-radius: 18px; background: linear-gradient(180deg, rgba(25,34,61,.95), rgba(12,18,35,.88));
  box-shadow: var(--shadow);
}}
.obs-title {{ font-size: 24px; font-weight: 800; letter-spacing: -0.03em; }}
.obs-subtitle {{ margin-top: 6px; color: var(--muted); font-size: 13px; }}
.obs-stats {{ display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }}
.obs-stat {{
  min-width: 120px; padding: 10px 12px; border-radius: 14px;
  background: rgba(255,255,255,0.04); border: 1px solid var(--line);
}}
.obs-stat-label {{ display: block; font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .12em; }}
.obs-stat-value {{ display: block; margin-top: 6px; font-size: 18px; font-weight: 700; }}
.obs-grid {{ display: grid; gap: 16px; }}
.obs-repo {{
  background: var(--panel); border: 1px solid var(--line); border-radius: 18px;
  overflow: hidden; box-shadow: var(--shadow);
}}
.obs-repo-header {{
  display: flex; justify-content: space-between; gap: 12px; align-items: center;
  padding: 16px 18px; background: var(--panel-2); border-bottom: 1px solid var(--line);
}}
.obs-repo-title {{ font-size: 18px; font-weight: 700; }}
.obs-repo-meta {{ margin-top: 4px; color: var(--muted); font-size: 12px; }}
.obs-job-grid {{ padding: 14px 18px 18px; }}
.obs-job-head, .obs-job {{
  display: grid; grid-template-columns: 1.2fr 1fr 1fr .9fr .9fr .9fr; gap: 10px;
  align-items: center;
}}
.obs-job-head {{
  padding: 0 6px 10px; color: var(--muted); font-size: 10px;
  text-transform: uppercase; letter-spacing: .14em;
}}
.obs-job {{
  padding: 10px 6px; border-top: 1px solid rgba(255,255,255,0.05);
  font-size: 13px;
}}
.obs-job:first-of-type {{ border-top: none; }}
.obs-job-id {{ color: var(--accent); font-weight: 700; }}
.obs-job-stage {{
  display: inline-flex; justify-self: start; padding: 4px 9px; border-radius: 999px;
  background: rgba(255,255,255,0.06); color: var(--text); font-size: 11px;
}}
.obs-job[data-stage="running"] .obs-job-stage {{ background: rgba(71, 215, 177, 0.16); color: var(--running); }}
.obs-job[data-stage="queued"] .obs-job-stage {{ background: rgba(122, 168, 255, 0.16); color: var(--queued); }}
.obs-job[data-stage="failed"] .obs-job-stage {{ background: rgba(255, 122, 144, 0.16); color: var(--failed); }}
.obs-job[data-stage="done"] .obs-job-stage {{ background: rgba(156, 163, 175, 0.16); color: var(--done); }}
.obs-job-age, .obs-job-cost, .obs-job-tokens {{ color: var(--muted); }}
.obs-empty-state, .obs-empty {{ padding: 18px 4px; color: var(--muted); }}
.wt-panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; overflow: hidden; box-shadow: var(--shadow); }}
.wt-header {{ display:flex; justify-content:space-between; align-items:center; gap:12px; padding:18px; background:var(--panel-2); border-bottom:1px solid var(--line); }}
.wt-header h2 {{ margin:4px 0 0; font-size:18px; }} .wt-kicker {{ color:var(--accent); font-size:10px; text-transform:uppercase; letter-spacing:.14em; }}
.wt-clean, .wt-inspect {{ cursor:pointer; border:1px solid rgba(71,215,177,.35); border-radius:8px; padding:8px 11px; background:rgba(71,215,177,.14); color:var(--accent); font:inherit; font-size:11px; font-weight:700; }}
.wt-metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; padding:16px 18px; }} .wt-metric {{ padding:13px; border:1px solid var(--line); border-radius:12px; background:rgba(255,255,255,.035); }}
.wt-metric span {{ display:block; color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.1em; }} .wt-metric strong {{ display:block; margin-top:7px; font-size:24px; }}
.wt-safe strong, .wt-pill.wt-safe {{ color:var(--accent); }} .wt-review strong, .wt-pill.wt-needs-review {{ color:#ffd166; }} .wt-dirty strong, .wt-pill.wt-dirty-artifact {{ color:#ff7a90; }}
.wt-table-wrap {{ overflow:auto; padding:0 18px 14px; }} .wt-table {{ width:100%; border-collapse:collapse; font-size:12px; }} .wt-table th {{ color:var(--muted); font-size:10px; text-align:left; text-transform:uppercase; letter-spacing:.1em; }} .wt-table th, .wt-table td {{ padding:11px 8px; border-top:1px solid rgba(255,255,255,.05); white-space:nowrap; }} .wt-path {{ color:var(--muted); max-width:300px; overflow:hidden; text-overflow:ellipsis; }}
.wt-pill {{ display:inline-flex; padding:4px 8px; border-radius:999px; background:rgba(255,255,255,.07); font-size:10px; font-weight:700; letter-spacing:.04em; }} .wt-result {{ padding:0 18px 14px; color:var(--muted); font-size:12px; }}
@media (max-width: 960px) {{
  body {{ padding: 16px; }}
  .obs-hero {{ flex-direction: column; align-items: flex-start; }}
  .obs-stats {{ justify-content: flex-start; }}
  .obs-job-head, .obs-job {{ grid-template-columns: 1fr 1fr; }}
  .obs-job-head span:nth-child(n+3), .obs-job > *:nth-child(n+3) {{ display: none; }}
  .wt-metrics {{ grid-template-columns:repeat(2,1fr); }} .wt-header {{ align-items:flex-start; flex-direction:column; }}
}}
</style>
</head>
<body>
<div class="obs-shell">
  <header class="obs-hero">
    <div>
      <div class="obs-title">Observatory</div>
      <div class="obs-subtitle">Live job board, refreshed every 10 seconds from <code>observatory-snapshot.json</code>.</div>
    </div>
    <div class="obs-stats" id="obs-stats">
      <div class="obs-stat"><span class="obs-stat-label">Total Cost</span><span class="obs-stat-value">{_money(rollups.get("total_cost"))}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Active</span><span class="obs-stat-value">{rollups.get("active_count", 0)}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Requests</span><span class="obs-stat-value">{rollups.get("total_requests", 0)}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Tokens</span><span class="obs-stat-value">{rollups.get("total_tokens", 0)}</span></div>
    </div>
  </header>
  <div class="obs-grid" id="obs-grid">
    {worktree_html}
    {repo_cards}
  </div>
</div>
<script>
(function() {{
  const snapshotEl = document.getElementById('obs-grid');
  const statsEl = document.getElementById('obs-stats');
  const initialSnapshot = {snapshot_json};

  function esc(value) {{
    return String(value ?? '').replace(/[&<>"]/g, (c) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
  }}

  function money(value) {{
    const n = Number(value || 0);
    return `$${{n.toFixed(2)}}`;
  }}

  function tokens(inputTokens, outputTokens) {{
    const total = Number(inputTokens || 0) + Number(outputTokens || 0);
    return total >= 1000 ? `${{(total / 1000).toFixed(1)}}k` : String(total);
  }}

  function age(seconds) {{
    seconds = Number(seconds || 0);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours) return `${{hours}}h ${{String(mins).padStart(2, '0')}}m`;
    if (minutes) return `${{minutes}}m ${{String(secs).padStart(2, '0')}}s`;
    return `${{secs}}s`;
  }}

  function renderJob(job) {{
    const stage = esc(job.stage || job.status || 'unknown');
    const repo = esc(job.repo || 'unknown');
    const jobId = esc(job.id || '—');
    const shortId = jobId.length > 8 ? jobId.slice(-8) : jobId;
    return `
      <div class="obs-job" data-stage="${{stage}}" data-repo="${{repo}}">
        <div class="obs-job-id">${{shortId}}</div>
        <div class="obs-job-agent">${{esc(job.agent || '—')}}</div>
        <div class="obs-job-stage">${{stage}}</div>
        <div class="obs-job-age">${{age(job.runtime_seconds)}}</div>
        <div class="obs-job-cost">${{money(job.cost_usd)}}</div>
        <div class="obs-job-tokens">${{tokens(job.input_tokens, job.output_tokens)}}</div>
      </div>`;
  }}

  function renderRepo(repo) {{
    const jobs = repo.jobs || [];
    const rollups = repo.rollups || {{}};
    return `
      <section class="obs-repo">
        <header class="obs-repo-header">
          <div>
            <div class="obs-repo-title">${{esc(repo.repo || 'unknown')}}</div>
            <div class="obs-repo-meta">${{jobs.length}} jobs · ${{money(rollups.total_cost)}} · ${{rollups.active_count || 0}} active</div>
          </div>
        </header>
        <div class="obs-job-grid">
          <div class="obs-job-head">
            <span>job</span><span>agent</span><span>stage</span><span>age</span><span>cost</span><span>tokens</span>
          </div>
          ${{jobs.length ? jobs.map(renderJob).join('') : '<div class="obs-empty">No jobs</div>'}}
        </div>
      </section>`;
  }}

  function renderStats(snapshot) {{
    const rollups = snapshot.rollups || {{}};
    statsEl.innerHTML = `
      <div class="obs-stat"><span class="obs-stat-label">Total Cost</span><span class="obs-stat-value">${{money(rollups.total_cost)}}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Active</span><span class="obs-stat-value">${{rollups.active_count || 0}}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Requests</span><span class="obs-stat-value">${{rollups.total_requests || 0}}</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Tokens</span><span class="obs-stat-value">${{rollups.total_tokens || 0}}</span></div>
    `;
  }}

  function render(snapshot) {{
    const repos = snapshot.repos || [];
    // Keep the lifecycle panel stable while refreshing the job board.
    const lifecycle = document.getElementById('worktree-lifecycle');
    snapshotEl.innerHTML = (lifecycle ? lifecycle.outerHTML : '') + (repos.length ? repos.map(renderRepo).join('') : '<div class="obs-empty-state">No live jobs in this workspace.</div>');
    renderStats(snapshot);
    const clean = document.getElementById('wt-clean');
    const result = document.getElementById('wt-result');
    if (clean && !clean.dataset.bound) {{
      clean.dataset.bound = '1';
      clean.addEventListener('click', async () => {{
        result.textContent = 'Cleaning safe worktrees…';
        try {{ const response = await fetch('/worktrees/clean', {{ method: 'POST', headers: Object.assign({{'Content-Type':'application/json'}}, window.vizorAuthHeaders ? window.vizorAuthHeaders() : {{}}), body: JSON.stringify({{apply:true}}) }}); const out = await response.json(); result.textContent = out.ok ? `Cleaned ${{out.cleaned_count}} safe worktree(s).` : (out.error || 'Cleanup failed.'); if (out.ok) setTimeout(refresh, 500); }} catch (err) {{ result.textContent = 'Cleanup failed: ' + err.message; }}
      }});
    }}
  }}

  async function refresh() {{
    try {{
      const response = await fetch('observatory-snapshot.json?_=' + Date.now(), {{ cache: 'no-store' }});
      if (!response.ok) return;
      render(await response.json());
    }} catch (err) {{}}
  }}

  window.__OBSERVATORY_SNAPSHOT__ = initialSnapshot;
  render(initialSnapshot);
  setInterval(refresh, 10000);
  refresh();
}})();
</script>
</body>
</html>"""
    return html_out


def generate_roles_html(data: dict, port: int) -> str:
    """Render the offline-first Workspace Agent Roles & Onboarding Studio."""
    workspace = data.get("workspace") or {}
    goals = data.get("goals") or []
    agents = [agent for agent in (data.get("workspace_agents") or []) if not agent.get("disabled")]
    cards = []
    for agent in agents:
        role = str(agent.get("role") or "unknown")
        durability = str(agent.get("durability") or "dispatch-only")
        badge = "Durable" if durability == "durable" else "Dispatch-only"
        harnesses = agent.get("target_harnesses") or ["Unassigned"]
        cards.append(f"""
        <article class="role-card">
          <div class="card-top"><span class="role-tag">@{html.escape(role)}</span>
            <span class="durability">{badge}</span></div>
          <h2>{html.escape(role.replace('-', ' ').title())}</h2>
          <div class="meta"><span>Target Harnesses</span><strong>{html.escape(', '.join(map(str, harnesses)))}</strong></div>
          <p class="excerpt">{html.escape(str(agent.get('charter_excerpt') or 'No charter excerpt available.'))}</p>
          <button class="edit" data-agent-id="{html.escape(str(agent.get('agent_id') or ''))}">Edit Charter</button>
        </article>""")
    cards_html = "\n".join(cards) or '<div class="empty">No active workspace roles yet. Provision the first one below.</div>'
    goal_summary = " · ".join(
        html.escape(str(goal.get("outcome") or goal.get("criterion") or ""))
        for goal in goals[:3] if isinstance(goal, dict)
    ) or "No active goals recorded"
    workspace_name = html.escape(str(workspace.get("name") or "workspace"))
    live = _live_js(port)
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>synlynk Vizor — Workspace Agent Roles</title>
<style>
:root{{--bg:#f6f8fa;--panel:#fff;--ink:#1f2328;--muted:#667085;--line:#d8dee4;--accent:#0d9e87;--accent-bg:#e6f7f4}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:34px 28px 70px}}.eyebrow{{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:11px}}
h1{{font-size:34px;margin:8px 0}}.subtitle{{color:var(--muted);margin:0 0 24px}}.summary{{display:flex;gap:18px;align-items:center;justify-content:space-between;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin-bottom:30px}}
.summary strong{{display:block;font-size:16px;margin-bottom:5px}}.summary span{{color:var(--muted)}}.summary .goals{{max-width:56%;text-align:right}}.section-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}}h2{{margin:0 0 12px;font-size:19px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}
.role-card,.empty{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 4px 15px #1f23280d}}.card-top{{display:flex;justify-content:space-between;align-items:center}}.role-tag{{color:var(--accent);font-weight:700}}.durability{{background:var(--accent-bg);border-radius:99px;color:#087462;padding:5px 9px;font-size:11px;font-weight:700}}.role-card h2{{margin-top:17px;text-transform:capitalize}}.meta{{border-top:1px solid var(--line);padding-top:12px;color:var(--muted);font-size:11px}}.meta strong{{display:block;color:var(--ink);font-size:13px;margin-top:4px}}.excerpt{{color:var(--muted);line-height:1.5;min-height:64px}}button{{cursor:pointer;border:0;border-radius:8px;padding:9px 13px;font-weight:700}}.edit,.primary{{background:var(--accent);color:#fff}}.empty{{color:var(--muted);padding:28px;text-align:center}}
.drawer{{margin-top:34px;background:#102a2d;color:#eefcf8;border-radius:16px;padding:24px}}.drawer h2{{color:#fff}}.drawer p{{color:#b7d4ce}}.options{{display:flex;flex-wrap:wrap;gap:9px;margin:18px 0}}.option{{background:#1b4546;color:#d6f5ef;border:1px solid #2b6463}}.option.selected{{background:#3de0c0;color:#082b2a}}form{{display:grid;grid-template-columns:1fr 1fr auto;gap:10px;align-items:end}}label{{display:flex;flex-direction:column;gap:6px;color:#b7d4ce;font-size:11px}}input,select{{border:1px solid #47736f;background:#0c2225;color:#fff;border-radius:7px;padding:10px;font:inherit}}@media(max-width:700px){{.summary,form{{display:block}}.summary .goals{{max-width:none;text-align:left;margin-top:12px}}form>*{{margin-top:10px;width:100%}}}}
</style></head><body><main>
<div class="eyebrow">Vizor / Living Workspace</div><h1>Workspace Agent Roles</h1>
<p class="subtitle">Living Charters for <strong>{workspace_name}</strong> — durable identities with visible ownership.</p>
<section class="summary"><div><strong>Workspace Persona &amp; Goals</strong><span>{len(agents)} active role(s) · governed by living charters</span></div><div class="goals"><strong>Active goals</strong><span>{goal_summary}</span></div></section>
<section><div class="section-head"><h2>Living Charters</h2><span>{len(agents)} active</span></div><div class="grid">{cards_html}</div></section>
<section class="drawer" id="provision"><h2>Onboard Workspace Role</h2><p>Choose an archetype to provision a governed identity in one click.</p>
<div class="options">{''.join(f'<button type="button" class="option{" selected" if value == "fullstack-builder" else ""}" data-archetype="{value}">{label}</button>' for value, label in (("fullstack-builder", "Fullstack Builder"), ("qa-reviewer", "QA Reviewer"), ("architect", "Architect"), ("marketing", "Marketing"), ("custom", "Custom")))}</div>
<form id="role-form"><label>Role slug<input id="role" name="role" value="fullstack-builder" required></label><label>Durability<select id="durability" name="durability"><option value="durable">Durable</option><option value="dispatch-only">Dispatch-only</option><option value="session-only">Session-only</option></select></label><button class="primary" type="submit">Provision role</button></form><div id="role-result" aria-live="polite"></div></section>
</main>{live}<script>
const options=document.querySelectorAll('.option');options.forEach(b=>b.addEventListener('click',()=>{{options.forEach(x=>x.classList.remove('selected'));b.classList.add('selected');document.querySelector('#role').value=b.dataset.archetype;}}));
document.querySelector('#role-form').addEventListener('submit',async e=>{{e.preventDefault();const result=document.querySelector('#role-result');const payload={{role:document.querySelector('#role').value.trim(),durability:document.querySelector('#durability').value}};try{{const r=await fetch('/roles/create',{{method:'POST',headers:Object.assign({{'Content-Type':'application/json'}},window.vizorAuthHeaders?window.vizorAuthHeaders():{{}}),body:JSON.stringify(payload)}});const out=await r.json();result.textContent=out.ok?'Provisioned '+out.agent_id:(out.error||'Provisioning failed');if(out.ok)setTimeout(()=>location.reload(),500);}}catch(err){{result.textContent='Provisioning failed: '+err.message;}}}});
</script></body></html>"""


def generate_board_html(port: int) -> str:
    """Render the local product board shell; cards come from product state.db."""
    live = _live_js(port)
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>synlynk Vizor — GOVERNS Board</title>
<style>
:root{--bg:#f6f8fa;--panel:#fff;--panel-2:#f1f5f9;--ink:#1f2328;--muted:#667085;--line:#d8dee4;--accent:#0d9e87;--accent-bg:#e6f7f4;--shadow:0 2px 8px rgba(31,35,40,0.06)}
@media (prefers-color-scheme: dark){
  :root{--bg:#0d1117;--panel:#161b22;--panel-2:#21262d;--ink:#f0f6fc;--muted:#8b949e;--line:#30363d;--accent:#3de0c0;--accent-bg:#0d2137;--shadow:0 2px 12px rgba(0,0,0,0.4)}
}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1600px;margin:0 auto;padding:28px 24px 70px}
.eyebrow{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:11px}
h1{font-size:30px;margin:6px 0 4px;font-weight:700}
.subtitle{color:var(--muted);margin:0 0 20px;font-size:13px}
.filters{display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin-bottom:20px;box-shadow:var(--shadow)}
select{border:1px solid var(--line);border-radius:6px;padding:6px 10px;background:var(--panel);color:var(--ink);font-size:12px;outline:none}
select:focus{border-color:var(--accent)}
.board{display:grid;grid-template-columns:repeat(7,minmax(200px,1fr));gap:12px;align-items:start;overflow-x:auto;padding-bottom:16px}
.column{background:var(--panel-2);border:1px solid var(--line);border-radius:10px;padding:10px;min-height:280px;display:flex;flex-direction:column}
.column-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--line)}
.column h2{font-size:12px;margin:0;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--ink)}
.column-count{font-size:10px;font-weight:700;padding:2px 6px;border-radius:999px;background:var(--panel);border:1px solid var(--line);color:var(--muted)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;margin-bottom:10px;box-shadow:var(--shadow);transition:transform .15s,border-color .15s}
.card:hover{border-color:var(--accent);transform:translateY(-1px)}
.card-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;gap:6px}
.status-pill{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;border:1px solid;text-transform:uppercase;letter-spacing:.03em}
.story-id{font-family:monospace;font-size:10px;color:var(--muted)}
.card h3{font-size:12px;margin:0 0 8px;line-height:1.4;font-weight:600;color:var(--ink)}
.meta{color:var(--muted);font-size:11px;margin:3px 0}
.goal-meta{color:var(--accent);font-weight:500}
.links{display:flex;gap:8px;font-size:11px;margin-top:6px}
.links a{color:var(--accent);text-decoration:none;font-weight:500}
.links a:hover{text-decoration:underline}
.card-actions{margin-top:10px;padding-top:8px;border-top:1px solid var(--line);display:flex;flex-direction:column;gap:6px}
.status-btns{display:flex;gap:4px;flex-wrap:wrap}
.st-btn{border:1px solid var(--line);background:var(--panel);border-radius:4px;padding:3px 6px;font-size:10px;cursor:pointer;font-family:inherit;font-weight:600;transition:all .15s}
.st-btn:hover{filter:brightness(.92);border-color:currentColor}
.stage-select{width:100%;font-size:10px;padding:3px 6px;border-radius:4px;border:1px solid var(--line);background:var(--bg)}
.pulse-dot{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block;animation:pdot 1.5s infinite}
@keyframes pdot{0%,100%{opacity:1}50%{opacity:.3}}
.empty{color:var(--muted);padding:24px 8px;font-size:11px;text-align:center;font-style:italic}
@media(max-width:1200px){.board{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}}
</style></head><body><main>
<div class="eyebrow">Vizor / Product graph</div>
<h1>GOVERNS Board</h1>
<p class="subtitle">Claimed work across every repository in this product mapped across the 7 GOVERNS lifecycle stages. Changes write to the product <code>state.db</code>.</p>
<div class="filters">
  <select id="repo"><option value="">All repositories</option></select>
  <select id="type"><option value="">All types</option></select>
  <select id="goal"><option value="">All goals</option></select>
  <select id="status"><option value="">All statuses</option><option value="open">Open</option><option value="ready">Ready</option><option value="in_progress">In Progress</option><option value="blocked">Blocked</option><option value="done">Done</option></select>
  <span id="identity" class="meta" style="margin-left:auto;font-weight:600;"></span>
</div>
<div id="board" class="board"></div>
</main>""" + live + """<script>
const stages=['goal','open','visualize','execute','release','notify','sustain'];
const stageIcons={goal:'◆ Goal',open:'○ Open',visualize:'◌ Visualize',execute:'⚙ Execute',release:'▲ Release',notify:'✉ Notify',sustain:'↺ Sustain'};
const statusColors={
  open:{bg:'rgba(100,116,139,0.12)',border:'#cbd5e1',color:'#64748b',label:'Open'},
  ready:{bg:'rgba(37,99,235,0.12)',border:'rgba(37,99,235,0.35)',color:'#2563eb',label:'Ready'},
  in_progress:{bg:'rgba(13,158,135,0.15)',border:'rgba(13,158,135,0.4)',color:'#0d9e87',label:'In Progress'},
  blocked:{bg:'rgba(220,38,38,0.12)',border:'rgba(220,38,38,0.35)',color:'#dc2626',label:'Blocked'},
  done:{bg:'rgba(22,163,74,0.12)',border:'rgba(22,163,74,0.35)',color:'#16a34a',label:'Done'}
};
let boardData={};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function options(id, values){const el=document.getElementById(id); values.forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;el.appendChild(o);});}
function link(pointer){return pointer&&pointer.url?`<a href="${esc(pointer.url)}" target="_blank" rel="noopener">${esc(pointer.tracker)} #${esc(pointer.id)}</a>`:'';}
function draw(){
  const repo=document.getElementById('repo').value,type=document.getElementById('type').value,goal=document.getElementById('goal').value,status=document.getElementById('status').value;
  const cards=(boardData.cards||[]).filter(c=>(!repo||c.repo_id===repo)&&(!type||c.type_id===type)&&(!goal||c.goal_id===goal)&&(!status||c.status===status));
  document.getElementById('board').innerHTML=stages.map(st=>{
    const stageCards=cards.filter(c=>(c.governs_stage||c.stage||'open')===st);
    return `<section class="column" data-stage="${st}">
      <div class="column-header"><h2>${stageIcons[st]||st}</h2><span class="column-count">${stageCards.length}</span></div>
      ${stageCards.map(c=>{
        const sc=statusColors[c.status]||statusColors.open;
        const pulseHtml=c.status==='in_progress'?'<span class="pulse-dot"></span> ':'';
        return `<article class="card" id="card-${esc(c.story_id)}">
          <div class="card-top">
            <span class="status-pill" style="background:${sc.bg};border-color:${sc.border};color:${sc.color};">${pulseHtml}${esc(sc.label)}</span>
            <span class="story-id">${esc(c.story_id)}</span>
          </div>
          <h3>${esc(c.title)}</h3>
          <div class="meta">${esc(c.repo_name||c.repo_id||'unassigned')} · ${esc(c.type_id||'untyped')}</div>
          ${c.goal_id?`<div class="meta goal-meta">🎯 ${esc(c.goal_id)}</div>`:''}
          <div class="links">${link(c.tracker)}${c.pr_url?`<a href="${esc(c.pr_url)}" target="_blank" rel="noopener">PR</a>`:''}</div>
          <div class="card-actions">
            <div class="status-btns">
              ${['ready','in_progress','done','blocked'].filter(s=>s!==c.status).map(s=>{
                const btnSc=statusColors[s]||statusColors.open;
                return `<button class="st-btn" data-id="${esc(c.story_id)}" data-status="${s}" style="color:${btnSc.color};">${esc(btnSc.label)}</button>`;
              }).join(' ')}
            </div>
            <select class="stage-select" data-id="${esc(c.story_id)}" onchange="updateStage('${esc(c.story_id)}',this.value)">
              ${stages.map(s=>`<option value="${s}" ${(c.governs_stage===s||(!c.governs_stage&&s==='open'))?'selected':''}>Move: ${stageIcons[s]}</option>`).join('')}
            </select>
          </div>
        </article>`;
      }).join('')||'<div class="empty">No cards</div>'}
    </section>`;
  }).join('');
  document.querySelectorAll('button[data-status]').forEach(b=>b.onclick=()=>updateStatus(b.dataset.id,b.dataset.status));
}
async function load(){
  const q=new URLSearchParams();
  ['repo','type','goal'].forEach(k=>{const v=document.getElementById(k).value;if(v)q.set(k+'_id',v)});
  const r=await fetch('/api/board?'+q.toString());
  if(!r.ok){document.getElementById('board').textContent='Board unavailable';return}
  boardData=await r.json();
  document.getElementById('identity').textContent='Product: '+(boardData.identity_slug||'unknown');
  draw();
}
async function updateStatus(id,status){
  const r=await fetch('/api/board/status',{method:'POST',headers:window.vizorAuthHeaders({'Content-Type':'application/json'}),body:JSON.stringify({story_id:id,status})});
  if(!r.ok){alert('Status update failed');return}
  await load();
}
async function updateStage(id,stage){
  const r=await fetch('/api/board/stage',{method:'POST',headers:window.vizorAuthHeaders({'Content-Type':'application/json'}),body:JSON.stringify({story_id:id,stage})});
  if(!r.ok){alert('Stage update failed');return}
  await load();
}
['repo','type','goal','status'].forEach(id=>document.getElementById(id).onchange=()=>id==='status'?draw():load());
fetch('/api/board').then(r=>r.json()).then(d=>{
  boardData=d;
  options('repo',d.filters.repos||[]);
  options('type',d.filters.types||[]);
  options('goal',d.filters.goals||[]);
  document.getElementById('identity').textContent='Product: '+(d.identity_slug||'unknown');
  draw();
});
</script></body></html>"""


def _enrich_graphify_html(html_str: str, graph_data: dict) -> str:
    """Enrich Graphify HTML graph with canonical community metadata, LOD zoom degree filtering, and rich sidebar."""
    if not html_str:
        return html_str

    from synlynk.viz_views import derive_canonical_community_metadata
    nodes = graph_data.get("nodes") or []
    meta_map = derive_canonical_community_metadata(nodes)

    m = re.search(r'const RAW_NODES = (\[.*?\]);', html_str, re.DOTALL)
    if m:
        try:
            raw_nodes = json.loads(m.group(1))
            for rn in raw_nodes:
                cid = rn.get("community")
                if cid in meta_map:
                    c_info = meta_map[cid]
                    cname = c_info.get("name") or rn.get("label")
                    rn["label"] = cname
                    rn["community_name"] = cname
                    rn["source_file"] = c_info.get("source_file") or rn.get("source_file") or ""
                    rn["file_type"] = c_info.get("kind") or "Module Cluster"
                    rn["_source_file"] = rn["source_file"]
                    rn["_file_type"] = rn["file_type"]
                    rn["_community_name"] = cname
                    rn["desc"] = c_info.get("desc") or ""
                    rn["_desc"] = rn["desc"]
                    rn["symbols"] = c_info.get("symbols") or []
                    rn["_symbols"] = rn["symbols"]
                    rn["title"] = f"{cname}\n{rn['desc']}\n{rn['file_type']} · {rn.get('degree', 0)} connections"
            new_nodes_json = json.dumps(raw_nodes)
            html_str = html_str[:m.start(1)] + new_nodes_json + html_str[m.end(1):]
        except Exception:
            pass

    lod_styles = """
<style>
  #graph-wrap { flex: 1; position: relative; min-width: 0; min-height: 0; }
  #graph-wrap #graph { position: absolute; inset: 0; flex: none; }
  .vis-map-zoom-bar {
    position: absolute;
    top: 16px;
    right: 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    background: rgba(26, 26, 46, 0.88);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 8px;
    padding: 6px;
    z-index: 1000;
    box-shadow: 0 4px 16px rgba(0,0,0,0.35);
    user-select: none;
    pointer-events: auto;
  }
  .vis-zoom-btn {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #fff;
    font-size: 15px;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .vis-zoom-btn:hover {
    background: rgba(255, 255, 255, 0.22);
    border-color: rgba(255, 255, 255, 0.35);
  }
  .vis-zoom-stepper {
    display: flex;
    flex-direction: column;
    gap: 3px;
    margin: 4px 0;
    width: 100%;
  }
  .vis-zoom-step {
    font-size: 10px;
    font-weight: 600;
    padding: 3px 6px;
    text-align: center;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.05);
    color: #94a3b8;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .vis-zoom-step:hover {
    background: rgba(255, 255, 255, 0.15);
    color: #e2e8f0;
  }
  .vis-zoom-step.active {
    background: #0d9e87;
    color: #ffffff;
    font-weight: bold;
    box-shadow: 0 0 8px rgba(13, 158, 135, 0.6);
  }
  .vis-zoom-badge {
    font-size: 9px;
    color: #cbd5e1;
    text-align: center;
    margin-top: 2px;
    white-space: nowrap;
    font-family: inherit;
  }
  .info-type-pill {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    background: rgba(13, 158, 135, 0.25);
    color: #2dd4bf;
    margin-bottom: 8px;
  }
  .info-desc-box {
    font-size: 12px;
    line-height: 1.5;
    color: #cbd5e1;
    margin-bottom: 12px;
    padding: 8px;
    background: rgba(0, 0, 0, 0.25);
    border-left: 3px solid #0d9e87;
    border-radius: 3px;
  }
  .info-section-title {
    margin-top: 12px;
    margin-bottom: 6px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #94a3b8;
    font-weight: 600;
  }
  .info-symbol-tag {
    display: inline-block;
    font-size: 11px;
    padding: 2px 6px;
    margin: 2px 4px 2px 0;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 3px;
    font-family: monospace;
    color: #e2e8f0;
  }
</style>
"""
    if "</head>" in html_str and ".vis-map-zoom-bar" not in html_str:
        html_str = html_str.replace("</head>", lod_styles + "</head>", 1)

    zoom_bar_html = """
<div class="vis-map-zoom-bar" id="vis-zoom-bar">
  <button type="button" class="vis-zoom-btn" onclick="zoomInStep()" title="Zoom In">+</button>
  <div class="vis-zoom-stepper">
    <div class="vis-zoom-step" data-level="3" onclick="setLODLevel(3)" title="Level 3: Micro (All symbols)">L3</div>
    <div class="vis-zoom-step" data-level="2" onclick="setLODLevel(2)" title="Level 2: Detailed (≥1 conns)">L2</div>
    <div class="vis-zoom-step" data-level="1" onclick="setLODLevel(1)" title="Level 1: Subsystem (≥2 conns)">L1</div>
    <div class="vis-zoom-step active" data-level="0" onclick="setLODLevel(0)" title="Level 0: Macro (≥3 conns)">L0</div>
  </div>
  <button type="button" class="vis-zoom-btn" onclick="zoomOutStep()" title="Zoom Out">−</button>
  <button type="button" class="vis-zoom-btn" onclick="resetFitLOD()" title="Reset / Fit Overview" style="font-size:12px;">⊙</button>
  <div class="vis-zoom-badge" id="vis-zoom-badge">L0 (≥3)</div>
</div>
"""
    if '<div id="graph"></div>' in html_str and 'id="vis-zoom-bar"' not in html_str:
        html_str = html_str.replace(
            '<div id="graph"></div>',
            '<div id="graph-wrap">' + zoom_bar_html + '<div id="graph"></div></div>',
            1,
        )

    lod_and_info_script = """
// Level-of-Detail (LOD) Manager & Enhanced Node Details
let currentLODLevel = 0; // 0: Macro (>=3), 1: Subsystem (>=2), 2: Component (>=1), 3: Micro (>=0)
const LOD_THRESHOLDS = [3, 2, 1, 0];
const LOD_SCALE_TIERS = [
  { minScale: 0.0, maxScale: 0.45, level: 0, label: 'L0 (≥3)', minDegree: 3, targetScale: 0.35 },
  { minScale: 0.45, maxScale: 0.85, level: 1, label: 'L1 (≥2)', minDegree: 2, targetScale: 0.60 },
  { minScale: 0.85, maxScale: 1.40, level: 2, label: 'L2 (≥1)', minDegree: 1, targetScale: 1.05 },
  { minScale: 1.40, maxScale: 99.0, level: 3, label: 'L3 (All)', minDegree: 0, targetScale: 1.60 }
];

let activeInspectedNodeId = null;
let inspectedEgoSet = new Set();
let activeKindFilters = null;
let currentSearchQuery = '';

function updateLODControlUI(level, visibleCount, totalCount) {
  document.querySelectorAll('.vis-zoom-step').forEach(el => {
    const elLvl = parseInt(el.dataset.level, 10);
    if (elLvl === level) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });
  const badge = document.getElementById('vis-zoom-badge');
  if (badge && LOD_SCALE_TIERS[level]) {
    badge.textContent = LOD_SCALE_TIERS[level].label;
  }
}

function growEgoNetwork(nodeId) {
  if (!nodeId || typeof network === 'undefined') return;
  inspectedEgoSet.add(String(nodeId));
  try {
    const neighbors = network.getConnectedNodes(nodeId) || [];
    neighbors.forEach(nid => inspectedEgoSet.add(String(nid)));
  } catch (_) {}
  activeInspectedNodeId = nodeId;
  showInfo(nodeId);
  applyLODAndFilter();
}

function inspectSourceCode(filePath, startLine, endLine) {
  if (window.parent && window.parent !== window) {
    window.parent.postMessage({
      type: 'open-source-drawer',
      file: filePath,
      start_line: startLine,
      end_line: endLine
    }, '*');
  }
}

function applyLODAndFilter() {
  if (typeof RAW_NODES === 'undefined' || typeof nodesDS === 'undefined') return;
  const minDegree = LOD_THRESHOLDS[currentLODLevel] !== undefined ? LOD_THRESHOLDS[currentLODLevel] : 3;
  const updates = [];
  const q = (currentSearchQuery || '').toLowerCase().trim();

  let visibleCount = 0;
  RAW_NODES.forEach(n => {
    const cKey = String(n.community);
    const isCommEnabled = typeof hiddenCommunities !== 'undefined' ? !hiddenCommunities.has(n.community) && !hiddenCommunities.has(cKey) : true;
    const k = n.file_type || n._file_type || 'Module Cluster';
    const isKindAllowed = (!activeKindFilters || activeKindFilters.size === 0 || activeKindFilters.has(k));
    const deg = n.degree || n._degree || 0;
    const meetsDegree = deg >= minDegree;
    const isInspected = inspectedEgoSet.size > 0 ? inspectedEgoSet.has(String(n.id)) : false;

    const visible = isCommEnabled && isKindAllowed && (meetsDegree || isInspected);
    if (visible) visibleCount++;

    let opacity = 1.0;
    if (q) {
      const match = (n.label || '').toLowerCase().includes(q) || (n.title || '').toLowerCase().includes(q) || (n.source_file || '').toLowerCase().includes(q);
      opacity = match ? 1.0 : 0.15;
    }
    updates.push({ id: n.id, hidden: !visible, opacity: opacity });
  });

  nodesDS.update(updates);
  updateLODControlUI(currentLODLevel, visibleCount, RAW_NODES.length);

  if (window.parent && window.parent !== window) {
    try {
      window.parent.postMessage({
        type: 'lod-status-update',
        level: currentLODLevel,
        minDegree: minDegree,
        visibleCount: visibleCount,
        totalCount: RAW_NODES.length
      }, '*');
    } catch (_) {}
  }
}

function setLODLevel(level, animate = true) {
  currentLODLevel = Math.max(0, Math.min(3, level));
  if (typeof network !== 'undefined' && LOD_SCALE_TIERS[currentLODLevel]) {
    const targetScale = LOD_SCALE_TIERS[currentLODLevel].targetScale;
    if (animate) {
      network.moveTo({ scale: targetScale, animation: { duration: 300, easingFunction: 'easeInOutQuad' } });
    }
  }
  applyLODAndFilter();
}

function zoomInStep() {
  if (typeof network !== 'undefined') {
    const curScale = network.getScale();
    const newScale = Math.min(curScale * 1.35, 3.5);
    network.moveTo({ scale: newScale, animation: { duration: 250 } });
  }
}

function zoomOutStep() {
  if (typeof network !== 'undefined') {
    const curScale = network.getScale();
    const newScale = Math.max(curScale / 1.35, 0.15);
    network.moveTo({ scale: newScale, animation: { duration: 250 } });
  }
}

function resetFitLOD() {
  currentLODLevel = 0;
  if (typeof network !== 'undefined') {
    network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
  }
  applyLODAndFilter();
}

function showInfo(nodeId) {
  if (typeof nodesDS === 'undefined') return;
  const n = nodesDS.get(nodeId);
  if (!n) return;
  activeInspectedNodeId = nodeId;

  let neighborItems = '';
  let neighborIds = [];
  if (typeof network !== 'undefined') {
    try {
      neighborIds = network.getConnectedNodes(nodeId) || [];
      neighborItems = neighborIds.map(nid => {
        const nb = nodesDS.get(nid);
        const color = nb && nb.color ? (nb.color.background || '#555') : '#555';
        const label = nb ? nb.label : nid;
        return `<span class="neighbor-link" style="border-left-color:${color}; cursor:pointer;" onclick="growEgoNetwork('${nid}')" title="Click to grow ego network around ${label}">${label}</span>`;
      }).join('');
    } catch (_) {}
  }

  const rawSymbols = n.symbols || n._symbols || [];
  const symbolsHtml = rawSymbols.map(s => {
    const symName = typeof s === 'string' ? s : (s.label || s.name || '');
    return `<span class="info-symbol-tag">${symName}</span>`;
  }).join('');

  const typeLabel = n.file_type || n._file_type || 'Module Cluster';
  const descText = n.desc || n._desc || 'Component cluster with cross-module AST connections.';
  const sourceFile = n.source_file || n._source_file || '-';
  const degCount = n.degree !== undefined ? n.degree : (n._degree !== undefined ? n._degree : 0);
  const inspectBtn = (sourceFile && sourceFile !== '-')
    ? `<a href="#" style="color:#38bdf8; margin-left:8px; font-size:11px; text-decoration:underline;" onclick="inspectSourceCode('${sourceFile}', ${n.start_line || 1}, ${n.end_line || 50}); return false;">[Inspect Source]</a>`
    : '';

  const infoEl = document.getElementById('info-content');
  if (infoEl) {
    infoEl.innerHTML = `
      <div style="font-size:14px; font-weight:700; color:#fff; margin-bottom:4px; word-break:break-word;">${n.label}</div>
      <div class="info-type-pill">${typeLabel}</div>
      
      <div class="info-desc-box">
        ${descText}
      </div>

      <div class="field" style="font-size:12px; margin-bottom:4px;"><b>Source:</b> <code style="color:#38bdf8;">${sourceFile}</code>${inspectBtn}</div>
      <div class="field" style="font-size:12px; margin-bottom:4px;"><b>Community:</b> ${n.community !== undefined ? n.community : '-'}</div>
      <div class="field" style="font-size:12px; margin-bottom:8px;"><b>Connectivity:</b> <span style="font-weight:600; color:#2dd4bf;">${degCount}</span> edges</div>

      ${symbolsHtml ? `<div class="info-section-title">Contained Symbols (${rawSymbols.length})</div><div style="margin-bottom:10px;">${symbolsHtml}</div>` : ''}

      ${neighborIds.length ? `<div class="info-section-title">Connected Neighbors (${neighborIds.length})</div><div id="neighbors-list" style="max-height:160px; overflow-y:auto;">${neighborItems}</div>` : ''}
    `;
  }
}

if (typeof network !== 'undefined') {
  network.on('zoom', function(params) {
    const scale = params.scale;
    let newLevel = 0;
    for (const tier of LOD_SCALE_TIERS) {
      if (scale >= tier.minScale && scale < tier.maxScale) {
        newLevel = tier.level;
        break;
      }
    }
    if (newLevel !== currentLODLevel) {
      currentLODLevel = newLevel;
      applyLODAndFilter();
    }
  });

  network.on('selectNode', function(params) {
    if (params.nodes && params.nodes.length > 0) {
      const selId = params.nodes[0];
      if (inspectedEgoSet.size > 0 && inspectedEgoSet.has(String(selId))) {
        growEgoNetwork(selId);
      } else {
        inspectedEgoSet.clear();
        growEgoNetwork(selId);
      }
    }
  });

  network.on('deselectNode', function() {
    activeInspectedNodeId = null;
    inspectedEgoSet.clear();
    applyLODAndFilter();
  });

  network.once('afterDrawing', function() {
    applyLODAndFilter();
  });
}

// Global Message Listener for Parent Vizor Windows
window.addEventListener('message', function(e) {
  if (!e.data) return;
  if (e.data.type === 'set-lod') {
    if (e.data.level !== undefined) setLODLevel(e.data.level);
  } else if (e.data.type === 'filter-community') {
    const comm = e.data.community;
    const enabled = e.data.enabled;
    if (typeof hiddenCommunities !== 'undefined') {
      if (enabled) {
        hiddenCommunities.delete(comm);
        hiddenCommunities.delete(parseInt(comm, 10));
      } else {
        hiddenCommunities.add(comm);
        hiddenCommunities.add(parseInt(comm, 10));
      }
    }
    applyLODAndFilter();
  } else if (e.data.type === 'filter-communities-batch') {
    const enabledMap = e.data.enabledMap || {};
    const allEnabled = e.data.allEnabled;
    if (typeof hiddenCommunities !== 'undefined' && typeof LEGEND !== 'undefined') {
      LEGEND.forEach(c => {
        let isEnabled = true;
        if (allEnabled !== undefined) {
          isEnabled = allEnabled;
        } else if (enabledMap[String(c.cid)] !== undefined) {
          isEnabled = enabledMap[String(c.cid)];
        }
        if (isEnabled) {
          hiddenCommunities.delete(c.cid);
          hiddenCommunities.delete(String(c.cid));
        } else {
          hiddenCommunities.add(c.cid);
          hiddenCommunities.add(String(c.cid));
        }
      });
    }
    applyLODAndFilter();
  } else if (e.data.type === 'filter-kind-l0') {
    activeKindFilters = Array.isArray(e.data.kinds) ? new Set(e.data.kinds) : null;
    applyLODAndFilter();
  } else if (e.data.type === 'grow-ego-network') {
    growEgoNetwork(e.data.nodeId);
  } else if (e.data.type === 'reset-inspect') {
    activeInspectedNodeId = null;
    inspectedEgoSet.clear();
    applyLODAndFilter();
  } else if (e.data.type === 'search') {
    currentSearchQuery = e.data.query || '';
    applyLODAndFilter();
  } else if (e.data.type === 'theme-change') {
    const theme = e.data.theme;
    if (theme === 'dark') {
      document.body.style.background = '#0d0f14';
      document.body.style.color = '#c9d1d9';
    } else {
      document.body.style.background = '#ffffff';
      document.body.style.color = '#1f2328';
    }
  }
});
"""

    if "</script>" in html_str and "LOD_THRESHOLDS" not in html_str:
        last_script = html_str.rfind("</script>")
        html_str = html_str[:last_script] + lod_and_info_script + html_str[last_script:]

    return html_str



def _write_cache(data: dict, port: int) -> None:
    """Generate all views and write to viz-cache/."""
    os.makedirs(VIZ_CACHE_DIR, exist_ok=True)
    views = {
        "index.html": generate_index_html(data, port),
        "overview.html": generate_overview_html(data, port),
        "activity.html": generate_activity_stream_html(data, port),
        "board.html": generate_board_html(port),
        "gantt.html": generate_gantt_html(data, port),
        "tube.html": generate_architect_map_html(data, port),
        "product.html": generate_product_html(data, port),
        "logical.html": generate_logical_html(data, port),
        "world.html": generate_world_html(data, port),
        "infra.html": generate_infra_html(data, port),

        "roles.html": generate_roles_html(data, port),
        "journeys.html": (
            '<!DOCTYPE html><html><head><meta charset="UTF-8">'
            '<meta http-equiv="refresh" content="0; url=product.html">'
            '<title>synlynk Vizor — Redirecting</title></head>'
            '<body>Redirecting to <a href="product.html">Product View</a>...'
            '<script>window.location.replace("product.html");</script>'
            "</body></html>"
        ),
        "effort.html": generate_effort_html(data, port),
        "efficiency.html": generate_efficiency_html(data, port),
        "observatory.html": generate_observatory_html(data.get("observatory") or {}),
    }
    for filename, html in views.items():
        with open(os.path.join(VIZ_CACHE_DIR, filename), "w") as f:
            f.write(html)

    # Copy graphify.html to cache if present in workspace and enrich with canonical labels
    graphify_src = os.path.join(os.getcwd(), ".synlynk", "graphify-out", "graph.html")
    graphify_json_src = os.path.join(os.getcwd(), ".synlynk", "graphify-out", "graph.json")
    if os.path.isfile(graphify_src):
        try:
            with open(graphify_src, "r", encoding="utf-8") as gf:
                html_str = gf.read()
            graph_data = {}
            if os.path.isfile(graphify_json_src):
                with open(graphify_json_src, "r", encoding="utf-8") as jf:
                    graph_data = json.load(jf)
            elif (data.get("workspace_views") or {}).get("logical"):
                graph_data = {"nodes": (data.get("workspace_views") or {}).get("logical", {}).get("nodes", [])}
            enriched_html = _enrich_graphify_html(html_str, graph_data)
            with open(os.path.join(VIZ_CACHE_DIR, "graphify.html"), "w", encoding="utf-8") as out_f:
                out_f.write(enriched_html)
            with open(os.path.join(VIZ_CACHE_DIR, "graph.html"), "w", encoding="utf-8") as out_f:
                out_f.write(enriched_html)
        except Exception:
            try:
                shutil.copyfile(graphify_src, os.path.join(VIZ_CACHE_DIR, "graphify.html"))
                shutil.copyfile(graphify_src, os.path.join(VIZ_CACHE_DIR, "graph.html"))
            except Exception:
                pass

    manifest = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "version": "0.1"}
    with open(os.path.join(VIZ_CACHE_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f)


def get_role_manifest_payload(
    role: str,
    repo_name: str = "workspace",
    port: int = 27472,
    org: str = "",
    project_slug: str = "",
    owner: str = "",
) -> dict:
    """Generate GitHub App Manifest payload for a specific workspace role."""
    role = role.lower()
    permissions = {
        "metadata": "read",
        "contents": "write",
        "pull_requests": "write",
        "issues": "write",
    }
    if role in ("qa", "dev", "infra"):
        permissions["checks"] = "write"
        permissions["statuses"] = "write"

    slug = project_slug or repo_name
    owner_str = (owner or org or "").lower().strip()

    role_abbr = {
        "architect": "arch",
        "marketing": "mktg",
    }.get(role, role)

    prefix = "syn"

    if owner_str:
        # Format: syn-{owner}-{slug}-{role}
        # Fixed: prefix (3) + 3 hyphens + role_abbr = 6 + len(role_abbr)
        avail = 34 - len(prefix) - len(role_abbr) - 3
        if len(owner_str) + len(slug) > avail:
            capped_owner = owner_str[:10].rstrip("-")
            avail_slug = max(1, avail - len(capped_owner))
            clean_slug = slug[:avail_slug].rstrip("-")
            app_name = f"{prefix}-{capped_owner}-{clean_slug}-{role_abbr}"
        else:
            app_name = f"{prefix}-{owner_str}-{slug}-{role_abbr}"
    else:
        # Format: syn-{slug}-{role}
        avail_slug = 34 - len(prefix) - len(role_abbr) - 2
        clean_slug = slug[:avail_slug].rstrip("-")
        app_name = f"{prefix}-{clean_slug}-{role_abbr}"

    if len(app_name) > 34:
        app_name = app_name[:34].rstrip("-")

    return {
        "name": app_name,
        "url": "https://synlynk.com",
        "hook_attributes": {
            "url": f"https://synlynk.com/github-apps/{slug}/{role}/webhook",
            "active": False,
        },
        "redirect_url": (
            f"http://localhost:{port}/auth/callback?role={role}&state={slug}"
            if project_slug else f"http://localhost:{port}/auth/callback?role={role}"
        ),
        "public": False,
        "default_permissions": permissions,
        "default_events": [],
    }


def handle_github_app_conversion(code: str, role: str, repo_root: str = ".") -> dict:
    """Exchange GitHub App manifest conversion code and write credentials."""
    import urllib.request
    from pathlib import Path

    url = f"https://api.github.com/app-manifests/{code}/conversions"
    req = urllib.request.Request(url, method="POST", headers={"Accept": "application/vnd.github+json"})

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    app_id = data.get("id")
    pem = data.get("pem")

    root = Path(repo_root).resolve()
    role_dir = root / ".synlynk" / "github_apps" / role
    role_dir.mkdir(parents=True, exist_ok=True)

    app_json_path = role_dir / f"{role}.app.json"
    pem_path = role_dir / f"{role}.private-key.pem"

    app_json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if pem:
        pem_path.write_text(pem, encoding="utf-8")
    os.chmod(str(app_json_path), 0o600)
    if pem_path.exists():
        os.chmod(str(pem_path), 0o600)

    # Also persist standard flat files expected by synlynk doctor and team.py
    apps_dir = root / ".synlynk" / "github_apps"
    legacy_json_path = apps_dir / f"{role}.json"
    legacy_pem_path = apps_dir / f"{role}.pem"
    if pem:
        legacy_pem_path.write_text(pem, encoding="utf-8")
        try:
            os.chmod(str(legacy_pem_path), 0o600)
        except OSError:
            pass

    flat_config = {
        "role": role,
        "app_id": app_id,
        "client_id": data.get("client_id"),
        "app_slug": data.get("slug") or data.get("name") or role,
        "installation_id": data.get("installation_id"),
        "private_key_path": str(legacy_pem_path if legacy_pem_path.exists() else pem_path),
    }
    legacy_json_path.write_text(json.dumps(flat_config, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(str(legacy_json_path), 0o600)
    except OSError:
        pass

    try:
        from synlynk.github_app_auth import refresh_installation_token
        from synlynk.product_store import resolve_github_apps_dir
        refresh_installation_token(role, apps_dir=str(resolve_github_apps_dir(str(root))))
    except Exception:
        pass

    return {"ok": True, "role": role, "app_id": app_id, "slug": data.get("slug")}


def generate_onboarding_html(data: dict = None, port: int = 27472) -> str:
    """Generate self-contained HTML for onboarding 3-view canvas and artifact tour."""
    import html as _html

    data = data or {}
    industry = _html.escape(data.get("domain", {}).get("industry", "Application Service"))

    try:
        from synlynk.coldstart import get_onboarding_recommendations
        recs = get_onboarding_recommendations()
    except Exception:
        recs = []

    recs_cards = []
    for rec in recs:
        name = _html.escape(str(rec.get("name", "")))
        label = _html.escape(str(rec.get("label", name)))
        desc = _html.escape(str(rec.get("description", "")))
        installed = rec.get("installed", False)
        if installed:
            recs_cards.append(f"""
    <div class="tool-item installed" style="background: #161b22; border: 1px solid #238636; border-radius: 8px; padding: 14px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
      <div style="display: flex; align-items: center; gap: 12px;">
        <input type="checkbox" id="tool-{name}" checked disabled style="width: 18px; height: 18px; accent-color: #238636;" />
        <div>
          <label for="tool-{name}" style="font-weight: 600; color: #f0f3f6;">{label}</label>
          <div style="font-size: 13px; color: #8b949e; margin-top: 2px;">{desc}</div>
        </div>
      </div>
      <span class="badge" style="background: #238636; font-size: 12px; padding: 4px 8px; border-radius: 4px; color: #fff;">Installed</span>
    </div>""")
        else:
            recs_cards.append(f"""
    <div class="tool-item recommended" style="background: #161b22; border: 1px solid #388bfd; border-radius: 8px; padding: 14px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
      <div style="display: flex; align-items: center; gap: 12px;">
        <input type="checkbox" id="tool-{name}" checked style="width: 18px; height: 18px; accent-color: #1f6feb;" />
        <div>
          <label for="tool-{name}" style="font-weight: 600; color: #f0f3f6; cursor: pointer;">{label}</label>
          <div style="font-size: 13px; color: #8b949e; margin-top: 2px;">{desc}</div>
        </div>
      </div>
      <form method="POST" action="/tools/install" style="margin: 0;">
        <input type="hidden" name="tool" value="{name}" />
        <button type="submit" class="btn-install" style="background: #238636; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 13px;">1-Click Install</button>
      </form>
    </div>""")

    tools_html = "".join(recs_cards) if recs_cards else "<p style='color: #8b949e;'>All recommended ecosystem tools are installed.</p>"

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Synlynk Onboarding Canvas</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background: #0f1419; color: #f0f3f6; }}
    .header {{ padding: 20px; border-bottom: 1px solid #21262d; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; padding: 20px; }}
    .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
    .badge {{ background: #1f6feb; color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
    .tour {{ margin: 20px; padding: 16px; background: #0d1117; border: 1px solid #238636; border-radius: 8px; }}
    .recommendations {{ margin: 20px; padding: 16px; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Synlynk Onboarding — {industry}</h1>
    <span class="badge">Local Offline Canvas</span>
  </div>
  <div class="grid">
    <div class="card"><h3>View 1: Physical File Tree</h3><p>Directories, frameworks, and component boundaries.</p></div>
    <div class="card"><h3>View 2: Logical Tubemap</h3><p>Data streams and entity lifecycles.</p></div>
    <div class="card"><h3>View 3: Application Screens</h3><p>Discovered routes and cloud topology.</p></div>
  </div>
  <div class="recommendations">
    <h2>Recommended Ecosystem Tools &amp; Substrates</h2>
    <p style="color: #8b949e; font-size: 14px; margin-bottom: 16px;">Deterministic AST knowledge graphs and official developer CLI tools for multi-agent hybrid workgroups.</p>
    {tools_html}
  </div>
  <div class="tour">
    <h2>Behind the Curtain: The Coordination Substrate</h2>
    <ul>
      <li><strong>state.db:</strong> SQLite persistent ledger tracking goals, stories, and jobs.</li>
      <li><strong>.synlynk/context.md:</strong> Real-time situational awareness snapshot.</li>
      <li><strong>project-docs/:</strong> Living 4-doc governance (roadmap.md, todo.md, memory.md, devlogs/).</li>
      <li><strong>.worktrees/:</strong> Clean, isolated task execution sandboxes.</li>
    </ul>
  </div>
</body>
</html>"""



def generate_roles_onboarding_html(repo_root: str = ".", port: int = 27472) -> str:
    """Generate in-browser role provisioning wizard HTML."""
    from pathlib import Path
    import html as _html

    root = Path(repo_root).resolve()
    repo_name = root.name
    roles_dir = root / ".synlynk" / "github_apps"

    owner_type = "user"
    owner_login = ""
    project_slug = repo_name
    try:
        from synlynk.team import _resolve_repo_owner
        owner_type, owner_login = _resolve_repo_owner(cwd=str(root))
    except Exception:
        pass

    owner_slug = ""
    try:
        cfg_path = root / ".synlynk" / "config.json"
        if cfg_path.exists():
            cfg_data = json.loads(cfg_path.read_text(encoding="utf-8"))
            if cfg_data.get("identity_slug"):
                project_slug = cfg_data["identity_slug"]
            elif cfg_data.get("repo"):
                project_slug = cfg_data["repo"]
            if cfg_data.get("owner_slug"):
                owner_slug = cfg_data["owner_slug"]
    except Exception:
        pass

    effective_owner = owner_slug or owner_login
    org_name = owner_login if owner_type == "org" else ""
    form_action = (
        f"https://github.com/organizations/{owner_login}/settings/apps/new"
        if owner_type == "org" and owner_login
        else "https://github.com/settings/apps/new"
    )

    roles_info = [
        ("pm", "Program Manager", "claude", "Roadmap, goal tracking, issue triage, and named release narratives."),
        ("tpm", "Technical Program Manager", "claude", "Milestone execution loop, cross-harness sweeps, and dependency tracking."),
        ("qa", "QA Engineer", "claude", "Autonomous PR review, test validation, and merge-gate authority."),
        ("dev", "Software Developer", "codex", "Core implementation, tests, bugfixes, refactoring, and PR creation."),
        ("architect", "Lead Architect", "claude", "System architecture, specifications, technical decisions, and charter governance."),
        ("marketing", "Marketing Engineer", "agy", "Release communications, documentation compilation, and build diary blogs."),
        ("infra", "DevOps & Infrastructure", "grok", "Pulumi IaC, AWS cloud resource management, and CI/CD pipelines."),
    ]

    cards_html = []
    for slug, title, default_harness, desc in roles_info:
        role_app = roles_dir / slug / f"{slug}.app.json"
        legacy_role_app = roles_dir / f"{slug}.json"
        is_configured = role_app.exists() or legacy_role_app.exists()

        conf = {}
        if legacy_role_app.exists():
            try:
                conf = json.loads(legacy_role_app.read_text(encoding="utf-8"))
            except Exception:
                pass
        elif role_app.exists():
            try:
                conf = json.loads(role_app.read_text(encoding="utf-8"))
            except Exception:
                pass

        installation_id = conf.get("installation_id")
        app_slug = conf.get("app_slug") or conf.get("slug") or slug

        if is_configured and installation_id:
            badge = '<span class="badge configured">✓ Installed & Active</span>'
            btn_html = '<button class="btn configured-btn" disabled>Active Role</button>'
            app_name_display = app_slug
        elif is_configured:
            badge = '<span class="badge configured" style="background:#f59e0b;color:#000;">Pending Installation</span>'
            btn_html = f'''<div style="display:flex;gap:8px;flex-direction:column;">
                <a href="https://github.com/apps/{app_slug}/installations/new" target="_blank" class="btn primary-btn" style="text-align:center;text-decoration:none;padding:8px 12px;">Install on GitHub ↗</a>
                <a href="/auth/sync?role={slug}" class="btn" style="text-align:center;text-decoration:none;padding:8px 12px;background:#283044;color:#f0f3f8;">Sync Installation ID</a>
            </div>'''
            app_name_display = app_slug
        else:
            badge = '<span class="badge unconfigured">Not Configured</span>'
            manifest = get_role_manifest_payload(
                slug,
                repo_name=repo_name,
                port=port,
                org=org_name,
                project_slug=project_slug,
                owner=effective_owner,
            )
            app_name_display = manifest.get("name", "")
            manifest_json = json.dumps(manifest)
            escaped = _html.escape(manifest_json, quote=True)
            btn_html = f'''<form action="{form_action}" method="POST" target="_blank">
                <input type="hidden" name="manifest" value="{escaped}">
                <button type="submit" class="btn primary-btn">Provision with GitHub</button>
            </form>'''

        cards_html.append(f'''
        <div class="role-card">
            <div class="card-header">
                <h3>{title} (<code>{slug}</code>)</h3>
                {badge}
            </div>
            <p class="role-desc">{desc}</p>
            <div class="role-meta">Default Harness: <strong>{default_harness}</strong> &bull; App: <code>{app_name_display}</code></div>
            <div class="card-actions">
                {btn_html}
            </div>
        </div>
        ''')

    cards_joined = "".join(cards_html)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>synlynk Vizor — Workspace Role Provisioning Wizard</title>
    <style>
        :root {{
            --bg-base: #0f1117;
            --bg-card: #181c27;
            --border: #283044;
            --text-main: #f0f3f8;
            --text-muted: #8b9bb4;
            --accent: #6366f1;
            --accent-hover: #4f46e5;
            --green: #10b981;
            --yellow: #f59e0b;
        }}
        body {{
            background: var(--bg-base);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 32px;
        }}
        header {{
            max-width: 1100px;
            margin: 0 auto 32px auto;
        }}
        h1 {{
            font-size: 28px;
            margin: 0 0 8px 0;
            color: #fff;
        }}
        p.subtitle {{
            color: var(--text-muted);
            margin: 0;
            font-size: 15px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            max-width: 1100px;
            margin: 0 auto 32px auto;
        }}
        .role-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .card-header h3 {{
            margin: 0;
            font-size: 18px;
        }}
        .badge {{
            font-size: 12px;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
        }}
        .badge.configured {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--green);
            border: 1px solid var(--green);
        }}
        .badge.unconfigured {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--yellow);
            border: 1px solid var(--yellow);
        }}
        .role-desc {{
            color: var(--text-muted);
            font-size: 14px;
            line-height: 1.5;
            margin: 0 0 16px 0;
        }}
        .role-meta {{
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 16px;
        }}
        .btn {{
            width: 100%;
            padding: 10px;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            font-size: 14px;
            transition: all 0.2s ease;
        }}
        .primary-btn {{
            background: var(--accent);
            color: #fff;
        }}
        .primary-btn:hover {{
            background: var(--accent-hover);
        }}
        .configured-btn {{
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-muted);
            cursor: default;
        }}
        .readiness-card {{
            max-width: 1100px;
            margin: 0 auto;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 24px;
        }}
        .readiness-card h2 {{
            margin-top: 0;
            font-size: 20px;
        }}
        .point-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid var(--border);
            font-size: 14px;
        }}
        .point-row:last-child {{
            border-bottom: none;
        }}
    </style>
</head>
<body>
    <header>
        <h1>Workspace Role Provisioning Wizard</h1>
        <p class="subtitle">1-Click GitHub App provisioning for autonomous fleet agents in <strong>{repo_name}</strong>.</p>
    </header>

    <div class="grid">
        {cards_joined}
    </div>

    <div class="readiness-card">
        <h2>Live 4-Point Fleet Readiness Matrix</h2>
        <div id="readiness-container">Loading live readiness points...</div>
    </div>

    <script>
        async function fetchReadiness() {{
            try {{
                const res = await fetch('/api/readiness/live');
                const data = await res.json();
                const container = document.getElementById('readiness-container');
                if (!data.points) return;
                let html = '';
                for (const p of data.points) {{
                    const color = p.status === 'PASS' ? '#10b981' : (p.status === 'WARN' ? '#f59e0b' : '#ef4444');
                    html += `<div class="point-row">
                        <span><strong>${{p.name}}</strong>: ${{p.message}}</span>
                        <span style="color: ${{color}}; font-weight: 600;">${{p.status}}</span>
                    </div>`;
                }}
                container.innerHTML = html;
            }} catch (err) {{
                console.error('Readiness poll error:', err);
            }}
        }}
        fetchReadiness();
        setInterval(fetchReadiness, 3000);
    </script>
</body>
</html>'''


def _get_source_slice(
    repo_root: str,
    file_rel_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> dict:
    """Safely fetch and slice source code lines from workspace with path traversal protection."""
    try:
        norm_root = os.path.abspath(repo_root)
        target_abs = os.path.abspath(os.path.join(norm_root, file_rel_path.lstrip("/")))

        # Path traversal guard
        if not (target_abs == norm_root or target_abs.startswith(norm_root + os.sep)):
            return {"status": "error", "error": "Path traversal rejected", "code": 403}

        if not os.path.isfile(target_abs):
            return {"status": "error", "error": f"File not found: {file_rel_path}", "code": 404}

        content = Path(target_abs).read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        total_lines = len(lines)

        s = max(1, start_line) if start_line is not None else 1
        e = min(total_lines, end_line) if end_line is not None else total_lines

        if s > total_lines or s > e:
            sliced = ""
        else:
            sliced = "\n".join(lines[s - 1:e])

        ext = os.path.splitext(file_rel_path)[1].lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".md": "markdown",
            ".sh": "bash",
            ".toml": "toml",
            ".yaml": "yaml",
            ".yml": "yaml",
        }
        lang = lang_map.get(ext, "text")

        return {
            "status": "ok",
            "file": file_rel_path,
            "start_line": s,
            "end_line": e,
            "total_lines": total_lines,
            "content": sliced,
            "language": lang,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "code": 500}


class VizorHandler(http.server.SimpleHTTPRequestHandler):
    """Serves viz-cache/ and handles Vizor POST routes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.abspath(VIZ_CACHE_DIR), **kwargs)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        return json.loads(body)

    def _drain_body(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            length = 0
        if length > 0:
            self.rfile.read(length)

    def _authorize_write(self) -> bool:
        from synlynk.local_http_auth import authorize_local_request

        ok, code, message = authorize_local_request(self.headers)
        if ok:
            return True
        self._drain_body()
        self.send_error(code, message)
        return False

    def _send_json_ok(self, payload: dict):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/api/source", "/api/v1/source") or path.endswith("/api/source"):
            params = parse_qs(parsed.query)
            file_param = params.get("file", [""])[0]
            start_p = params.get("start", [None])[0]
            end_p = params.get("end", [None])[0]
            slug_p = params.get("slug", [None])[0]

            s_line = int(start_p) if start_p and start_p.isdigit() else None
            e_line = int(end_p) if end_p and end_p.isdigit() else None

            repo_root = "."
            if slug_p:
                try:
                    from synlynk.state_registry import get_registered_product
                    entry = get_registered_product(slug_p)
                    if entry and entry.get("repo_path"):
                        repo_root = entry["repo_path"]
                except Exception:
                    pass

            res = _get_source_slice(repo_root, file_param, s_line, e_line)
            status_code = 200 if res["status"] == "ok" else res.get("code", 400)
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        if path in ("/graphify", "/graph"):
            self.send_response(302)
            self.send_header("Location", "/graphify.html")
            self.end_headers()
            return

        if path in ("/onboarding", "/onboarding/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            port = getattr(self.server, "server_port", 27472)
            html = generate_onboarding_html(port=port)
            self.wfile.write(html.encode("utf-8"))
            return

        if path in ("/onboarding/roles", "/onboarding/roles/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            port = getattr(self.server, "server_port", 27472)
            html = generate_roles_onboarding_html(port=port)
            self.wfile.write(html.encode("utf-8"))
            return

        if path == "/auth/callback":
            params = parse_qs(parsed.query)
            code = params.get("code", [""])[0]
            role = params.get("role", [""])[0] or "qa"
            state_slug = params.get("state", [""])[0]
            redirect_target = (
                f"/w/{state_slug}/onboarding/roles?success={role}"
                if state_slug else f"/onboarding/roles?success={role}"
            )
            if code:
                try:
                    handle_github_app_conversion(code=code, role=role)
                    self.send_response(302)
                    self.send_header("Location", redirect_target)
                    self.end_headers()
                    return
                except Exception as e:
                    self.send_error(500, f"GitHub App conversion error: {e}")
                    return
            self.send_error(400, "Missing code query param")
            return

        if path == "/auth/sync":
            params = parse_qs(parsed.query)
            role = params.get("role", [""])[0]
            if role:
                try:
                    from pathlib import Path
                    from synlynk.github_app_auth import _sign_jwt, refresh_installation_token
                    from synlynk.product_store import resolve_github_apps_dir
                    from urllib.request import Request, urlopen
                    root = Path(".").resolve()
                    apps_dir = resolve_github_apps_dir(str(root))
                    json_path = apps_dir / f"{role}.json"
                    app_json_path = apps_dir / role / f"{role}.app.json"
                    target_path = json_path if json_path.exists() else app_json_path
                    if target_path.exists():
                        conf = json.loads(target_path.read_text(encoding="utf-8"))
                        app_id = conf.get("app_id") or conf.get("id")
                        pem_path = conf.get("private_key_path")
                        if not pem_path or not os.path.exists(pem_path):
                            cand_pem = apps_dir / f"{role}.pem"
                            cand_pem2 = apps_dir / role / f"{role}.private-key.pem"
                            pem_path = str(cand_pem if cand_pem.exists() else cand_pem2)
                        if app_id and pem_path and os.path.exists(pem_path):
                            jwt = _sign_jwt(app_id, pem_path)
                            req = Request(
                                "https://api.github.com/app/installations",
                                headers={
                                    "Accept": "application/vnd.github+json",
                                    "Authorization": f"Bearer {jwt}",
                                    "X-GitHub-Api-Version": "2022-11-28",
                                    "User-Agent": "synlynk-viz",
                                }
                            )
                            with urlopen(req) as resp:
                                inst_payload = json.loads(resp.read().decode("utf-8"))
                            inst_list = inst_payload if isinstance(inst_payload, list) else inst_payload.get("installations", [])
                            if inst_list and isinstance(inst_list[0], dict) and "id" in inst_list[0]:
                                inst_id = inst_list[0]["id"]
                                conf["installation_id"] = inst_id
                                target_path.write_text(json.dumps(conf, indent=2) + "\n", encoding="utf-8")
                                if json_path.exists() and target_path != json_path:
                                    jconf = json.loads(json_path.read_text(encoding="utf-8"))
                                    jconf["installation_id"] = inst_id
                                    json_path.write_text(json.dumps(jconf, indent=2) + "\n", encoding="utf-8")
                                if app_json_path.exists() and target_path != app_json_path:
                                    aconf = json.loads(app_json_path.read_text(encoding="utf-8"))
                                    aconf["installation_id"] = inst_id
                                    app_json_path.write_text(json.dumps(aconf, indent=2) + "\n", encoding="utf-8")
                                try:
                                    refresh_installation_token(role, conf, apps_dir=str(apps_dir))
                                except Exception:
                                    pass
                except Exception:
                    pass
            self.send_response(302)
            self.send_header("Location", f"/onboarding/roles?synced={role}")
            self.end_headers()
            return

        if path == "/api/readiness/live":
            from synlynk.readiness import evaluate_readiness_matrix
            matrix = evaluate_readiness_matrix()
            self._send_json_ok(matrix)
            return

        if path == "/api/board":
            from synlynk.board import board_data
            filters = parse_qs(parsed.query)
            try:
                payload = board_data(
                    repo_id=(filters.get("repo_id") or [None])[0],
                    type_id=(filters.get("type_id") or [None])[0],
                    goal_id=(filters.get("goal_id") or [None])[0],
                )
            except FileNotFoundError:
                payload = {"identity_slug": "", "cards": [], "filters": {"repos": [], "types": [], "goals": []}}
            self._send_json_ok(payload)
            return

        super().do_GET()

    def do_OPTIONS(self):
        clean_path = self.path.split("?")[0]
        valid_paths = ("/note", "/dispatch", "/approve", "/kill", "/architect-map/view-pref", "/roles/create", "/worktrees/clean", "/tools/install", "/api/tools/install", "/api/board/status", "/api/board/stage", "/graph/refresh", "/api/graph/refresh", "/api/v1/graph/refresh")
        if clean_path not in valid_paths and not clean_path.endswith("/api/graph/refresh") and not clean_path.endswith("/api/tools/install"):
            self.send_error(404)
            return
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        if not self._authorize_write():
            return
        clean_path = self.path.split("?")[0]
        if clean_path == "/note":
            self._handle_note_request()
        elif clean_path == "/dispatch":
            self._handle_dispatch_request()
        elif clean_path == "/approve":
            self._handle_approve_request()
        elif clean_path == "/kill":
            self._handle_kill_request()
        elif clean_path == "/architect-map/view-pref":
            self._handle_view_pref_request()
        elif clean_path == "/roles/create":
            self._handle_role_create_request()
        elif clean_path == "/worktrees/clean":
            self._handle_worktree_clean_request()
        elif clean_path in ("/tools/install", "/api/tools/install") or clean_path.endswith("/api/tools/install"):
            self._handle_tool_install_request()
        elif clean_path == "/api/board/status" or clean_path.endswith("/api/board/status"):
            self._handle_board_status_request()
        elif clean_path == "/api/board/stage" or clean_path.endswith("/api/board/stage"):
            self._handle_board_stage_request()
        elif clean_path in ("/graph/refresh", "/api/graph/refresh", "/api/v1/graph/refresh") or clean_path.endswith("/api/graph/refresh"):
            self._handle_graph_refresh_request()
        else:
            self.send_error(404)

    def _handle_graph_refresh_request(self):
        try:
            from synlynk.scan import _run_graphify_extract
            clean_path = self.path.split("?")[0]
            slug = None
            if clean_path.startswith("/w/"):
                parts = clean_path.strip("/").split("/")
                if len(parts) >= 2:
                    slug = parts[1]
            elif clean_path.startswith("/"):
                parts = clean_path.strip("/").split("/")
                if len(parts) >= 3 and parts[-2] == "api" and parts[-1] == "refresh":
                    slug = parts[0]

            repo_root = None
            if slug:
                try:
                    from synlynk.vizor_daemon import _registered_workspaces
                    workspaces = _registered_workspaces()
                    if slug in workspaces:
                        repo_root = workspaces[slug].get("repo_path")
                except Exception:
                    pass

            if not repo_root:
                repo_root = os.getcwd()

            success = _run_graphify_extract(repo_root)
            if not success:
                self.send_error(500, "Graph extraction failed or tool unavailable")
                return

            port = getattr(self.server, "server_port", 8721) if hasattr(self, "server") else 8721
            if slug:
                try:
                    from synlynk.vizor_daemon import refresh_workspace, _registered_workspaces
                    workspaces = _registered_workspaces()
                    if slug in workspaces:
                        db_path = workspaces[slug].get("canonical_path")
                        if db_path and os.path.isfile(db_path):
                            try:
                                import sqlite3
                                from synlynk.viz_views import build_workspace_views_snapshot
                                conn = sqlite3.connect(db_path)
                                build_workspace_views_snapshot(conn, repo_root)
                                conn.commit()
                                conn.close()
                            except Exception:
                                pass
                        refresh_workspace(slug, workspaces[slug], port)
                except Exception:
                    pass
            else:
                try:
                    views_conn = _get_db()
                    try:
                        from synlynk.viz_views import build_workspace_views_snapshot
                        build_workspace_views_snapshot(views_conn, repo_root)
                        if hasattr(views_conn, "commit"):
                            views_conn.commit()
                    finally:
                        views_conn.close()
                except Exception:
                    pass
                try:
                    data = generate_viz_data()
                    _write_cache(data, port)
                except Exception:
                    pass

            self._send_json_ok({"status": "ok", "message": "Knowledge graph successfully extracted and refreshed", "workspace": slug or "default"})
        except Exception as exc:
            self.send_error(500, str(exc))

    def _handle_board_status_request(self):
        try:
            payload = self._read_json_body()
            from synlynk.board import update_status
            result = update_status(payload.get("story_id"), payload.get("status"))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_error(400, str(exc) or "Invalid JSON")
            return
        except KeyError as exc:
            self.send_error(404, str(exc))
            return
        except FileNotFoundError as exc:
            self.send_error(404, str(exc))
            return
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_board_stage_request(self):
        try:
            payload = self._read_json_body()
            from synlynk.board import update_stage
            result = update_stage(payload.get("story_id"), payload.get("stage"))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_error(400, str(exc) or "Invalid JSON")
            return
        except KeyError as exc:
            self.send_error(404, str(exc))
            return
        except FileNotFoundError as exc:
            self.send_error(404, str(exc))
            return
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_tool_install_request(self):
        from urllib.parse import parse_qs
        from synlynk.tool_installer import install_tool

        content_type = self.headers.get("Content-Type", "")
        tool_name = "graphify"
        if "application/json" in content_type:
            try:
                payload = self._read_json_body()
                tool_name = payload.get("tool", "graphify")
            except (json.JSONDecodeError, TypeError, ValueError):
                self.send_error(400, "Invalid JSON")
                return
        else:
            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
                params = parse_qs(body)
                tool_name = params.get("tool", ["graphify"])[0]
            except Exception:
                tool_name = "graphify"

        try:
            ok = install_tool(tool_name)
        except Exception:
            ok = False

        if "application/json" in content_type:
            self._send_json_ok({"ok": ok, "tool": tool_name})
        else:
            self.send_response(302)
            status_param = "success" if ok else "failed"
            self.send_header("Location", f"/onboarding?installed={tool_name}&status={status_param}")
            self.end_headers()

    def _handle_worktree_clean(self, payload: dict) -> dict:
        """Run the guarded worktree cleaner and return a small UI-friendly result."""
        from synlynk.worktree import cmd_worktree_clean

        apply = bool(payload.get("apply")) and not bool(payload.get("dry_run"))
        output = cmd_worktree_clean(apply=apply, json_output=True)
        if isinstance(output, dict):
            details = output
            output = json.dumps(output)
        else:
            details = None
        try:
            details = details or json.loads(output)
        except (TypeError, json.JSONDecodeError):
            details = {}
        if apply:
            cleaned_count = len(details.get("results") or [])
        else:
            cleaned_count = int(details.get("would_remove", 0) or 0)
        return {
            "ok": True,
            "dry_run": not apply,
            "cleaned_count": cleaned_count,
            "output": output,
        }

    def _handle_worktree_clean_request(self):
        try:
            payload = self._read_json_body()
        except (json.JSONDecodeError, TypeError, ValueError):
            self.send_error(400, "Invalid JSON")
            return
        try:
            result = self._handle_worktree_clean(payload)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_role_create(self, payload: dict) -> dict:
        """Provision a role identity and its first living charter."""
        from synlynk import agent_store, agent_cli, charter_schema

        role = str(payload.get("role") or "").strip().lower()
        durability = str(payload.get("durability") or "durable").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", role):
            return {"ok": False, "error": "role must be a lowercase slug"}
        if durability not in charter_schema.VALID_DURABILITY:
            return {"ok": False, "error": "invalid durability"}
        for entry in agent_store.list_agents():
            for alias in entry.get("aliases", []):
                if alias.get("kind") == "role_slug" and alias.get("value") == role:
                    return {"ok": True, "agent_id": entry.get("agent_id"), "existing": True}
        agent_id = f"{role}-{uuid.uuid4().hex[:10]}"
        seed = agent_cli.SEED_CHARTERS.get(role)
        if seed:
            charter = re.sub(r"^durability: .*?$", f"durability: {durability}", seed, count=1, flags=re.MULTILINE)
        else:
            charter = (
                "---\n"
                "schema_version: 1\n"
                "role: dev\n"
                f'description: "Workspace role {role}"\n'
                f"durability: {durability}\n"
                "tools: []\ncredentials: []\n"
                "---\n\n"
                "## Instructions\n\n"
                f"Act as the {role} workspace persona according to the approved task brief.\n\n"
                "## Authority & Escalation\n\n"
                "Operate within workspace policy and escalate decisions outside the brief.\n\n"
                "## Workflow Ownership\n\n"
                f"Own work assigned to the {role} role.\n"
            )
        agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": role}])
        agent_store.propose_charter_revision(agent_id, charter, actor="vizor", parent_revision=0)
        return {"ok": True, "agent_id": agent_id}

    def _handle_role_create_request(self):
        try:
            payload = self._read_json_body()
        except (json.JSONDecodeError, TypeError, ValueError):
            self.send_error(400, "Invalid JSON")
            return
        try:
            result = self._handle_role_create(payload)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_note_request(self):
        try:
            note = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        notes = {}
        if os.path.exists(VIZ_NOTES_PATH):
            with open(VIZ_NOTES_PATH) as f:
                try:
                    notes = json.load(f)
                except json.JSONDecodeError:
                    notes = {}
        element_id = note.get("id", "")
        if not element_id:
            self.send_error(400, "Missing id")
            return
        notes[element_id] = {
            "text": note.get("text", ""),
            "tags": note.get("tags", []),
            "state": note.get("state", "info"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(VIZ_NOTES_PATH, "w") as f:
            json.dump(notes, f, indent=2)
        self._send_json_ok({"ok": True})

    def _handle_dispatch(self, payload: dict) -> dict:
        from synlynk import uxcore

        agent = payload.get("agent", "codex")
        task = payload.get("task", "")
        result = uxcore.dispatch(agent=agent, task=task)
        return {"ok": result.ok, "message": result.message, "job_id": result.job_id}

    def _handle_dispatch_request(self):
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        if not payload.get("task"):
            self.send_error(400, "Missing task")
            return
        try:
            result = self._handle_dispatch(payload)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_approve(self, payload: dict) -> dict:
        from synlynk import uxcore

        approve_kwargs = {"pr_number": payload["pr_number"]}
        if payload.get("story_id"):
            approve_kwargs["story_id"] = payload["story_id"]
        result = uxcore.approve_pr(**approve_kwargs)
        return {"ok": result.ok, "message": result.message, "job_id": result.job_id}

    def _handle_approve_request(self):
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        if not payload.get("pr_number"):
            self.send_error(400, "Missing pr_number")
            return
        try:
            result = self._handle_approve(payload)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_kill(self, payload: dict) -> dict:
        from synlynk import uxcore

        result = uxcore.kill_job(job_id=payload["job_id"])
        return {"ok": result.ok, "message": result.message, "job_id": result.job_id}

    def _handle_kill_request(self):
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        if not payload.get("job_id"):
            self.send_error(400, "Missing job_id")
            return
        try:
            result = self._handle_kill(payload)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_view_pref(self, payload: dict) -> dict:
        view = payload.get("view", "graph")
        config = {}
        config_path = ".synlynk/config.json"
        if os.path.exists(config_path):
            with open(config_path) as f:
                try:
                    config = json.load(f)
                except json.JSONDecodeError:
                    config = {}
        config.setdefault("vizor", {})["architect_map_view"] = view
        os.makedirs(".synlynk", exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        return {"ok": True}

    def _handle_view_pref_request(self):
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        result = self._handle_view_pref(payload)
        self._send_json_ok(result)

    def log_message(self, format, *args):
        pass  # suppress request logs


def _server_is_running() -> bool:
    meta_path = VIZ_META_PATH
    if not os.path.exists(meta_path):
        return False
    try:
        with open(meta_path) as f:
            meta = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    return meta.get("serving", False)


def _start_server(port: int) -> http.server.HTTPServer:
    from synlynk.local_http_auth import ensure_local_token

    ensure_local_token()
    server = http.server.HTTPServer(("127.0.0.1", port), VizorHandler)
    meta = {"port": port, "serving": True}
    with open(VIZ_META_PATH, "w") as f:
        json.dump(meta, f)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def _serve_until_stopped(server: http.server.HTTPServer) -> None:
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


def _stop_server() -> None:
    if os.path.exists(VIZ_META_PATH):
        with open(VIZ_META_PATH, "w") as f:
            json.dump({"serving": False}, f)
    print("Vizor: server stopped (next startup will start a fresh server).")


def _ftue_prompts(config: dict) -> dict:
    """Run first-use prompts; update and return config with vizor key."""
    vizor = config.get("vizor", {})
    if vizor.get("ftue_done"):
        return config
    print("\n✦ synlynk viz — first setup\n")
    if sys.stdin.isatty():
        has_ux = input("  Does this project have user-facing UX? (y/n) ").strip().lower() == "y"
        vizor["second_view"] = "journeys" if has_ux else "tube"
        notify = input("  Enable browser notifications? (y/n) ").strip().lower() == "y"
        vizor["notify_on_refresh"] = notify
        interval_raw = input("  Auto-refresh interval? (15 / 30 / off) [off] ").strip() or "off"
        vizor["refresh_interval_minutes"] = 0 if interval_raw == "off" else int(interval_raw)
    else:
        vizor["second_view"] = "tube"
        vizor["notify_on_refresh"] = False
        vizor["refresh_interval_minutes"] = 0
    vizor["port"] = DEFAULT_PORT
    vizor["theme"] = "system"
    vizor["timeline_weeks"] = 10
    vizor["ftue_done"] = True
    config["vizor"] = vizor
    config_path = ".synlynk/config.json"
    os.makedirs(".synlynk", exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print("  ✓ Settings saved to .synlynk/config.json\n")
    return config


def _current_workspace_slug() -> str:
    from synlynk.product_store import identity_slug_from_config

    return identity_slug_from_config(".")


def cmd_viz(args) -> None:
    """Entry point for `synlynk viz` subcommand."""
    from synlynk import vizor_daemon

    if getattr(args, "hosted", False):
        from synlynk.product_store import identity_slug_from_config
        from synlynk.wave6 import hosted_vizor_placeholder
        print(json.dumps(hosted_vizor_placeholder(identity_slug_from_config(".")), indent=2))
        return

    if getattr(args, "install", False):
        result = vizor_daemon.install()
        if result.get("installed"):
            print(f"  ✓ Vizor daemon installed via {result['manager']} ({result['unit_path']})")
        else:
            print(f"  ✗ Install failed: {result.get('reason', 'unknown error')}")
        return

    if getattr(args, "uninstall", False):
        result = vizor_daemon.uninstall()
        if result.get("uninstalled"):
            print(f"  ✓ Vizor daemon uninstalled ({result['manager']})")
        else:
            print(f"  ✗ Uninstall failed: {result.get('reason', 'unknown error')}")
        return

    if getattr(args, "daemon_status", False):
        status = vizor_daemon.status()
        print(json.dumps(status, indent=2))
        return

    slug = _current_workspace_slug()
    if not vizor_daemon.is_running():
        print("  ✗ Vizor daemon is not running.")
        print("  Run: synlynk viz --install")
        print("  Or check: synlynk viz --daemon-status")
        return

    port = vizor_daemon._read_port() or DEFAULT_PORT
    url = f"http://localhost:{port}/w/{slug}/overview.html"
    webbrowser.open(url)
    print(f"  ✓ Opened {url}")
