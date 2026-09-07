from synlynk.rebase import _merge_markdown_conflict, reconcile_union_merged_markdown


def test_markdown_conflict_combines_unique_rows_in_pr_order():
    text = """before\n<<<<<<< HEAD\n| PR #1346 | newer |\n=======\n| PR #1345 | older |\n>>>>>>> origin/main\nafter\n"""
    resolved = _merge_markdown_conflict(text)
    assert resolved == "before\n| PR #1345 | older |\n| PR #1346 | newer |\nafter\n"


def test_reconcile_union_merged_markdown_prefers_checked_checkbox_and_dedupes():
    text = (
        "- [ ] Alpha\n"
        "- [x] Alpha\n"
        "- [ ] Beta\n"
        "- [ ] Beta\n"
        "row\n"
        "row\n"
    )
    assert reconcile_union_merged_markdown(text) == (
        "- [x] Alpha\n"
        "- [ ] Beta\n"
        "row\n"
    )
