import os


def test_sop_docs_exist_and_are_referenced_from_claude_md():
    sop_files = [
        "docs/sop/capability-task-allocation.md",
        "docs/sop/pr-review-discipline.md",
        "docs/sop/worktree-and-cost-hygiene.md",
    ]
    for path in sop_files:
        assert os.path.exists(path), f"{path} should exist"

    with open("CLAUDE.md") as f:
        claude_md = f.read()
    for path in sop_files:
        assert path in claude_md, f"CLAUDE.md should point to {path}"


def test_claude_md_is_leaner_than_before():
    with open("CLAUDE.md") as f:
        line_count = sum(1 for _ in f)
    # Was ~335 lines pre-migration (per gh:#2243 audit); the moved
    # sections alone are well over 150 lines, so this is a conservative
    # ceiling that still catches a no-op "refactor".
    assert line_count < 250, f"CLAUDE.md still has {line_count} lines"
