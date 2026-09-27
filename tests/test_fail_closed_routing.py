import pytest
from synlynk.capability_probe import (
    CAP_SHELL,
    CAP_GH_WRITE,
    IncompatibleHarnessCapabilityError,
    NoCapableHarnessError,
    resolve_capable_dispatch_harness,
)


def test_force_agent_incompatible_raises_error():
    # Grok has no shell capability. Forcing Grok on a task that requires shell must raise IncompatibleHarnessCapabilityError.
    with pytest.raises(IncompatibleHarnessCapabilityError) as excinfo:
        resolve_capable_dispatch_harness(
            candidate_harness="grok",
            task="run pytest tests/test_jobs.py",
            required_capabilities={CAP_SHELL},
            force_agent=True,
        )
    assert "forced harness 'grok' lacks required capabilities" in str(excinfo.value)
    assert "run:shell" in str(excinfo.value)


def test_force_agent_gh_write_incompatible_raises_error():
    # Grok cannot do gh write. Forcing Grok on a gh write task must raise IncompatibleHarnessCapabilityError.
    with pytest.raises(IncompatibleHarnessCapabilityError) as excinfo:
        resolve_capable_dispatch_harness(
            candidate_harness="grok",
            task="gh pr merge 1809 --squash",
            requires_gh_write=True,
            force_agent=True,
        )
    assert "forced harness 'grok' lacks required capabilities" in str(excinfo.value)


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
