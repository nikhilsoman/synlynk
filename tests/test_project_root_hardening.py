import subprocess
import pytest

import synlynk


def test_project_root_raises_when_git_resolution_fails(monkeypatch):
    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0] if args else ["git"])

    monkeypatch.setattr(subprocess, "check_output", _raise)
    monkeypatch.delenv("SYNLYNK_ALLOW_CWD_FALLBACK", raising=False)

    with pytest.raises(RuntimeError, match="git-common-dir"):
        synlynk._project_root()


def test_project_root_falls_back_to_cwd_with_explicit_override(monkeypatch, tmp_path):
    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0] if args else ["git"])

    monkeypatch.setattr(subprocess, "check_output", _raise)
    monkeypatch.setenv("SYNLYNK_ALLOW_CWD_FALLBACK", "1")
    monkeypatch.chdir(tmp_path)

    assert synlynk._project_root() == str(tmp_path)
