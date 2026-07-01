import sys
import os
import sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import synlynk


def test_cycle_names_constant_exists():
    assert hasattr(synlynk, 'CYCLE_NAMES')
    assert synlynk.CYCLE_NAMES == ["dream", "design", "plan", "build", "ship", "sustain"]


def test_cycle_colors_constant_exists():
    assert hasattr(synlynk, 'CYCLE_COLORS')
    assert synlynk.CYCLE_COLORS["dream"] == "#a78bfa"
    assert synlynk.CYCLE_COLORS["sustain"] == "#94a3b8"


def test_cycle_rename_migration_idempotent(tmp_path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    synlynk._migrate_db(conn)
    synlynk._migrate_db(conn)  # second run must not raise
    conn.close()


def test_scan_returns_test_ratio(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text("def foo(): pass")
    (tmp_path / "test_app.py").write_text("def test_foo(): pass")
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(roots=[str(tmp_path)], workspace_name="test")
    assert "test_ratio" in result
    assert isinstance(result["test_ratio"], float)


def test_scan_returns_has_ci_false_when_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(roots=[str(tmp_path)], workspace_name="test")
    assert result["has_ci"] is False


def test_scan_returns_readme_word_count(tmp_path, monkeypatch):
    (tmp_path / "README.md").write_text("Hello world this is a README with ten words total")
    monkeypatch.chdir(tmp_path)
    result = synlynk.run_workspace_scan(roots=[str(tmp_path)], workspace_name="test")
    assert result["readme_word_count"] >= 9


def test_launch_task_templates_count():
    assert len(synlynk.LAUNCH_TASK_TEMPLATES) == 12


def test_launch_task_templates_have_required_fields():
    required = {"id", "title", "description", "cycle", "agent", "context_mode",
                "prompt_template", "est_hours", "r_tokens", "w_tokens", "tool_calls"}
    for t in synlynk.LAUNCH_TASK_TEMPLATES:
        missing = required - set(t.keys())
        assert not missing, f"Template '{t.get('id')}' missing fields: {missing}"


def test_launch_task_templates_core_ids():
    ids = {t["id"] for t in synlynk.LAUNCH_TASK_TEMPLATES}
    for core_id in ("arch-review", "product-assessment", "lifecycle-setup"):
        assert core_id in ids
