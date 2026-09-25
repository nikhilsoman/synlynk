import os
import subprocess
from unittest.mock import patch, MagicMock
from synlynk.scan import _run_graphify_extract


def test_run_graphify_extract_when_installed(tmp_path):
    with patch("synlynk.scan.is_tool_available", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ok = _run_graphify_extract(str(tmp_path))
        assert ok is True
        mock_run.assert_called_once_with(
            ["graphify", "extract", str(tmp_path), "--code-only", "--out", os.path.join(str(tmp_path), ".synlynk", "graphify-out")],
            capture_output=True,
            text=True,
            timeout=120,
        )


def test_run_graphify_extract_auto_installs_if_missing(tmp_path):
    with patch("synlynk.scan.is_tool_available", side_effect=[False, True]), \
         patch("synlynk.scan.install_tool", return_value=True) as mock_install, \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ok = _run_graphify_extract(str(tmp_path))
        assert ok is True
        mock_install.assert_called_once_with("graphify")


def test_run_graphify_extract_install_fails(tmp_path):
    with patch("synlynk.scan.is_tool_available", return_value=False), \
         patch("synlynk.scan.install_tool", return_value=False) as mock_install:
        ok = _run_graphify_extract(str(tmp_path))
        assert ok is False
        mock_install.assert_called_once_with("graphify")


def test_run_graphify_extract_subprocess_error(tmp_path):
    with patch("synlynk.scan.is_tool_available", return_value=True), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
        ok = _run_graphify_extract(str(tmp_path))
        assert ok is False


def test_cmd_scan_deep_calls_run_graphify_extract(tmp_path):
    from synlynk.scan import cmd_scan

    with patch("synlynk.scan._pkg") as mock_pkg, \
         patch("synlynk.scan._run_graphify_extract") as mock_extract, \
         patch("os.getcwd", return_value=str(tmp_path)):
        mock_pkg.side_effect = lambda name, default=None: (
            (lambda: ({}, 10, 20)) if name == "_scan_full_repo"
            else (lambda: "1234567890") if name == "_git_head_sha"
            else default
        )
        cmd_scan(deep=True)
        mock_extract.assert_called_once_with(str(tmp_path))


def test_execute_upgrade_calls_run_graphify_extract(tmp_path):
    import importlib
    upgrade_mod = importlib.import_module("synlynk.upgrade")

    with patch.object(upgrade_mod, "_run_graphify_extract") as mock_extract, \
         patch("synlynk.surface.detect_developer_surfaces", return_value=[]), \
         patch("synlynk.surface.bind_surface_rules"):
        res = upgrade_mod.execute_upgrade(str(tmp_path))
        assert res["status"] == "upgraded"
        mock_extract.assert_called_once_with(str(tmp_path))
