import json
import pytest


def test_policy_json_has_eligibility_block():
    with open(".synlynk/policy.json") as f:
        policy = json.load(f)
    eligibility = policy["capability_policy"]["eligibility"]
    # Every harness already in HARNESS_CAPABILITY_BASELINES must have an entry.
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES
    for harness in HARNESS_CAPABILITY_BASELINES:
        assert harness in eligibility, f"missing eligibility entry for {harness}"
        assert "can_gh_write" in eligibility[harness]
        assert eligibility[harness]["can_gh_write"] == HARNESS_CAPABILITY_BASELINES[harness]["can_gh_write"]


def test_policy_json_task_allocation_untouched():
    """The Phase 2 decision requires task_allocation stays the binding authority — this
    task is additive only and must not remove or restructure it."""
    with open(".synlynk/policy.json") as f:
        policy = json.load(f)
    task_allocation = policy["overrides"]["dev_authority"]["task_allocation"]
    assert "implement" in task_allocation
    assert task_allocation["implement"]["harness"] == "codex"
