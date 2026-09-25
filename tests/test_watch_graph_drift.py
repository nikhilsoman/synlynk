import json
import os
import time
from unittest.mock import patch, MagicMock
import pytest
from pathlib import Path
from synlynk.daemon import WatchDaemon


def test_watch_daemon_detects_graph_staleness_and_triggers_refresh(tmp_path):
    d = WatchDaemon()
    d.workspace_root = str(tmp_path)
    d.pidfile = str(tmp_path / "watch.pid")
    d.logfile = str(tmp_path / "watch.log")

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    manifest_file = out_dir / "manifest.json"
    manifest_file.write_text(json.dumps({"head_commit": "old_commit_sha"}))
    graph_file = out_dir / "graph.json"
    graph_file.write_text("{}")

    with patch("synlynk.daemon._current_repo_revision", return_value="new_commit_sha"), \
         patch("synlynk.scan._run_graphify_extract") as mock_extract:
        d._check_graph_staleness_and_refresh()
        # Give background thread a split second to start
        time.sleep(0.1)
        assert mock_extract.called
        assert mock_extract.call_args[0][0] == str(tmp_path)


def test_watch_daemon_respects_refresh_cooldown(tmp_path):
    d = WatchDaemon()
    d.workspace_root = str(tmp_path)
    d.pidfile = str(tmp_path / "watch.pid")
    d.logfile = str(tmp_path / "watch.log")

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    (out_dir / "manifest.json").write_text(json.dumps({"head_commit": "old_commit_sha"}))
    (out_dir / "graph.json").write_text("{}")

    with patch("synlynk.daemon._current_repo_revision", return_value="new_commit_sha"), \
         patch("synlynk.scan._run_graphify_extract") as mock_extract:
        d._check_graph_staleness_and_refresh()
        time.sleep(0.05)
        assert mock_extract.call_count == 1

        # Second call within 30s cooldown should NOT trigger another extract
        d._check_graph_staleness_and_refresh()
        time.sleep(0.05)
        assert mock_extract.call_count == 1


def test_dispatch_jit_cache_check_triggers_extraction_when_missing(tmp_path):
    from synlynk.dispatch import _format_prompt_for_agent

    with patch("synlynk.scan._run_graphify_extract") as mock_extract, \
         patch("synlynk.pack.synthesize_context_pack", return_value=""):
        _format_prompt_for_agent(
            agent="codex",
            context_text="Base context",
            story_id=None,
            task="Test task",
            file_section="",
            verify_section="",
            cwd_hint=str(tmp_path),
        )
        assert mock_extract.called
        assert mock_extract.call_args[0][0] == str(tmp_path)
