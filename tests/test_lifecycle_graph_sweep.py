import os
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.watch import check_and_refresh_ast_on_drift, trigger_post_merge_graph_sweep
from synlynk.pr_check import check_pr_impact_attestation


def test_watch_drift_detection_triggers_refresh_when_stale():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / ".synlynk" / "graphify-out"
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = out_dir / "manifest.json"
        manifest_file.write_text(json.dumps({"built_at_commit": "old_commit_111"}), encoding="utf-8")

        with patch("synlynk.watch._get_head_commit", return_value="new_commit_222"), \
             patch("synlynk.scan.ensure_graph_for_head", return_value=True) as mock_ensure:
            refreshed = check_and_refresh_ast_on_drift(tmpdir)
            assert refreshed is True
            mock_ensure.assert_called_once_with(tmpdir)


def test_watch_drift_detection_no_op_when_head_matches():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / ".synlynk" / "graphify-out"
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = out_dir / "manifest.json"
        manifest_file.write_text(json.dumps({"built_at_commit": "matching_commit_333"}), encoding="utf-8")

        with patch("synlynk.watch._get_head_commit", return_value="matching_commit_333"), \
             patch("synlynk.scan.ensure_graph_for_head") as mock_ensure:
            refreshed = check_and_refresh_ast_on_drift(tmpdir)
            assert refreshed is False
            assert mock_ensure.call_count == 0


def test_trigger_post_merge_graph_sweep_calls_refresh():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("synlynk.watch.check_and_refresh_ast_on_drift", return_value=True) as mock_refresh:
            res = trigger_post_merge_graph_sweep(tmpdir)
            assert res is True
            mock_refresh.assert_called_once_with(tmpdir)


def test_pr_check_triggers_graph_currency_sweep():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("synlynk.watch.check_and_refresh_ast_on_drift") as mock_refresh, \
             patch("synlynk.pr_check._get_modified_symbols_from_diff", return_value=[]):
            res = check_pr_impact_attestation(tmpdir)
            assert res["passed"] is True
            mock_refresh.assert_called_once_with(tmpdir)
