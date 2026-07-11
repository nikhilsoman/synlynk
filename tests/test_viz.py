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

def test_load_workspace_repos_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import _load_workspace_repos
    assert _load_workspace_repos({}) == []


def test_load_workspace_repos_reads_default_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ws_dir = tmp_path / "fake-home" / ".synlynk" / "workspaces" / "default"
    ws_dir.mkdir(parents=True)
    (ws_dir / "config.json").write_text(json.dumps({
        "workspace_name": "default",
        "repos": [{"path": "/repo/a", "name": "repo-a", "stack_labels": ["python"]}],
    }))
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    from synlynk.viz import _load_workspace_repos
    repos = _load_workspace_repos({})
    assert repos == [{"path": "/repo/a", "name": "repo-a", "stack_labels": ["python"]}]


def test_load_workspace_repos_honors_explicit_workspace_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ws_dir = tmp_path / "fake-home" / ".synlynk" / "workspaces" / "acme"
    ws_dir.mkdir(parents=True)
    (ws_dir / "config.json").write_text(json.dumps({
        "workspace_name": "acme",
        "repos": [{"path": "/repo/b", "name": "repo-b", "stack_labels": []}],
    }))
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    from synlynk.viz import _load_workspace_repos
    repos = _load_workspace_repos({"workspace_name": "acme"})
    assert repos == [{"path": "/repo/b", "name": "repo-b", "stack_labels": []}]


def test_load_workspace_map_missing_returns_empty_shape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.viz import _load_workspace_map
    assert _load_workspace_map() == {"edges": [], "edge_types": {}}


def test_load_workspace_map_reads_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/vizor-workspace-map.json", "w") as f:
        json.dump({
            "edges": [{"from": "a", "to": "b", "type": "api-call"}],
            "edge_types": {"api-call": {"label": "API Call", "color": "#0d9e87"}},
        }, f)
    from synlynk.viz import _load_workspace_map
    result = _load_workspace_map()
    assert result["edges"] == [{"from": "a", "to": "b", "type": "api-call"}]
    assert result["edge_types"]["api-call"]["color"] == "#0d9e87"


def test_generate_viz_data_structure(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    make_test_db(db_path)
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"project_name": "test-project"}, f)

    from synlynk.viz import generate_viz_data
    with patch("synlynk._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        data = generate_viz_data()

    assert "workspace" in data
    assert "dreams" in data
    assert "costs" in data
    assert "agents" in data
    assert "telemetry" in data
    assert "notes" in data
    assert "workspace_map" in data
    assert "repos" in data["workspace"]
    assert "observatory" in data


def test_generate_viz_data_includes_file_tree(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT UNIQUE, title TEXT, status TEXT DEFAULT 'active', target_date TEXT, notes TEXT);
        CREATE TABLE roadmap_phases (id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT, status TEXT DEFAULT 'planned', priority TEXT, story_id TEXT, notes TEXT);
        CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT UNIQUE, title TEXT, status TEXT DEFAULT 'open', phase TEXT DEFAULT 'build', estimated_tokens INTEGER, created_at TEXT);
        CREATE TABLE cost_entries (id INTEGER PRIMARY KEY, session_date TEXT, agent TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, total_cost_usd REAL, notes TEXT);
        CREATE TABLE source_symbols (id INTEGER PRIMARY KEY AUTOINCREMENT, head_sha TEXT NOT NULL, file TEXT NOT NULL, language TEXT NOT NULL, symbol TEXT NOT NULL, symbol_type TEXT NOT NULL, line INTEGER, scanned_at TEXT NOT NULL);
        INSERT INTO source_symbols (head_sha, file, language, symbol, symbol_type, line, scanned_at)
            VALUES ('abc', 'synlynk/viz.py', 'python', 'generate_gantt_html', 'function', 930, '2026-07-11T00:00:00Z');
    """)
    conn.commit()
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"project_name": "test-project"}, f)

    from synlynk.viz import generate_viz_data
    with patch("synlynk._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        data = generate_viz_data()

    assert "file_tree" in data
    assert "synlynk" in data["file_tree"]["dirs"]

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


def test_generate_effort_html_renders_svg_charts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import generate_effort_html

    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "dreams": [
            {"id": "d1", "name": "Dream One", "status": "active", "cost_total": 120.0, "cost_est": 100.0},
            {"id": "d2", "name": "Dream Two", "status": "parked", "cost_total": 60.0, "cost_est": None},
        ],
        "costs": {
            "total_usd": 180.0,
            "by_agent": {"claude": 50.0, "agy": 80.0, "codex": 40.0, "grok": 10.0},
            "by_stage": {"design": 20.0, "plan": 30.0, "build": 40.0, "ship": 50.0, "sustain": 40.0},
        },
        "agents": {},
        "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [],
        "workspace_map": {"edges": [], "edge_types": {}},
        "notes": {},
    }

    html = generate_effort_html(data, port=8721)

    assert "window.VIZOR_DATA =" in html
    assert "Total Spend" in html
    assert "Dreams In Flight" in html
    assert "Over Budget" in html
    assert "Top Agent" in html
    assert "<svg viewBox=\"0 0 500" in html
    assert "Dream One" in html
    assert "$120.00 / est $100.00" in html
    assert "claude" in html
    assert "No cost data yet" not in html


def test_generate_effort_html_empty_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import generate_effort_html

    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "dreams": [],
        "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
        "agents": {},
        "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [],
        "workspace_map": {"edges": [], "edge_types": {}},
        "notes": {},
    }

    html = generate_effort_html(data, port=8721)

    assert "No cost data yet" in html
    assert "<svg" not in html

def test_generate_architect_map_html_no_repos_shows_single_node():
    from synlynk.viz import generate_architect_map_html

    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "workspace_map": {"edges": [], "edge_types": {}},
        "file_tree": {"name": ".", "dirs": {}, "files": []},
    }
    html = generate_architect_map_html(data, 8721)
    assert "🗺️ Architect Map" in html or "Architect Map" in html
    assert "synlynk viz --setup-tube" not in html
    assert "test-ws" in html


def test_generate_architect_map_html_renders_repo_nodes():
    from synlynk.viz import generate_architect_map_html

    data = {
        "workspace": {
            "name": "test-ws",
            "updated_at": "2026-07-03T10:00:00Z",
            "repos": [
                {
                    "path": "/repo/core",
                    "name": "synlynk-core",
                    "stack_labels": ["python"],
                    "github_url": "https://github.com/nikhilsoman/synlynk",
                },
                {
                    "path": "/repo/web",
                    "name": "synlynk-website",
                    "stack_labels": ["node"],
                    "github_url": None,
                },
            ],
        },
        "workspace_map": {
            "edges": [{"from": "synlynk-website", "to": "synlynk-core", "type": "api-call"}],
            "edge_types": {"api-call": {"label": "API Call", "color": "#0d9e87"}},
        },
        "file_tree": {"name": ".", "dirs": {}, "files": []},
    }
    html = generate_architect_map_html(data, 8721)
    assert "synlynk-core" in html
    assert "synlynk-website" in html
    assert "api-call" in html
    assert "#0d9e87" in html
    assert "API Call" in html


def test_generate_architect_map_html_includes_layout_and_drawer_js():
    from synlynk.viz import generate_architect_map_html

    data = {
        "workspace": {
            "name": "test-ws",
            "updated_at": "",
            "repos": [
                {
                    "path": "/r/a",
                    "name": "repo-a",
                    "stack_labels": [],
                    "github_url": "https://github.com/x/a",
                },
            ],
        },
        "workspace_map": {"edges": [], "edge_types": {}},
        "file_tree": {"name": ".", "dirs": {}, "files": []},
    }

    html_out = generate_architect_map_html(data, 8721)

    assert "function layoutGraph" in html_out
    assert "function setArchitectView" in html_out
    assert "function openDrawer" in html_out
    assert "function closeDrawer" in html_out
    assert "function drawerDispatch" in html_out
    assert "function drawerJumpGantt" in html_out
    assert "function renderTree" in html_out
    assert "if (view === 'tree' && !window._treeRendered)" in html_out


def test_generate_architect_map_html_includes_tree_render_js():
    from synlynk.viz import generate_architect_map_html

    data = {
        "workspace": {"name": "test-ws", "updated_at": "", "repos": []},
        "workspace_map": {"edges": [], "edge_types": {}},
        "file_tree": {"name": ".", "dirs": {}, "files": []},
    }
    html_out = generate_architect_map_html(data, 8721)
    assert "function renderTree" in html_out
    assert "window.ARCHITECT_FILE_TREE" in html_out


def test_generate_gantt_html_renders_dreams_and_notes():
    from synlynk.viz import generate_gantt_html

    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "dreams": [
            {
                "id": "bs21",
                "name": "Vizor",
                "status": "active",
                "stages": [
                    {
                        "key": "Plan",
                        "status": "active",
                        "start_frac": 0.10,
                        "width_frac": 0.20,
                        "agents": ["agy", "codex"],
                        "tasks": [
                            {"id": "task-1", "name": "Shell layout", "agent": "agy", "status": "done", "note": {"state": "info", "text": "ready"}},
                            {"id": "task-2", "name": "Gantt view", "agent": "codex", "status": "active", "note": {"state": "urgent", "text": "blocked"}},
                        ],
                    }
                ],
            }
        ],
        "notes": {
            "bs21": {"text": "dream note", "tags": ["Redo stage"], "state": "action", "updated_at": "2026-07-03T10:00:00Z"}
        },
    }

    html = generate_gantt_html(data, port=8721)

    assert "window.VIZOR_DATA =" in html
    assert "Vizor" in html
    assert "Shell layout" in html
    assert "Gantt view" in html
    assert "note-info" in html
    assert "note-urgent" in html
    assert "http://localhost:' + PORT + '/note" in html


def test_generate_gantt_html_empty_state():
    from synlynk.viz import generate_gantt_html

    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "dreams": [],
        "notes": {},
    }

    html = generate_gantt_html(data, port=8721)

    assert "No Dreams found in state db" in html
    assert "<p class='empty-state'>" in html


def test_generate_journeys_html_empty():
    from synlynk.viz import generate_journeys_html
    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "journeys": []
    }
    html = generate_journeys_html(data, 8721)
    assert "User Journeys" in html
    assert "No journeys found. Create docs/journeys/ with .md files, each starting with a # H1 title. Steps use ## Screen Name headings with route:, desc:, agent:, stage: key-value lines." in html


def test_generate_journeys_html_with_data():
    from synlynk.viz import generate_journeys_html
    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "journeys": [
            {
                "id": "onboarding",
                "name": "User Onboarding Flow",
                "steps": [
                    {
                        "screen": "Welcome Screen",
                        "route": "/welcome",
                        "desc": "Shows welcome message",
                        "agent": "agy",
                        "stage": "design"
                    },
                    {
                        "screen": "Profile Setup",
                        "route": "/profile",
                        "desc": "User enters profile details",
                        "agent": "codex",
                        "stage": "build"
                    }
                ]
            }
        ]
    }
    html = generate_journeys_html(data, 8721)
    assert "User Onboarding Flow" in html
    assert "Welcome Screen" in html
    assert "/welcome" in html
    assert "Shows welcome message" in html
    assert "Profile Setup" in html
    assert "/profile" in html
    assert "User enters profile details" in html
    assert "stage-pill" in html
    assert "aa-agy" in html
    assert "aa-codex" in html


def test_generate_journeys_html_ftue_notice():
    from synlynk.viz import generate_journeys_html
    data = {
        "workspace": {
            "name": "test-ws",
            "updated_at": "2026-07-03T10:00:00Z",
            "repos": [],
            "vizor_second_view": "tube"
        },
        "journeys": [
            {
                "id": "test",
                "name": "Test Journey",
                "steps": []
            }
        ]
    }
    html = generate_journeys_html(data, 8721)
    assert "Your workspace is configured for the Architect Map as the primary structural view. User Journeys is available if your project has UX screens." in html


def test_write_cache_creates_all_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import _write_cache, VIZ_CACHE_DIR
    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "dreams": [], "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
        "agents": {}, "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [], "workspace_map": {"edges": [], "edge_types": {}}, "notes": {},
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
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "dreams": [], "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
        "agents": {}, "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [], "workspace_map": {"edges": [], "edge_types": {}}, "notes": {},
    }
    _write_cache(data, port=8721)
    with open(os.path.join(VIZ_CACHE_DIR, "manifest.json")) as f:
        m = json.load(f)
    assert "updated_at" in m
    from datetime import datetime
    datetime.fromisoformat(m["updated_at"].replace("Z", "+00:00"))


def test_gantt_html_contains_vizor_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import generate_gantt_html
    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "dreams": [{"id": "v0.11.0", "name": "Retention", "status": "active",
                    "cost_total": 1.5, "cost_est": 2.0,
                    "stages": [{"key": "Plan", "status": "done", "agents": ["codex"],
                                "start_frac": 0.0, "width_frac": 0.2,
                                "cost_actual": 0.5, "cost_est": 0.5, "tasks": []}]}],
        "costs": {"total_usd": 1.5, "by_agent": {}, "by_stage": {}},
        "agents": {}, "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [], "workspace_map": {"edges": [], "edge_types": {}}, "notes": {},
    }
    html = generate_gantt_html(data, port=8721)
    assert "VIZOR_DATA" in html
    assert "Retention" in html
    assert "v0.11.0" in html


def test_effort_html_shows_empty_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import generate_effort_html
    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "dreams": [], "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
        "agents": {}, "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [], "workspace_map": {"edges": [], "edge_types": {}}, "notes": {},
    }
    html = generate_effort_html(data, port=8721)
    assert "No cost data" in html


def test_all_html_contain_live_js(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import (generate_index_html, generate_gantt_html,
                              generate_architect_map_html, generate_journeys_html,
                              generate_effort_html, generate_efficiency_html)
    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "dreams": [], "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
        "agents": {}, "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [], "workspace_map": {"edges": [], "edge_types": {}}, "notes": {},
    }
    for fn in [generate_index_html, generate_gantt_html, generate_architect_map_html,
               generate_journeys_html, generate_effort_html, generate_efficiency_html]:
        html = fn(data, port=8721)
        assert "checkManifest" in html, f"{fn.__name__} missing live JS"


def test_vizor_handler_dispatch_route_exists():
    import inspect
    from synlynk.viz import VizorHandler
    src = inspect.getsource(VizorHandler.do_POST)
    assert "/dispatch" in src
    assert "/architect-map/view-pref" in src


def test_vizor_handler_handle_dispatch_calls_dispatch_agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import VizorHandler
    called = {}

    def fake_dispatch_agent(agent, task, force_agent=False, context_mode=None, **kwargs):
        called["agent"] = agent
        called["task"] = task
        called["force_agent"] = force_agent
        called["context_mode"] = context_mode
        return {"job_id": "job-test123", "status": "dispatched"}

    monkeypatch.setattr("synlynk.dispatch.dispatch_agent", fake_dispatch_agent)

    handler = VizorHandler.__new__(VizorHandler)
    result = handler._handle_dispatch({"agent": "codex", "task": "do the thing"})

    assert called["agent"] == "codex"
    assert called["task"] == "do the thing"
    assert called["force_agent"] is True
    assert called["context_mode"] == "full"
    assert result["job_id"] == "job-test123"


def test_vizor_handler_handle_view_pref_persists_to_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"vizor": {"port": 8721}}, f)

    from synlynk.viz import VizorHandler
    handler = VizorHandler.__new__(VizorHandler)
    result = handler._handle_view_pref({"view": "tree"})

    assert result == {"ok": True}
    with open(".synlynk/config.json") as f:
        saved = json.load(f)
    assert saved["vizor"]["architect_map_view"] == "tree"


def test_vizor_handler_handle_view_pref_creates_config_if_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import VizorHandler
    handler = VizorHandler.__new__(VizorHandler)
    handler._handle_view_pref({"view": "graph"})
    with open(".synlynk/config.json") as f:
        saved = json.load(f)
    assert saved["vizor"]["architect_map_view"] == "graph"
