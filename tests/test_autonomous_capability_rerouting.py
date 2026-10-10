import pytest
from synlynk.capability_probe import (
    CAP_SHELL,
    CAP_GH_WRITE,
    resolve_capable_dispatch_harness,
)


def test_autonomous_routing_keeps_grok_for_shell_task():
    resolved = resolve_capable_dispatch_harness(
        candidate_harness="grok",
        task="run pytest tests/test_jobs.py and fix bug",
        fallback_chain=["codex", "agy", "claude"],
        force_agent=False,
    )
    assert resolved == "grok"


def test_autonomous_routing_keeps_grok_with_custom_fallback_chain():
    resolved = resolve_capable_dispatch_harness(
        candidate_harness="grok",
        task="run pytest tests/test_jobs.py",
        required_capabilities={CAP_SHELL},
        fallback_chain=["agy", "claude", "codex"],
        force_agent=False,
    )
    assert resolved == "grok"


def test_no_reroute_needed_when_candidate_is_capable():
    resolved = resolve_capable_dispatch_harness(
        candidate_harness="codex",
        task="run pytest tests/test_jobs.py",
        required_capabilities={CAP_SHELL},
        fallback_chain=["agy", "claude"],
        force_agent=False,
    )
    assert resolved == "codex"


def test_autonomous_rerouting_gh_write():
    # Reroute from local to codex for gh_write task
    resolved = resolve_capable_dispatch_harness(
        candidate_harness="local",
        task="gh pr merge 1809",
        requires_gh_write=True,
        fallback_chain=["local", "codex", "claude"],
        force_agent=False,
    )
    assert resolved == "codex"


def test_review_routing_never_falls_back_to_local_permission_crash():
    """Review permissions require enforcement that the local adapter lacks."""
    resolved = resolve_capable_dispatch_harness(
        candidate_harness="local",
        task="review PR #2123",
        task_type="review",
        fallback_chain=["local", "codex", "agy", "claude"],
        force_agent=False,
    )
    assert resolved == "codex"

    from synlynk.dispatch import _permissions_to_flags

    assert _permissions_to_flags(resolved, ["read:*"], read_only=True) == [
        "-s",
        "read-only",
    ]
