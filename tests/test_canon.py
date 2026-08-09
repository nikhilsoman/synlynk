import os

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
