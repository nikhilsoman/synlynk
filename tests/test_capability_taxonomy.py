import pytest
from synlynk.capability_probe import (
    CAP_SHELL,
    CAP_WORKSPACE_WRITE,
    CAP_GH_WRITE,
    CAP_NET,
    ALL_CAPABILITIES,
    HARNESS_CAPABILITY_PROFILES,
    infer_task_required_capabilities,
    evaluate_harness_capabilities,
    probe_harness_runtime_capability,
)


def test_capability_constants_defined_and_distinct():
    assert CAP_SHELL == "run:shell"
    assert CAP_WORKSPACE_WRITE == "write:workspace"
    assert CAP_GH_WRITE == "write:github"
    assert CAP_NET == "net:external"
    assert len({CAP_SHELL, CAP_WORKSPACE_WRITE, CAP_GH_WRITE, CAP_NET}) == 4
    assert ALL_CAPABILITIES == {CAP_SHELL, CAP_WORKSPACE_WRITE, CAP_GH_WRITE, CAP_NET}


def test_harness_profiles_conform_to_known_constraints():
    # Live TC-9 retest 2026-10-04 confirmed Grok GitHub-write capability
    # post-LIVE-13 fix (gh:#2034).
    assert HARNESS_CAPABILITY_PROFILES["grok"][CAP_SHELL] is True
    assert HARNESS_CAPABILITY_PROFILES["grok"][CAP_GH_WRITE] is True
    assert HARNESS_CAPABILITY_PROFILES["grok"][CAP_WORKSPACE_WRITE] is True

    # Codex has full capabilities when grants/network are enabled
    assert HARNESS_CAPABILITY_PROFILES["codex"][CAP_SHELL] is True
    assert HARNESS_CAPABILITY_PROFILES["codex"][CAP_WORKSPACE_WRITE] is True
    assert HARNESS_CAPABILITY_PROFILES["codex"][CAP_GH_WRITE] is True

    # Agy and Claude have full capabilities
    assert HARNESS_CAPABILITY_PROFILES["agy"][CAP_SHELL] is True
    assert HARNESS_CAPABILITY_PROFILES["claude"][CAP_SHELL] is True

    # Local harness is air-gapped without remote gh write
    assert HARNESS_CAPABILITY_PROFILES["local"][CAP_NET] is False
    assert HARNESS_CAPABILITY_PROFILES["local"][CAP_GH_WRITE] is False


def test_infer_task_required_capabilities_explicit():
    reqs = infer_task_required_capabilities(
        "run tests and review PR",
        requires=["run:shell", "write:github"],
    )
    assert CAP_SHELL in reqs
    assert CAP_GH_WRITE in reqs


def test_infer_task_required_capabilities_gh_write_flag():
    reqs = infer_task_required_capabilities(
        "review pull request and merge",
        requires_gh_write=True,
    )
    assert CAP_GH_WRITE in reqs
    assert CAP_SHELL in reqs


def test_infer_task_required_capabilities_from_keywords():
    reqs_test = infer_task_required_capabilities("Run pytest tests/test_jobs.py and fix regressions")
    assert CAP_SHELL in reqs_test
    assert CAP_WORKSPACE_WRITE in reqs_test

    reqs_doc = infer_task_required_capabilities("Update README.md with new documentation")
    assert CAP_WORKSPACE_WRITE in reqs_doc


def test_evaluate_harness_capabilities_satisfied():
    eval_result = evaluate_harness_capabilities(
        "codex",
        {CAP_SHELL, CAP_WORKSPACE_WRITE},
    )
    assert eval_result.allowed is True
    assert len(eval_result.missing_capabilities) == 0


def test_evaluate_harness_capabilities_missing():
    eval_result = evaluate_harness_capabilities(
        "grok",
        {CAP_SHELL, CAP_WORKSPACE_WRITE},
    )
    assert eval_result.allowed is True
    assert eval_result.missing_capabilities == []


def test_grok_runtime_shell_capability_defaults_true_and_supports_kill_switch(monkeypatch):
    monkeypatch.delenv("SYNLYNK_GROK_SHELL_DISABLED", raising=False)
    assert probe_harness_runtime_capability("grok", CAP_SHELL, ttl_seconds=0) is True

    monkeypatch.setenv("SYNLYNK_GROK_SHELL_DISABLED", "1")
    assert probe_harness_runtime_capability("grok", CAP_SHELL, ttl_seconds=0) is False


def test_evaluate_harness_capabilities_grants_and_revokes():
    # Granting shell to grok
    res_granted = evaluate_harness_capabilities(
        "grok",
        {CAP_SHELL},
        grants=["run:shell"],
    )
    assert res_granted.allowed is True

    # Revoking shell from codex
    res_revoked = evaluate_harness_capabilities(
        "codex",
        {CAP_SHELL},
        revokes=["run:shell"],
    )
    assert res_revoked.allowed is False
    assert CAP_SHELL in res_revoked.missing_capabilities
