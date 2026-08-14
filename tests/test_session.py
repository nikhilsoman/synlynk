import json
import os

import pytest


def test_write_and_read_active_session(tmp_path, monkeypatch):
    from synlynk.session import _write_active_session, _read_active_session, _active_session_path

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    _write_active_session("session-abc12345")

    assert os.path.exists(_active_session_path())
    assert _read_active_session() == "session-abc12345"


def test_read_active_session_returns_none_when_absent(tmp_path, monkeypatch):
    from synlynk.session import _read_active_session

    monkeypatch.chdir(tmp_path)
    assert _read_active_session() is None


def test_clear_active_session_removes_marker(tmp_path, monkeypatch):
    from synlynk.session import _write_active_session, _read_active_session, _clear_active_session

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    _write_active_session("session-abc12345")
    _clear_active_session()

    assert _read_active_session() is None
