from synlynk.worktree import (
    WorktreeEntry,
    WorktreeVerdict,
    _build_worktree_entries,
    _classify_worktree,
    _parse_worktree_porcelain,
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
