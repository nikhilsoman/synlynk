"""BS-21 Vizor: local browser dashboard generator and server."""
import html
import http.server
import json
import os
import re
import subprocess
import threading
import time
import webbrowser
from typing import Optional

from synlynk import _get_db

VIZ_CACHE_DIR = ".synlynk/viz-cache"
VIZ_NOTES_PATH = ".synlynk/viz-notes.json"
VIZ_META_PATH = ".synlynk/viz-meta.json"
VIZ_TUBE_PATH = ".synlynk/vizor-tube.json"
DEFAULT_PORT = 8721


def _live_js(port: int) -> str:
    return f"""
<script>
(function() {{
  const PORT = {port};
  let lastUpdated = null;

  async function checkManifest() {{
    try {{
      const r = await fetch(`http://localhost:${{PORT}}/manifest.json?_=${{Date.now()}}`);
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

    def _base_data() -> dict:
        return {
            "workspace": {"name": _workspace_name(), "updated_at": _ts()},
            "dreams": [],
            "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
            "agents": {},
            "tube_config": _load_json_optional(VIZ_TUBE_PATH, default=None),
            "notes": _load_json_optional(VIZ_NOTES_PATH, default={}),
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

    def _normalize_stage(name: str) -> str:
        key = (name or "").strip().lower()
        aliases = {
            "design": "design",
            "plan": "plan",
            "build": "build",
            "ship": "ship",
            "sustain": "sustain",
        }
        return aliases.get(key, key)

    _KNOWN_AGENTS = {"claude", "agy", "codex", "grok"}

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
        if not os.path.exists(sentinel_path):
            return []
        alerts = []
        pattern = re.compile(
            r"^\-\s*(?:\[(?P<severity>[A-Z]+)\]\s*)?\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)\]\s*(?P<pattern>[A-Z_]+):"
        )
        try:
            with open(sentinel_path) as f:
                for line in f:
                    text = line.strip()
                    m = pattern.match(text)
                    if not m:
                        continue
                    alerts.append({
                        "ts": m.group("ts"),
                        "pattern": m.group("pattern"),
                        "severity": m.group("severity") or "WARNING",
                        "resolved": "[RESOLVED]" in text,
                    })
        except Exception:
            return []
        return alerts

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

    def _dream_cost_actual(conn, dream_id: str) -> float:
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(total_cost_usd), 0) FROM cost_entries WHERE notes LIKE ?",
                (f"%{dream_id}%",),
            ).fetchone()
        except Exception:
            return 0.0
        return float(row[0] or 0.0) if row else 0.0

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

    try:
        conn = _get_db()
    except Exception:
        return _minimal_data()

    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return _minimal_data()

    required_tables = {"roadmap_arcs", "roadmap_phases", "stories", "cost_entries"}
    if not required_tables.issubset(tables):
        try:
            conn.close()
        except Exception:
            pass
        return _minimal_data()

    data = _read_support_files()
    by_agent = {name: 0.0 for name in ("claude", "agy", "codex", "grok")}
    by_stage = {name: 0.0 for name in ("design", "plan", "build", "ship", "sustain")}
    agents = {}
    agent_runs = {}

    try:
        arc_rows = conn.execute(
            "SELECT version, title, status, target_date, notes FROM roadmap_arcs ORDER BY id"
        ).fetchall()
        phase_rows = conn.execute(
            "SELECT id, arc_version, phase_title, status, priority, story_id, notes "
            "FROM roadmap_phases ORDER BY arc_version, id"
        ).fetchall()
        story_rows = conn.execute(
            "SELECT story_id, title, status, phase, estimated_tokens FROM stories ORDER BY id"
        ).fetchall()
        cost_rows = conn.execute(
            "SELECT session_date, agent, total_cost_usd, notes FROM cost_entries ORDER BY id"
        ).fetchall()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return _minimal_data()

    stories_by_id = {}
    stories_by_phase = {}
    for story_id, title, status, phase, estimated_tokens in story_rows:
        story = {
            "id": story_id,
            "name": title or "",
            "agent": phase or "",
            "status": status or "open",
            "cost_est": _story_cost_est(estimated_tokens),
            "cost_actual": 0.0,
            "note": data["notes"].get(story_id) if isinstance(data["notes"], dict) else None,
        }
        stories_by_id[story_id] = story
        stories_by_phase.setdefault((phase or "").strip().lower(), []).append(story)

    for row in cost_rows:
        agent = row[1] or ""
        amount = float(row[2] or 0.0)
        notes = row[3] or ""
        if agent:
            by_agent.setdefault(agent, 0.0)
            by_agent[agent] += amount
            agents.setdefault(agent, _empty_agent_bucket())
        for story_id, story in stories_by_id.items():
            if story_id and story_id in notes:
                story["cost_actual"] += amount

    for agent in list(by_agent):
        agents.setdefault(agent, _empty_agent_bucket())
        agents[agent]["total_usd"] = float(by_agent.get(agent, 0.0))

    for row in data["telemetry"]["recent"]:
        agent = row.get("agent") or ""
        if not agent:
            continue
        agent_runs.setdefault(agent, {"ok": 0, "total": 0})
        agent_runs[agent]["total"] += 1
        if int(row.get("exit_code") or 0) == 0:
            agent_runs[agent]["ok"] += 1
        agents.setdefault(agent, _empty_agent_bucket())

    for alert in data["telemetry"]["sentinel_alerts"]:
        alert_line = ""
        if isinstance(alert, dict):
            alert_line = f"{alert.get('pattern', '')} {alert.get('ts', '')}"
        for agent in list(agents):
            if agent and agent.lower() in alert_line.lower():
                agents[agent]["alert_count"] += 1

    for story in stories_by_id.values():
        agent = story["agent"] or _get_latest_capability_agent(conn, story["id"])
        if agent and not _looks_like_stage_label(agent):
            agents.setdefault(agent, _empty_agent_bucket())
            if story["status"] == "done":
                agents[agent]["tasks_done"] += 1
            elif story["status"] in ("active", "open"):
                agents[agent]["tasks_active"] += 1

    for agent, run_stats in agent_runs.items():
        agents.setdefault(agent, _empty_agent_bucket())
        total = run_stats["total"]
        agents[agent]["success_rate"] = (run_stats["ok"] / total) if total else 0.0

    dreams = []
    for arc in arc_rows:
        dream_id, dream_name, dream_status, _target_date, _notes = arc
        stage_rows = [row for row in phase_rows if row[1] == dream_id]
        stage_count = len(stage_rows)
        dream_stages = []
        dream_tasks_cost_actual = 0.0
        dream_tasks_cost_est = 0.0
        for index, phase_row in enumerate(stage_rows):
            _phase_id, _arc_version, phase_title, phase_status, _priority, story_id, notes = phase_row
            agent_list = []
            for match in re.findall(r"\bagent:([a-z,]+)\b", notes or ""):
                agent_list.extend([agent for agent in match.split(",") if agent])
            phase_key = (phase_title or "").strip()
            matched_tasks = []
            if story_id and story_id in stories_by_id:
                matched_tasks.append(stories_by_id[story_id])
            matched_tasks.extend(stories_by_phase.get(phase_key.lower(), []))
            deduped_tasks = []
            seen_task_ids = set()
            for task in matched_tasks:
                if task["id"] in seen_task_ids:
                    continue
                seen_task_ids.add(task["id"])
                deduped_tasks.append(task)
            stage_cost_actual = sum(float(task["cost_actual"] or 0.0) for task in deduped_tasks)
            stage_cost_est = sum(float(task["cost_est"] or 0.0) for task in deduped_tasks) or None
            dream_tasks_cost_actual += stage_cost_actual
            if stage_cost_est is not None:
                dream_tasks_cost_est += stage_cost_est
            for task in deduped_tasks:
                if task["agent"] and not _looks_like_stage_label(task["agent"]):
                    agent_list.append(task["agent"])
            dream_stages.append({
                "key": phase_key,
                "status": phase_status or "planned",
                "agents": sorted(dict.fromkeys(agent_list)),
                "start_frac": (index / stage_count) if stage_count else 0.0,
                "width_frac": (1.0 / stage_count) if stage_count else 1.0,
                "cost_actual": stage_cost_actual or None,
                "cost_est": stage_cost_est,
                "tasks": deduped_tasks,
            })
            if phase_key.lower() in by_stage:
                by_stage[phase_key.lower()] += stage_cost_actual
        dream_cost_actual = _dream_cost_actual(conn, dream_id)
        dreams.append({
            "id": dream_id,
            "name": dream_name or "",
            "status": dream_status or "planned",
            "cost_total": float(dream_cost_actual),
            "cost_est": dream_tasks_cost_est or None,
            "stages": dream_stages,
        })

    data["dreams"] = dreams
    data["costs"] = {
        "total_usd": float(sum(float(row[2] or 0.0) for row in cost_rows)),
        "by_agent": by_agent,
        "by_stage": by_stage,
    }
    data["agents"] = agents

    try:
        conn.close()
    except Exception:
        pass
    return data


def generate_index_html(data: dict, port: int) -> str:
    workspace = data.get("workspace") or {}
    workspace_name = str(workspace.get("name") or "workspace")
    updated_at = str(workspace.get("updated_at") or "")
    repos = workspace.get("repos") or []
    repo_items = []
    for repo in repos:
        if isinstance(repo, dict):
            repo_name = str(repo.get("name") or repo.get("path") or repo.get("slug") or "")
            repo_badge = str(repo.get("branch") or repo.get("status") or "")
            active = bool(repo.get("active"))
        else:
            repo_name = str(repo)
            repo_badge = ""
            active = False
        if not repo_name:
            continue
        badge_html = f'<span class="repo-badge">{html.escape(repo_badge)}</span>' if repo_badge else ""
        repo_items.append(
            f"""
        <div class="repo-item{' active' if active else ''}">
          <span class="repo-dot"></span>
          <span class="repo-name">{html.escape(repo_name)}</span>
          {badge_html}
        </div>
            """.rstrip()
        )
    repo_list_html = "\n".join(repo_items)
    if repo_list_html:
        repo_list_html = f"""
      <div class="nav-group">
        <div class="nav-group-label">Repos</div>
        {repo_list_html}
      </div>
        """.rstrip()

    nav_items = [
        ("gantt", "📅", "Gantt", "gantt.html", True),
        ("journeys", "🗺", "Journeys", "journeys.html", False),
        ("tube", "🚇", "Architect Map", "tube.html", False),
        ("effort", "💰", "Effort & Cost", "effort.html", False),
        ("efficiency", "📊", "Efficiency", "efficiency.html", False),
    ]
    nav_html = "\n".join(
        f"""
        <a class="nav-link{' active' if active else ''}" href="{view_html}" data-view="{view_id}" onclick="document.getElementById('view-frame').src = '{view_html}'; return setView('{view_id}');">
          <span class="nav-icon">{icon}</span>
          <span class="nav-label">{label}</span>
        </a>
        """.rstrip()
        for view_id, icon, label, view_html, active in nav_items
    )

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
    html, body { height:100%; }
    body {
      display:flex;
      height:100vh;
      margin:0;
      overflow:hidden;
      font-family:'SF Mono','JetBrains Mono',monospace;
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
      width:220px;
      min-width:220px;
      flex-shrink:0;
      background:var(--bg2);
      border-right:1px solid var(--border);
      display:flex;
      flex-direction:column;
      overflow:hidden;
    }
    .nav-header {
      padding:14px 14px 12px;
      border-bottom:1px solid var(--border);
    }
    .nav-logo {
      font-size:14px;
      font-weight:800;
      color:var(--accent);
      letter-spacing:-.5px;
      line-height:1.2;
    }
    .workspace-name {
      margin-top:5px;
      font-size:12px;
      color:var(--text2);
      line-height:1.35;
      word-break:break-word;
    }
    .nav-section {
      flex:1;
      overflow-y:auto;
      padding:10px 0 8px;
    }
    .nav-group-label {
      font-size:10px;
      text-transform:uppercase;
      letter-spacing:1px;
      color:var(--text3);
      padding:6px 14px 4px;
    }
    .nav-link {
      padding:7px 10px 7px 14px;
      display:flex;
      align-items:center;
      gap:8px;
      cursor:pointer;
      border-radius:5px;
      margin:1px 6px;
      color:var(--text2);
      font-size:12px;
      line-height:1.2;
      user-select:none;
    }
    .nav-link:hover { background:var(--bg3); color:var(--text); }
    .nav-link.active { background:var(--accent-bg); color:var(--accent); }
    .nav-icon { width:16px; text-align:center; flex-shrink:0; }
    .nav-label { white-space:nowrap; }
    .repo-item {
      padding:4px 10px 4px 30px;
      display:flex;
      align-items:center;
      gap:7px;
      margin:0 6px;
      color:var(--text3);
      font-size:11px;
      border-radius:4px;
    }
    .repo-item:hover { background:var(--bg3); color:var(--text2); }
    .repo-item.active { background:var(--accent-bg); color:var(--accent); }
    .repo-dot {
      width:6px;
      height:6px;
      border-radius:50%;
      background:var(--accent);
      flex-shrink:0;
    }
    .repo-badge {
      margin-left:auto;
      font-size:10px;
      background:var(--bg3);
      color:var(--text3);
      padding:1px 5px;
      border-radius:8px;
    }
    .nav-footer {
      border-top:1px solid var(--border);
      padding:10px 12px;
    }
    .theme-label {
      font-size:10px;
      color:var(--text3);
      margin-bottom:6px;
      text-transform:uppercase;
      letter-spacing:.5px;
    }
    .theme-sw {
      display:flex;
      gap:4px;
    }
    .theme-btn {
      flex:1;
      padding:5px 0;
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
      margin-top:10px;
    }
    .avatar {
      width:24px;
      height:24px;
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

    .main {
      flex:1;
      display:flex;
      flex-direction:column;
      overflow:hidden;
      min-width:0;
    }
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
    .status-workspace { color:var(--text2); }
    .status-updated { margin-left:auto; }
    """

    meta_json = json.dumps({"port": port, "updated_at": updated_at})
    avatar_label = (workspace_name[:1] or "S").upper()
    if workspace_name.lower().startswith("synlynk"):
        avatar_label = "S"
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
      <div class="nav-logo">Synlynk viz</div>
      <div class="workspace-name">{html.escape(workspace_name)}</div>
    </div>
    <div class="nav-section">
      <div class="nav-group-label">Views</div>
      {nav_html}
      {repo_list_html}
    </div>
    <div class="nav-footer">
      <div class="theme-label">Theme</div>
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
    <iframe id="view-frame" src="gantt.html" title="Synlynk Vizor view"></iframe>
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

  function setView(viewId, viewSrc) {{
    if (viewSrc && viewFrame) {{
      viewFrame.src = viewSrc;
    }}
    navLinks.forEach((link) => {{
      link.classList.toggle('active', link.dataset.view === viewId);
    }});
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
      const viewId = link.dataset.view || 'gantt';
      const viewSrc = link.getAttribute('href') || 'gantt.html';
      document.getElementById('view-frame').src = viewSrc;
      setView(viewId);
    }});
  }});

  setView('gantt', 'gantt.html');
}})();
</script>
{_live_js(port)}
</body>
</html>"""


def generate_gantt_html(data: dict, port: int) -> str:
    from pathlib import Path

    data_json = json.dumps(data)
    reference_path = Path(__file__).resolve().parent.parent / "docs/brainstorm/bs21-vizor/viz-gantt-v5.html"
    reference_html = reference_path.read_text() if reference_path.exists() else ""
    css_start = reference_html.find("<style>")
    css_end = reference_html.find("</style>", css_start + 7) if css_start != -1 else -1
    style_content = reference_html[css_start + 7 : css_end] if css_start != -1 and css_end != -1 else ""

    script_content = """
const PORT = __PORT__;
const NOTE_STATE_CLASS = { none:'note-none', info:'note-info', action:'note-action', urgent:'note-urgent', done:'note-done' };
const STAGE_CLASS = { dream:'dream', plan:'plan', work:'work', ship:'ship', maintain:'maint', engage:'engage' };
const STAGE_ICON = { dream:'✦ Dream', plan:'⊡ Plan', work:'⚙ Work', ship:'▲ Ship', maintain:'↺ Maintain', engage:'♡ Engage' };
const STAGE_STYLE = {
  dream:'background:var(--s-dream-bg);border-color:var(--s-dream-bd);color:var(--s-dream-tx)',
  plan:'background:var(--s-plan-bg);border-color:var(--s-plan-bd);color:var(--s-plan-tx)',
  work:'background:var(--s-work-bg);border-color:var(--s-work-bd);color:var(--s-work-tx)',
  ship:'background:var(--s-ship-bg);border-color:var(--s-ship-bd);color:var(--s-ship-tx)',
  maintain:'background:var(--s-maint-bg);border-color:var(--s-maint-bd);color:var(--s-maint-tx)',
  engage:'background:var(--s-engage-bg);border-color:var(--s-engage-bd);color:var(--s-engage-tx)',
};
const dreams = Array.isArray(window.VIZOR_DATA && window.VIZOR_DATA.dreams) ? window.VIZOR_DATA.dreams : [];
const notes = (window.VIZOR_DATA && window.VIZOR_DATA.notes && typeof window.VIZOR_DATA.notes === 'object') ? window.VIZOR_DATA.notes : {};
let openDrills = {};
let currentNoteTarget = null;

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

function classForStage(stageKey) {
  const key = String(stageKey || '').trim().toLowerCase();
  return STAGE_CLASS[key] || 'plan';
}

function iconForStage(stageKey) {
  const key = String(stageKey || '').trim().toLowerCase();
  return STAGE_ICON[key] || (stageKey ? escapeHtml(stageKey) : '✦ Dream');
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
  const response = await fetch('http://localhost:' + PORT + '/note', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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

function renderTask(task, dreamId, stageKey, index, total) {
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

function renderDrill(dreamId, stageKey) {
  const dream = dreams.find(d => d.id === dreamId);
  const stage = dream && Array.isArray(dream.stages) ? dream.stages.find(s => s.key === stageKey) : null;
  const dr = document.getElementById('drill-' + dreamId);
  if (!dr) return;
  if (!stage) {
    dr.innerHTML = `<div style="padding:12px 14px;font-size:11px;color:var(--text3)">No tasks defined. <span style="color:var(--accent);cursor:pointer">📝 Add note</span></div>`;
    return;
  }

  const tasks = Array.isArray(stage.tasks) ? stage.tasks : [];
  const total = Math.max(tasks.length, 1);
  const gridCols = `260px repeat(${total}, 1fr)`;
  const headerCols = tasks.map((task, idx) => `<div class="zoom-col">${escapeHtml(task.name || ('Task ' + (idx + 1)))}</div>`).join('');
  const taskRows = tasks.map((task, idx) => renderTask(task, dreamId, stageKey, idx, total)).join('');
  const pillKey = classForStage(stageKey);
  const lastLabel = tasks.length > 1 ? tasks[tasks.length - 1].name : '';
  dr.innerHTML = `
    <div class="drill-header">
      <div class="stage-pill" style="${STAGE_STYLE[pillKey] || STAGE_STYLE.plan}">${escapeHtml(iconForStage(stageKey))} stage</div>
      <div class="drill-ttl">${escapeHtml(dreamId.toUpperCase())} — ${tasks.length} task${tasks.length !== 1 ? 's' : ''} · zoomed to stage window</div>
      <div class="drill-close" onclick="closeDrill('${escapeHtml(dreamId)}')">✕ collapse</div>
    </div>
    <div class="zoom-grid" style="grid-template-columns:${gridCols}">
      <div class="zoom-lbl">↳ zoomed: ${escapeHtml(stage.key || stageKey)}${lastLabel ? ' → ' + escapeHtml(lastLabel) : ''}</div>
      ${headerCols}
    </div>
    ${taskRows}`;
}

function zoomStage(dreamId, stageKey, barEl) {
  const dr = document.getElementById('drill-' + dreamId);
  const drow = document.getElementById('drow-' + dreamId);
  if (!dr || !drow) return;
  if (openDrills[dreamId] === stageKey) {
    closeDrill(dreamId);
    return;
  }
  if (openDrills[dreamId]) {
    const prevBar = document.getElementById('sb-' + dreamId + '-' + openDrills[dreamId]);
    if (prevBar) prevBar.classList.remove('sel');
  }
  renderDrill(dreamId, stageKey);
  dr.classList.add('open');
  drow.classList.add('exp');
  if (barEl) barEl.classList.add('sel');
  openDrills[dreamId] = stageKey;
}

function closeDrill(dreamId) {
  const dr = document.getElementById('drill-' + dreamId);
  const drow = document.getElementById('drow-' + dreamId);
  dr?.classList.remove('open');
  drow?.classList.remove('exp');
  if (openDrills[dreamId]) {
    const prevBar = document.getElementById('sb-' + dreamId + '-' + openDrills[dreamId]);
    if (prevBar) prevBar.classList.remove('sel');
  }
  delete openDrills[dreamId];
}

function toggleDrill(dreamId) {
  if (openDrills[dreamId]) {
    closeDrill(dreamId);
    return;
  }
  const dream = dreams.find(d => d.id === dreamId);
  if (!dream || !Array.isArray(dream.stages) || !dream.stages.length) return;
  const activeStage = dream.stages.find(s => String(s.status || '').toLowerCase() === 'active') || dream.stages[0];
  const barEl = document.getElementById('sb-' + dreamId + '-' + activeStage.key);
  zoomStage(dreamId, activeStage.key, barEl);
}

function renderDream(dream) {
  const stages = Array.isArray(dream.stages) ? dream.stages : [];
  const note = dream.note || noteData(dream.id);
  const noteClass = noteStateClass(note && note.state);
  const taskCount = stages.reduce((sum, stage) => sum + (Array.isArray(stage.tasks) ? stage.tasks.length : 0), 0);
  const status = String(dream.status || 'planned').trim().toLowerCase();
  const statusClass = status === 'done' ? 'ok' : status === 'blocked' ? 'over' : 'na';
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
    return `<div class="sb sb-${cls} ${live}" id="sb-${dream.id}-${stage.key}" style="left:${left}%;width:${width}%" onclick="zoomStage('${escapeHtml(dream.id)}','${escapeHtml(stage.key)}',this)">${escapeHtml(iconForStage(stage.key))}${agentHtml}</div>`;
  }).join('');
  return `
      <div class="drow" id="drow-${dream.id}">
        <div class="dlbl editable" onclick="toggleDrill('${escapeHtml(dream.id)}')">
          <div class="dtop"><span class="darr">▶</span><div class="dname">${escapeHtml(dream.id)} · ${escapeHtml(dream.name || dream.id)}</div>
            <span class="note-chip nc-${noteClass.replace('note-', '') === 'none' ? 'info' : noteClass.replace('note-', '')}" style="display:${noteClass === 'note-none' ? 'none' : 'inline-flex'}" onclick="openNote('${escapeHtml(dream.id)}','${escapeHtml(dream.name || dream.id)}');event.stopPropagation()">✎ note</span>
          </div>
          <div class="dbot"><div class="aa-stack">${agentsHtml}</div><span class="dcost ${statusClass}">${escapeHtml(dream.status || 'planned')}${taskCount ? ' · ' + taskCount + ' tasks' : ''}</span></div>
          <div class="pencil-wrap ${noteClass}" data-note-target="${escapeHtml(dream.id)}" data-note-label="${escapeHtml(dream.name || dream.id)}" onclick="openNoteFromEl(this);event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div>
        </div>
        <div class="dbars">
          <div class="today-ln" style="left:19%"></div>
          ${barHtml}
        </div>
      </div>
      <div class="drill" id="drill-${dream.id}"></div>`;
}

function renderDreams() {
  const body = document.getElementById('gantt-body');
  const wsSub = document.getElementById('ws-sub');
  const dreamCount = document.getElementById('dream-count');
  const dreamSub = document.getElementById('dream-sub');
  const statusWorkspaces = document.getElementById('status-workspaces');
  if (!body) return;

  if (!dreams.length) {
    body.innerHTML = "<p class='empty-state'>No Dreams found in state db</p>";
    if (wsSub) wsSub.textContent = '0 Dreams · no stage data';
    if (dreamCount) dreamCount.textContent = '0';
    if (dreamSub) dreamSub.textContent = '0 stages';
    if (statusWorkspaces) statusWorkspaces.textContent = '0 dreams';
    return;
  }

  const dreamCountValue = dreams.length;
  const stageCountValue = dreams.reduce((sum, dream) => sum + (Array.isArray(dream.stages) ? dream.stages.length : 0), 0);
  const activeDreams = dreams.filter(dream => String(dream.status || '').toLowerCase() === 'active').length;
  body.innerHTML = dreams.map(renderDream).join('');
  if (wsSub) wsSub.textContent = dreamCountValue + ' Dreams · click any stage bar to zoom in';
  if (dreamCount) dreamCount.textContent = String(dreamCountValue);
  if (dreamSub) dreamSub.textContent = stageCountValue + ' stages · ' + activeDreams + ' active';
  if (statusWorkspaces) statusWorkspaces.textContent = dreamCountValue + ' dreams';
  const firstDream = dreams[0];
  const firstStage = firstDream && Array.isArray(firstDream.stages) ? (firstDream.stages.find(s => String(s.status || '').toLowerCase() === 'active') || firstDream.stages[0]) : null;
  if (firstDream && firstStage) {
    const barEl = document.getElementById('sb-' + firstDream.id + '-' + firstStage.key);
    zoomStage(firstDream.id, firstStage.key, barEl);
  }
}

setTheme(safeStorageGet('vizor-theme', 'light'));
renderDreams();
""".replace("__PORT__", str(port))

    if not style_content:
        style_content = "body{font-family:monospace;background:#f6f8fa;color:#1f2328;}"

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Gantt v5</title>
<script>window.VIZOR_DATA = {data_json};</script>
<style>
{style_content}
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

<div class="shell">
<div class="sidenav">
  <div class="nav-header"><div class="nav-logo">S<span>ynlynk</span> <span style="color:var(--accent)">viz</span></div></div>
  <input class="nav-search" placeholder="⌘K  search…" readonly>
  <div class="nav-section">
    <div class="nav-sec-label">Workspaces</div>
    <div class="nav-item active"><span>▾</span> synlynk-core <span class="nav-badge">5</span></div>
    <div class="repo-item active"><div class="rdot" style="background:var(--accent)"></div>synlynk (main)</div>
    <div class="repo-item"><div class="rdot" style="background:#f59e0b"></div>synlynk-website</div>
    <div class="repo-item"><div class="rdot" style="background:var(--text3)"></div>tokq-bridge</div>
    <div class="nav-item" style="margin-top:5px"><span>▸</span> rxcc <span class="nav-badge">1</span></div>
    <div class="nav-item"><span>▸</span> playblazer-ng <span class="nav-badge">2</span></div>
    <div class="nav-sec-label" style="color:var(--accent);cursor:pointer;margin-top:4px">+ Add workspace</div>
  </div>
  <div class="nav-footer">
    <div class="nav-footer-top"><div class="avatar">N</div><div class="av-name">nikhilsoman</div><div class="gear-btn">⚙</div></div>
    <div class="theme-label">Theme</div>
    <div class="theme-sw">
      <button class="theme-btn active" id="btn-light" onclick="setTheme('light')">☀ Light</button>
      <button class="theme-btn" id="btn-dark" onclick="setTheme('dark')">☾ Dark</button>
      <button class="theme-btn" id="btn-sys" onclick="setTheme('system')">⊙ System</button>
    </div>
  </div>
</div>

<div class="main">
  <div class="view-tabs">
    <div class="vtab active">📅 Gantt</div>
    <div class="vtab">🗺 User Journeys</div>
    <div class="vtab">🚇 Architect Map</div>
    <div class="vtab">💰 Effort & Cost</div>
    <div class="vtab">📊 Efficiency</div>
    <div class="tab-sp"></div>
    <div class="tab-meta"><div class="live-dot"></div>updated 3m ago</div>
  </div>
  <div class="content">
    <div class="ws-header">
      <div><div class="ws-title">{html.escape(str(data.get("workspace", {}).get("name", "workspace")))}</div><div class="ws-sub" id="ws-sub">Loading dreams…</div></div>
      <div class="ws-chip">Developer Preview · v0.10.0</div>
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
        <div class="ghl">Dream / Epic</div>
        <div class="gwk">Jul W1</div><div class="gwk">Jul W2</div>
        <div class="gwk now">Jul W3 ▾</div><div class="gwk">Jul W4</div>
        <div class="gwk">Aug W1</div><div class="gwk">Aug W2</div>
        <div class="gwk">Aug W3</div><div class="gwk">Aug W4</div>
        <div class="gwk">Sep W1</div><div class="gwk">Sep W2</div>
      </div>
      <div id="gantt-body"></div>
    </div></div>

    <div class="legend">
      <div class="li"><div class="ld" style="background:var(--s-dream-bg);border-color:var(--s-dream-bd)"></div>✦ Dream</div>
      <div class="li"><div class="ld" style="background:var(--s-plan-bg);border-color:var(--s-plan-bd)"></div>⊡ Plan</div>
      <div class="li"><div class="ld" style="background:var(--s-work-bg);border-color:var(--s-work-bd)"></div>⚙ Work</div>
      <div class="li"><div class="ld" style="background:var(--s-ship-bg);border-color:var(--s-ship-bd)"></div>▲ Ship</div>
      <div class="li"><div class="ld" style="background:var(--s-maint-bg);border-color:var(--s-maint-bd)"></div>↺ Maintain</div>
      <div class="li"><div class="ld" style="background:var(--s-engage-bg);border-color:var(--s-engage-bd)"></div>♡ Engage</div>
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
      <div class="sc teal editable"><div class="sl">Dreams in flight</div><div class="sv" id="dream-count">0</div><div class="ss" id="dream-sub">0 stages</div><div class="wow">⚡ live</div><div class="pencil-wrap note-none" onclick="openNote('summary','Summary');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
      <div class="sc blue editable"><div class="sl">Active agents</div><div class="sv">3</div><div class="aa-stack" style="margin-top:6px"><div class="aa aa-agy">A</div><div class="aa aa-codex">Co</div><div class="aa aa-grok">G</div></div><div class="pencil-wrap note-none" onclick="openNote('agents','Agents');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
      <div class="sc org editable"><div class="sl">Total spend</div><div class="sv">$28.50</div><div class="ss">of ~$71 · 40% in</div><div class="pencil-wrap note-none" onclick="openNote('cost','Total spend');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
      <div class="sc purp editable"><div class="sl">Next ship</div><div class="sv">Jul 24</div><div class="ss">Module Extraction → main</div><div class="pencil-wrap note-none" onclick="openNote('ship','Next ship');event.stopPropagation()"><svg class="pencil-icon"><use href="#pencil-svg"/></svg></div></div>
    </div>
  </div>
  <div class="status-bar"><span class="sb-ok">● local · offline-ready</span><span id="status-workspaces">3 workspaces</span><div class="sb-rt">next update: ~7 min</div></div>
</div>
</div>

<script>
{script_content}
</script>
{_live_js(port)}
</body>
</html>"""


def generate_tube_html(data: dict, port: int) -> str:
    """Generate the Architect Map view (tube map style SVG or setup prompt)."""
    import json
    import math

    json_data = json.dumps(data)
    workspace_name = data.get("workspace", {}).get("name", "workspace")
    updated_at = data.get("workspace", {}).get("updated_at", "")

    live_js_html = _live_js(port)

    style_content = """
    :root {
      --bg:#f6f8fa; --bg2:#ffffff; --bg3:#eaeef2;
      --border:#d1d5db; --border2:#e8ebee;
      --text:#1f2328; --text2:#57606a; --text3:#8b949e;
      --accent:#0d9e87; --accent-bg:#e6f7f4; --accent-dim:#c0ede6;
      --shadow:0 2px 12px rgba(0,0,0,.10);
      /* line colors */
      --l-invoke:#0d9e87;
      --l-ctx:   #3b82f6;
      --l-sent:  #f59e0b;
      --l-init:  #7c3aed;
      --l-vizor: #d97706;
    }
    [data-theme="dark"] {
      --bg:#0d0f14; --bg2:#0a0c10; --bg3:#13171f;
      --border:#1e2430; --border2:#13171f;
      --text:#c9d1d9; --text2:#8b949e; --text3:#4a5568;
      --accent:#3de0c0; --accent-bg:#0d2137; --accent-dim:#0a3050;
      --shadow:0 2px 20px rgba(0,0,0,.5);
      --l-invoke:#3de0c0;
      --l-ctx:   #60a5fa;
      --l-sent:  #fbbf24;
      --l-init:  #a78bfa;
      --l-vizor: #fcd34d;
    }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { font-family:'SF Mono','JetBrains Mono',monospace; background:var(--bg); color:var(--text); font-size:13px; transition:background .2s,color .2s; padding: 18px 22px; }
    .content { display:flex; flex-direction:column; }
    .view-header { display:flex;align-items:center;gap:12px;margin-bottom:14px; }
    .view-title { font-size:16px;font-weight:700;color:var(--text); }
    .view-sub { font-size:12px;color:var(--text3);margin-top:2px; }
    .view-chip { background:var(--accent-bg);color:var(--accent);border:1px solid var(--accent-dim);border-radius:12px;font-size:11px;padding:3px 10px; }
    .toolbar { display:flex;align-items:center;gap:8px;margin-bottom:12px; }
    .chip { padding:3px 9px;border-radius:10px;font-size:11px;border:1px solid var(--border);color:var(--text2);cursor:pointer;background:transparent;font-family:inherit; }
    .chip.on { background:var(--accent-bg);border-color:var(--accent);color:var(--accent); }
    .sp { flex:1; }
    .zbtn { padding:4px 9px;border-radius:5px;font-size:11px;background:var(--bg3);border:1px solid var(--border);color:var(--text2);cursor:pointer;font-family:inherit; }
    .tube-wrap { background:var(--bg2);border:1px solid var(--border);border-radius:8px;overflow:hidden;position:relative; }
    svg.tube { width:100%;height:auto;display:block; transition: transform 0.2s ease; }
    /* Station tooltip */
    .tip {
      position:absolute;display:none;background:var(--bg2);border:1px solid var(--border);
      border-radius:7px;padding:9px 12px;font-size:11px;color:var(--text);
      box-shadow:var(--shadow);pointer-events:none;z-index:100;max-width:240px;
      white-space:nowrap;
    }
    .tip-name { font-weight:700;color:var(--text);margin-bottom:3px; }
    .tip-line { color:var(--text3);font-size:10px; }
    .tip-desc { color:var(--text2);font-size:10px;margin-top:4px;white-space:normal; }
    .legend-row { display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-top:14px; }
    .li { display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text3); }
    .lline { width:28px;height:4px;border-radius:2px;flex-shrink:0; }
    .lsep { color:var(--border);margin:0 4px; }
    .aa { width:18px;height:18px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:8px;font-weight:800;flex-shrink:0;border:1.5px solid; }

    /* Setup view */
    .setup-container {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 80vh;
    }
    .setup-card {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 40px;
      text-align: center;
      max-width: 480px;
      width: 100%;
      box-shadow: var(--shadow);
      transition: transform 0.3s ease, border-color 0.3s ease;
    }
    .setup-card:hover {
      transform: translateY(-4px);
      border-color: var(--accent);
    }
    .setup-icon {
      font-size: 48px;
      margin-bottom: 20px;
    }
    .setup-card h1 {
      font-size: 22px;
      font-weight: 700;
      margin-bottom: 12px;
      color: var(--text);
    }
    .setup-desc {
      color: var(--text2);
      font-size: 14px;
      margin-bottom: 24px;
      line-height: 1.5;
    }
    .setup-cmd {
      background: var(--bg3);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 24px;
    }
    .setup-cmd code {
      font-family: 'SF Mono', 'JetBrains Mono', monospace;
      font-size: 13px;
      color: var(--accent);
    }
    .copy-btn {
      background: var(--accent-bg);
      border: 1px solid var(--accent-dim);
      color: var(--accent);
      padding: 4px 8px;
      border-radius: 4px;
      font-family: inherit;
      font-size: 11px;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .copy-btn:hover {
      background: var(--accent);
      color: #fff;
    }
    .setup-spec a {
      color: var(--accent);
      text-decoration: none;
      font-size: 12px;
      font-weight: 600;
    }
    .setup-spec a:hover {
      text-decoration: underline;
    }
    """

    tube_config = data.get("tube_config")

    if not tube_config:
        template = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Architect Map Setup</title>
<style>
__STYLE_CONTENT__
</style>
</head>
<body>
<div class="setup-container">
  <div class="setup-card">
    <div class="setup-icon">🚇</div>
    <h1>🚇 Architect Map</h1>
    <p class="setup-desc">Define your architecture lines to unlock this view.</p>
    <div class="setup-cmd">
      <code>synlynk viz --setup-tube</code>
      <button class="copy-btn" onclick="navigator.clipboard.writeText('synlynk viz --setup-tube')">Copy</button>
    </div>
    <div class="setup-spec">
      <a href="file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-07-03-bs21-vizor-design.md" target="_blank">
        docs/superpowers/specs/2026-07-03-bs21-vizor-design.md ↗
      </a>
    </div>
  </div>
</div>
<script>
window.VIZOR_DATA = __JSON_DATA__;
</script>
__LIVE_JS_HTML__
</body>
</html>"""
        return (
            template.replace("__STYLE_CONTENT__", style_content)
            .replace("__JSON_DATA__", json_data)
            .replace("__LIVE_JS_HTML__", live_js_html)
        )

    stations_config = tube_config.get("stations", {})
    lines_config = tube_config.get("lines", [])

    # Compute segs per station ID
    segs_by_station = {}
    for station_id in stations_config:
        segs = sum(1 for line in lines_config if station_id in line.get("stations", []))
        segs_by_station[station_id] = segs

    lines_svg_list = []
    legend_lines_list = []

    for line in lines_config:
        line_id = line.get("id", "")
        line_name = line.get("name", "")
        color = line.get("color", "var(--text)")
        stations_in_line = line.get("stations", [])

        points = []
        for station_id in stations_in_line:
            s_info = stations_config.get(station_id)
            if s_info and "x" in s_info and "y" in s_info:
                points.append(f"{s_info['x']},{s_info['y']}")

        if len(points) >= 2:
            points_str = " ".join(points)
            lines_svg_list.append(
                f'<polyline points="{points_str}" fill="none" stroke="{color}" stroke-width="5" '
                f'stroke-linecap="round" stroke-linejoin="round" class="tube-line line-{line_id}"/>'
            )

            # Midpoint placement for labels
            label_x = line.get("label_x")
            label_y = line.get("label_y")
            if label_x is None or label_y is None:
                valid_stations = [stations_config[s] for s in stations_in_line if s in stations_config and "x" in stations_config[s] and "y" in stations_config[s]]
                if valid_stations:
                    mid_idx = len(valid_stations) // 2
                    mid_station = valid_stations[mid_idx]
                    label_x = mid_station["x"]
                    label_y = mid_station["y"] - 15

            if label_x is not None and label_y is not None:
                lines_svg_list.append(
                    f'<text x="{label_x}" y="{label_y}" text-anchor="middle" font-size="10" fill="{color}" '
                    f'font-family="SF Mono,monospace" font-weight="700" letter-spacing="1">{line_name.upper()}</text>'
                )

        legend_lines_list.append(
            f'<div class="li"><div class="lline" style="background:{color}"></div>{line_name}</div>'
        )

    stations_svg_list = []
    num_interchanges = 0

    for s_id, s_info in stations_config.items():
        x = s_info.get("x")
        y = s_info.get("y")
        if x is None or y is None:
            continue
        label = s_info.get("label", s_id)
        desc = s_info.get("desc", "")

        segs = segs_by_station.get(s_id, 0)
        r = 4 + segs * 2

        station_lines = []
        for line in lines_config:
            if s_id in line.get("stations", []):
                station_lines.append(line.get("name", line.get("id", "")))
        lines_str = ", ".join(station_lines)

        station_elements = []
        is_active = s_info.get("active", False)

        if is_active:
            # Find closest matching glow filter
            line_color = "teal"
            if segs_lines := [l for l in lines_config if s_id in l.get("stations", [])]:
                first_color = segs_lines[0].get("color", "").lower()
                if "#3b82f6" in first_color or "blue" in first_color:
                    line_color = "blue"
                elif "#d97706" in first_color or "gold" in first_color or "#f59e0b" in first_color or "amber" in first_color:
                    line_color = "gold"
                elif "#7c3aed" in first_color or "purple" in first_color:
                    line_color = "purple"
                else:
                    line_color = "teal"
            station_elements.append(
                f'<circle cx="{x}" cy="{y}" r="{r + 4}" fill="#0d9e87" opacity=".12" filter="url(#glow-{line_color})"/>'
            )

        if segs > 1:
            num_interchanges += 1
            segs_lines = [l for l in lines_config if s_id in l.get("stations", [])]
            R = r + 8
            perimeter = 2 * math.pi * R
            S = perimeter / segs
            gap = 4
            A = max(2.0, S - gap)
            for i, line in enumerate(segs_lines):
                line_color = line.get("color", "var(--text)")
                dasharray = f"{A:.2f} {perimeter - A:.2f}"
                dashoffset = f"-{i * S:.2f}"
                station_elements.append(
                    f'<circle cx="{x}" cy="{y}" r="{R}" fill="none" stroke="{line_color}" stroke-width="5" '
                    f'stroke-dasharray="{dasharray}" stroke-dashoffset="{dashoffset}" opacity="0.8"/>'
                )
            station_elements.append(
                f'<circle cx="{x}" cy="{y}" r="{r}" fill="var(--bg2)" stroke="var(--text2)" stroke-width="2.5"/>'
            )
        else:
            segs_lines = [l for l in lines_config if s_id in l.get("stations", [])]
            color = segs_lines[0].get("color", "var(--text)") if segs_lines else "var(--text)"
            station_elements.append(
                f'<circle cx="{x}" cy="{y}" r="{r}" fill="var(--bg2)" stroke="{color}" stroke-width="2.5"/>'
            )

        if is_active:
            center_color = "#0d9e87"
            if segs_lines := [l for l in lines_config if s_id in l.get("stations", [])]:
                center_color = segs_lines[0].get("color", "#0d9e87")
            station_elements.append(
                f'<circle cx="{x}" cy="{y}" r="3" fill="{center_color}" opacity=".7"/>'
            )

        agent = s_info.get("agent")
        if agent:
            agent_mapping = {
                "claude": {"initial": "C", "fill": "#e6f7f4", "stroke": "#0d9e87"},
                "agy": {"initial": "A", "fill": "#e8f0fe", "stroke": "#3b82f6"},
                "codex": {"initial": "Co", "fill": "#e6f4f0", "stroke": "#10a37f"},
                "grok": {"initial": "G", "fill": "#f0f0f0", "stroke": "#666060"},
            }
            if agent.lower() in agent_mapping:
                amp = agent_mapping[agent.lower()]
                bx, by = x, y - r - 10
                station_elements.append(
                    f'<circle cx="{bx}" cy="{by}" r="9" fill="{amp["fill"]}" stroke="{amp["stroke"]}" stroke-width="1.5"/>'
                    f'<text x="{bx}" y="{by + 3}" text-anchor="middle" font-size="8" fill="{amp["stroke"]}" font-weight="800">{amp["initial"]}</text>'
                )

        label_pos = s_info.get("label_pos", "bottom")
        if label_pos == "top":
            anchor = "middle"
            lx, ly = x, y - r - 8
            if agent:
                ly -= 12
        elif label_pos == "left":
            anchor = "end"
            lx, ly = x - r - 8, y + 4
        elif label_pos == "right":
            anchor = "start"
            lx, ly = x + r + 8, y + 4
        else:
            anchor = "middle"
            lx, ly = x, y + r + 14

        if "\n" in label:
            parts = label.split("\n")
            station_elements.append(
                "\n".join(
                    f'<text x="{lx}" y="{ly + i * 12}" text-anchor="{anchor}" font-size="11" fill="var(--text)" '
                    f'font-family="SF Mono,monospace">{part}</text>'
                    for i, part in enumerate(parts)
                )
            )
        else:
            station_elements.append(
                f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="11" fill="var(--text)" '
                f'font-family="SF Mono,monospace">{label}</text>'
            )

        elements_str = "\n".join(station_elements)
        active_attr = ' data-active="true"' if is_active else ''
        stations_svg_list.append(
            f'<g class="station" data-name="{label}" data-line="{lines_str}" data-desc="{desc}"{active_attr}>\n'
            f'{elements_str}\n'
            f'</g>'
        )

    lines_svg = "\n".join(lines_svg_list)
    stations_svg = "\n".join(stations_svg_list)
    legend_lines = "\n".join(legend_lines_list)

    num_lines = len(lines_config)
    hub_suffix = "s" if num_interchanges != 1 else ""

    template = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<title>synlynk Vizor — Architect Tube Map</title>
<style>
__STYLE_CONTENT__
</style>
</head>
<body>

<!-- Tooltip -->
<div class="tip" id="tip">
  <div class="tip-name" id="tip-name"></div>
  <div class="tip-line" id="tip-line"></div>
  <div class="tip-desc" id="tip-desc"></div>
</div>

<div class="content">
  <div class="view-header">
    <div>
      <div class="view-title">Architect Map — __WORKSPACE_NAME__</div>
      <div class="view-sub">__NUM_LINES__ subsystem lines · __NUM_INTERCHANGES__ interchange hub__HUB_SUFFIX__ · hover any station for details</div>
    </div>
    <div class="view-chip">🚇 tube map</div>
  </div>

  <div class="toolbar">
    <span style="font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.8px">Show:</span>
    <button class="chip on">All lines</button>
    <button class="chip">Active only</button>
    <button class="chip">Agents</button>
    <div class="sp"></div>
    <button class="zbtn" id="zoom-out">− zoom</button>
    <button class="zbtn" id="zoom-in">+ zoom</button>
  </div>

  <div class="tube-wrap">
    <svg class="tube" id="tube-svg" viewBox="0 0 1060 580" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <!-- Glow filters for active stations -->
        <filter id="glow-teal" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="glow-blue" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="glow-gold" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="5" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="glow-purple" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      <!-- Background Grid -->
      <rect width="1060" height="580" fill="none"/>
      <pattern id="dotgrid" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
        <circle cx="20" cy="20" r="1" fill="currentColor" opacity=".08"/>
      </pattern>
      <rect width="1060" height="580" fill="url(#dotgrid)" color="var(--text3)"/>

      <!-- Lines -->
      __LINES_SVG__

      <!-- Stations -->
      __STATIONS_SVG__
    </svg>
  </div>

  <!-- Legend -->
  <div class="legend-row">
    __LEGEND_LINES__
    <span class="lsep">|</span>
    <div class="li"><div style="width:10px;height:10px;border-radius:50%;border:2px solid var(--text);background:var(--bg2)"></div>regular station</div>
    <div class="li"><div style="width:10px;height:10px;border-radius:2px;border:2px solid var(--text3);background:var(--bg2)"></div>terminal</div>
    <div class="li"><div style="width:14px;height:14px;border-radius:50%;border:3px solid var(--text2);background:var(--bg2)"></div>interchange ⬡</div>
    <div class="li"><div style="width:8px;height:8px;border-radius:50%;background:#0d9e87;opacity:.7"></div>active station</div>
  </div>
</div>

<script>
/* ── THEME ───────────────────────────────────── */
function setTheme(t) {
  const resolved = t==='system'?(window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):t;
  document.documentElement.setAttribute('data-theme', resolved);
}
setTheme(localStorage.getItem('vizor-theme')||'light');
window.addEventListener('storage', (e) => {
  if (e.key === 'vizor-theme') {
    setTheme(e.newValue || 'light');
  }
});
try {
  if (window.parent && window.parent.document.documentElement.hasAttribute('data-theme')) {
    document.documentElement.setAttribute('data-theme', window.parent.document.documentElement.getAttribute('data-theme'));
  }
} catch(e) {}

/* ── STATION TOOLTIPS ────────────────────────── */
const tip = document.getElementById('tip');
document.querySelectorAll('.station').forEach(el => {
  el.style.cursor = 'pointer';
  el.addEventListener('mouseenter', e => {
    document.getElementById('tip-name').textContent = el.dataset.name;
    document.getElementById('tip-line').textContent = el.dataset.line || '';
    document.getElementById('tip-desc').textContent = el.dataset.desc || '';
    tip.style.display = 'block';
    positionTip(e);
  });
  el.addEventListener('mousemove', positionTip);
  el.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
});

function positionTip(e) {
  const x = e.clientX + 14;
  const y = e.clientY - 10;
  const tw = tip.offsetWidth;
  const th = tip.offsetHeight;
  tip.style.left = (x + tw > window.innerWidth - 10 ? x - tw - 20 : x) + 'px';
  tip.style.top  = (y + th > window.innerHeight - 10 ? y - th - 10 : y) + 'px';
}

/* ── ZOOM ────────────────────────────────────── */
let scale = 1;
const svg = document.getElementById('tube-svg');
if (svg) {
  document.getElementById('zoom-in').addEventListener('click', () => {
    scale = Math.min(scale + 0.15, 2.5);
    svg.style.transform = `scale(${scale})`;
    svg.style.transformOrigin = 'top left';
  });
  document.getElementById('zoom-out').addEventListener('click', () => {
    scale = Math.max(scale - 0.15, 0.5);
    svg.style.transform = `scale(${scale})`;
    svg.style.transformOrigin = 'top left';
  });
}
window.VIZOR_DATA = __JSON_DATA__;
</script>
__LIVE_JS_HTML__
</body>
</html>"""

    return (
        template.replace("__STYLE_CONTENT__", style_content)
        .replace("__WORKSPACE_NAME__", workspace_name)
        .replace("__NUM_LINES__", str(num_lines))
        .replace("__NUM_INTERCHANGES__", str(num_interchanges))
        .replace("__HUB_SUFFIX__", hub_suffix)
        .replace("__LINES_SVG__", lines_svg)
        .replace("__STATIONS_SVG__", stations_svg)
        .replace("__LEGEND_LINES__", legend_lines)
        .replace("__JSON_DATA__", json_data)
        .replace("__LIVE_JS_HTML__", live_js_html)
    )


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
        "design": "#f39c6b",
        "plan": "#7b8cff",
        "build": "#1a9e5c",
        "ship": "#0d9e87",
        "sustain": "#888888",
    }.get(stage, "#0d9e87")


def generate_effort_html(data: dict, port: int) -> str:
    costs = data.get("costs") or {}
    dreams = list(data.get("dreams") or [])
    by_agent = dict(costs.get("by_agent") or {})
    by_stage = dict(costs.get("by_stage") or {})
    total_usd = float(costs.get("total_usd") or 0.0)

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
    top_agent = max(by_agent.items(), key=lambda item: float(item[1] or 0.0))[0] if by_agent else "—"

    def build_summary_cards() -> str:
        cards = [
            ("Total Spend", _fmt_usd(total_usd)),
            ("Dreams In Flight", str(dreams_in_flight)),
            ("Over Budget", str(over_budget)),
            ("Top Agent", _svg_text(top_agent)),
        ]
        return "".join(
            f'<div class="stat"><span>{label}</span><strong>{value}</strong></div>'
            for label, value in cards
        )

    def render_bar_chart(rows, title, value_key, color_fn, label_fn, empty_text, max_value=None) -> str:
        rows = list(rows)
        row_count = max(len(rows), 1)
        svg_height = 54 + row_count * 30
        max_value = max_value or max([float(row.get(value_key) or 0.0) for row in rows] + [0.0]) or 1.0
        svg_rows = []
        if rows:
            for idx, row in enumerate(rows):
                value = float(row.get(value_key) or 0.0)
                y = 18 + idx * 30
                width = (value / max_value) * 380 if max_value else 0.0
                bar_color = color_fn(row, value)
                label = label_fn(row, value)
                svg_rows.append(
                    f'<text x="0" y="{y + 7}" class="y-label">{_svg_text(row.get("label") or row.get("name") or row.get("key") or "")}</text>'
                    f'<rect x="110" y="{y}" width="{width:.2f}" height="18" rx="9" fill="{bar_color}"></rect>'
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
            "cost_est": dream.get("cost_est"),
            "cost_total": float(dream.get("cost_total") or 0.0),
        }
        for dream in dreams_sorted
    ]

    agent_rows = [
        {"label": agent, "name": agent, "value": float(spend or 0.0), "spend": float(spend or 0.0)}
        for agent, spend in sorted(by_agent.items(), key=lambda item: float(item[1] or 0.0), reverse=True)
        if float(spend or 0.0) > 0
    ]

    stage_rows = [
        {"label": stage, "name": stage, "value": float(spend or 0.0), "spend": float(spend or 0.0)}
        for stage, spend in sorted(by_stage.items(), key=lambda item: float(item[1] or 0.0), reverse=True)
        if float(spend or 0.0) > 0
    ]

    def dream_color(row, value):
        est = row.get("cost_est")
        if est is not None and value > float(est or 0.0):
            return "#e05"
        return "#0d9e87"

    def dream_label(row, value):
        est = row.get("cost_est")
        if est is None:
            return _fmt_usd(value)
        return f"{_fmt_usd(value)} / est {_fmt_usd(est)}"

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
        return f"{_fmt_usd(value)} ({_fmt_pct(pct)})"

    def stage_label(row, value):
        pct = (value / total_usd * 100.0) if total_usd else 0.0
        return f"{_fmt_usd(value)} ({_fmt_pct(pct)})"

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
      grid-template-columns: repeat(4, minmax(0, 1fr));
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
      .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
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
        <div class="subtle">Workspace spend, dream overruns, and agent allocation at a glance.</div>
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
    )}
    {render_bar_chart(
        agent_rows,
        "By Agent",
        "value",
        agent_color,
        agent_label,
        "No agent spend yet",
    )}
    {render_bar_chart(
        stage_rows,
        "By Stage",
        "value",
        stage_color,
        stage_label,
        "No stage spend yet",
    )}
  </main>
  {_live_js(port)}
</body>
</html>"""


def generate_efficiency_html(data: dict, port: int) -> str:
    import html
    import json

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

    def _avatar(name: str) -> tuple[str, str]:
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
      --ok:#16a34a; --warn:#d97706; --bad:#dc2626;
    }
    [data-theme="dark"] {
      --bg:#0d0f14; --bg2:#0a0c10; --bg3:#13171f;
      --border:#1e2430; --border2:#13171f;
      --text:#c9d1d9; --text2:#8b949e; --text3:#4a5568;
      --accent:#3de0c0; --accent-bg:#0d2137; --accent-dim:#0a3050;
      --shadow:0 2px 20px rgba(0,0,0,.5);

      --ag-claude-bg:#0d2a2a; --ag-claude-bd:#3de0c0; --ag-claude-tx:#3de0c0;
      --ag-agy-bg:#0d1a3a; --ag-agy-bd:#4285f4; --ag-agy-tx:#4285f4;
      --ag-codex-bg:#0a1f18; --ag-codex-bd:#10a37f; --ag-codex-tx:#10a37f;
      --ag-grok-bg:#1a1a1a; --ag-grok-bd:#e0e0e0; --ag-grok-tx:#e0e0e0;
      --ok:#4ade80; --warn:#fbbf24; --bad:#f87171;
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
    """

    if not agents:
        return f"""<!DOCTYPE html>
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
  <div class="empty-state"><span>No telemetry recorded yet. Run synlynk exec or synlynk launch to generate efficiency data.</span></div>
  {_live_js(port)}
</body>
</html>"""

    cards_html = []
    for name, stats in agents.items():
        rate = _rate(stats.get("success_rate"))
        alerts = int(stats.get("alert_count") or 0)
        initials, avatar_class = _avatar(name)
        dot_class = _dot_class(rate, alerts)
        bar_class = _bar_class(rate)
        alert_html = f'<div class="alert-count">{alerts} sentinel alerts</div>' if alerts > 0 else ""
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
          </div>
        </div>
            """.rstrip()
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

    <section class="section">
      <div class="section-head">
        <div class="section-title">Agent Cards</div>
        <div class="section-note">Traffic-light status uses success rate and sentinel alert count.</div>
      </div>
      <div class="{grid_class}">
        {''.join(cards_html)}
      </div>
    </section>

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


def _write_cache(data: dict, port: int) -> None:
    """Generate all views and write to viz-cache/."""
    os.makedirs(VIZ_CACHE_DIR, exist_ok=True)
    views = {
        "index.html": generate_index_html(data, port),
        "gantt.html": generate_gantt_html(data, port),
        "tube.html": generate_tube_html(data, port),
        "journeys.html": generate_journeys_html(data, port),
        "effort.html": generate_effort_html(data, port),
        "efficiency.html": generate_efficiency_html(data, port),
    }
    for filename, html in views.items():
        with open(os.path.join(VIZ_CACHE_DIR, filename), "w") as f:
            f.write(html)
    manifest = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "version": "0.1"}
    with open(os.path.join(VIZ_CACHE_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f)


class VizorHandler(http.server.SimpleHTTPRequestHandler):
    """Serves viz-cache/ and handles POST /note."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.abspath(VIZ_CACHE_DIR), **kwargs)

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        if self.path != "/note":
            self.send_error(404)
            return
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path != "/note":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            note = json.loads(body)
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
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

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


def _start_server(port: int) -> None:
    server = http.server.HTTPServer(("127.0.0.1", port), VizorHandler)
    meta = {"port": port, "serving": True}
    with open(VIZ_META_PATH, "w") as f:
        json.dump(meta, f)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


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
    has_ux = input("  Does this project have user-facing UX? (y/n) ").strip().lower() == "y"
    vizor["second_view"] = "journeys" if has_ux else "tube"
    notify = input("  Enable browser notifications? (y/n) ").strip().lower() == "y"
    vizor["notify_on_refresh"] = notify
    interval_raw = input("  Auto-refresh interval? (15 / 30 / off) [off] ").strip() or "off"
    vizor["refresh_interval_minutes"] = 0 if interval_raw == "off" else int(interval_raw)
    vizor["port"] = DEFAULT_PORT
    vizor["theme"] = "system"
    vizor["timeline_weeks"] = 10
    vizor["ftue_done"] = True
    config["vizor"] = vizor
    config_path = ".synlynk/config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print("  ✓ Settings saved to .synlynk/config.json\n")
    return config


def cmd_viz(args) -> None:
    """Entry point for `synlynk viz` subcommand."""
    import synlynk  # local import to avoid circular at module load
    config_path = ".synlynk/config.json"
    config = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)

    port = getattr(args, "port", None) or config.get("vizor", {}).get("port", DEFAULT_PORT)

    if args.stop:
        _stop_server()
        return

    if args.open:
        webbrowser.open(f"http://localhost:{port}/index.html")
        return

    if not args.generate:
        config = _ftue_prompts(config)
        port = getattr(args, "port", None) or config.get("vizor", {}).get("port", DEFAULT_PORT)

    print("  Generating Vizor views…")
    try:
        data = generate_viz_data()
    except NotImplementedError:
        data = {
            "workspace": {
                "name": os.path.basename(os.getcwd()) or "workspace",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "notes": {},
            "tube_config": None,
        }
    except Exception as e:
        print(f"  ✗ Data extraction failed: {e}")
        return

    _write_cache(data, port)
    print(f"  ✓ Views written to {VIZ_CACHE_DIR}/")

    if args.generate:
        print("  (--generate only: server not started)")
        return

    if not _server_is_running() or args.serve:
        server = _start_server(port)
        print(f"  ✓ Serving at http://localhost:{port}/")

    if not args.serve:
        webbrowser.open(f"http://localhost:{port}/index.html")
