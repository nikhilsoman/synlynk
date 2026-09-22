import os
from pathlib import Path

import pytest

from synlynk import vizor_daemon


def test_poll_interval_default(monkeypatch):
    monkeypatch.delenv("SYNLYNK_VIZOR_POLL_INTERVAL", raising=False)
    assert vizor_daemon.poll_interval() == 15


def test_poll_interval_override(monkeypatch):
    monkeypatch.setenv("SYNLYNK_VIZOR_POLL_INTERVAL", "5")
    assert vizor_daemon.poll_interval() == 5


def test_poll_interval_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("SYNLYNK_VIZOR_POLL_INTERVAL", "not-a-number")
    assert vizor_daemon.poll_interval() == 15


def test_workspace_render_context_chdirs_and_restores(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = tmp_path / "state.db"
    db_path.write_bytes(b"")
    original_cwd = os.getcwd()

    seen_cwd = {}
    with vizor_daemon.workspace_render_context(repo, db_path, tmp_path / "cache"):
        seen_cwd["inside"] = Path(os.getcwd())

    assert seen_cwd["inside"] == repo.resolve()
    assert Path(os.getcwd()) == Path(original_cwd)


def test_workspace_render_context_restores_get_db_on_exception(tmp_path):
    import synlynk.viz as viz_module

    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = tmp_path / "state.db"
    db_path.write_bytes(b"")
    original_get_db = viz_module._get_db

    with pytest.raises(RuntimeError):
        with vizor_daemon.workspace_render_context(repo, db_path, tmp_path / "cache"):
            raise RuntimeError("boom")

    assert viz_module._get_db is original_get_db
