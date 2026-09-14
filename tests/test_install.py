import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synlynk.install import check_install_prerequisites, run_install_preflight


def test_check_install_prerequisites_all_satisfied():
    with patch("shutil.which", side_effect=lambda bin_name: f"/usr/bin/{bin_name}"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="git version 2.40.0\n")
            result = check_install_prerequisites()
            assert result["git"]["satisfied"] is True
            assert result["python"]["satisfied"] is True
            assert result["can_proceed"] is True
            assert run_install_preflight() is True


def test_check_install_prerequisites_git_missing():
    with patch("shutil.which", return_value=None):
        result = check_install_prerequisites()
        assert result["git"]["satisfied"] is False
        assert result["can_proceed"] is False
        assert run_install_preflight() is False
