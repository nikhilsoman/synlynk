"""Post-merge semantic completion checking: does a merged PR fulfill the
spec/plan/issue it references? Non-blocking -- feeds the spec_verified
GOVERNS event, never gates a merge. See
docs/superpowers/specs/2026-08-22-qa-completion-tracker-design.md.
"""

import json
import re
import subprocess


_SPEC_PATH_RE = re.compile(r"docs/superpowers/(?:specs|plans)/[\w\-/.]+\.md")
_CLOSES_ISSUE_RE = re.compile(r"(?:closes|fixes|resolves)\s+#(\d+)", re.IGNORECASE)
_GH_HASH_RE = re.compile(r"gh:#(\d+)")

_VALID_VERDICTS = ("fulfilled", "partial", "diverged")


def parse_spec_reference(pr_body):
    """Extract a spec/plan path or issue reference from a PR body.

    Returns a spec/plan path as-is, an issue reference as ``#N``, or ``None``.
    Spec/plan paths take priority over issue references when both appear.
    """
    if not pr_body:
        return None

    match = _SPEC_PATH_RE.search(pr_body)
    if match:
        return match.group(0)

    match = _CLOSES_ISSUE_RE.search(pr_body)
    if match:
        return f"#{match.group(1)}"

    match = _GH_HASH_RE.search(pr_body)
    if match:
        return f"#{match.group(1)}"

    return None
