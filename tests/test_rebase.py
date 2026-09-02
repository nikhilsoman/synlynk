from synlynk.rebase import _merge_markdown_conflict


def test_markdown_conflict_combines_unique_rows_in_pr_order():
    text = """before\n<<<<<<< HEAD\n| PR #1346 | newer |\n=======\n| PR #1345 | older |\n>>>>>>> origin/main\nafter\n"""
    resolved = _merge_markdown_conflict(text)
    assert resolved == "before\n| PR #1345 | older |\n| PR #1346 | newer |\nafter\n"
