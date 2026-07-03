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

    def _looks_like_stage_label(name: str) -> bool:
        return _normalize_stage(name) in {"design", "plan", "build", "ship", "sustain"}

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
    return f"<html><body>index stub port={port}</body></html>"


def generate_gantt_html(data: dict, port: int) -> str:
    return f"<html><body>gantt stub</body></html>"


def generate_tube_html(data: dict, port: int) -> str:
    """Generate the Architect Map view (tube map style SVG or setup prompt)."""
    import json
    import math

    json_data = json.dumps(data)
    workspace_name = data.get("workspace", {}).get("name", "workspace")
    updated_at = data.get("workspace", {}).get("updated_at", "")

    # Check if _live_js function exists in the module.
    live_js_html = ""
    try:
        if "_live_js" in globals():
            live_js_html = globals()["_live_js"](port)
    except Exception:
        pass

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
    return f"<html><body>journeys stub</body></html>"


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
  <main class="shell">
    <section class="empty">
      <h1>Effort & Cost</h1>
      <p>No cost data yet. Cost entries are recorded automatically on each synlynk exec run.</p>
    </section>
  </main>
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
        return "var(--teal)"

    def dream_label(row, value):
        est = row.get("cost_est")
        if est is None:
            return _fmt_usd(value)
        return f"{_fmt_usd(value)} / est {_fmt_usd(est)}"

    def agent_color(row, value):
        agent = (row.get("label") or "").strip().lower()
        return {
            "claude": "var(--teal)",
            "agy": "var(--blue)",
            "codex": "var(--green)",
            "grok": "var(--gray)",
        }.get(agent, "var(--teal)")

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
</body>
</html>"""


def generate_efficiency_html(data: dict, port: int) -> str:
    return f"<html><body>efficiency stub</body></html>"


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
