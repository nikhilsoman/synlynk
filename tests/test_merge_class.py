from synlynk.merge_class import is_docs_only_change


def test_is_docs_only_change_true_for_docs_dir_files():
    assert is_docs_only_change(["docs/superpowers/specs/2026-08-22-example.md", "docs/blog/01-post.md"]) is True


def test_is_docs_only_change_true_for_root_markdown():
    assert is_docs_only_change(["README.md", "CLAUDE.md", "CHANGELOG.md"]) is True


def test_is_docs_only_change_true_for_project_docs():
    assert is_docs_only_change(["project-docs/roadmap.md", "project-docs/todo.md"]) is True


def test_is_docs_only_change_false_for_project_docs_config():
    assert is_docs_only_change(["project-docs/.synlynk_config.json"]) is False


def test_is_docs_only_change_false_when_any_code_file_present():
    assert is_docs_only_change(["docs/blog/01-post.md", "synlynk/db.py"]) is False


def test_is_docs_only_change_false_for_ci_config():
    assert is_docs_only_change([".github/workflows/test.yml"]) is False


def test_is_docs_only_change_false_for_synlynk_config():
    assert is_docs_only_change(["synlynk/config.json"]) is False


def test_is_docs_only_change_false_for_empty_change_list():
    assert is_docs_only_change([]) is False


def test_is_docs_only_change_true_for_nested_markdown_outside_docs_dir():
    assert is_docs_only_change(["tests/README.md"]) is True
