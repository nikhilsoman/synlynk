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
