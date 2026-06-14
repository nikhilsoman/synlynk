import os
import sqlite3
import tempfile
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bin'))

def test_get_db_creates_state_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    conn = _get_db()
    conn.close()
    assert os.path.exists(".synlynk/state/state.db")

def test_migrate_db_creates_tables(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    conn = _get_db()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "stories" in tables
    assert "capability_ratings" in tables

def test_migrate_db_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    _get_db().close()
    _get_db().close()  # second call must not crash

def test_init_writes_industry_to_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def mock_input(prompt):
        if "[y/N]" in prompt:
            return "n"
        elif "Email or synlynk ID" in prompt:
            return "user@example.com"
        elif "Industry vertical" in prompt:
            return "ott"
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init
    init(force=True)
    import json
    config = json.load(open(".synlynk/config.json"))
    assert config.get("industry") == "ott"
    assert config.get("workgroup_invite_email") == "user@example.com"

def test_init_infers_industry_from_readme(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# MyApp\nA fintech platform for trading.")
    def mock_input(prompt):
        if "[y/N]" in prompt:
            return "n"
        elif "Email or synlynk ID" in prompt:
            return ""
        elif "Industry vertical" in prompt:
            return "" # Accept default
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init, _infer_industry
    inferred = _infer_industry(str(tmp_path))
    assert inferred == "fintech"
    init(force=True)
    import json
    config = json.load(open(".synlynk/config.json"))
    assert config.get("industry") == "fintech"

def test_story_create_writes_to_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import cmd_story_create, _get_db
    cmd_story_create(title="Add billing endpoint", engg_domain="backend",
                     org_domain="monetization", phase="build")
    conn = _get_db()
    rows = conn.execute("SELECT * FROM stories WHERE title=?",
                        ("Add billing endpoint",)).fetchall()
    conn.close()
    assert len(rows) == 1

def test_story_create_generates_unique_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import cmd_story_create, _get_db
    cmd_story_create(title="Story A", engg_domain="backend", org_domain="platform", phase="build")
    cmd_story_create(title="Story B", engg_domain="frontend", org_domain="growth", phase="build")
    conn = _get_db()
    rows = conn.execute("SELECT story_id FROM stories").fetchall()
    conn.close()
    ids = [r[0] for r in rows]
    assert len(set(ids)) == 2

def test_story_list_returns_rows(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import cmd_story_create, cmd_story_list
    cmd_story_create(title="My story", engg_domain="data", org_domain="analytics", phase="build")
    cmd_story_list()
    out = capsys.readouterr().out
    assert "My story" in out



