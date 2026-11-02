"""Tests for autonomous workspace agent role charters, wake-cycle SOPs, and policy inheritance."""
import json
import os
from pathlib import Path
import pytest

from synlynk.charters import DEFAULT_ROLE_CHARTERS, load_charter, validate_charter
from synlynk.policy import load_policy

ROLES = ["pm", "architect", "tpm", "dev", "designer", "qa", "maintainer"]


def test_all_canonical_charters_exist_and_validate():
    """Verify each canonical role charter loads and passes validation."""
    for role in ROLES:
        charter = load_charter(role)
        assert charter is not None, f"Charter for {role} failed to load"
        assert charter.role == role
        assert charter.mandate, f"Charter for {role} missing mandate"
        assert validate_charter(charter), f"Charter for {role} failed validation"


def test_charter_wake_cycle_sops_contain_governs_primitives():
    """Verify each role's wake_cycle_sop defines its autonomous GOVERNS stage."""
    pm_charter = load_charter("pm")
    pm_sop_text = " ".join(pm_charter.wake_cycle_sop).lower()
    assert "goal list" in pm_sop_text
    assert "brainstorm" in pm_sop_text
    assert "agenda" in pm_sop_text
    assert "gh issue create" in pm_sop_text
    assert "closed" in pm_sop_text

    architect_charter = load_charter("architect")
    arch_sop_text = " ".join(architect_charter.wake_cycle_sop).lower()
    assert "spec" in arch_sop_text
    assert "plan" in arch_sop_text
    assert "gh issue create" in arch_sop_text
    assert "closed" in arch_sop_text

    tpm_charter = load_charter("tpm")
    tpm_sop_text = " ".join(tpm_charter.wake_cycle_sop).lower()
    assert "plan" in tpm_sop_text
    assert "story create" in tpm_sop_text
    assert "ready" in tpm_sop_text

    dev_charter = load_charter("dev")
    dev_sop_text = " ".join(dev_charter.wake_cycle_sop).lower()
    assert "worktree" in dev_sop_text
    assert "tdd" in dev_sop_text
    assert "pr create" in dev_sop_text

    qa_charter = load_charter("qa")
    qa_sop_text = " ".join(qa_charter.wake_cycle_sop).lower()
    assert "synlynk pr check" in qa_sop_text
    assert "merge" in qa_sop_text

    maintainer_charter = load_charter("maintainer")
    maint_sop_text = " ".join(maintainer_charter.wake_cycle_sop).lower()
    assert "worktree clean" in maint_sop_text
    assert "sentinel" in maint_sop_text


def test_policy_inheritance_schema():
    """Verify policy.json provisions for Team/Enterprise policy inheritance."""
    repo_root = Path(__file__).resolve().parent.parent
    policy = load_policy(str(repo_root))
    assert "policy_inheritance" in policy, "policy.json missing policy_inheritance block"
    inheritance = policy["policy_inheritance"]
    assert inheritance.get("mode") in ("standalone", "inherited")
    assert "immutable_enterprise_rules" in inheritance
    assert "merge_authority.can_merge" in inheritance["immutable_enterprise_rules"]
    assert "merge_authority.require_non_authoring_review" in inheritance["immutable_enterprise_rules"]


def test_charters_are_domain_agnostic():
    """Verify core charters remain strictly domain/industry agnostic."""
    prohibited_domain_keywords = ["hipaa", "pci-dss", "finra", "healthcare", "ecommerce", "banking"]
    for role in ROLES:
        charter = load_charter(role)
        full_text = f"{charter.mandate} {' '.join(charter.wake_cycle_sop)}".lower()
        for kw in prohibited_domain_keywords:
            assert kw not in full_text, f"Charter for {role} contains domain-specific keyword {kw!r}"
