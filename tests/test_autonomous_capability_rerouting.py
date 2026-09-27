import pytest
from synlynk.capability_probe import (
    CAP_SHELL,
    CAP_GH_WRITE,
    resolve_capable_dispatch_harness,
)


def test_autonomous_rerouting_from_grok_to_capable_harness_on_shell():
    # If grok is requested for a shell-requiring task without force_agent, it should reroute to codex or agy
    resolved = resolve_capable_dispatch_harness(
        candidate_harness="grok",
        task="run pytest tests/test_jobs.py and fix bug",
        fallback_chain=["codex", "agy", "claude"],
        force_agent=False,
    )
    assert resolved == "codex"


def test_autonomous_rerouting_respects_custom_fallback_chain():
    # Fallback chain order should determine the rerouted target
    resolved = resolve_capable_dispatch_harness(
        candidate_harness="grok",
        task="run pytest tests/test_jobs.py",
        required_capabilities={CAP_SHELL},
        fallback_chain=["agy", "claude", "codex"],
        force_agent=False,
    )
    assert resolved == "agy"


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
