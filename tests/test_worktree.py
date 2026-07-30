from synlynk.worktree import WorktreeEntry, WorktreeVerdict, _build_worktree_entries, _parse_worktree_porcelain


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
