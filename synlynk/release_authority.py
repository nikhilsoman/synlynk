"""Read-only release metadata authority checks (#1914)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence


_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
_CHANGELOG_HEADER_RE = re.compile(r"^##\s+\[v?([^\]]+)\]", re.MULTILINE)
_README_BADGE_RE = re.compile(r"badge/version-([^-/]+)", re.IGNORECASE)
_README_HERO_RE = re.compile(r"\*\*v([^:]+):\*\*", re.IGNORECASE)


@dataclass(frozen=True)
class VersionAuthorityFinding:
    source: str
    message: str


def _normalise(version: str) -> str:
    return version.strip().lstrip("v")


def _findings_for_changelog(path: Path, expected: str) -> list[VersionAuthorityFinding]:
    if not path.is_file():
        return [VersionAuthorityFinding("changelog", "CHANGELOG.md is missing")]
    text = path.read_text(encoding="utf-8")
    headers = list(_CHANGELOG_HEADER_RE.finditer(text))
    if not headers:
        return [VersionAuthorityFinding("changelog", "CHANGELOG.md has no release header")]
    current = next(
        (header for header in headers if _VERSION_RE.fullmatch(_normalise(header.group(1)))),
        None,
    )
    if current is None:
        return [VersionAuthorityFinding("changelog", "CHANGELOG.md has no semantic-version release header")]
    observed = _normalise(current.group(1))
    if observed != expected:
        return [VersionAuthorityFinding(
            "changelog",
            f"current CHANGELOG release is v{observed}, expected v{expected}",
        )]
    current_index = headers.index(current)
    end = headers[current_index + 1].start() if current_index + 1 < len(headers) else len(text)
    body = text[current.end():end]
    if not re.search(r"^-\s+\S", body, re.MULTILINE):
        return [VersionAuthorityFinding(
            "changelog", f"CHANGELOG entry for v{expected} has no release content",
        )]
    return []


def validate_release_authority(
    root: str, expected_version: Optional[str] = None
) -> tuple[Optional[str], list[VersionAuthorityFinding]]:
    """Validate release-facing metadata against root ``VERSION`` without writing.

    ``expected_version`` is used by release checks to prevent callers from
    validating a different proposed version against the current repository.
    """
    repo = Path(root).resolve()
    findings: list[VersionAuthorityFinding] = []
    version_path = repo / "VERSION"
    if not version_path.is_file():
        return None, [VersionAuthorityFinding(
            "VERSION", "VERSION is missing; release operations require the repository authority",
        )]
    version = _normalise(version_path.read_text(encoding="utf-8"))
    if not _VERSION_RE.fullmatch(version):
        findings.append(VersionAuthorityFinding(
            "VERSION", f"VERSION contains invalid semantic version {version!r}",
        ))
    requested = _normalise(expected_version) if expected_version else version
    if expected_version and requested != version:
        findings.append(VersionAuthorityFinding(
            "VERSION", f"VERSION is {version}, expected {requested}",
        ))

    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file():
        findings.append(VersionAuthorityFinding("package", "pyproject.toml is missing"))
    else:
        config = pyproject.read_text(encoding="utf-8")
        if not re.search(r'^\s*dynamic\s*=\s*\["version"\]\s*$', config, re.MULTILINE):
            findings.append(VersionAuthorityFinding(
                "package", "package metadata is not declared as a dynamic VERSION projection",
            ))
        if not re.search(
            r'^\s*version\s*=\s*\{\s*file\s*=\s*\["VERSION"\]\s*\}\s*$',
            config,
            re.MULTILINE,
        ):
            findings.append(VersionAuthorityFinding(
                "package", "package metadata does not read the root VERSION file",
            ))

    readme = repo / "README.md"
    if not readme.is_file():
        findings.append(VersionAuthorityFinding("README", "README.md is missing"))
    else:
        text = readme.read_text(encoding="utf-8")
        badges = _README_BADGE_RE.findall(text)
        heroes = _README_HERO_RE.findall(text)
        if not badges:
            findings.append(VersionAuthorityFinding("README", "README has no version badge"))
        elif _normalise(badges[0]) != requested:
            findings.append(VersionAuthorityFinding(
                "README", f"README badge is v{_normalise(badges[0])}, expected v{requested}",
            ))
        if not heroes:
            findings.append(VersionAuthorityFinding("README", "README has no release hero"))
        elif _normalise(heroes[0]) != requested:
            findings.append(VersionAuthorityFinding(
                "README", f"README hero is v{_normalise(heroes[0])}, expected v{requested}",
            ))

    findings.extend(_findings_for_changelog(repo / "CHANGELOG.md", requested))
    return version, findings


def format_version_authority_report(
    version: Optional[str], findings: Sequence[VersionAuthorityFinding]
) -> str:
    """Render a stable, concise read-only diagnostic."""
    if not findings:
        return f"Version authority: VERSION v{version} is synchronized"
    lines = [f"Version authority: VERSION v{version or 'missing'} is not synchronized"]
    lines.extend(f"- {finding.source}: {finding.message}" for finding in findings)
    return "\n".join(lines)
