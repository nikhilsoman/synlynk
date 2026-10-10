import pytest
from synlynk.capability_probe import (
    CAP_SHELL,
    NoCapableHarnessError,
    resolve_capable_dispatch_harness,
)


def test_force_agent_shell_capability_is_satisfied_by_grok():
    assert resolve_capable_dispatch_harness(
        candidate_harness="grok",
        task="run pytest tests/test_jobs.py",
        required_capabilities={CAP_SHELL},
        force_agent=True,
    ) == "grok"


def test_force_agent_gh_write_now_satisfied_by_grok():
    assert resolve_capable_dispatch_harness(
        candidate_harness="grok",
        task="gh pr merge 1809 --squash",
        requires_gh_write=True,
        force_agent=True,
    ) == "grok"


def test_no_capable_harness_in_fleet_raises_error():
    # When a requirement cannot be met by ANY harness in the fallback chain, raise NoCapableHarnessError
    with pytest.raises(NoCapableHarnessError) as excinfo:
        resolve_capable_dispatch_harness(
            candidate_harness="grok",
            task="do quantum computation",
            required_capabilities={"quantum:supercomputer"},
            force_agent=False,
            fallback_chain=["codex", "agy", "claude", "grok", "local"],
        )
    assert "no harness in fleet satisfies required capabilities" in str(excinfo.value)
