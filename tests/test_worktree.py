from synlynk.worktree import WorktreeEntry, WorktreeVerdict, _parse_worktree_porcelain


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
