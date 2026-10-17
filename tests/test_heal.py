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


def test_run_magic_heal_dry_run(tmp_path):
    from synlynk.heal import run_magic_heal
    (tmp_path / "service.py").write_text("def ping():\n    return 'pong'\n")
    res = run_magic_heal(repo_root=str(tmp_path), dry_run=True, role="dev")
    assert res["success"] is True
    assert res["dry_run"] is True
    assert "test_magic_service.py" in res["test_file"]
    assert "service.py" in res["pr_title"]
    assert "Co-Authored-By:" in res["trailer"]


def test_run_magic_heal_resolves_dynamic_trailer():
    from synlynk.heal import _resolve_agent_trailer
    agy_trailer = _resolve_agent_trailer(role="frontend")
    assert "AGY <noreply@antigravity.dev>" in agy_trailer
    grok_trailer = _resolve_agent_trailer(harness="grok")
    assert "Grok <noreply@x.ai>" in grok_trailer
    claude_trailer = _resolve_agent_trailer(harness="claude")
    assert "Claude Sonnet <noreply@anthropic.com>" in claude_trailer


def test_run_magic_heal_worktree_isolation(tmp_path):
    import subprocess
    from synlynk.heal import run_magic_heal

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@synlynk.dev"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Synlynk Test"], check=True)
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    subprocess.run(["git", "-C", str(repo), "add", "calc.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial commit"], check=True)

    branch_before = subprocess.run(
        ["git", "-C", str(repo), "branch", "--show-current"],
        capture_output=True, text=True, check=True
    ).stdout.strip()
    assert branch_before == "main"

    res = run_magic_heal(repo_root=str(repo), dry_run=False, auto_pr=False, role="dev", harness="agy")

    # Working tree branch must remain strictly untouched
    branch_after = subprocess.run(
        ["git", "-C", str(repo), "branch", "--show-current"],
        capture_output=True, text=True, check=True
    ).stdout.strip()
    assert branch_after == "main"

    # Ephemeral worktree must have been cleaned up
    wt_list = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list"],
        capture_output=True, text=True, check=True
    ).stdout
    assert len(wt_list.strip().splitlines()) == 1

    # Magic heal branch must exist with the committed test
    assert res["success"] is True
    assert res["committed"] is True
    assert res["worktree_isolated"] is True
