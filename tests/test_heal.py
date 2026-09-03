from synlynk.heal import _diagnostics, _auto_merge


def test_diagnostics_normalizes_scan_findings():
    assert _diagnostics({"findings": ["missing test"]}) == [
        {"title": "missing test", "body": "missing test", "source_type": "scan"}
    ]


def test_auto_merge_is_fail_closed_when_qa_is_red():
    assert _auto_merge([{"story_id": "story-1", "pr_number": 12}], [{"passed": False}]) == []
