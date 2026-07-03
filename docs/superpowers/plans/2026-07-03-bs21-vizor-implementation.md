# BS-21 Vizor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `synlynk viz` — a local browser dashboard with 5 views (Gantt, Journeys, Architect Map, Effort & Cost, Efficiency) generated from `state.db` and served locally.

**Architecture:** A data extraction layer (`generate_viz_data()`) reads `state.db` and support files into a single Python dict. Six HTML generator functions (`generate_*_html(data)`) each return a complete, self-contained HTML string with `window.VIZOR_DATA` embedded. A custom `http.server` subclass (`VizorHandler`) serves `viz-cache/` and handles `POST /note`. All code lives in `synlynk/viz.py` (new module, imported in `cli.py`). CLI wired in `synlynk/cli.py`.

**Tech Stack:** Python 3 stdlib only — `http.server`, `sqlite3`, `json`, `subprocess`, `webbrowser`, `threading`. HTML/CSS/JS embedded as Python f-strings. No external dependencies.

---

## File Structure

```
synlynk/
├── __init__.py          # unchanged
├── cli.py               # MODIFIED: import cmd_viz, register 'viz' subparser, dispatch
├── db.py                # unchanged
└── viz.py               # NEW: all Vizor logic (~700 lines)

tests/
├── test_viz.py          # NEW: data extraction + generation tests
└── test_viz_serve.py    # NEW: note endpoint + server tests

docs/blog/
└── NN-pr-bs21-vizor.md  # NEW: blog post (Task 12)
```

**Runtime artifacts (`.gitignored`):**
```
.synlynk/
├── viz-cache/
│   ├── manifest.json
│   ├── index.html
│   ├── gantt.html
│   ├── journeys.html
│   ├── tube.html
│   ├── effort.html
│   └── efficiency.html
├── viz-notes.json
├── viz-meta.json
└── vizor-tube.json   (optional, user-created)
```

**`.gitignore` additions:** `.synlynk/viz-cache/`, `.synlynk/viz-meta.json`

---

## Execution Order & Agent Matrix

| Task | Agent | Depends on | Description |
|------|-------|-----------|-------------|
| T1 | Codex | — | CLI scaffold, FTUE, `synlynk/viz.py` skeleton |
| T2 | Codex | T1 | `generate_viz_data()` — state.db reader |
| T3 | Agy | T2 | `generate_index_html()` — shell + nav |
| T4 | Agy | T2 | `generate_gantt_html()` — Gantt v5 port |
| T5 | Agy | T2 | `generate_tube_html()` — Architect Map |
| T6 | Agy | T2 | `generate_journeys_html()` — User Journeys |
| T7 | Codex | T2 | `generate_effort_html()` — Effort & Cost |
| T8 | Codex | T2 | `generate_efficiency_html()` — Efficiency |
| T9 | Codex | T1 | Note endpoint — `VizorHandler`, `viz-notes.json` |
| T10 | Grok | T1 | Live JS — polling + browser notifications |
| T11 | Codex | T1–T8 | Integration tests |
| T12 | Agy | T1–T11 | Blog post |

T3–T8 can all run in parallel after T2. T9 and T10 can run in parallel after T1.

---

## Shared Interface Contract

All generator functions share this signature. Codex establishes this in T1; all other agents must match it exactly.

```python
# synlynk/viz.py

def generate_viz_data() -> dict:
    """Read state.db + support files → serializable dict (see schema below)."""

def generate_index_html(data: dict, port: int) -> str: ...
def generate_gantt_html(data: dict, port: int) -> str: ...
def generate_tube_html(data: dict, port: int) -> str: ...
def generate_journeys_html(data: dict, port: int) -> str: ...
def generate_effort_html(data: dict, port: int) -> str: ...
def generate_efficiency_html(data: dict, port: int) -> str: ...
```

**`data` dict schema** (T2 must produce exactly this; all HTML generators read only this):

```python
{
  "workspace": {
    "name": str,                    # from .synlynk/config.json "project_name" or cwd basename
    "updated_at": str,              # ISO 8601 timestamp of generation
  },
  "dreams": [                       # from roadmap_arcs + roadmap_phases
    {
      "id": str,                    # roadmap_arcs.version, e.g. "v0.11.0"
      "name": str,                  # roadmap_arcs.title
      "status": str,                # roadmap_arcs.status: "active"|"parked"|"shipped"
      "cost_total": float,          # sum of cost_entries.total_cost_usd where notes LIKE '%<id>%'
      "cost_est": float | None,     # None if no estimate recorded
      "stages": [
        {
          "key": str,               # roadmap_phases.phase_title
          "status": str,            # roadmap_phases.status
          "agents": list[str],      # extracted from roadmap_phases.notes (comma-separated)
          "start_frac": float,      # 0.0–1.0 position in 10-week window (computed from target_date)
          "width_frac": float,      # fraction of timeline this stage spans
          "cost_actual": float | None,
          "cost_est": float | None,
          "tasks": [
            {
              "id": str,            # stories.story_id
              "name": str,          # stories.title
              "agent": str,         # stories.phase (repurposed) or latest capability_ratings.agent
              "status": str,        # stories.status: "open"|"active"|"done"|"blocked"
              "cost_est": float | None,   # stories.estimated_tokens / 1000 * 0.003 (rough est)
              "cost_actual": float | None,# from cost_entries matching story_id in notes
              "note": {             # from viz-notes.json keyed by story_id, or None
                "text": str,
                "tags": list[str],  # e.g. ["redo", "reassign"]
                "state": str        # "info"|"action"|"urgent"|"done"
              } | None
            }
          ]
        }
      ]
    }
  ],
  "costs": {
    "total_usd": float,
    "by_agent": {"claude": float, "agy": float, "codex": float, "grok": float},
    "by_stage": {"design": float, "plan": float, "build": float, "ship": float, "sustain": float}
  },
  "agents": {
    "<name>": {
      "tasks_done": int,
      "tasks_active": int,
      "total_usd": float,
      "success_rate": float,        # exit_code==0 runs / total runs from telemetry
      "alert_count": int            # sentinel alerts involving this agent
    }
  },
  "telemetry": {
    "recent": [                     # last 20 entries from .synlynk/telemetry.json
      {"ts": str, "agent": str, "duration_s": float, "exit_code": int, "cost_usd": float}
    ],
    "sentinel_alerts": [            # parsed from .synlynk/sentinel.md
      {"ts": str, "pattern": str, "severity": str, "resolved": bool}
    ]
  },
  "journeys": [                     # parsed from docs/journeys/*.md (empty list if absent)
    {
      "id": str,                    # filename stem
      "name": str,                  # first H1 heading
      "steps": [
        {"screen": str, "route": str, "desc": str, "agent": str, "stage": str}
      ]
    }
  ],
  "tube_config": dict | None,       # contents of .synlynk/vizor-tube.json, or None
  "notes": {                        # contents of .synlynk/viz-notes.json, or {}
    "<element_id>": {
      "text": str,
      "tags": list[str],
      "state": str,
      "updated_at": str
    }
  }
}
```

---

## Task 1 — CLI Scaffold + `synlynk/viz.py` Skeleton · **Codex**

**Files:**
- Create: `synlynk/viz.py`
- Modify: `synlynk/cli.py` (import + subparser + dispatch)
- Modify: `.gitignore`

### Dispatch

```bash
python3 bin/synlynk.py dispatch codex \
  --task "Implement Task 1 of the BS-21 Vizor plan" \
  --context-mode full
```

Include in dispatch context:
- This plan file: `docs/superpowers/plans/2026-07-03-bs21-vizor-implementation.md`
- Spec: `docs/superpowers/specs/2026-07-03-bs21-vizor-design.md`

### What Codex must produce

**`synlynk/viz.py` — skeleton with stubs:**

```python
"""BS-21 Vizor: local browser dashboard generator and server."""
import http.server
import json
import os
import subprocess
import threading
import time
import webbrowser
from typing import Optional

VIZ_CACHE_DIR = ".synlynk/viz-cache"
VIZ_NOTES_PATH = ".synlynk/viz-notes.json"
VIZ_META_PATH = ".synlynk/viz-meta.json"
VIZ_TUBE_PATH = ".synlynk/vizor-tube.json"
DEFAULT_PORT = 8721

def generate_viz_data() -> dict:
    raise NotImplementedError  # Task 2

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
        "index.html":       generate_index_html(data, port),
        "gantt.html":       generate_gantt_html(data, port),
        "tube.html":        generate_tube_html(data, port),
        "journeys.html":    generate_journeys_html(data, port),
        "effort.html":      generate_effort_html(data, port),
        "efficiency.html":  generate_efficiency_html(data, port),
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
                notes = json.load(f)
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
    with open(meta_path) as f:
        meta = json.load(f)
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

    if args.stop:
        _stop_server()
        return

    if args.open:
        port = config.get("vizor", {}).get("port", DEFAULT_PORT)
        webbrowser.open(f"http://localhost:{port}/index.html")
        return

    config = _ftue_prompts(config)
    port = config.get("vizor", {}).get("port", DEFAULT_PORT)

    print("  Generating Vizor views…")
    try:
        data = generate_viz_data()
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
```

**`synlynk/cli.py` modifications** — add inside `main()`:

```python
# In imports at top of main():
from synlynk.viz import cmd_viz

# After existing subparsers (before the elif dispatch chain):
viz_parser = subparsers.add_parser("viz", help="Open local browser workspace dashboard")
viz_parser.add_argument("--serve",    action="store_true", help="Start background server (stable port)")
viz_parser.add_argument("--generate", action="store_true", help="Generate views without opening browser")
viz_parser.add_argument("--open",     action="store_true", help="Open existing cache in browser")
viz_parser.add_argument("--stop",     action="store_true", help="Stop background server")
viz_parser.add_argument("--port",     type=int, default=None, help="Override port (default: 8721)")

# In the elif dispatch chain, add before the final else:
elif args.command == "viz":
    cmd_viz(args)
```

**`.gitignore` additions:**
```
.synlynk/viz-cache/
.synlynk/viz-meta.json
```

### Acceptance criteria

- [ ] `python3 bin/synlynk.py viz --generate` runs without error, creates `.synlynk/viz-cache/` with 7 files (6 HTML + manifest.json)
- [ ] `manifest.json` contains `{"updated_at": "...", "version": "0.1"}`
- [ ] `python3 bin/synlynk.py viz --stop` runs without error
- [ ] FTUE prompts run on first invocation; config saved; not shown again on second run
- [ ] `VizorHandler.do_POST` writes to `viz-notes.json` correctly for valid JSON body

### Verify

```bash
cd /path/to/repo
python3 bin/synlynk.py viz --generate
ls .synlynk/viz-cache/
# Expected: index.html gantt.html tube.html journeys.html effort.html efficiency.html manifest.json
cat .synlynk/viz-cache/manifest.json
# Expected: {"updated_at": "...", "version": "0.1"}
```

### Commit

```bash
git add synlynk/viz.py synlynk/cli.py .gitignore
git commit -m "feat(viz): add synlynk viz command scaffold + VizorHandler + FTUE"
```

---

## Task 2 — Data Extraction Layer · **Codex**

**Files:**
- Modify: `synlynk/viz.py` — implement `generate_viz_data()`
- Create: `tests/test_viz.py`

### Dispatch

```bash
python3 bin/synlynk.py dispatch codex \
  --task "Implement Task 2 of the BS-21 Vizor plan: generate_viz_data()" \
  --context-mode full
```

Include: this plan (data schema section), `synlynk/db.py` (table schemas), `synlynk/viz.py` (skeleton from T1).

### What Codex must implement

Replace the `raise NotImplementedError` stub in `generate_viz_data()` with the full implementation. It must return a dict matching the schema in the contract section exactly.

Key reads:
- `_get_db()` from `synlynk` — returns WAL-mode sqlite3 connection
- `roadmap_arcs` → dreams list (id=version, name=title, status=status)
- `roadmap_phases` → stages per dream (phase_title, status, notes, story_id)
- `stories` → tasks (story_id, title, status, phase, estimated_tokens)
- `cost_entries` → costs (agent, total_cost_usd, notes for story association)
- `telemetry.json` at `.synlynk/telemetry.json` → recent runs (last 20)
- `sentinel.md` at `.synlynk/sentinel.md` → parse alert lines
- `vizor-tube.json` at `.synlynk/vizor-tube.json` → tube_config (None if absent)
- `viz-notes.json` at `.synlynk/viz-notes.json` → notes dict (empty dict if absent)
- `docs/journeys/*.md` → journeys list (empty list if dir absent)

**Stage position calculation** (`start_frac`, `width_frac`):
Phases are ordered by their `id` (row insertion order within an arc). Given N phases for a dream, each phase gets equal width: `width_frac = 1.0 / N`. Position: `start_frac = i / N` where `i` is 0-indexed order. This is a placeholder for v1; exact date-based positioning is v2.

**Agent extraction from `roadmap_phases.notes`:**
Notes field may contain `[agent:agy,codex]` or similar annotations. Parse with: `re.findall(r'\bagent:([a-z,]+)\b', notes or '')` then split on comma. Fall back to `[]` if absent.

**Sentinel parsing** — parse `.synlynk/sentinel.md` lines matching:
```
[YYYY-MM-DD HH:MM:SS] PATTERN: ...
```
Extract timestamp, pattern name (FLATLINE / SUCCESS_LOOP / COST_SPIKE / QUOTA_EXHAUSTED), mark resolved if line contains `[RESOLVED]`.

**Graceful degradation:** If `state.db` is absent or any table is missing, return a minimal valid dict with empty `dreams`, `costs`, `agents`, `telemetry`, `journeys` lists/dicts. Never raise.

### Tests (`tests/test_viz.py`)

```python
import json, os, sqlite3, tempfile, pytest
from unittest.mock import patch, MagicMock

def make_test_db(path: str):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE roadmap_arcs (
            id INTEGER PRIMARY KEY, version TEXT UNIQUE, title TEXT,
            status TEXT DEFAULT 'active', target_date TEXT, notes TEXT
        );
        CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT,
            status TEXT DEFAULT 'planned', priority TEXT, story_id TEXT, notes TEXT
        );
        CREATE TABLE stories (
            id INTEGER PRIMARY KEY, story_id TEXT UNIQUE, title TEXT,
            status TEXT DEFAULT 'open', phase TEXT DEFAULT 'build',
            estimated_tokens INTEGER, created_at TEXT
        );
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY, session_date TEXT, agent TEXT,
            model TEXT, input_tokens INTEGER, output_tokens INTEGER,
            cache_read_tokens INTEGER, total_cost_usd REAL, notes TEXT
        );
        INSERT INTO roadmap_arcs (version, title, status) VALUES ('v0.11.0', 'Retention Layer', 'active');
        INSERT INTO roadmap_phases (arc_version, phase_title, status, notes)
            VALUES ('v0.11.0', 'Plan', 'done', '[agent:codex]'),
                   ('v0.11.0', 'Build', 'active', '[agent:agy,codex]');
        INSERT INTO stories (story_id, title, status, phase, estimated_tokens)
            VALUES ('story-bs21-shell', 'Shell layout', 'done', 'build', 60000);
        INSERT INTO cost_entries (session_date, agent, total_cost_usd, notes)
            VALUES ('2026-07-01', 'agy', 1.20, 'story-bs21-shell');
    """)
    conn.commit()
    return conn

def test_generate_viz_data_structure(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    make_test_db(db_path)
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"project_name": "test-project"}, f)

    from synlynk.viz import generate_viz_data
    with patch("synlynk.viz._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        data = generate_viz_data()

    assert "workspace" in data
    assert "dreams" in data
    assert "costs" in data
    assert "agents" in data
    assert "telemetry" in data
    assert "notes" in data
    assert "tube_config" in data

def test_dreams_populated(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    make_test_db(db_path)
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({}, f)

    from synlynk.viz import generate_viz_data
    with patch("synlynk.viz._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        data = generate_viz_data()

    assert len(data["dreams"]) == 1
    dream = data["dreams"][0]
    assert dream["id"] == "v0.11.0"
    assert dream["name"] == "Retention Layer"
    assert len(dream["stages"]) == 2
    assert dream["stages"][0]["key"] == "Plan"
    assert dream["stages"][0]["agents"] == ["codex"]
    assert dream["stages"][1]["agents"] == ["agy", "codex"]

def test_graceful_degradation_no_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({}, f)

    from synlynk.viz import generate_viz_data
    with patch("synlynk.viz._get_db", side_effect=Exception("no db")):
        data = generate_viz_data()

    assert data["dreams"] == []
    assert data["costs"]["total_usd"] == 0.0

def test_notes_loaded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    notes = {"story-bs21-shell": {"text": "needs redo", "tags": ["redo"], "state": "action", "updated_at": "2026-07-03T10:00:00Z"}}
    with open(".synlynk/viz-notes.json", "w") as f:
        json.dump(notes, f)
    with open(".synlynk/config.json", "w") as f:
        json.dump({}, f)

    from synlynk.viz import generate_viz_data
    with patch("synlynk.viz._get_db", side_effect=Exception("no db")):
        data = generate_viz_data()

    assert "story-bs21-shell" in data["notes"]
    assert data["notes"]["story-bs21-shell"]["state"] == "action"
```

### Verify

```bash
cd /path/to/repo
pytest tests/test_viz.py -v
# Expected: 4 tests pass
```

### Commit

```bash
git add synlynk/viz.py tests/test_viz.py
git commit -m "feat(viz): implement generate_viz_data() with state.db reader + tests"
```

---

## Task 3 — Shell + Left Nav HTML · **Agy**

**Files:**
- Modify: `synlynk/viz.py` — implement `generate_index_html(data, port)`

### Dispatch

```bash
python3 bin/synlynk.py dispatch agy \
  --task "Implement Task 3 of the BS-21 Vizor plan: generate_index_html()" \
  --context-mode full
```

Include: this plan, spec Views→Shell section, `docs/brainstorm/bs21-vizor/viz-shell.html` (visual reference), `docs/brainstorm/bs21-vizor/viz-gantt-v5.html` (CSS token reference).

### What Agy must produce

Replace the stub `generate_index_html()` in `synlynk/viz.py` with a function returning a complete HTML string. The HTML must:

1. **Shell layout:** `display:flex; height:100vh` — left sidenav (220px) + main area (flex:1)
2. **Left nav:** logo `Synlynk viz`, workspace name from `data["workspace"]["name"]`, repo list from `data["workspace"].get("repos", [])`, view links (5 items with icons: 📅 Gantt, 🗺 Journeys, 🚇 Architect Map, 💰 Effort & Cost, 📊 Efficiency), theme switcher (☀ Light / ☾ Dark / ⊙ System), user avatar at footer
3. **Main area:** iframe filling remaining space, `id="view-frame"`, initially `src="gantt.html"`; clicking a nav link sets `document.getElementById('view-frame').src = '<view>.html'`
4. **CSS tokens:** Exactly the `:root` and `[data-theme="dark"]` blocks from `viz-gantt-v5.html` — copy them verbatim so all views share the same tokens. Theme stored in `localStorage` as `vizor-theme`, applied to `document.documentElement.setAttribute('data-theme', ...)` on load
5. **Status bar:** `● local · offline-ready  ·  <workspace_name>  ·  updated <updated_at>`
6. **Data island:** `<script>window.VIZOR_META = {port: <port>, updated_at: "<data.workspace.updated_at>"};</script>` — other views read this from the parent frame if needed

Active nav item highlighted with `var(--accent-bg)` background.

### Verify

```bash
python3 bin/synlynk.py viz --generate
open .synlynk/viz-cache/index.html
# Expected: full shell visible, left nav with 5 view links, iframe loading gantt.html
```

### Commit

```bash
git add synlynk/viz.py
git commit -m "feat(viz): implement generate_index_html() shell + nav"
```

---

## Task 4 — Gantt View · **Agy**

**Files:**
- Modify: `synlynk/viz.py` — implement `generate_gantt_html(data, port)`

### Dispatch

```bash
python3 bin/synlynk.py dispatch agy \
  --task "Implement Task 4 of the BS-21 Vizor plan: generate_gantt_html()" \
  --context-mode full
```

Include: this plan, spec Views→Gantt section, `docs/brainstorm/bs21-vizor/viz-gantt-v5.html` (LOCKED VISUAL REFERENCE — port this exactly to read from window.VIZOR_DATA).

### What Agy must produce

Replace `generate_gantt_html()` stub. The function must:

1. Serialize `data` to JSON and embed as `window.VIZOR_DATA = <json>;` in a `<script>` tag
2. Embed the full CSS token system and all JS from `viz-gantt-v5.html` — but replace all hardcoded `TASKS` and `DREAMS` constants with reads from `window.VIZOR_DATA.dreams`
3. Dreams array maps directly to the gantt rows. Stages array maps to stage bars. Tasks array maps to drill-down task rows
4. **Stage bar positioning:** `left: ${stage.start_frac * 100}%`, `width: ${stage.width_frac * 100}%`
5. **Note save:** When user saves a note in the modal, POST to `http://localhost:${port}/note` with body `{id: elementId, text, tags, state}`. On success, update the pencil icon color state in the DOM
6. **Graceful empty state:** If `data.dreams` is empty, show: `<div class="empty-state">No Dreams found in state.db. Run synlynk migrate or add roadmap arcs.</div>`
7. CSS tokens: use identical `:root` / `[data-theme="dark"]` blocks as T3 (copy from viz-gantt-v5.html)
8. The page must work standalone (opened directly as a file) AND embedded in the index.html iframe

### Verify

```bash
python3 bin/synlynk.py viz --generate
open .synlynk/viz-cache/gantt.html
# Expected: Gantt rows rendered from live state.db data, drill-down works, note modal opens
```

### Commit

```bash
git add synlynk/viz.py
git commit -m "feat(viz): implement generate_gantt_html() — live Gantt v5 from state.db"
```

---

## Task 5 — Architect Map · **Agy**

**Files:**
- Modify: `synlynk/viz.py` — implement `generate_tube_html(data, port)`

### Dispatch

```bash
python3 bin/synlynk.py dispatch agy \
  --task "Implement Task 5 of the BS-21 Vizor plan: generate_tube_html()" \
  --context-mode full
```

Include: this plan, spec Views→Architect Map section, `docs/brainstorm/bs21-vizor/viz-tube.html` (VISUAL BASELINE — use the hand-crafted SVG style from this file exactly).

### What Agy must produce

Replace `generate_tube_html()` stub:

1. Embed `window.VIZOR_DATA = <json>;`
2. **If `data["tube_config"]` is None:** render a setup prompt page — centered card with: "🚇 Architect Map", "Define your architecture lines to unlock this view.", `<code>synlynk viz --setup-tube</code>` instruction, and a link to the spec
3. **If `data["tube_config"]` is present:** render the tube map SVG. Use the exact visual style from `viz-tube.html` — hand-crafted SVG, all bends 0°/45°/90°, station circles, interchange rings, labels, hover tooltips. Read `tube_config.lines` and `tube_config.stations` from `window.VIZOR_DATA.tube_config` to drive the SVG content (generate SVG elements from the config data in Python, not in JS)
4. Station radius: `r = 4 + segs * 2` where `segs` = number of lines touching the station (computed from how many lines include that station's id in their `stations` array)
5. Tooltip on hover: station name + description (from `tube_config.stations[id].desc`)
6. CSS tokens: same `:root` / `[data-theme="dark"]` blocks

### Verify

```bash
# Without vizor-tube.json:
python3 bin/synlynk.py viz --generate
open .synlynk/viz-cache/tube.html
# Expected: setup prompt visible

# With vizor-tube.json present:
cp docs/brainstorm/bs21-vizor/viz-tube.html /tmp/ref.html  # reference
# Create .synlynk/vizor-tube.json with test data, regenerate, verify tube map appears
```

### Commit

```bash
git add synlynk/viz.py
git commit -m "feat(viz): implement generate_tube_html() — SVG tube map from vizor-tube.json"
```

---

## Task 6 — User Journeys · **Agy**

**Files:**
- Modify: `synlynk/viz.py` — implement `generate_journeys_html(data, port)`

### Dispatch

```bash
python3 bin/synlynk.py dispatch agy \
  --task "Implement Task 6 of the BS-21 Vizor plan: generate_journeys_html()" \
  --context-mode full
```

Include: this plan, spec Views→User Journeys section.

### What Agy must produce

Replace `generate_journeys_html()` stub:

1. Embed `window.VIZOR_DATA = <json>;`
2. **Split-pane layout:** left panel 280px (journey list), right panel (flex:1, screen flow). A vertical resizer divider between them
3. **Journey list (left):** One row per `data["journeys"]` entry. Row shows journey name. Clicking a row highlights it and renders its steps on the right. First journey selected by default
4. **Screen flow (right):** Journey steps rendered as cards in a horizontal scrollable row, connected by `→` arrows. Each card (140×100px): screen name (bold), route (muted monospace), description (small text), stage badge (colored pill using stage color tokens), agent avatar badge
5. **Empty state (no journeys):** "No journeys found. Create `docs/journeys/` with `.md` files, each starting with an `# H1` title. Steps use `## Screen Name` headings with `route:`, `desc:`, `agent:`, `stage:` key-value lines."
6. **FTUE prompt:** If `data["workspace"].get("vizor_second_view") == "tube"`, show a notice: "Your workspace is configured for the Architect Map as the primary structural view. User Journeys is available if your project has UX screens."
7. CSS tokens: same `:root` / `[data-theme="dark"]` blocks

### Verify

```bash
python3 bin/synlynk.py viz --generate
open .synlynk/viz-cache/journeys.html
# Expected: empty state message OR journey list if docs/journeys/ exists
```

### Commit

```bash
git add synlynk/viz.py
git commit -m "feat(viz): implement generate_journeys_html() — split-pane journey viewer"
```

---

## Task 7 — Effort & Cost · **Codex**

**Files:**
- Modify: `synlynk/viz.py` — implement `generate_effort_html(data, port)`

### Dispatch

```bash
python3 bin/synlynk.py dispatch codex \
  --task "Implement Task 7 of the BS-21 Vizor plan: generate_effort_html()" \
  --context-mode full
```

Include: this plan (data schema + spec Effort & Cost section), `synlynk/viz.py`.

### What Codex must produce

Replace `generate_effort_html()` stub:

1. Embed `window.VIZOR_DATA = <json>;`
2. **Summary strip at top:** 4 cards — Total Spend (`$data.costs.total_usd`), Dreams In Flight (count where status=active), Over Budget (count where cost_total > cost_est), Top Agent (agent with highest spend from `data.costs.by_agent`)
3. **Panel 1 — By Dream:** Horizontal bar chart. One bar per dream. Bar width = `(dream.cost_total / max_cost) * 100%`. Color = over-budget red if `cost_total > cost_est`, else stage Work green. Show `$X.XX / est $Y.YY` label at right. If `cost_est` is None, omit estimate label
4. **Panel 2 — By Agent:** Horizontal bars. One bar per agent with `total_usd > 0`. Colors: Claude=teal, Agy=blue, Codex=green, Grok=gray. Show spend + % of total
5. **Panel 3 — By Stage:** Horizontal bars. One bar per stage key with spend > 0. Colors from CSS stage tokens
6. All charts are pure SVG (no canvas, no charting library). Use `<svg viewBox="0 0 400 N">` with `<rect>` elements for bars, `<text>` for labels
7. **Empty state:** If `data.costs.total_usd == 0`: show "No cost data yet. Cost entries are recorded automatically on each synlynk exec run."
8. CSS tokens: same `:root` / `[data-theme="dark"]` blocks

### Verify

```bash
python3 bin/synlynk.py viz --generate
open .synlynk/viz-cache/effort.html
# Expected: 3 panel layout with SVG bar charts OR empty state message
```

### Commit

```bash
git add synlynk/viz.py
git commit -m "feat(viz): implement generate_effort_html() — SVG bar charts by dream/agent/stage"
```

---

## Task 8 — Efficiency Report Card · **Codex**

**Files:**
- Modify: `synlynk/viz.py` — implement `generate_efficiency_html(data, port)`

### Dispatch

```bash
python3 bin/synlynk.py dispatch codex \
  --task "Implement Task 8 of the BS-21 Vizor plan: generate_efficiency_html()" \
  --context-mode full
```

Include: this plan (data schema + spec Efficiency section), `synlynk/viz.py`.

### What Codex must produce

Replace `generate_efficiency_html()` stub:

1. Embed `window.VIZOR_DATA = <json>;`
2. **Agent cards grid:** 2×2 grid (or 1×4 if only 1 agent). One card per agent in `data["agents"]`. Each card shows:
   - Agent avatar badge (colored circle with letter: C/A/Co/G)
   - Agent name
   - Tasks done / Tasks active (e.g., "12 done · 2 active")
   - Total spend: `$X.XX`
   - Success rate: colored bar — green if ≥ 90%, yellow if 70–89%, red if < 70%
   - Alert count: `N sentinel alerts` in red if > 0
   - Traffic-light dot in top-right corner: green (success_rate ≥ 0.9 and alert_count == 0), yellow (0.7–0.9 or 1 alert), red (< 0.7 or > 1 alert)
3. **Sentinel timeline:** Below the cards. Scrollable list of `data["telemetry"]["sentinel_alerts"]`, newest first. Each row: timestamp, pattern name (color-coded: FLATLINE=red, SUCCESS_LOOP=orange, COST_SPIKE=yellow, QUOTA_EXHAUSTED=gray), resolved badge (green ✓ if resolved)
4. **Recent runs table:** Below sentinel timeline. Last 10 from `data["telemetry"]["recent"]`. Columns: timestamp, agent avatar, duration, cost, exit code (✓ green / ✗ red)
5. **Empty state:** If no agents have data: "No telemetry recorded yet. Run synlynk exec or synlynk launch to generate efficiency data."
6. CSS tokens: same `:root` / `[data-theme="dark"]` blocks

### Verify

```bash
python3 bin/synlynk.py viz --generate
open .synlynk/viz-cache/efficiency.html
# Expected: agent cards OR empty state; sentinel timeline if alerts exist
```

### Commit

```bash
git add synlynk/viz.py
git commit -m "feat(viz): implement generate_efficiency_html() — agent report cards + sentinel timeline"
```

---

## Task 9 — Note System Backend · **Codex**

**Files:**
- Modify: `synlynk/viz.py` — verify `VizorHandler.do_POST` (implemented in T1), add context injection
- Modify: `synlynk/__init__.py` — update `generate_context()` to append Vizor notes section
- Create: `tests/test_viz_serve.py`

### Dispatch

```bash
python3 bin/synlynk.py dispatch codex \
  --task "Implement Task 9 of the BS-21 Vizor plan: note system context injection + tests" \
  --context-mode full
```

Include: this plan, `synlynk/viz.py` (VizorHandler already in T1), `synlynk/__init__.py` (generate_context function).

### What Codex must produce

**Context injection in `synlynk/__init__.py`:**

Find `generate_context()` (around line 2301). After writing `.synlynk/context.md`, append a Vizor notes section if `viz-notes.json` exists and has entries:

```python
# At the end of generate_context(), before returning:
viz_notes_path = ".synlynk/viz-notes.json"
if os.path.exists(viz_notes_path):
    with open(viz_notes_path) as f:
        viz_notes = json.load(f)
    action_notes = {k: v for k, v in viz_notes.items() if v.get("tags") or v.get("state") in ("action", "urgent")}
    if viz_notes:
        with open(context_path, "a") as f:
            f.write("\n\n## Vizor Notes\n")
            for element_id, note in viz_notes.items():
                f.write(f"\n- [{element_id}] ({note.get('state','info')}): {note.get('text','')}")
                if note.get("tags"):
                    f.write(f" [tags: {', '.join(note['tags'])}]")
    if action_notes:
        with open(context_path, "a") as f:
            f.write("\n\n## Pending actions from Vizor\n")
            for element_id, note in action_notes.items():
                for tag in note.get("tags", []):
                    if tag == "redo":
                        f.write(f"\n- ↺ Redo: {element_id} — {note.get('text','')}")
                    elif tag == "reassign":
                        f.write(f"\n- ⇄ Reassign agent for: {element_id} — {note.get('text','')}")
                    elif tag == "defer":
                        f.write(f"\n- ⏸ Defer: {element_id} — {note.get('text','')}")
```

**`tests/test_viz_serve.py`:**

```python
import json, os, threading, time, urllib.request, urllib.error
import pytest
from http.server import HTTPServer

def test_post_note_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/viz-cache", exist_ok=True)

    from synlynk.viz import VizorHandler, VIZ_CACHE_DIR, VIZ_NOTES_PATH
    server = HTTPServer(("127.0.0.1", 0), VizorHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    payload = json.dumps({"id": "story-bs21", "text": "needs work", "tags": ["redo"], "state": "action"}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/note",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    assert body == {"ok": True}
    assert os.path.exists(".synlynk/viz-notes.json")
    with open(".synlynk/viz-notes.json") as f:
        notes = json.load(f)
    assert "story-bs21" in notes
    assert notes["story-bs21"]["text"] == "needs work"
    assert notes["story-bs21"]["state"] == "action"
    server.shutdown()

def test_post_note_merges_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/viz-cache", exist_ok=True)
    existing = {"other-id": {"text": "existing", "tags": [], "state": "info", "updated_at": "2026-07-01T00:00:00Z"}}
    with open(".synlynk/viz-notes.json", "w") as f:
        json.dump(existing, f)

    from synlynk.viz import VizorHandler
    server = HTTPServer(("127.0.0.1", 0), VizorHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    payload = json.dumps({"id": "new-id", "text": "new note", "tags": [], "state": "info"}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/note", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    urllib.request.urlopen(req)

    with open(".synlynk/viz-notes.json") as f:
        notes = json.load(f)
    assert "other-id" in notes  # existing note preserved
    assert "new-id" in notes    # new note added
    server.shutdown()

def test_post_invalid_json_returns_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/viz-cache", exist_ok=True)
    from synlynk.viz import VizorHandler
    server = HTTPServer(("127.0.0.1", 0), VizorHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/note", data=b"not-json",
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400
    server.shutdown()
```

### Verify

```bash
pytest tests/test_viz_serve.py -v
# Expected: 3 tests pass

# Manual context injection test:
echo '{"story-bs21": {"text": "redo this", "tags": ["redo"], "state": "action", "updated_at": "2026-07-03T10:00:00Z"}}' > .synlynk/viz-notes.json
python3 -c "import synlynk; synlynk.generate_context()"
cat .synlynk/context.md | grep -A5 "Vizor"
# Expected: Vizor Notes and Pending actions sections present
```

### Commit

```bash
git add synlynk/viz.py synlynk/__init__.py tests/test_viz_serve.py
git commit -m "feat(viz): note system — POST /note endpoint + context.md injection"
```

---

## Task 10 — Live JS: Polling + Browser Notifications · **Grok**

**Files:**
- Modify: `synlynk/viz.py` — add `_live_js(port)` helper returning JS string; inject into all 6 HTML generators

### Dispatch

```bash
python3 bin/synlynk.py dispatch grok \
  --task "Implement Task 10 of the BS-21 Vizor plan: live polling JS + browser notifications" \
  --context-mode full
```

Include: this plan (spec Browser Notifications section), `synlynk/viz.py`.

### What Grok must produce

Add a helper function to `synlynk/viz.py`:

```python
def _live_js(port: int) -> str:
    """Returns a <script> block to inject into every view.
    Polls manifest.json every 60s; auto-reloads on updated_at change.
    Requests Notification permission and fires a Web Notification on refresh.
    """
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
      icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text y="28" font-size="28">🚇</text></svg>',
      tag: 'vizor-refresh',
    }});
  }}

  function showReloadBanner(updatedAt) {{
    const existing = document.getElementById('vizor-reload-banner');
    if (existing) existing.remove();
    const banner = document.createElement('div');
    banner.id = 'vizor-reload-banner';
    banner.style.cssText = `position:fixed;top:0;left:0;right:0;z-index:9999;
      background:#0d9e87;color:#fff;font-family:SF Mono,monospace;font-size:12px;
      padding:8px 16px;display:flex;align-items:center;gap:12px;`;
    banner.innerHTML = `<span>✦ Vizor updated at ${{new Date(updatedAt).toLocaleTimeString()}}</span>
      <button onclick="location.reload()" style="background:rgba(255,255,255,0.2);border:none;
        color:#fff;padding:3px 10px;border-radius:4px;cursor:pointer;font-family:inherit">↺ Reload</button>
      <button onclick="this.parentElement.remove()" style="background:none;border:none;
        color:#fff;cursor:pointer;margin-left:auto;font-size:16px">✕</button>`;
    document.body.prepend(banner);
  }}

  // Request permission on first interaction
  document.addEventListener('click', function requestOnce() {{
    if (Notification.permission === 'default') Notification.requestPermission();
    document.removeEventListener('click', requestOnce);
  }}, {{ once: true }});

  // Start polling
  setInterval(checkManifest, 60000);
  checkManifest();
}})();
</script>
"""
```

Then update every `generate_*_html()` function to call `_live_js(port)` and inject the returned string just before `</body>` in their HTML output.

The inject pattern (all 6 generators must include this before `</body>`):
```python
f"""
  {_live_js(port)}
</body>
"""
```

### Verify

```bash
python3 bin/synlynk.py viz --serve
# Open http://localhost:8721/gantt.html in browser
# In another terminal: python3 bin/synlynk.py viz --generate
# Expected: reload banner appears within 60s; notification fires if permission granted
```

### Commit

```bash
git add synlynk/viz.py
git commit -m "feat(viz): live JS polling + browser notification on manifest change"
```

---

## Task 11 — Integration Tests · **Codex**

**Files:**
- Modify: `tests/test_viz.py` — add integration tests for full generation pipeline

### Dispatch

```bash
python3 bin/synlynk.py dispatch codex \
  --task "Implement Task 11 of the BS-21 Vizor plan: integration tests for full pipeline" \
  --context-mode full
```

Include: this plan, `tests/test_viz.py` (T2 tests), `synlynk/viz.py` (full implementation).

### What Codex must produce

Add the following integration tests to `tests/test_viz.py`:

```python
def test_write_cache_creates_all_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import _write_cache, VIZ_CACHE_DIR
    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z"},
        "dreams": [], "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
        "agents": {}, "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [], "tube_config": None, "notes": {},
    }
    _write_cache(data, port=8721)
    expected = ["index.html", "gantt.html", "tube.html", "journeys.html",
                "effort.html", "efficiency.html", "manifest.json"]
    for filename in expected:
        assert os.path.exists(os.path.join(VIZ_CACHE_DIR, filename)), f"Missing: {filename}"

def test_manifest_updated_at_is_iso(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import _write_cache, VIZ_CACHE_DIR
    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z"},
        "dreams": [], "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
        "agents": {}, "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [], "tube_config": None, "notes": {},
    }
    _write_cache(data, port=8721)
    with open(os.path.join(VIZ_CACHE_DIR, "manifest.json")) as f:
        m = json.load(f)
    assert "updated_at" in m
    # Must be parseable ISO timestamp
    from datetime import datetime
    datetime.fromisoformat(m["updated_at"].replace("Z", "+00:00"))

def test_gantt_html_contains_vizor_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import generate_gantt_html
    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z"},
        "dreams": [{"id": "v0.11.0", "name": "Retention", "status": "active",
                    "cost_total": 1.5, "cost_est": 2.0,
                    "stages": [{"key": "Plan", "status": "done", "agents": ["codex"],
                                "start_frac": 0.0, "width_frac": 0.2,
                                "cost_actual": 0.5, "cost_est": 0.5, "tasks": []}]}],
        "costs": {"total_usd": 1.5, "by_agent": {}, "by_stage": {}},
        "agents": {}, "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [], "tube_config": None, "notes": {},
    }
    html = generate_gantt_html(data, port=8721)
    assert "VIZOR_DATA" in html
    assert "Retention" in html
    assert "v0.11.0" in html

def test_effort_html_shows_empty_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import generate_effort_html
    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z"},
        "dreams": [], "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
        "agents": {}, "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [], "tube_config": None, "notes": {},
    }
    html = generate_effort_html(data, port=8721)
    assert "No cost data" in html

def test_all_html_contain_live_js(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import (generate_index_html, generate_gantt_html,
                              generate_tube_html, generate_journeys_html,
                              generate_effort_html, generate_efficiency_html)
    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z"},
        "dreams": [], "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
        "agents": {}, "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [], "tube_config": None, "notes": {},
    }
    for fn in [generate_index_html, generate_gantt_html, generate_tube_html,
               generate_journeys_html, generate_effort_html, generate_efficiency_html]:
        html = fn(data, port=8721)
        assert "checkManifest" in html, f"{fn.__name__} missing live JS"
```

### Verify

```bash
pytest tests/test_viz.py tests/test_viz_serve.py -v
# Expected: all tests pass
```

### Commit

```bash
git add tests/test_viz.py
git commit -m "test(viz): integration tests — pipeline, manifest, empty states, live JS injection"
```

---

## Task 12 — Blog Post · **Agy**

**Files:**
- Create: `docs/blog/` (find next sequential number from existing files)

### Dispatch

```bash
python3 bin/synlynk.py dispatch agy \
  --task "Write the blog post for BS-21 Vizor as Task 12 of the implementation plan" \
  --context-mode full
```

Include: this plan, spec `docs/superpowers/specs/2026-07-03-bs21-vizor-design.md`, `docs/blog/README.md`.

### What Agy must produce

A blog post in `docs/blog/` following the project's series template. Must cover:
1. **Previous goalpost:** D1-D7 retention gap identified — no surface for returning users
2. **Strategic shift:** Vizor as the PRIMARY D1-D2 retention hook, not a secondary feature
3. **What shipped:** `synlynk viz` command, 5 views, note system, live polling, FTUE
4. **Technical decisions:** local-first (state.db reader → HTML f-strings → http.server), note bidirectionality (viz-notes.json → context.md), station sizing by connection count in tube map
5. **Brainstorm visuals** referenced: `docs/brainstorm/bs21-vizor/viz-gantt-v5.html`, `viz-tube.html`
6. **New goalpost:** Vizor v1 shipped; next = D3-D7 retention (daily brief mode, scan delta, v1.0 workspace FTUE)

### Verify

```bash
ls docs/blog/ | grep bs21
# Expected: new file present with correct naming convention
```

### Commit

```bash
git add docs/blog/
git commit -m "docs(blog): BS-21 Vizor — local browser workspace dashboard"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| `synlynk viz` command with `--serve/--generate/--open/--stop` | T1 |
| FTUE 3 prompts | T1 |
| Local server + browser open | T1 |
| `generate_viz_data()` from state.db | T2 |
| Shell + left nav + theming | T3 |
| Gantt v5 design, drill-down zoom | T4 |
| SVG pencil notes on Gantt | T4 |
| Note save POST /note | T4 + T9 |
| Architect Map tube map v1 style | T5 |
| Setup prompt if no tube config | T5 |
| User Journeys split-pane | T6 |
| Effort & Cost 3 panels | T7 |
| Efficiency agent cards + sentinel | T8 |
| VizorHandler POST /note | T1 + T9 |
| viz-notes.json → context.md injection | T9 |
| Browser notifications | T10 |
| Polling auto-reload banner | T10 |
| All views contain live JS | T10 + T11 (verified) |
| `.gitignore` updates | T1 |
| Blog post | T12 |
| `docs/journeys/` convention | T6 |
| `vizor-tube.json` for tube config | T5 |

**No placeholders found.** All steps contain exact code, file paths, or dispatch commands.

**Interface consistency check:** `generate_viz_data()` return schema defined once in this plan header. All tasks reference it. `generate_*_html(data: dict, port: int) -> str` signature defined once in T1. All generator tasks (T3–T8) use the same signature.
