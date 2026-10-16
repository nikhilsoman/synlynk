import os
import sys
from unittest.mock import patch
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.doctor import _hc_todo_drift, HEALTH_CHECKS


def test_hc_todo_drift_in_health_checks_list():
    assert _hc_todo_drift in HEALTH_CHECKS


def test_hc_todo_drift_ok_when_synchronized(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "project-docs").mkdir()
    (tmp_path / ".synlynk" / "project-docs" / "todo.md").write_text("# Tasks\n- [ ] Task 1\n")

    with patch("synlynk.doctor._pkg") as mock_pkg:
        def _get_pkg(name, default=None):
            if name == "_is_migrated":
                return lambda: True
            if name == "_synlynk_project_docs_dir":
                return lambda: str(tmp_path / ".synlynk" / "project-docs")
            if name == "_docs_dir":
                return lambda: str(tmp_path / "project-docs")
            if name == "_detect_hand_edit":
                return lambda fname: None
            return default
        mock_pkg.side_effect = _get_pkg

        res = _hc_todo_drift()
        assert res.status == "ok"
        assert res.name == "todo_drift"


def test_hc_todo_drift_uses_canonical_export_and_pr_check_blocks_checkout_copy(tmp_path, monkeypatch):
    import synlynk
    from synlynk.db import _generate_todo_md, cmd_pr_check

    monkeypatch.chdir(tmp_path)
    canonical_docs = tmp_path / "canonical" / "project-docs"
    monkeypatch.setattr(synlynk, "_generated_project_docs_dir", lambda: str(canonical_docs))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    conn = synlynk._get_db()
    conn.execute("INSERT INTO stories (story_id, title, status) VALUES ('story-1', 'Canonical task', 'open')")
    conn.commit()
    conn.close()
    _generate_todo_md()
    export = canonical_docs / "todo.md"
    assert export.exists()
    assert "Canonical task" in export.read_text()
    assert not (tmp_path / "project-docs" / "todo.md").exists()

    with patch("synlynk.doctor._pkg") as mock_pkg:
        def _get_pkg(name, default=None):
            if name == "_is_migrated":
                return lambda: True
            if name == "_synlynk_project_docs_dir":
                return lambda: str(tmp_path / ".synlynk" / "project-docs")
            if name == "_generated_project_docs_dir":
                return lambda: str(canonical_docs)
            if name == "_docs_dir":
                return lambda: str(tmp_path / "project-docs")
            if name == "_detect_hand_edit":
                return lambda fname: None
            return default
        mock_pkg.side_effect = _get_pkg

        res = _hc_todo_drift()
        assert res.status == "ok"
        assert "synchronized" in res.message

    monkeypatch.setattr("synlynk.db._gh_pr_changed_files", lambda _: [
        "project-docs/todo.md", "project-docs/roadmap.md", "project-docs/costs.md",
    ])
    with pytest.raises(SystemExit) as exc:
        cmd_pr_check(pr_number=123)
    assert exc.value.code == 1


def test_hc_todo_drift_warns_on_state_db_drift(tmp_path, monkeypatch):
    canonical_docs = tmp_path / "canonical" / "project-docs"
    with patch("synlynk.doctor._pkg") as mock_pkg:
        def _get_pkg(name, default=None):
            if name == "_is_migrated":
                return lambda: False
            if name == "_docs_dir":
                return lambda: str(tmp_path / "project-docs")
            if name == "_generated_project_docs_dir":
                return lambda: str(canonical_docs)
            if name == "_detect_hand_edit":
                return lambda fname: "⚠ hand-edit detected in todo.md"
            return default
        mock_pkg.side_effect = _get_pkg

        res = _hc_todo_drift()
        assert res.status == "warn"
        assert "drifted from state.db" in res.message
        assert "synlynk story create" in res.fix
