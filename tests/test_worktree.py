import json
import os
import subprocess as _subprocess

from synlynk.worktree import (
    WorktreeEntry,
    WorktreeVerdict,
    _apply_nesting_floor,
    _build_worktree_entries,
    _classify_worktree,
    cmd_worktree_audit,
    _parse_worktree_porcelain,
    cmd_worktree_clean,
)


def test_parse_worktree_porcelain_basic():
    text = (
        "worktree /repo/main\n"
        "HEAD abc123\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /repo/.worktrees/chore+foo\n"
        "HEAD def456\n"
        "branch refs/heads/chore/foo\n"
        "\n"
        "worktree /repo/.worktrees/detached-one\n"
        "HEAD ghi789\n"
        "detached\n"
    )
    parsed = _parse_worktree_porcelain(text)
    assert parsed == [
        {"path": "/repo/main", "branch": "main", "bare": False},
        {"path": "/repo/.worktrees/chore+foo", "branch": "chore/foo", "bare": False},
        {"path": "/repo/.worktrees/detached-one", "branch": None, "bare": False},
    ]


def test_worktree_entry_and_verdict_are_dataclasses_with_defaults():
    entry = WorktreeEntry(path="/x", branch="feat/y")
    assert entry.nested_under is None
    verdict = WorktreeVerdict(path="/x", branch="feat/y", verdict="safe", reason="merged")
    assert verdict.nested_under is None


def test_build_worktree_entries_excludes_main_and_cwd():
    raw = [
        {"path": "/repo", "branch": "main", "bare": False},
        {"path": "/repo/.worktrees/a", "branch": "chore/a", "bare": False},
        {"path": "/repo/.worktrees/b", "branch": "chore/b", "bare": False},
    ]
    entries = _build_worktree_entries(raw, main_repo_path="/repo", cwd_worktree_path="/repo/.worktrees/b")
    assert [e.path for e in entries] == ["/repo/.worktrees/a"]
    assert entries[0].branch == "chore/a"


def test_build_worktree_entries_computes_nesting():
    raw = [
        {"path": "/repo", "branch": "main", "bare": False},
        {"path": "/repo/.worktrees/parent", "branch": "chore/parent", "bare": False},
        {"path": "/repo/.worktrees/parent/worktrees/job-1", "branch": "dispatch/codex/job-1", "bare": False},
    ]
    entries = _build_worktree_entries(raw, main_repo_path="/repo", cwd_worktree_path="/nowhere")
    by_path = {e.path: e for e in entries}
    assert by_path["/repo/.worktrees/parent"].nested_under is None
    assert by_path["/repo/.worktrees/parent/worktrees/job-1"].nested_under == "/repo/.worktrees/parent"


def test_nesting_floor_nested_under_safe_parent_stays_safe():
    parent = WorktreeVerdict(path="/p", branch="chore/parent", verdict="safe", reason="merged, direct ancestor")
    child = WorktreeVerdict(
        path="/p/worktrees/job-1", branch="dispatch/codex/job-1", verdict="safe",
        reason="merged, direct ancestor", nested_under="/p",
    )
    result = _apply_nesting_floor([parent, child])
    by_path = {v.path: v for v in result}
    assert by_path["/p/worktrees/job-1"].verdict == "safe"


def test_nesting_floor_raises_child_to_parent_verdict():
    parent_needs_review = WorktreeVerdict(path="/p", branch="chore/parent", verdict="needs-review", reason="no PR found, 1 commits ahead of main")
    child_safe = WorktreeVerdict(
        path="/p/worktrees/job-1", branch="dispatch/codex/job-1", verdict="safe",
        reason="merged, direct ancestor", nested_under="/p",
    )
    result = _apply_nesting_floor([parent_needs_review, child_safe])
    by_path = {v.path: v for v in result}
    assert by_path["/p/worktrees/job-1"].verdict == "needs-review"
    assert "parent worktree not yet safe" in by_path["/p/worktrees/job-1"].reason

    parent_unsafe = WorktreeVerdict(path="/q", branch="chore/parent2", verdict="unsafe", reason="PR #1 open — active work")
    child_needs_review = WorktreeVerdict(
        path="/q/worktrees/job-2", branch="dispatch/codex/job-2", verdict="needs-review",
        reason="no PR found, 1 commits ahead of main", nested_under="/q",
    )
    result2 = _apply_nesting_floor([parent_unsafe, child_needs_review])
    by_path2 = {v.path: v for v in result2}
    assert by_path2["/q/worktrees/job-2"].verdict == "unsafe"


def _entry(path="/repo/.worktrees/x", branch="chore/x"):
    return WorktreeEntry(path=path, branch=branch)


def test_classify_ancestor_true_is_safe():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=True, gh_available=True, pr_info=None, net_diff_lines=None, commits_ahead=0,
    )
    assert v.verdict == "safe"
    assert v.reason == "merged, direct ancestor"


def test_classify_pr_merged_is_safe():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True,
        pr_info={"number": 552, "state": "MERGED"}, net_diff_lines=None, commits_ahead=3,
    )
    assert v.verdict == "safe"
    assert v.reason == "PR #552 merged"


def test_classify_pr_closed_net_zero_or_negative_is_safe():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True,
        pr_info={"number": 516, "state": "CLOSED"}, net_diff_lines=-4, commits_ahead=2,
    )
    assert v.verdict == "safe"
    assert "no unique content" in v.reason


def test_classify_pr_closed_net_positive_is_needs_review():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True,
        pr_info={"number": 517, "state": "CLOSED"}, net_diff_lines=42, commits_ahead=2,
    )
    assert v.verdict == "needs-review"
    assert v.reason == "PR #517 closed, 42 net lines of unmerged content"


def test_classify_pr_open_is_unsafe():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True,
        pr_info={"number": 566, "state": "OPEN"}, net_diff_lines=None, commits_ahead=1,
    )
    assert v.verdict == "unsafe"
    assert v.reason == "PR #566 open — active work"


def test_classify_no_pr_found_is_needs_review():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True,
        pr_info=None, net_diff_lines=None, commits_ahead=1,
    )
    assert v.verdict == "needs-review"
    assert v.reason == "no PR found, 1 commits ahead of main"


def test_classify_dirty_overrides_everything():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=True, dirty_summary="M GEMINI.md",
        is_ancestor=True, gh_available=True,
        pr_info={"number": 1, "state": "MERGED"}, net_diff_lines=None, commits_ahead=0,
    )
    assert v.verdict == "needs-review"
    assert v.reason == "dirty: M GEMINI.md"


def test_classify_gh_unavailable_falls_back_to_needs_review():
    v = _classify_worktree(
        _entry(), worktree_missing=False, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=False,
        pr_info=None, net_diff_lines=None, commits_ahead=0,
    )
    assert v.verdict == "needs-review"
    assert v.reason == "could not verify PR state — gh unavailable"


def test_classify_missing_worktree_directory_is_safe():
    v = _classify_worktree(
        _entry(), worktree_missing=True, is_dirty=False, dirty_summary="",
        is_ancestor=False, gh_available=True, pr_info=None, net_diff_lines=None, commits_ahead=0,
    )
    assert v.verdict == "safe"
    assert v.reason == "worktree directory missing — stale registration"


def _run(cmd, cwd):
    result = _subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, f"{cmd} failed: {result.stderr}"
    return result


def _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False):
    """Real git repo fixture: main repo with one linked worktree on a
    feature branch. If branch_ahead_of_main, the feature branch gets an
    extra commit main doesn't have (so merge-base --is-ancestor is false)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.email", "test@test.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test"], cwd=repo)
    (repo / "README.md").write_text("hello\n")
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "init"], cwd=repo)
    _run(["git", "remote", "add", "origin", str(repo)], cwd=repo)
    _run(["git", "branch", "origin/main"], cwd=repo)

    wt_dir = tmp_path / "wt-feature"
    _run(["git", "worktree", "add", str(wt_dir), "-b", "chore/feature"], cwd=repo)
    if branch_ahead_of_main:
        (wt_dir / "extra.txt").write_text("new stuff\n")
        _run(["git", "add", "."], cwd=wt_dir)
        _run(["git", "commit", "-m", "extra work"], cwd=wt_dir)
    return repo, wt_dir


def _make_stub_gh(tmp_path, monkeypatch, auth_ok=True, pr_json="[]"):
    script = tmp_path / "gh"
    script.write_text(
        f"""#!/bin/sh
if [ "$1" = "auth" ]; then
  {"exit 0" if auth_ok else "exit 1"}
fi
if [ "$1" = "pr" ]; then
  echo '{pr_json}'
  exit 0
fi
exit 0
"""
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")


def test_cmd_worktree_audit_reports_safe_ancestor(tmp_path, monkeypatch):
    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    output = cmd_worktree_audit(json_output=False)
    assert "SAFE (1)" in output
    assert "chore/feature" in output
    assert "merged, direct ancestor" in output


def test_cmd_worktree_audit_json_output_shape(tmp_path, monkeypatch):
    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    output = cmd_worktree_audit(json_output=True)
    payload = json.loads(output)
    assert payload == [
        {
            "path": str(wt_dir),
            "branch": "chore/feature",
            "verdict": "safe",
            "reason": "merged, direct ancestor",
            "nested_under": None,
        }
    ]


def test_cmd_worktree_audit_no_worktrees_prints_one_liner(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.email", "test@test.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test"], cwd=repo)
    (repo / "README.md").write_text("hello\n")
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "init"], cwd=repo)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    output = cmd_worktree_audit(json_output=False)
    assert output == "No stale worktrees — nothing to audit."


def test_cmd_worktree_clean_dry_run_does_not_mutate(tmp_path, monkeypatch):
    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    output = cmd_worktree_clean(apply=False, json_output=False)
    assert "[dry-run] would remove 1 worktrees + branches (use --apply)" in output
    assert wt_dir.exists()
    branches = _run(["git", "branch", "--list", "chore/feature"], cwd=repo).stdout
    assert "chore/feature" in branches


def test_cmd_worktree_clean_apply_removes_safe_items(tmp_path, monkeypatch):
    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    output = cmd_worktree_clean(apply=True, json_output=False)
    assert "wt=removed" in output
    assert "branch=deleted" in output
    assert not wt_dir.exists()
    branches = _run(["git", "branch", "--list", "chore/feature"], cwd=repo).stdout
    assert "chore/feature" not in branches


def test_cmd_worktree_clean_apply_partial_failure_continues_batch(tmp_path, monkeypatch):
    from synlynk import worktree as worktree_mod

    repo, wt_dir_a = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    wt_dir_b = tmp_path / "wt-feature-b"
    _run(["git", "worktree", "add", str(wt_dir_b), "-b", "chore/feature-b"], cwd=repo)
    _make_stub_gh(tmp_path, monkeypatch, auth_ok=True)
    monkeypatch.chdir(repo)

    real_run = worktree_mod.subprocess.run

    def _flaky_run(cmd, *args, **kwargs):
        if cmd[:3] == ["git", "branch", "-D"] and cmd[3] == "chore/feature":
            class _Result:
                returncode = 1
                stderr = "branch is checked out elsewhere"
                stdout = ""
            return _Result()
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(worktree_mod.subprocess, "run", _flaky_run)

    output = worktree_mod.cmd_worktree_clean(apply=True, json_output=False)
    assert "chore/feature   wt=removed   branch=FAILED" in output
    assert "chore/feature-b   wt=removed   branch=deleted" in output


def test_cli_registers_worktree_audit_and_clean_subcommands():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["worktree", "audit", "--json"])
    assert args.command == "worktree"
    assert args.worktree_action == "audit"
    assert args.json_output is True

    args2 = parser.parse_args(["worktree", "clean", "--apply"])
    assert args2.command == "worktree"
    assert args2.worktree_action == "clean"
    assert args2.apply is True
    assert args2.json_output is False


def test_worktree_status_hint_counts_non_dirty_worktrees(tmp_path, monkeypatch):
    from synlynk.worktree import _worktree_status_hint

    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=True)
    monkeypatch.chdir(repo)

    hint = _worktree_status_hint()
    assert hint == {"local": 1, "stale_hint": 1}


def test_worktree_status_hint_returns_none_when_no_worktrees(tmp_path, monkeypatch):
    from synlynk.worktree import _worktree_status_hint

    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.email", "test@test.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test"], cwd=repo)
    (repo / "README.md").write_text("hello\n")
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "init"], cwd=repo)
    monkeypatch.chdir(repo)

    assert _worktree_status_hint() is None


def test_worktree_status_hint_never_invokes_gh(tmp_path, monkeypatch):
    from synlynk import worktree as worktree_mod

    repo, wt_dir = _init_repo_with_worktree(tmp_path, branch_ahead_of_main=False)
    monkeypatch.chdir(repo)

    real_run = worktree_mod.subprocess.run

    def _guarded_run(cmd, *args, **kwargs):
        assert cmd[0] != "gh", "_worktree_status_hint must never call gh"
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(worktree_mod.subprocess, "run", _guarded_run)
    hint = worktree_mod._worktree_status_hint()
    assert hint == {"local": 1, "stale_hint": 1}


def test_status_terminal_includes_worktrees_line_when_stale_present():
    from synlynk.status import _format_status_terminal

    output = _format_status_terminal(
        harness_rows=[], cycle_map={}, efficiency_ratio=1.0, dispatch_mode="daily-grind",
        sentinels_active=0, json_output=False, rates_updated_at="2026-07-29",
        worktree_hint={"local": 6, "stale_hint": 2},
    )
    assert "WORKTREES  6 local, 2 look stale — run `synlynk worktree audit`" in output


def test_status_terminal_omits_worktrees_line_when_no_stale():
    from synlynk.status import _format_status_terminal

    output = _format_status_terminal(
        harness_rows=[], cycle_map={}, efficiency_ratio=1.0, dispatch_mode="daily-grind",
        sentinels_active=0, json_output=False, rates_updated_at="2026-07-29",
        worktree_hint=None,
    )
    assert "WORKTREES" not in output


def test_status_json_includes_worktrees_field():
    import json as _json
    from synlynk.status import _format_status_terminal

    output = _format_status_terminal(
        harness_rows=[], cycle_map={}, efficiency_ratio=1.0, dispatch_mode="daily-grind",
        sentinels_active=0, json_output=True, rates_updated_at="2026-07-29",
        worktree_hint={"local": 6, "stale_hint": 2},
    )
    payload = _json.loads(output)
    assert payload["worktrees"] == {"local": 6, "stale_hint": 2}
