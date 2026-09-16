import os
from unittest.mock import patch

from synlynk.heal import _diagnostics, _auto_merge


def test_diagnostics_normalizes_scan_findings():
    assert _diagnostics({"findings": ["missing test"]}) == [
        {"title": "missing test", "body": "missing test", "source_type": "scan"}
    ]


def test_auto_merge_is_fail_closed_when_qa_is_red():
    assert _auto_merge([{"story_id": "story-1", "pr_number": 12}], [{"passed": False}]) == []


def test_auto_merge_reaps_worktree_after_successful_merge():
    with patch("synlynk.heal._merged_pr_branch", return_value="feat/merged"), \
         patch("synlynk.merge_oracle.require_merge_oracle", return_value={"merge_allowed": True}), \
         patch("synlynk.heal.subprocess.run") as run, \
         patch("synlynk.worktree_prune.reap_merged_worktree") as reap:
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        assert _auto_merge([{"pr_number": 12}], [{"passed": True}]) == ["12"]
    reap.assert_called_once_with(os.getcwd(), branch="feat/merged")
