"""Human titles for stories. The GitHub issue title is this summary.

A story's ``title`` often stores a dispatch prompt. GitHub is the browsable
surface, so the summary is a short name of the work. Issue numbers are not
a sequence or a priority.
"""

from __future__ import annotations

import re

_SUMMARY_MAX = 80


def derive_story_summary(title: str) -> str:
    """Return a short name for a story. Never a mid-word slice of a prompt."""
    line = _first_line(title)
    if line == "Untitled story":
        return line

    task = re.match(
        r"Implement Task (\d+)\b.*?((?:docs|synlynk|scripts)/[A-Za-z0-9_./-]+\.md)",
        line,
    )
    if task:
        slug = task.group(2).rsplit("/", 1)[-1].removesuffix(".md")
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug).replace("-", " ")
        return _fit(f"Task {task.group(1)}: {slug}")

    example = re.match(
        r"Write a minimal example demonstrating (.+?)(?: for a small .+)?\.?$",
        line,
    )
    if example:
        return _fit(f"Example: {example.group(1).strip().rstrip('.')}")

    calibration = re.match(r"Review this (.+?) calibration", line, re.IGNORECASE)
    if calibration:
        return _fit(f"Review calibration: {calibration.group(1).strip()}")

    pull = re.search(r"Pull request number (\d+)", line, re.IGNORECASE)
    if pull and re.search(r"\bmerge", line, re.IGNORECASE):
        return f"Merge PR #{pull.group(1)}"
    if pull and re.match(r"Review\b", line, re.IGNORECASE):
        return f"Review PR #{pull.group(1)}"

    if len(line) <= _SUMMARY_MAX:
        return line

    sentence = re.split(r"(?<=[.!?])\s", line, maxsplit=1)[0].strip()
    if sentence and sentence != line and len(sentence) <= _SUMMARY_MAX:
        return sentence
    return _words(line, _SUMMARY_MAX)


def _first_line(title: str) -> str:
    for line in (title or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return "Untitled story"


def _fit(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= _SUMMARY_MAX:
        return text
    return _words(text, _SUMMARY_MAX)


def _words(text: str, limit: int) -> str:
    chosen: list[str] = []
    for word in text.split():
        trial = " ".join(chosen + [word])
        if len(trial) > limit:
            break
        chosen.append(word)
    return " ".join(chosen) if chosen else text.split()[0][:limit]
