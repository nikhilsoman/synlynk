import os
from unittest.mock import patch

from synlynk.canon import _build_documentation_index


def test_documentation_index_lists_files_from_both_dirs(tmp_path):
    os.makedirs(tmp_path / "project-docs")
    (tmp_path / "project-docs" / "roadmap.md").write_text("# roadmap")
    os.makedirs(tmp_path / "docs" / "superpowers" / "specs")
    (tmp_path / "docs" / "superpowers" / "specs" / "x-design.md").write_text("# x")

    result = _build_documentation_index(str(tmp_path))

    assert "project-docs/roadmap.md" in result
    assert os.path.join("docs", "superpowers", "specs", "x-design.md") in result


def test_documentation_index_handles_missing_dirs(tmp_path):
    result = _build_documentation_index(str(tmp_path))
    assert "No project-docs/ or docs/ markdown files found" in result


def test_documentation_index_ignores_non_markdown_files(tmp_path):
    os.makedirs(tmp_path / "docs")
    (tmp_path / "docs" / "notes.txt").write_text("not markdown")
    result = _build_documentation_index(str(tmp_path))
    assert "notes.txt" not in result


from synlynk.canon import _build_claim_receipt


def test_claim_receipt_full_scan_yields_three_claims():
    scan = {
        "repos": [{"path": "/tmp/x", "stack_labels": ["python"]}],
        "harnesses": [{"name": "claude"}],
    }
    claims = _build_claim_receipt(scan)
    assert len(claims) == 3
    assert all(c["confidence"] == "found" for c in claims)
    assert "python" in claims[0]["claim"]
    assert "/tmp/x" in claims[1]["claim"]
    assert "claude" in claims[2]["claim"]


def test_claim_receipt_skips_missing_fields():
    scan = {"repos": [], "harnesses": []}
    claims = _build_claim_receipt(scan)
    assert claims == []


def test_claim_receipt_partial_scan_yields_partial_claims():
    scan = {"repos": [{"path": "/tmp/x", "stack_labels": []}], "harnesses": []}
    claims = _build_claim_receipt(scan)
    assert len(claims) == 1
    assert "/tmp/x" in claims[0]["claim"]


from synlynk.canon import _render_canon, _write_canon, _CANON_FILENAME


def test_render_canon_includes_provenance_and_both_real_sections(tmp_path):
    scan = {"repos": [{"path": str(tmp_path), "stack_labels": ["python"]}], "harnesses": []}
    content = _render_canon(str(tmp_path), scan, head_sha="a" * 40)
    assert f"canon:section=baseline sha={'a' * 40}" in content
    assert "## Documentation Index" in content
    assert "## 3-Claim Receipt" in content
    assert "Detected stack: python" in content


def test_render_canon_includes_skeleton_sections_without_provenance(tmp_path):
    scan = {"repos": [], "harnesses": []}
    content = _render_canon(str(tmp_path), scan, head_sha="a" * 40)
    assert "## Current State (active code only)" in content
    assert "Not yet assessed" in content
    # Only one provenance comment total — skeleton sections carry none.
    assert content.count("<!-- canon:section=") == 1


def test_render_canon_defaults_to_unknown_sha_when_none(tmp_path):
    content = _render_canon(str(tmp_path), {"repos": [], "harnesses": []}, head_sha=None)
    assert "sha=unknown" in content


def test_write_canon_writes_file(tmp_path):
    path = _write_canon(str(tmp_path), "hello")
    assert os.path.exists(path)
    assert os.path.basename(path) == _CANON_FILENAME
    assert open(path).read() == "hello"


import subprocess

from synlynk.canon import _parse_canon_provenance, _check_canon_staleness


def _git_init_simple(root):
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True, check=True)
    (root / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=root, capture_output=True, check=True)


def _current_sha(root):
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def test_parse_canon_provenance_round_trips(tmp_path):
    content = _render_canon(str(tmp_path), {"repos": [], "harnesses": []}, head_sha="b" * 40)
    _write_canon(str(tmp_path), content)
    provenance = _parse_canon_provenance(str(tmp_path))
    assert provenance["sha"] == "b" * 40


def test_parse_canon_provenance_missing_file_returns_none(tmp_path):
    assert _parse_canon_provenance(str(tmp_path)) is None


def test_parse_canon_provenance_malformed_comment_returns_none(tmp_path):
    (tmp_path / _CANON_FILENAME).write_text("# Workspace Canon\nno provenance comment here\n")
    assert _parse_canon_provenance(str(tmp_path)) is None


def test_check_canon_staleness_same_sha_not_stale(tmp_path):
    _git_init_simple(tmp_path)
    sha = _current_sha(tmp_path)
    content = _render_canon(str(tmp_path), {"repos": [], "harnesses": []}, head_sha=sha)
    _write_canon(str(tmp_path), content)
    assert _check_canon_staleness(str(tmp_path)) == []


def test_check_canon_staleness_different_sha_is_stale(tmp_path):
    _git_init_simple(tmp_path)
    old_sha = _current_sha(tmp_path)
    content = _render_canon(str(tmp_path), {"repos": [], "harnesses": []}, head_sha=old_sha)
    _write_canon(str(tmp_path), content)
    (tmp_path / "new.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=tmp_path, capture_output=True, check=True)
    assert _check_canon_staleness(str(tmp_path)) == ["baseline"]


def test_check_canon_staleness_unknown_sha_never_stale(tmp_path):
    _git_init_simple(tmp_path)
    content = _render_canon(str(tmp_path), {"repos": [], "harnesses": []}, head_sha=None)
    _write_canon(str(tmp_path), content)
    assert _check_canon_staleness(str(tmp_path)) == []


def test_check_canon_staleness_missing_canon_is_stale(tmp_path):
    assert _check_canon_staleness(str(tmp_path)) == ["baseline"]


from synlynk.canon import _offer_deep_scan_consent, run_canon_baseline


def test_offer_deep_scan_consent_yes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    assert _offer_deep_scan_consent() is True


def test_offer_deep_scan_consent_no(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    assert _offer_deep_scan_consent() is False


def test_run_canon_baseline_first_run_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    scan = {"repos": [{"path": str(tmp_path), "stack_labels": []}], "harnesses": []}
    with patch("synlynk.scan.cmd_scan") as mock_deep_scan:
        run_canon_baseline(str(tmp_path), scan)
        mock_deep_scan.assert_not_called()
    assert os.path.exists(tmp_path / _CANON_FILENAME)


def test_run_canon_baseline_first_run_accepts_deep_scan_consent(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    scan = {"repos": [], "harnesses": []}
    with patch("synlynk.scan.cmd_scan") as mock_deep_scan:
        run_canon_baseline(str(tmp_path), scan)
        mock_deep_scan.assert_called_once_with(deep=True)


def test_run_canon_baseline_rerun_skips_consent_prompt(tmp_path, monkeypatch):
    def _fail_input(prompt):
        raise AssertionError("should not prompt on rerun")
    scan = {"repos": [], "harnesses": []}
    _write_canon(str(tmp_path), _render_canon(str(tmp_path), scan, head_sha=None))
    monkeypatch.setattr("builtins.input", _fail_input)
    run_canon_baseline(str(tmp_path), scan)  # must not raise


def test_run_canon_baseline_rerun_prints_staleness_banner(tmp_path, monkeypatch, capsys):
    _git_init_simple(tmp_path)
    old_sha = _current_sha(tmp_path)
    scan = {"repos": [], "harnesses": []}
    _write_canon(str(tmp_path), _render_canon(str(tmp_path), scan, head_sha=old_sha))
    (tmp_path / "new.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=tmp_path, capture_output=True, check=True)

    def _fail_input(prompt):
        raise AssertionError("should not prompt on rerun")
    monkeypatch.setattr("builtins.input", _fail_input)

    run_canon_baseline(str(tmp_path), scan)

    captured = capsys.readouterr()
    assert "may be stale" in captured.out.lower()
