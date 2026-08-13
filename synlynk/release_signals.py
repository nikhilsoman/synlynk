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
