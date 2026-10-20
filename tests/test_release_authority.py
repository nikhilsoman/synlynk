"""Regression coverage for #1914 version-authority checks."""

from __future__ import annotations

from pathlib import Path

from synlynk.release_authority import validate_release_authority


def _repo(root: Path, version: str = "0.25.1") -> None:
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\ndynamic = ["version"]\n\n[tool.setuptools.dynamic]\n'
        'version = { file = ["VERSION"] }\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        f"badge/version-{version}-blue\n\n**v{version}:** a sufficiently detailed release summary\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [v{version}] - 2026-10-20\n- A real release item\n",
        encoding="utf-8",
    )


def test_release_authority_accepts_synchronized_repository(tmp_path):
    _repo(tmp_path)

    version, findings = validate_release_authority(str(tmp_path))

    assert version == "0.25.1"
    assert findings == []


def test_release_authority_rejects_missing_version_file(tmp_path):
    _repo(tmp_path)
    (tmp_path / "VERSION").unlink()

    version, findings = validate_release_authority(str(tmp_path))

    assert version is None
    assert [(finding.source, finding.message) for finding in findings] == [
        ("VERSION", "VERSION is missing; release operations require the repository authority")
    ]


def test_release_authority_reports_projection_mismatches(tmp_path):
    _repo(tmp_path)
    (tmp_path / "README.md").write_text(
        "badge/version-0.25.0-blue\n\n**v0.25.0:** old release summary\n",
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [v0.25.0] - 2026-10-02\n- Old release item\n",
        encoding="utf-8",
    )

    _, findings = validate_release_authority(str(tmp_path))

    assert {finding.source for finding in findings} == {"README", "changelog"}
    assert any("badge is v0.25.0" in finding.message for finding in findings)
    assert any("current CHANGELOG release is v0.25.0" in finding.message for finding in findings)


def test_release_authority_requires_nonempty_current_changelog_entry(tmp_path):
    _repo(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [v0.25.1] - 2026-10-20\n\n## [v0.25.0] - 2026-10-02\n- Old item\n",
        encoding="utf-8",
    )

    _, findings = validate_release_authority(str(tmp_path))

    assert [(finding.source, finding.message) for finding in findings] == [
        ("changelog", "CHANGELOG entry for v0.25.1 has no release content")
    ]


def test_release_authority_ignores_unreleased_changelog_heading(tmp_path):
    _repo(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n- Work in progress\n\n"
        "## [v0.25.1] - 2026-10-20\n- A real release item\n",
        encoding="utf-8",
    )

    _, findings = validate_release_authority(str(tmp_path))

    assert findings == []
