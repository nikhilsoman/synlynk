"""Test FTUE invocation of Vizor in an uninitialized directory (gh:#4819)."""

import os
from unittest.mock import patch, MagicMock

import pytest

import synlynk.viz.server as viz_server


def test_start_server_ensures_synlynk_directory(tmp_path, monkeypatch):
    """Calling _start_server in a directory where .synlynk/ does not exist must not raise FileNotFoundError."""
    monkeypatch.chdir(tmp_path)
    assert not (tmp_path / ".synlynk").exists()

    # Mock socket / server serving so we only test server startup directory initialization
    mock_server = MagicMock()
    with patch("http.server.HTTPServer", return_value=mock_server):
        with patch("threading.Thread") as mock_thread:
            server = viz_server._start_server(33333)
            assert server is mock_server
            assert (tmp_path / ".synlynk").exists()
            assert (tmp_path / ".synlynk" / "viz-meta.json").exists()
            assert (tmp_path / ".synlynk" / "viz-cache").is_dir()


def test_ftue_prompts_ensures_synlynk_directory(tmp_path, monkeypatch):
    """Calling _ftue_prompts in a directory without .synlynk/ must save settings cleanly."""
    monkeypatch.chdir(tmp_path)
    assert not (tmp_path / ".synlynk").exists()

    config = {}
    with patch("sys.stdin.isatty", return_value=False):
        result = viz_server._ftue_prompts(config)
        assert (tmp_path / ".synlynk").exists()
        assert (tmp_path / ".synlynk" / "config.json").exists()
        assert result.get("vizor", {}).get("ftue_done") is True
