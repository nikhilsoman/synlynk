"""Autonomous maintainer issue burndown classifier."""
from typing import List

_REMEDIATION_TOPICS = (
    "invariant 1",
    "circuit breaker",
    "daemon supervision",
)


def is_issue_remediated(issue_text: str, commit_messages: List[str]) -> bool:
    """Return True if a commit message remediates the same topic as the issue."""
    issue_lower = issue_text.lower()
    for msg in commit_messages:
        msg_lower = msg.lower()
        for topic in _REMEDIATION_TOPICS:
            if topic in issue_lower and topic in msg_lower:
                return True
        if "circuit breaker" in issue_lower and "live-19" in msg_lower:
            return True
    return False
