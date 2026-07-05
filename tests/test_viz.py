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
    assert "observatory" in data

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
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z"},
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
        "tube_config": None,
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
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z"},
        "dreams": [],
        "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
        "agents": {},
        "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [],
        "tube_config": None,
        "notes": {},
    }

    html = generate_effort_html(data, port=8721)

    assert "No cost data yet" in html
    assert "<svg" not in html

def test_generate_tube_html_no_config():
    from synlynk.viz import generate_tube_html
    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z"},
        "tube_config": None
    }
    html = generate_tube_html(data, 8721)
    assert "🚇 Architect Map" in html
    assert "Define your architecture lines to unlock this view." in html
    assert "synlynk viz --setup-tube" in html
    assert "docs/superpowers/specs/2026-07-03-bs21-vizor-design.md" in html

def test_generate_tube_html_with_config():
    from synlynk.viz import generate_tube_html
    config = {
        "lines": [
            {"id": "init", "name": "Init Line", "color": "#7c3aed", "stations": ["s1", "s2"]}
        ],
        "stations": {
            "s1": {"label": "Station One", "desc": "First station", "x": 100, "y": 200, "active": True, "agent": "claude"},
            "s2": {"label": "Station Two", "desc": "Second station", "x": 300, "y": 200}
        }
    }
    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z"},
        "tube_config": config
    }
    html = generate_tube_html(data, 8721)
    assert "Station One" in html
    assert "First station" in html
    assert "Station Two" in html
    assert "Second station" in html
    assert "svg" in html
    assert "polyline" in html
    # check radius calculation
    # s1 belongs to 1 line, so segs = 1. r = 4 + 1 * 2 = 6.
    assert 'r="6"' in html
    # check active class/dot/filter
    assert 'filter="url(#glow-purple)"' in html
    # check agent assignment
    assert 'claude' in html
    assert 'text-anchor="middle"' in html


def test_generate_gantt_html_renders_dreams_and_notes():
    from synlynk.viz import generate_gantt_html

    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z"},
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
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z"},
        "dreams": [],
        "notes": {},
    }

    html = generate_gantt_html(data, port=8721)

    assert "No Dreams found in state db" in html
    assert "<p class='empty-state'>" in html


def test_generate_journeys_html_empty():
    from synlynk.viz import generate_journeys_html
    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z"},
        "journeys": []
    }
    html = generate_journeys_html(data, 8721)
    assert "User Journeys" in html
    assert "No journeys found. Create docs/journeys/ with .md files, each starting with a # H1 title. Steps use ## Screen Name headings with route:, desc:, agent:, stage: key-value lines." in html


def test_generate_journeys_html_with_data():
    from synlynk.viz import generate_journeys_html
    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-07-03T10:00:00Z"},
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
