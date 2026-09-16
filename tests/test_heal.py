import os
from unittest.mock import patch

import synlynk
from synlynk.db import cmd_story_create
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


def test_auto_merge_marks_linked_story_done(project_dir):
    story_id = cmd_story_create("merged story")
    with patch("synlynk.heal._merged_pr_branch", return_value="feat/merged"), \
         patch("synlynk.merge_oracle.require_merge_oracle", return_value={"merge_allowed": True}), \
         patch("synlynk.heal.subprocess.run") as run, \
         patch("synlynk.worktree_prune.reap_merged_worktree"):
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        assert _auto_merge(
            [{"story_id": story_id, "pr_number": 12}], [{"passed": True}]
        ) == ["12"]

    conn = synlynk._get_db()
    status = conn.execute(
        "SELECT status FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()[0]
    conn.close()
    assert status == "done"


def test_auto_merge_does_not_reach_gh_merge_when_role_is_unauthorized():
    with patch("synlynk.heal._merged_pr_branch", return_value="feat/blocked"), \
         patch("synlynk.policy_cli.cmd_policy_check_merge", return_value=1) as check_merge, \
         patch("synlynk.heal.subprocess.run") as run:
        assert _auto_merge([{"pr_number": 12}], [{"passed": True}], role="dev") == []

    check_merge.assert_called_once_with(role="dev")
    assert not any("merge" in call.args[0] for call in run.call_args_list)
