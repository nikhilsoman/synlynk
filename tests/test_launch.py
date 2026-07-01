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


def _minimal_scan(**kwargs):
    """Returns a scan dict with sensible defaults for testing."""
    base = {
        "workspace_name": "test-ws",
        "topology": "single",
        "repos": [{"name": "test-repo", "stack_labels": ["python"]}],
        "test_ratio": 0.5,
        "readme_word_count": 500,
        "has_ci": True,
        "has_docs": True,
        "has_type_hints": True,
        "has_orm": False,
    }
    base.update(kwargs)
    return base


def test_template_matches_core_always_eligible():
    scan = _minimal_scan()
    for t in synlynk.LAUNCH_TASK_TEMPLATES:
        if t["id"] in synlynk.CORE_TEMPLATE_IDS:
            assert synlynk._template_matches(t, scan), f"Core template '{t['id']}' should always match"


def test_template_matches_add_tests_triggered():
    scan = _minimal_scan(test_ratio=0.05)
    tmpl = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "add-tests")
    assert synlynk._template_matches(tmpl, scan)


def test_template_matches_add_tests_not_triggered():
    scan = _minimal_scan(test_ratio=0.5)
    tmpl = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "add-tests")
    assert not synlynk._template_matches(tmpl, scan)


def test_template_matches_setup_ci_triggered():
    scan = _minimal_scan(has_ci=False)
    tmpl = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "setup-ci")
    assert synlynk._template_matches(tmpl, scan)


def test_template_matches_type_safety_python_only():
    scan = _minimal_scan(has_type_hints=False,
                         repos=[{"name": "r", "stack_labels": ["node"]}])
    tmpl = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "type-safety")
    assert not synlynk._template_matches(tmpl, scan)


def test_select_tasks_returns_max_5():
    scan = _minimal_scan(
        test_ratio=0.0, has_ci=False, has_docs=False, readme_word_count=10,
        topology="multi", has_orm=True, has_type_hints=False,
        repos=[{"name": "r", "stack_labels": ["python", "react", "django", "next"]}]
    )
    tasks = synlynk._select_launch_tasks(scan)
    assert len(tasks) <= 5


def test_select_tasks_core_always_first():
    scan = _minimal_scan(test_ratio=0.0)
    tasks = synlynk._select_launch_tasks(scan)
    core_ids = synlynk.CORE_TEMPLATE_IDS
    core_positions = [i for i, t in enumerate(tasks) if t["id"] in core_ids]
    non_core_positions = [i for i, t in enumerate(tasks) if t["id"] not in core_ids]
    if core_positions and non_core_positions:
        assert max(core_positions) < min(non_core_positions)


def test_select_tasks_empty_scan_returns_core_3():
    scan = {
        "workspace_name": "x", "topology": "single",
        "repos": [{"name": "r", "stack_labels": []}],
        "test_ratio": 1.0, "readme_word_count": 999, "has_ci": True,
        "has_docs": True, "has_type_hints": True, "has_orm": False,
    }
    tasks = synlynk._select_launch_tasks(scan)
    assert len(tasks) == 3
    assert {t["id"] for t in tasks} == synlynk.CORE_TEMPLATE_IDS


def test_render_prompt_substitutes_all_variables():
    template = {
        "prompt_template": "Review {workspace} ({stack}) topology={topology} date={date} repo={repo_name}",
        "agent": "claude",
    }
    scan = {
        "workspace_name": "myws",
        "repos": [{"name": "myrepo", "stack_labels": ["python", "fastapi"]}],
        "topology": "single",
    }
    result = synlynk._render_prompt(template, scan)
    assert "myws" in result
    assert "python, fastapi" in result
    assert "single" in result
    assert "{workspace}" not in result
    assert "{date}" not in result
    assert "myrepo" in result


def test_render_prompt_missing_variable_uses_empty_string():
    template = {"prompt_template": "Hello {unknown_var} world", "agent": "claude"}
    result = synlynk._render_prompt(template, {})
    assert "{unknown_var}" not in result
    assert "Hello" in result


def test_launch_screen_tasks_skip_returns_none(monkeypatch):
    tasks = synlynk._select_launch_tasks(_minimal_scan())
    scan = _minimal_scan()
    monkeypatch.setattr(synlynk, '_wiz_read_key', lambda: 's')
    result = synlynk._launch_screen_tasks(tasks, scan)
    assert result is None


def test_launch_screen_cycles_returns_on_any_key(monkeypatch, capsys):
    monkeypatch.setattr(synlynk, '_wiz_read_key', lambda: 'x')
    synlynk._launch_screen_cycles()
    out = capsys.readouterr().out
    assert "dream" in out.lower() or "Dream" in out


def test_launch_screen_preview_returns_confirmed_and_prompt(monkeypatch):
    task = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "arch-review")
    scan = _minimal_scan()
    monkeypatch.setattr(synlynk, '_wiz_read_key', lambda: '\r')
    confirmed, prompt = synlynk._launch_screen_preview(task, scan)
    assert confirmed is True
    assert isinstance(prompt, str)
    assert len(prompt) > 10


def test_launch_screen_preview_esc_returns_not_confirmed(monkeypatch):
    task = next(t for t in synlynk.LAUNCH_TASK_TEMPLATES if t["id"] == "arch-review")
    scan = _minimal_scan()
    monkeypatch.setattr(synlynk, '_wiz_read_key', lambda: '\x1b')
    confirmed, prompt = synlynk._launch_screen_preview(task, scan)
    assert confirmed is False
