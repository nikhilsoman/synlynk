"""BS-21 Vizor: local browser dashboard generator and server."""
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
    return f"<html><body>tube stub</body></html>"


def generate_journeys_html(data: dict, port: int) -> str:
    return f"<html><body>journeys stub</body></html>"


def generate_effort_html(data: dict, port: int) -> str:
    return f"<html><body>effort stub</body></html>"


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
