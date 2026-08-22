import json
from unittest.mock import MagicMock, patch

from synlynk.completion_tracker import compute_completion_verdict, parse_spec_reference


def test_parse_spec_reference_finds_spec_path():
    body = "Implements docs/superpowers/specs/2026-08-20-example-design.md as approved"
    assert parse_spec_reference(body) == "docs/superpowers/specs/2026-08-20-example-design.md"


def test_parse_spec_reference_finds_plan_path():
    body = "Task 2 of docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md"
    assert parse_spec_reference(body) == "docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md"


def test_parse_spec_reference_finds_path_with_internal_dot():
    body = "See docs/superpowers/specs/2026-08-22-v1.5-example-design.md"
    assert parse_spec_reference(body) == "docs/superpowers/specs/2026-08-22-v1.5-example-design.md"


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


def test_compute_completion_verdict_reads_local_spec_file(tmp_path, monkeypatch):
    spec_dir = tmp_path / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    spec_file = spec_dir / "2026-08-20-example-design.md"
    spec_file.write_text("# Example Design\n\nDo the thing\n")
    monkeypatch.chdir(tmp_path)
    diff_result = MagicMock(returncode=0, stdout="diff --git a/x b/x\n+the thing")
    claude_result = MagicMock(
        returncode=0,
        stdout=json.dumps({"verdict": "fulfilled", "rationale": "Does the thing as specced\n"}),
    )
    with patch("subprocess.run", side_effect=[diff_result, claude_result]) as mock_run:
        verdict = compute_completion_verdict(42, "docs/superpowers/specs/2026-08-20-example-design.md")
    assert verdict == {"verdict": "fulfilled", "rationale": "Does the thing as specced\n"}
    assert mock_run.call_args_list[0].args[0] == ["gh", "pr", "diff", "42"]
    assert mock_run.call_args_list[1].args[0][0] == "claude"


def test_compute_completion_verdict_reads_issue_body_for_hash_reference():
    issue_result = MagicMock(returncode=0, stdout=json.dumps({"body": "Fix the flake\n"}))
    diff_result = MagicMock(returncode=0, stdout="diff --git a/x b/x\n+fix")
    claude_result = MagicMock(
        returncode=0,
        stdout=json.dumps({"verdict": "fulfilled", "rationale": "Fixes the flake\n"}),
    )
    with patch("subprocess.run", side_effect=[issue_result, diff_result, claude_result]) as mock_run:
        verdict = compute_completion_verdict(99, "#1087")
    assert verdict == {"verdict": "fulfilled", "rationale": "Fixes the flake\n"}
    assert mock_run.call_args_list[0].args[0] == ["gh", "issue", "view", "1087", "--json", "body"]


def test_compute_completion_verdict_returns_none_when_reference_unreadable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    verdict = compute_completion_verdict(42, "docs/superpowers/specs/does-not-exist.md")
    assert verdict is None


def test_compute_completion_verdict_returns_none_when_diff_fails(tmp_path, monkeypatch):
    spec_dir = tmp_path / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "x.md").write_text("spec")
    monkeypatch.chdir(tmp_path)
    diff_result = MagicMock(returncode=1, stdout="")
    with patch("subprocess.run", return_value=diff_result):
        verdict = compute_completion_verdict(42, "docs/superpowers/specs/x.md")
    assert verdict is None


def test_compute_completion_verdict_returns_none_on_unparseable_claude_output(tmp_path, monkeypatch):
    spec_dir = tmp_path / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "x.md").write_text("spec")
    monkeypatch.chdir(tmp_path)
    diff_result = MagicMock(returncode=0, stdout="diff")
    claude_result = MagicMock(returncode=0, stdout="not json")
    with patch("subprocess.run", side_effect=[diff_result, claude_result]):
        verdict = compute_completion_verdict(42, "docs/superpowers/specs/x.md")
    assert verdict is None


def test_compute_completion_verdict_returns_none_for_invalid_verdict_value(tmp_path, monkeypatch):
    spec_dir = tmp_path / "docs" / "superpowers" / "specs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "x.md").write_text("spec")
    monkeypatch.chdir(tmp_path)
    diff_result = MagicMock(returncode=0, stdout="diff")
    claude_result = MagicMock(returncode=0, stdout=json.dumps({"verdict": "maybe", "rationale": ""}))
    with patch("subprocess.run", side_effect=[diff_result, claude_result]):
        verdict = compute_completion_verdict(42, "docs/superpowers/specs/x.md")
    assert verdict is None
