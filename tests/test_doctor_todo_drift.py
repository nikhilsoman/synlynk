import os
import sys
from unittest.mock import patch

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


def test_hc_todo_drift_warns_on_split_path_divergence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "project-docs" / "todo.md").write_text("# Real Tasks\n- [ ] Real Task 1\n")

    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "project-docs").mkdir()
    (tmp_path / ".synlynk" / "project-docs" / "todo.md").write_text("# Placeholder\n- [ ] Placeholder\n")

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
        assert res.status == "warn"
        assert "divergent content" in res.message
        assert "synlynk checkpoint" in res.fix


def test_hc_todo_drift_warns_on_state_db_drift(tmp_path, monkeypatch):
    with patch("synlynk.doctor._pkg") as mock_pkg:
        def _get_pkg(name, default=None):
            if name == "_is_migrated":
                return lambda: False
            if name == "_docs_dir":
                return lambda: str(tmp_path / "project-docs")
            if name == "_detect_hand_edit":
                return lambda fname: "⚠ hand-edit detected in todo.md"
            return default
        mock_pkg.side_effect = _get_pkg

        res = _hc_todo_drift()
        assert res.status == "warn"
        assert "drifted from state.db" in res.message
        assert "synlynk story create" in res.fix
