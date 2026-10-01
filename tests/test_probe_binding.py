from unittest.mock import patch, MagicMock
import pytest
from synlynk.probe_binding import (
    probe_dependency,
    probe_all_dependencies,
    probe_harness_live,
    probe_all_harnesses,
)


def test_probe_dependency_git():
    res = probe_dependency("git")
    assert "installed" in res
    assert "status" in res
    if res["installed"]:
        assert res["version"] is not None


def test_probe_harness_live_offline():
    with patch("shutil.which", return_value=None):
        res = probe_harness_live("claude")
        assert res["installed"] is False
        assert res["auth_verified"] is False
        assert res["status"] == "missing"


def test_probe_harness_live_active_mock():
    with patch("shutil.which", return_value="/usr/local/bin/codex"), \
         patch("subprocess.run") as mock_run:
        # Mock version call
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="codex 1.2.3\n", stderr=""),
            MagicMock(returncode=0, stdout="authenticated as test\n", stderr=""),
        ]
        res = probe_harness_live("codex")
        assert res["installed"] is True
        assert res["auth_verified"] is True
        assert res["status"] == "verified"
