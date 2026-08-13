"""Release-tag signal detection for cold-start canon sections.

Pure detection primitives — no canon writes, no CLI wiring. Consumed by
Phase 3's Retrospective Roadmap and Current State (active code) sections.
See docs/superpowers/specs/2026-08-09-cold-start-design.md.
"""
import json
import re
import subprocess

_TAG_FORMAT = "%(refname:short)\t%(creatordate:iso-strict)\t%(objectname)"


def _git_tags_with_dates(root: str = ".") -> list:
    """Returns [{"tag": str, "date": str (ISO 8601), "sha": str}, ...] sorted
    oldest-to-newest by creation date. Works for both annotated and
    lightweight tags. Returns [] if not a git repo or no tags exist."""
    try:
        result = subprocess.run(
            ["git", "for-each-ref", "--sort=creatordate",
             f"--format={_TAG_FORMAT}", "refs/tags"],
            cwd=root, capture_output=True, text=True,
        )
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        return []

    tags = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        tag, date, sha = parts
        tags.append({"tag": tag, "date": date, "sha": sha})
    return tags


_SEMVER_RE = re.compile(r"^v?\d+\.\d+\.\d+")
_CALVER_RE = re.compile(r"^v?(19|20)\d{2}[.\-]\d{1,2}([.\-]\d{1,2})?$")
_MONOREPO_RE = re.compile(r"^[\w\-./]+@v?\d+\.\d+\.\d+")


def _classify_single_tag(tag: str) -> str:
    if _MONOREPO_RE.match(tag):
        return "monorepo"
    if _CALVER_RE.match(tag):
        return "calver"
    if _SEMVER_RE.match(tag):
        return "semver"
    return "other"


def _detect_tag_pattern(tags: list) -> str:
    """Returns "semver" | "calver" | "monorepo" | "none" | "mixed".

    "none" means no tags exist. "mixed" means tags exist but don't share a
    single recognizable pattern — still meaningful signal (an inconsistently
    tagged repo), never silently dropped."""
    if not tags:
        return "none"

    classifications = {_classify_single_tag(t["tag"]) for t in tags}
    if classifications == {"semver"}:
        return "semver"
    if classifications == {"calver"}:
        return "calver"
    if classifications == {"monorepo"}:
        return "monorepo"
    return "mixed"


def _latest_tag(root: str = ".") -> dict:
    """Returns the most recently created tag dict, or None if no tags exist."""
    tags = _git_tags_with_dates(root)
    return tags[-1] if tags else None


def _commits_since(root: str, ref: str) -> int:
    """Returns the count of non-merge-excluding commits on HEAD since `ref`."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{ref}..HEAD"],
            cwd=root, capture_output=True, text=True,
        )
    except FileNotFoundError:
        return 0
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip() or "0")
    except ValueError:
        return 0


