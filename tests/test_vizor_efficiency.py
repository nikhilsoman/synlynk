import json
import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from synlynk.viz import generate_efficiency_html, generate_viz_data

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
            cache_read_tokens INTEGER, total_cost_usd REAL, notes TEXT,
            cost_source TEXT DEFAULT 'actual'
        );
        INSERT INTO roadmap_arcs (version, title, status) VALUES ('v0.11.0', 'Retention Layer', 'active');
        INSERT INTO roadmap_phases (arc_version, phase_title, status, notes)
            VALUES ('v0.11.0', 'Plan', 'done', '[agent:codex]'),
                   ('v0.11.0', 'Build', 'active', '[agent:agy,codex]');
        INSERT INTO stories (story_id, title, status, phase, estimated_tokens)
            VALUES ('story-bs21-shell', 'Shell layout', 'done', 'build', 60000);
        INSERT INTO cost_entries (session_date, agent, total_cost_usd, notes, cost_source)
            VALUES ('2026-07-01', 'agy', 1.20, 'story-bs21-shell', 'actual');
    """)
    conn.commit()
    return conn

# (1) generate_efficiency_html returns string containing 'headless' or 'Nx' or 'efficiency'
def test_generate_efficiency_html_basic_keywords():
    data = {
        "workspace": {"name": "test-ws"},
        "agents": {"claude": {}},
        "ecosystem": {
            "headless_efficiency": 3.5,
            "fleet": {"attached": 1, "total": 4, "dispatch_mode": "daily-grind"},
            "agents": {},
            "cycle_capability": {},
            "capacity": {},
            "sentinels_active": 0
        }
    }
    html_str = generate_efficiency_html(data, port=8721)
    assert isinstance(html_str, str)
    assert any(x in html_str.lower() for x in ["headless", "nx", "efficiency"])

# (2) capacity table renders all 4 agents (claude, agy, codex, grok)
def test_capacity_table_renders_all_agents():
    data = {
        "workspace": {"name": "test-ws"},
        "agents": {"claude": {}},
        "ecosystem": {
            "headless_efficiency": 3.5,
            "fleet": {"attached": 1, "total": 4, "dispatch_mode": "daily-grind"},
            "agents": {},
            "cycle_capability": {},
            "capacity": {
                "claude": {"ctx_window_tokens": 200_000, "read_budget_tokens": 750_000, "write_budget_tokens": 32_000, "tool_budget_count": 200},
                "agy": {"ctx_window_tokens": 1_000_000, "read_budget_tokens": 900_000, "write_budget_tokens": 65_000, "tool_budget_count": 500},
                "codex": {"ctx_window_tokens": 128_000, "read_budget_tokens": 110_000, "write_budget_tokens": 16_000, "tool_budget_count": 128},
                "grok": {"ctx_window_tokens": 131_000, "read_budget_tokens": 115_000, "write_budget_tokens": 16_000, "tool_budget_count": 100},
            },
            "sentinels_active": 0
        }
    }
    html_str = generate_efficiency_html(data, port=8721)
    # The table rows must contain claude, agy, codex, grok
    assert "claude" in html_str.lower()
    assert "agy" in html_str.lower()
    assert "codex" in html_str.lower()
    assert "grok" in html_str.lower()
    # Check that capacity table headers or classes exist
    assert "capacity table" in html_str.lower()

# (3) cycle matrix renders all 6 cycles (dream, plan, work, ship, maintain, engage)
def test_cycle_matrix_renders_all_cycles():
    data = {
        "workspace": {"name": "test-ws"},
        "agents": {"claude": {}},
        "ecosystem": {
            "headless_efficiency": 3.5,
            "fleet": {"attached": 1, "total": 4, "dispatch_mode": "daily-grind"},
            "agents": {},
            "cycle_capability": {
                "claude": {"dream": "full", "plan": "partial", "work": "full", "ship": "none", "maintain": "none", "engage": "none"}
            },
            "capacity": {},
            "sentinels_active": 0
        }
    }
    html_str = generate_efficiency_html(data, port=8721)
    assert "cycle capability matrix" in html_str.lower()
    for cycle in ["dream", "plan", "work", "ship", "maintain", "engage"]:
        assert cycle in html_str.lower()

# (4) fleet header shows dispatch_mode value
def test_fleet_header_shows_dispatch_mode():
    data = {
        "workspace": {"name": "test-ws"},
        "agents": {"claude": {}},
        "ecosystem": {
            "headless_efficiency": 3.5,
            "fleet": {"attached": 3, "total": 4, "dispatch_mode": "super-fast-mode"},
            "agents": {},
            "cycle_capability": {},
            "capacity": {},
            "sentinels_active": 0
        }
    }
    html_str = generate_efficiency_html(data, port=8721)
    assert "super-fast-mode" in html_str
    assert "3/4" in html_str

# (5) empty ecosystem data renders placeholder without crashing
def test_empty_ecosystem_renders_placeholder_without_crashing():
    data = {
        "workspace": {"name": "test-ws"},
        "agents": {},
        "ecosystem": {}
    }
    html_str = generate_efficiency_html(data, port=8721)
    assert "headless efficiency" in html_str.lower()
    assert "capacity table" in html_str.lower()
    assert "cycle capability matrix" in html_str.lower()
    # Should render skeleton/placeholder
    assert "—x" in html_str or "1.0x" in html_str

# (6) generate_viz_data() result includes 'ecosystem' key
def test_generate_viz_data_result_includes_ecosystem(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    make_test_db(db_path)
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({}, f)

    # Test with mocked subprocess
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = json.dumps({
        "headless_efficiency": 4.2,
        "fleet": {"attached": 2, "total": 4, "dispatch_mode": "daily-grind"},
        "agents": {},
        "cycle_capability": {},
        "capacity": {},
        "sentinels_active": 3
    })

    with patch("synlynk.viz._get_db") as mock_db, patch("subprocess.run", mock_run):
        mock_db.return_value = sqlite3.connect(db_path)
        data = generate_viz_data()

    assert "ecosystem" in data
    assert data["ecosystem"]["headless_efficiency"] == 4.2
    assert data["ecosystem"]["fleet"]["dispatch_mode"] == "daily-grind"

def test_generate_viz_data_real_graceful_fallback(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    make_test_db(db_path)
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({}, f)

    # Let it execute the real subprocess (which might fail or return empty due to no DB/env setup)
    # It should still include the "ecosystem" key
    with patch("synlynk.viz._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        data = generate_viz_data()

    assert "ecosystem" in data
    assert isinstance(data["ecosystem"], dict)
