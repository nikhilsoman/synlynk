import json
import subprocess
from unittest.mock import patch

from synlynk.pr_rebase import rebase_pr_if_behind


def test_rebase_pr_if_behind_rebases_and_force_pushes_with_lease(tmp_path):
    view = subprocess.CompletedProcess([], 0, json.dumps({
        "mergeStateStatus": "BEHIND",
        "mergeable": "MERGEABLE",
        "headRefName": "feat/stacked",
    }), "")
    git_ok = subprocess.CompletedProcess([], 0, "", "")
    with patch("synlynk.pr_rebase.subprocess.run", side_effect=[view, git_ok, git_ok, git_ok]) as run:
        result = rebase_pr_if_behind(1604, str(tmp_path))

    assert result["rebased"] is True
    assert run.call_args_list[1].args[0] == ["git", "-C", str(tmp_path), "fetch", "origin", "main"]
    assert run.call_args_list[2].args[0] == ["git", "-C", str(tmp_path), "rebase", "origin/main"]
    assert run.call_args_list[3].args[0] == [
        "git", "-C", str(tmp_path), "push", "origin", "HEAD:feat/stacked", "--force-with-lease"
    ]


def test_rebase_pr_if_behind_aborts_conflict_without_push(tmp_path):
    view = subprocess.CompletedProcess([], 0, json.dumps({
        "mergeStateStatus": "BEHIND", "mergeable": "MERGEABLE", "headRefName": "feat/stacked"
    }), "")
    conflict = subprocess.CompletedProcess([], 1, "", "conflict")
    aborted = subprocess.CompletedProcess([], 0, "", "")
    with patch("synlynk.pr_rebase.subprocess.run", side_effect=[view, subprocess.CompletedProcess([], 0), conflict, aborted]) as run:
        result = rebase_pr_if_behind(1604, str(tmp_path))

    assert result["rebased"] is False
    assert run.call_args_list[-1].args[0][-2:] == ["rebase", "--abort"]
    assert not any("push" in call.args[0] for call in run.call_args_list)


def test_rebase_pr_if_behind_skips_non_behind_pr(tmp_path):
    view = subprocess.CompletedProcess([], 0, json.dumps({"mergeStateStatus": "CLEAN", "mergeable": "MERGEABLE"}), "")
    with patch("synlynk.pr_rebase.subprocess.run", return_value=view) as run:
        result = rebase_pr_if_behind(1604, str(tmp_path))

    assert result["attempted"] is False
    assert run.call_count == 1
