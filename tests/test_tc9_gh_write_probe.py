import io
import os
import sqlite3
import subprocess
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.db import _migrate_db
from synlynk.doctor import cmd_doctor
from synlynk.probe import _run_tc9


def test_tc9_auth_failure(monkeypatch):
    with patch("synlynk.probe._run_tc6", return_value={"passed": False, "error": "not logged in", "output": "not logged in"}):
        res = _run_tc9("claude")
        assert res["passed"] is False
        assert res["can_gh_write"] is False
        assert res["mechanism"] == "gh_auth_failed"


def test_tc9_claude_dry_and_live(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda bin_name: "/usr/local/bin/claude")
    with patch("synlynk.probe._run_tc6", return_value={"passed": True, "error": "", "output": "ok"}):
        # Dry mode
        res_dry = _run_tc9("claude", live=False)
        assert res_dry["passed"] is True
        assert res_dry["can_gh_write"] is True
        assert res_dry["mechanism"] == "direct_cli"

        # Live mode success
        mock_proc = MagicMock(returncode=0, stdout="gh version 2.50.0", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            res_live = _run_tc9("claude", live=True)
            assert res_live["passed"] is True
            assert res_live["can_gh_write"] is True
            assert res_live["mechanism"] == "direct_cli"


def test_tc9_codex_dry_and_live(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda bin_name: "/usr/local/bin/codex")
    with patch("synlynk.probe._run_tc6", return_value={"passed": True, "error": "", "output": "ok"}):
        # Dry mode
        res_dry = _run_tc9("codex", live=False)
        assert res_dry["passed"] is True
        assert res_dry["can_gh_write"] is True
        assert res_dry["mechanism"] == "requires_gh_write_flag"

        # Live mode
        mock_proc = MagicMock(returncode=0, stdout="gh version 2.50.0", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            res_live = _run_tc9("codex", live=True)
            assert res_live["passed"] is True
            assert res_live["mechanism"] == "verified_sandbox_execution"


def test_tc9_grok_sandbox_denied(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda bin_name: "/usr/local/bin/grok")
    with patch("synlynk.probe._run_tc6", return_value={"passed": True, "error": "", "output": "ok"}):
        # Dry mode
        res_dry = _run_tc9("grok", live=False)
        assert res_dry["passed"] is False
        assert res_dry["can_gh_write"] is False
        assert res_dry["mechanism"] == "sandbox_denied"

        # Live mode
        mock_proc = MagicMock(returncode=1, stdout="Error: execution denied in headless sandbox", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            res_live = _run_tc9("grok", live=True)
            assert res_live["passed"] is False
            assert res_live["mechanism"] == "sandbox_denied"


def test_tc9_agy_allow_rules(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda bin_name: "/usr/local/bin/agy")
    with patch("synlynk.probe._run_tc6", return_value={"passed": True, "error": "", "output": "ok"}):
        # TC-7 fails
        with patch("synlynk.doctor._run_tc7", return_value={"passed": False, "missing": ["command(gh pr review)"]}):
            res = _run_tc9("agy")
            assert res["passed"] is False
            assert res["can_gh_write"] is False
            assert res["mechanism"] == "missing_allow_rules"

        # TC-7 passes
        with patch("synlynk.doctor._run_tc7", return_value={"passed": True, "missing": []}):
            res = _run_tc9("agy")
            assert res["passed"] is True
            assert res["can_gh_write"] is True
            assert res["mechanism"] == "verified_allow_rules"


def test_tc9_uninstalled_cli(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda bin_name: None)
    with patch("synlynk.probe._run_tc6", return_value={"passed": True, "error": "", "output": "ok"}):
        res = _run_tc9("nonexistent_agent")
        assert res["passed"] is False
        assert res["mechanism"] == "uninstalled"


def test_tc9_db_persistence(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda bin_name: "/usr/local/bin/claude")
    with patch("synlynk.probe._run_tc6", return_value={"passed": True, "error": "", "output": "ok"}):
        db = sqlite3.connect(":memory:")
        _migrate_db(db)

        res = _run_tc9("claude", db_conn=db)
        assert res["passed"] is True

        row = db.execute(
            "SELECT harness_name, event_type, cli_version FROM harness_version_history WHERE event_type='gh_write_probe'"
        ).fetchone()
        assert row is not None
        assert row[0] == "claude"
        assert row[1] == "gh_write_probe"
        assert row[2] == "direct_cli"


def test_doctor_prints_tc9_output(monkeypatch, capsys):
    monkeypatch.setattr("shutil.which", lambda bin_name: "/usr/local/bin/claude")
    with patch("synlynk.probe._run_tc6", return_value={"passed": True, "error": "", "output": "ok"}):
        db = sqlite3.connect(":memory:")
        _migrate_db(db)

        # Mock _get_db to return our memory db
        monkeypatch.setattr("synlynk._get_db", lambda: db)
        monkeypatch.setattr("synlynk.doctor.find_nested_product_state_dbs", lambda path: [])
        monkeypatch.setattr("synlynk.doctor.repo_has_any_core_instruction_file", lambda path: False)

        args = MagicMock(fix=None, agent="claude")
        cmd_doctor(args=args)

        captured = capsys.readouterr().out
        assert "TC-9 gh-write: ✓ (direct_cli)" in captured
