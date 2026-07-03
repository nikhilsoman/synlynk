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
