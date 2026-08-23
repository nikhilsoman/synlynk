import os
import sys
import subprocess
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from synlynk import cmd_release


def test_cmd_release_refuses_when_role_not_authorized(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "VERSION").write_text("0.14.0")
    with pytest.raises(RuntimeError, match="not authorized"):
        cmd_release(dry_run=True, role="dev")

def test_cmd_release_dry_run_no_writes(tmp_path, monkeypatch):
    # Setup files
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.10.0\n")
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("# Changelog\n\n## [0.9.0] - 2026-06-01\n")
    blog_dir = tmp_path / "docs" / "blog"
    blog_dir.mkdir(parents=True)
    readme_file = blog_dir / "README.md"
    readme_file.write_text("## Per-PR Post Template\n```markdown\n---\ntitle: \"PR #N — <theme>\"\ndate: YYYY-MM-DD\nmerged: YYYY-MM-DD (or status: open)\n---\n```\n")

    monkeypatch.chdir(tmp_path)

    # Mock git calls
    def mock_check_output(cmd, **kwargs):
        return b""
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    # Run release command in dry-run mode
    cmd_release(dry_run=True, role="pm")

    # Ensure no files were changed
    assert version_file.read_text().strip() == "0.10.0"
    assert "0.10.1" not in changelog_file.read_text()
    assert len(list(blog_dir.glob("*.md"))) == 1 # only README.md

def test_cmd_release_bumps_version(tmp_path, monkeypatch):
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.10.0\n")

    monkeypatch.chdir(tmp_path)

    # Mock git calls
    def mock_check_output(cmd, **kwargs):
        return b""
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    # Run release command
    cmd_release(dry_run=False, role="pm")

    # Ensure version file was bumped
    assert version_file.read_text().strip() == "0.10.1"

def test_cmd_release_writes_changelog(tmp_path, monkeypatch):
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.10.0\n")
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("# Changelog\n\n## [0.9.0] - 2026-06-01\n")

    monkeypatch.chdir(tmp_path)

    # Mock git calls to simulate some commits
    def mock_check_output(cmd, **kwargs):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
        if "describe" in cmd_str:
            return b"v0.9.0\n"
        elif "log" in cmd_str:
            return b"123456 feat: add release command\n789012 fix: resolve bug\n"
        return b""
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    # Run release command
    cmd_release(dry_run=False, role="pm")

    changelog_content = changelog_file.read_text()
    assert "## [v0.10.1]" in changelog_content
    assert "### Added" in changelog_content
    assert "- feat: add release command" in changelog_content
    assert "### Fixed" in changelog_content
    assert "- fix: resolve bug" in changelog_content

def test_cmd_release_writes_blog_stub(tmp_path, monkeypatch):
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.10.0\n")
    blog_dir = tmp_path / "docs" / "blog"
    blog_dir.mkdir(parents=True)
    # Add a mock blog post to ensure NN sequence works
    (blog_dir / "05-pr12-v0.9.0.md").write_text("stub")

    monkeypatch.chdir(tmp_path)

    # Mock git calls
    def mock_check_output(cmd, **kwargs):
        return b""
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    # Run release command
    cmd_release(dry_run=False, role="pm")

    # Expected next blog is 06-prTBD-v0.10.1.md
    expected_blog = blog_dir / "06-prTBD-v0.10.1.md"
    assert expected_blog.exists()
    assert "PR #TBD" in expected_blog.read_text()

def test_cmd_release_checklist_printed(tmp_path, monkeypatch, capsys):
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.10.0\n")
    blog_dir = tmp_path / "docs" / "blog"
    blog_dir.mkdir(parents=True)

    monkeypatch.chdir(tmp_path)

    # Mock git calls
    def mock_check_output(cmd, **kwargs):
        return b""
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    # Run release command
    cmd_release(dry_run=False, role="pm")

    captured = capsys.readouterr()
    assert "synlynk release checklist for v0.10.1" in captured.out
    assert "[x] VERSION bumped" in captured.out
    assert "[x] CHANGELOG entry written" in captured.out
    assert "Blog post stub: docs/blog/00-prTBD-v0.10.1.md" in captured.out
    assert "[ ] git tag v0.10.1 && git push --tags" in captured.out

def test_cmd_release_minor_flag(tmp_path, monkeypatch):
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.10.0\n")

    monkeypatch.chdir(tmp_path)

    # Mock git calls
    def mock_check_output(cmd, **kwargs):
        return b""
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    # Run release command with minor=True
    cmd_release(dry_run=False, minor=True, role="pm")

    # Ensure version bumped to 0.11.0
    assert version_file.read_text().strip() == "0.11.0"
