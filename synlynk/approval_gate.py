"""GitHub-ticket-based approval gate for policy-flagged autonomous actions."""
from __future__ import annotations

import subprocess


def raise_approval_ticket(
    story_id: str, action: str, reason: str, assignee: str, context: str
) -> str:
    """File a GitHub issue assigned to ``assignee`` requesting approval to proceed.

    Returns the issue URL, or an empty string if ``gh issue create`` failed.
    """
    title = f"[APPROVAL] {action} — {story_id}"
    body = (
        f"Story `{story_id}` is paused pending approval.\n\n"
        f"**Action:** {action}\n"
        f"**Why it needs approval:** policy.json rule `{reason}` matched.\n\n"
        f"**Context:**\n{context}\n\n"
        "Reply `approve` on this issue, or take the equivalent action directly on "
        "GitHub, to let the sweep proceed."
    )
    result = subprocess.run(
        [
            "gh",
            "issue",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--assignee",
            assignee,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"WARNING: failed to raise approval ticket for {story_id}: {result.stderr[:500]}")
        return ""
    return result.stdout.strip()
