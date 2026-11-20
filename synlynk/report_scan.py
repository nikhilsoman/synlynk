"""Secret-pattern scan applied to the entire rendered report body."""
from __future__ import annotations

import re

from synlynk.logs import _SECRET_PATTERNS

_EXTRA_PATTERNS = [
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def find_secrets(text: str) -> list[str]:
    """Return matched substrings; an empty list means the text is clean."""
    hits: list[str] = []
    seen: set[tuple[int, int, str]] = set()
    for pattern in [*_SECRET_PATTERNS, *_EXTRA_PATTERNS]:
        for match in pattern.finditer(text):
            occurrence = (match.start(), match.end(), match.group(0))
            if occurrence not in seen:
                seen.add(occurrence)
                hits.append(match.group(0))
    return hits
