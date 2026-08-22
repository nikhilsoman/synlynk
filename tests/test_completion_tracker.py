from synlynk.completion_tracker import parse_spec_reference


def test_parse_spec_reference_finds_spec_path():
    body = "Implements docs/superpowers/specs/2026-08-20-example-design.md as approved"
    assert parse_spec_reference(body) == "docs/superpowers/specs/2026-08-20-example-design.md"


def test_parse_spec_reference_finds_plan_path():
    body = "Task 2 of docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md"
    assert parse_spec_reference(body) == "docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md"


def test_parse_spec_reference_finds_closes_issue():
    body = "Fixes the flake described in the ticket\n\nCloses #1087"
    assert parse_spec_reference(body) == "#1087"


def test_parse_spec_reference_finds_gh_hash_reference():
    body = "See gh:#616 for background on the base-branch bug"
    assert parse_spec_reference(body) == "#616"


def test_parse_spec_reference_prefers_spec_path_over_issue_ref():
    body = "Implements docs/superpowers/specs/2026-08-01-thing-design.md, closes #42"
    assert parse_spec_reference(body) == "docs/superpowers/specs/2026-08-01-thing-design.md"


def test_parse_spec_reference_returns_none_when_no_match():
    assert parse_spec_reference("Just a small typo fix, no ticket") is None


def test_parse_spec_reference_returns_none_for_empty_body():
    assert parse_spec_reference("") is None
    assert parse_spec_reference(None) is None
