import pytest
from synlynk.capability_probe import IncompatibleHarnessCapabilityError, NoCapableHarnessError
from synlynk.dispatch import resolve_dispatch_harness, dispatch_agent


def test_resolve_dispatch_harness_with_task_capability_reroute():
    # Calling resolve_dispatch_harness for grok on a shell task should resolve to codex
    resolved = resolve_dispatch_harness(
        agent="grok",
        task="pytest tests/test_jobs.py",
        force_agent=False,
    )
    assert resolved == "codex"


def test_resolve_dispatch_harness_with_task_force_agent_incompatible():
    # Calling resolve_dispatch_harness for grok with force_agent on shell task raises IncompatibleHarnessCapabilityError
    with pytest.raises(IncompatibleHarnessCapabilityError):
        resolve_dispatch_harness(
            agent="grok",
            task="pytest tests/test_jobs.py",
            force_agent=True,
        )


def test_resolve_dispatch_harness_with_explicit_requires():
    # Explicit requires=["run:shell"] on grok without force_agent reroutes to codex
    resolved = resolve_dispatch_harness(
        agent="grok",
        task="inspect something",
        requires=["run:shell"],
        force_agent=False,
    )
    assert resolved == "codex"


def test_resolve_dispatch_harness_with_grants_allows_forced_harness():
    # When grok is explicitly granted run:shell, force_agent succeeds
    resolved = resolve_dispatch_harness(
        agent="grok",
        task="pytest tests/test_jobs.py",
        grants=["run:shell"],
        force_agent=True,
    )
    assert resolved == "grok"
