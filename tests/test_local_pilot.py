import json
import os
from pathlib import Path

import pytest

from synlynk import local_pilot
from synlynk.local_pilot import (
    APPROVED_SHARES,
    PILOT_CLASSES,
    evaluate_local_pilot,
    evaluate_promotion_gate,
)


def _decision(**overrides):
    values = {
        "enabled": True,
        "qualified": True,
        "isolated": True,
        "pilot_class": "test_summary",
        "role": "dev",
        "requires_gh_write": False,
        "share": 0.20,
        "dispatch_key": "issue-2349-task-1",
        "scope_paths": ["test.log"],
    }
    values.update(overrides)
    return evaluate_local_pilot(**values)


def test_pilot_fails_closed_when_any_safety_prerequisite_is_missing():
    assert _decision(enabled=False).reason == "pilot_disabled"
    assert _decision(qualified=False).reason == "qualification_not_passed"
    assert _decision(isolated=False).reason == "isolated_runner_unavailable"
    assert _decision(pilot_class=None).reason == "pilot_class_not_allowlisted"
    assert _decision(role="architect").reason == "role_excluded"
    assert _decision(requires_gh_write=True).reason == "github_write_excluded"
    assert _decision(share=0.21).reason == "share_not_an_approved_gate"
    assert _decision(dispatch_key=None).reason == "dispatch_identity_missing"


def test_tracked_rebaseline_config_keeps_local_disabled_after_merge():
    """A merge must leave the tracked pilot unable to admit live work."""
    repo_root = Path(__file__).resolve().parents[1]
    workspace = json.loads((repo_root / ".synlynk" / "workspace.json").read_text())

    assert workspace["local_pilot"]["enabled"] is False

    decision = evaluate_local_pilot(
        enabled=workspace["local_pilot"]["enabled"],
        qualified=True,
        isolated=True,
        pilot_class="test_summary",
        role="dev",
        requires_gh_write=False,
        share=workspace["local_pilot"]["share"],
        dispatch_key="merged-rebaseline-task",
        scope_paths=["test.log"],
        rebaseline=True,
    )

    assert not decision.route_local
    assert decision.reason == "pilot_disabled"


def test_pilot_rejects_excluded_work_and_unscoped_edits():
    assert _decision(task="refactor the code", pilot_class="change_summary").reason == "task_text_excluded"
    assert _decision(pilot_class="documentation_edit", scope_paths=[]).reason == "bounded_scope_required"
    scoped = _decision(
        pilot_class="documentation_edit", scope_paths=["docs/guide.md"],
        dispatch_key="test-2",
    )
    assert scoped.route_local


def test_only_named_pilot_classes_are_allowlisted():
    assert PILOT_CLASSES == {
        "test_summary",
        "test_diagnosis",
        "codepath_summary",
        "change_summary",
        "documentation_edit",
        "mechanical_edit",
    }
    assert _decision(pilot_class="implement").reason == "pilot_class_not_allowlisted"


def test_rebaseline_admission_restricts_the_existing_pilot_classes_to_its_two_classes():
    """Admitting documentation work in re-baseline mode would widen the approved lane."""
    assert _decision(pilot_class="documentation_edit", rebaseline=True).reason == (
        "rebaseline_pilot_class_not_allowlisted"
    )
    assert _decision(pilot_class="codepath_summary", rebaseline=True).reason != (
        "rebaseline_pilot_class_not_allowlisted"
    )


def test_pilot_cohort_is_deterministic_and_cannot_exceed_approved_share():
    assert APPROVED_SHARES == {0.20, 0.35, 0.50}
    for share in APPROVED_SHARES:
        first = _decision(share=share)
        second = _decision(share=share)
        assert first == second
        assert first.bucket is not None and 0 <= first.bucket < 10_000
        assert first.route_local == (first.bucket < int(share * 10_000))


def test_pilot_bucket_is_stable_across_share_gates():
    low = _decision(share=0.20)
    high = _decision(share=0.50)
    assert low.bucket == high.bucket
    assert not low.route_local or high.route_local


def _status(*, validation=None, expansion=None):
    return {
        "historical": {"cohort": "historical", "accepted": 8, "eligible": 12},
        "validation": {
            "cohort": "validation", "accepted": 0, "eligible": 0,
            "pending": 0, "rejected": 0, "safety_failed": 0,
            **(validation or {}),
        },
        "expansion": {
            "cohort": "expansion", "accepted": 0, "eligible": 0,
            "pending": 0, "rejected": 0, "safety_failed": 0,
            "consecutive_accepted": 0,
            **(expansion or {}),
        },
    }


def test_historical_safety_failure_requires_an_active_resume_authorization():
    """A historical hard failure cannot be bypassed by ordinary rebaseline evidence."""
    decision = local_pilot.evaluate_rebaseline(
        {**_status(), "historical_safety_failures": 1, "active_authorization": None}
    )

    assert not decision.allow_admission
    assert decision.pause_required
    assert decision.reason == "operational_resume_required"


def test_resume_preflight_fails_closed_for_config_runtime_or_reconciliation_debt(tmp_path, monkeypatch):
    """A relaxed preflight branch could resume against unsafe state."""
    import sqlite3
    from synlynk import local_agent

    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    (repo / ".agents").mkdir()
    (repo / ".synlynk" / "workspace.json").write_text(
        json.dumps({"local_pilot": {"enabled": False, "share": 0.20, "max_concurrent": 1}})
    )
    (repo / ".agents" / "local.json").write_text(json.dumps({"max_concurrent": 1}))
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE daemon_jobs (status TEXT, agent TEXT)")
    monkeypatch.setattr(local_agent, "load_pilot_runtime", lambda *_: {
        "enabled": False, "share": 0.20, "qualified": True, "qualified_models": ["ornith-test"], "isolated": True,
    })
    monkeypatch.setattr(local_agent, "resolve_effective_local_model", lambda **_: {"resolved_model": "ornith-test"})
    monkeypatch.setattr(local_agent, "_usable_compose_runner", lambda: True)

    passed = local_agent.preflight_local_pilot_resume(str(repo), conn)
    assert passed["result"] == "passed"

    (repo / ".synlynk" / "workspace.json").write_text(
        json.dumps({"local_pilot": {"enabled": False, "share": 0.35, "max_concurrent": 1}})
    )
    failed = local_agent.preflight_local_pilot_resume(str(repo), conn)
    assert failed["result"] == "failed"
    assert "config_share" in failed["failures"]


def test_resume_preflight_requires_the_effectively_resolved_model_to_be_qualified_ornith(tmp_path, monkeypatch):
    """A qualified fallback model must not authorize an unqualified pinned selection."""
    import sqlite3
    from synlynk import local_agent

    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    (repo / ".agents").mkdir()
    (repo / ".synlynk" / "workspace.json").write_text(
        json.dumps({"local_pilot": {"enabled": False, "share": 0.20, "max_concurrent": 1}})
    )
    (repo / ".agents" / "local.json").write_text(json.dumps({"max_concurrent": 1}))
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE daemon_jobs (status TEXT, agent TEXT)")
    monkeypatch.setattr(local_agent, "load_pilot_runtime", lambda *_: {
        "enabled": False, "share": 0.20, "qualified": True,
        "qualified_models": ["ornith-qualified"], "isolated": True,
    })
    monkeypatch.setattr(
        local_agent, "resolve_effective_local_model", lambda **_: {"resolved_model": "unqualified-pinned-model"}
    )
    monkeypatch.setattr(local_agent, "_usable_compose_runner", lambda: True)

    result = local_agent.preflight_local_pilot_resume(str(repo), conn)

    assert result["result"] == "failed"
    assert "resolved_model_unqualified" in result["failures"]


def test_resume_preflight_fails_when_local_reservation_source_is_unreadable(tmp_path, monkeypatch):
    """A missing reservation table cannot safely mean no Local work is running."""
    import sqlite3
    from synlynk import local_agent

    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    (repo / ".agents").mkdir()
    (repo / ".synlynk" / "workspace.json").write_text(
        json.dumps({"local_pilot": {"enabled": False, "share": 0.20, "max_concurrent": 1}})
    )
    (repo / ".agents" / "local.json").write_text(json.dumps({"max_concurrent": 1}))
    conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(local_agent, "load_pilot_runtime", lambda *_: {
        "enabled": False, "share": 0.20, "qualified": True, "qualified_models": ["ornith-test"], "isolated": True,
    })
    monkeypatch.setattr(local_agent, "resolve_effective_local_model", lambda **_: {"resolved_model": "ornith-test"})
    monkeypatch.setattr(local_agent, "_usable_compose_runner", lambda: True)

    result = local_agent.preflight_local_pilot_resume(str(repo), conn)

    assert result["result"] == "failed"
    assert "reservation_unreadable" in result["failures"]


def test_resume_preflight_reconciles_stranded_activation_without_inferring_config_approval(tmp_path):
    """An activating record must become failed even when a config later looks enabled."""
    import sqlite3
    from synlynk import local_agent
    from synlynk.local_pilot_ledger import ensure_local_pilot_ledger

    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    (repo / ".synlynk" / "workspace.json").write_text(json.dumps({"local_pilot": {"enabled": False, "share": .2}}))
    conn = sqlite3.connect(":memory:")
    ensure_local_pilot_ledger(conn)
    conn.execute(
        "INSERT INTO local_pilot_resume_authorizations "
        "(authorization_id, created_at, signed_payload_json, signed_payload_digest, config_fingerprint, "
        "remediation_reference, verification_reference, safety_watermark, preflight_receipt_json, "
        "preflight_receipt_digest, state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'activating')",
        ("stranded", "now", "{}", "digest", "fingerprint", "fix", "verify", 0, "{}", "digest"),
    )
    conn.commit()

    result = local_agent.preflight_local_pilot_resume(str(repo), conn)

    assert result["result"] == "failed"
    assert conn.execute(
        "SELECT state FROM local_pilot_resume_authorizations WHERE authorization_id = 'stranded'"
    ).fetchone()[0] == "failed"


def test_status_reconciles_stranded_activation_to_a_disabled_terminal_state(project_dir, monkeypatch):
    """A read-only status request is also a required crash-boundary reconciliation point."""
    import sqlite3
    from synlynk import local_agent
    from synlynk.local_pilot_ledger import ensure_local_pilot_ledger

    conn = sqlite3.connect(":memory:")
    ensure_local_pilot_ledger(conn)
    conn.execute("CREATE TABLE daemon_jobs (status TEXT, agent TEXT)")
    conn.execute(
        "INSERT INTO local_pilot_resume_authorizations "
        "(authorization_id, created_at, signed_payload_json, signed_payload_digest, config_fingerprint, "
        "remediation_reference, verification_reference, safety_watermark, preflight_receipt_json, "
        "preflight_receipt_digest, state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'activating')",
        ("stranded-status", "now", "{}", "digest", "fingerprint", "fix", "verify", 0, "{}", "digest"),
    )
    conn.commit()
    (project_dir / ".synlynk" / "workspace.json").write_text(
        json.dumps({"local_pilot": {"enabled": True, "share": .2, "max_concurrent": 1}})
    )
    monkeypatch.setattr(local_agent, "_get_db", lambda: conn)
    monkeypatch.setattr(local_agent, "load_pilot_runtime", lambda *_: {
        "enabled": False, "share": .2, "qualified": True, "qualified_models": ["ornith-test"], "isolated": True,
    })
    monkeypatch.setattr(local_agent, "_local_pilot_endpoint_status", lambda: "healthy")

    status = local_agent.local_pilot_status()

    assert status["cohorts"]["latest_authorization"]["state"] == "failed"
    workspace = json.loads((project_dir / ".synlynk" / "workspace.json").read_text())
    assert workspace["local_pilot"]["enabled"] is False


def test_pilot_resume_signs_and_activates_only_the_fixed_lane(tmp_path, monkeypatch):
    """Changing the staged values or dispatching work would violate the recovery boundary."""
    import sqlite3
    from synlynk import local_agent, local_pilot_ledger

    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    (repo / ".agents").mkdir()
    (repo / ".synlynk" / "workspace.json").write_text(
        json.dumps({"local_pilot": {"enabled": False, "share": 0.20, "max_concurrent": 1}})
    )
    (repo / ".agents" / "local.json").write_text(json.dumps({"max_concurrent": 1}))
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE daemon_jobs (status TEXT, agent TEXT)")
    monkeypatch.setattr(local_agent, "load_pilot_runtime", lambda *_: {
        "enabled": False, "share": 0.20, "qualified": True, "qualified_models": ["ornith-test"], "isolated": True,
    })
    monkeypatch.setattr(local_agent, "resolve_effective_local_model", lambda **_: {"resolved_model": "ornith-test"})
    monkeypatch.setattr(local_agent, "_usable_compose_runner", lambda: True)
    monkeypatch.setattr(local_agent, "_sign_resume_authorization", lambda _: "signed-by-test")
    monkeypatch.setattr(local_pilot_ledger, "_verify_resume_signature", lambda *_: True)

    result = local_agent.resume_local_pilot(
        str(repo), conn, "issue-2342", "review-2349", lambda _: "RESUME LOCAL PILOT"
    )

    workspace = json.loads((repo / ".synlynk" / "workspace.json").read_text())
    assert workspace["local_pilot"] == {"enabled": True, "share": 0.20, "max_concurrent": 1}
    assert result["authorization"]["state"] == "active"
    assert result["authorization"]["signed_payload_json"]
    assert conn.execute("SELECT COUNT(*) FROM local_pilot_evidence").fetchone()[0] == 0


def test_pilot_resume_refusal_or_missing_signing_key_leaves_config_disabled(tmp_path, monkeypatch):
    """A declined or unsigned ceremony must not write an active authorization."""
    import sqlite3
    from synlynk import local_agent

    repo = tmp_path / "repo"
    (repo / ".synlynk").mkdir(parents=True)
    (repo / ".agents").mkdir()
    baseline = {"local_pilot": {"enabled": False, "share": 0.20, "max_concurrent": 1}}
    (repo / ".synlynk" / "workspace.json").write_text(json.dumps(baseline))
    (repo / ".agents" / "local.json").write_text(json.dumps({"max_concurrent": 1}))
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE daemon_jobs (status TEXT, agent TEXT)")
    monkeypatch.setattr(local_agent, "load_pilot_runtime", lambda *_: {
        "enabled": False, "share": 0.20, "qualified": True, "qualified_models": ["ornith-test"], "isolated": True,
    })
    monkeypatch.setattr(local_agent, "resolve_effective_local_model", lambda **_: {"resolved_model": "ornith-test"})
    monkeypatch.setattr(local_agent, "_usable_compose_runner", lambda: True)
    monkeypatch.setattr(local_agent, "_identity_key_path", lambda: str(repo / "missing-identity.key"))

    with pytest.raises(ValueError, match="confirmation"):
        local_agent.resume_local_pilot(str(repo), conn, "fix", "verify", lambda _: "no")
    with pytest.raises(ValueError, match="signing key"):
        local_agent.resume_local_pilot(str(repo), conn, "fix", "verify", lambda _: "RESUME LOCAL PILOT")

    assert json.loads((repo / ".synlynk" / "workspace.json").read_text()) == baseline
    assert conn.execute("SELECT COUNT(*) FROM local_pilot_resume_authorizations").fetchone()[0] == 0


def test_active_resume_authorization_uses_only_its_new_epoch_for_rebaseline():
    """The policy consumes the reset status arithmetic rather than old evidence."""
    decision = local_pilot.evaluate_rebaseline(
        {
            **_status(validation={"accepted": 1, "eligible": 1}),
            "historical_safety_failures": 1,
            "active_epoch_safety_failures": 0,
            "active_authorization": {"authorization_id": "resume-1", "state": "active"},
        }
    )

    assert decision.allow_admission
    assert decision.cohort == "validation"
    assert decision.reason == "validation_incomplete"


def test_activating_resume_authorization_cannot_admit_after_a_historical_failure():
    """A crash before activation must remain fail-closed."""
    decision = local_pilot.evaluate_rebaseline(
        {
            **_status(),
            "historical_safety_failures": 1,
            "active_epoch_safety_failures": 0,
            "active_authorization": {"authorization_id": "resume-1", "state": "activating"},
        }
    )

    assert not decision.allow_admission
    assert decision.pause_required
    assert decision.reason == "operational_resume_required"


def test_rebaseline_uses_only_the_new_validation_cohort_not_historical_evidence():
    """Counting the historical 8/12 toward validation must never open expansion."""
    decision = local_pilot.evaluate_rebaseline(_status())

    assert local_pilot.REBASELINE_PILOT_CLASSES == {"test_summary", "codepath_summary"}
    assert decision.allow_admission
    assert decision.cohort == "validation"
    assert decision.share == 0.20
    assert not decision.proposal_35_eligible
    assert decision.reason == "validation_incomplete"


def test_five_accepted_validation_samples_open_expansion_without_changing_share():
    """Returning 0.35 after five validation acceptances would widen traffic automatically."""
    decision = local_pilot.evaluate_rebaseline(_status(validation={"accepted": 5, "eligible": 5}))

    assert decision.allow_admission
    assert decision.cohort == "expansion"
    assert decision.share == 0.20
    assert not decision.pause_required
    assert not decision.proposal_35_eligible
    assert decision.reason == "expansion_evidence_required"


def test_validation_rejection_requires_a_human_review_before_more_admission():
    """Treating a rejected validation result as another attempt would bypass the 5/5 gate."""
    decision = local_pilot.evaluate_rebaseline(_status(validation={"accepted": 4, "rejected": 1}))

    assert not decision.allow_admission
    assert decision.cohort is None
    assert decision.share == 0.20
    assert not decision.pause_required
    assert decision.reason == "validation_quality_rejection_requires_human_review"


def test_expansion_quality_rejection_resets_only_the_consecutive_acceptance_run():
    """A quality rejection must not pause the pilot or preserve the prior run."""
    decision = local_pilot.evaluate_rebaseline(
        _status(
            validation={"accepted": 5, "eligible": 5},
            expansion={"accepted": 7, "rejected": 1, "consecutive_accepted": 0},
        )
    )

    assert decision.allow_admission
    assert decision.cohort == "expansion"
    assert decision.share == 0.20
    assert not decision.pause_required
    assert not decision.proposal_35_eligible
    assert decision.reason == "expansion_evidence_required"


def test_ten_consecutive_expansion_acceptances_only_make_a_35_percent_proposal_eligible():
    """Changing the share to 0.35 here would bypass the human expansion approval."""
    decision = local_pilot.evaluate_rebaseline(
        _status(
            validation={"accepted": 5, "eligible": 5},
            expansion={"accepted": 10, "eligible": 10, "consecutive_accepted": 10},
        )
    )

    assert decision.allow_admission
    assert decision.cohort == "expansion"
    assert decision.share == 0.20
    assert decision.proposal_35_eligible
    assert decision.reason == "proposal_35_eligible"


def test_hard_safety_failure_pauses_every_rebaseline_stage():
    """Admitting another Local sample after a safety failure would violate the hard gate."""
    decision = local_pilot.evaluate_rebaseline(_status(expansion={"safety_failed": 1}))

    assert not decision.allow_admission
    assert decision.cohort is None
    assert decision.share == 0.20
    assert decision.pause_required
    assert not decision.proposal_35_eligible
    assert decision.reason == "hard_safety_failure_requires_pause"


def test_legacy_promotion_gate_is_retired_and_fails_closed():
    """Returning 0.35 or 0.50 to an old caller would restore automatic promotion."""
    decision = evaluate_promotion_gate(
        current_share=0.35, eligible_jobs=75, accepted_jobs=75,
        serious_incidents=0, latency_stable=True, memory_stable=True,
        rollback_drill_passed=True,
    )

    assert decision.next_share == 0.0
    assert decision.rollback_required
    assert decision.reason == "promotion_gate_retired_use_evaluate_rebaseline"


def test_isolated_compose_builder_passes_only_local_model_credential(tmp_path, monkeypatch):
    from synlynk import local_pilot

    repo = tmp_path / "repo"
    (repo / "docker").mkdir(parents=True)
    (repo / local_pilot.LOCAL_PILOT_COMPOSE).write_text("services: {}\n")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    prompt = tmp_path / "prompt.md"
    prompt.write_text("summarize test output")
    log = tmp_path / "runner.log"
    exit_file = tmp_path / "runner.exit"
    monkeypatch.setattr(local_pilot.shutil, "which", lambda name: "/usr/local/bin/docker")

    command, env = local_pilot.build_isolated_compose_shell(
        repo_root=str(repo), worktree=str(worktree),
        prompt_file=str(prompt), log_file=str(log), exit_file=str(exit_file),
        job_id="job-abc123", aider_args=["--model", "openai/Ornith"],
        pilot_class="test_summary", scope_paths=["test.log"],
        env={
            "PATH": "/usr/bin", "OPENAI_API_KEY": "local-test-secret",
            "GH_TOKEN": "github-test-secret", "ANTHROPIC_API_KEY": "other-test-secret",
        },
    )

    assert command[1:3] == ["-m", "synlynk.local_pilot_runner"]
    assert "--openai-api-base" in command
    assert command[command.index("--openai-api-base") + 1] == "http://omlx:8000/v1"
    assert env["OPENAI_API_KEY"] == "local-test-secret"
    assert "GH_TOKEN" not in env
    assert "ANTHROPIC_API_KEY" not in env
    assert "local-test-secret" not in " ".join(command)


def test_isolated_compose_builder_fails_closed_without_key_or_runner(tmp_path):
    from synlynk.local_pilot import LocalPilotSetupError, build_isolated_compose_shell

    with pytest.raises(LocalPilotSetupError, match="OPENAI_API_KEY"):
        build_isolated_compose_shell(
            repo_root=str(tmp_path), worktree=str(tmp_path),
            prompt_file=str(tmp_path / "missing"),
            log_file=str(tmp_path / "log"), exit_file=str(tmp_path / "exit"),
            job_id="job", aider_args=[], pilot_class="test_summary",
            scope_paths=["test.log"], env={},
        )


def test_sensitive_files_are_rejected_before_the_worktree_is_mounted(tmp_path, monkeypatch):
    from synlynk import local_pilot

    repo = tmp_path / "repo"
    (repo / "docker").mkdir(parents=True)
    (repo / local_pilot.LOCAL_PILOT_COMPOSE).write_text("services: {}\n")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".env.local").write_text("DO_NOT_READ=secret")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("summarize test output")
    monkeypatch.setattr(local_pilot.shutil, "which", lambda name: "/usr/local/bin/docker")

    with pytest.raises(local_pilot.LocalPilotSetupError, match="credential-like paths"):
        local_pilot.build_isolated_compose_shell(
            repo_root=str(repo), worktree=str(worktree),
            prompt_file=str(prompt), log_file=str(tmp_path / "log"),
            exit_file=str(tmp_path / "exit"), job_id="job-test", aider_args=[],
            pilot_class="test_summary", scope_paths=["test.log"],
            env={"OPENAI_API_KEY": "local-key"},
        )


def test_runner_redacts_api_key_across_output_chunks():
    from io import BytesIO
    from synlynk.local_pilot_runner import _SecretRedactor

    output = BytesIO()
    redactor = _SecretRedactor(b"test-secret", output)
    redactor.write(b"response token=test-se")
    redactor.write(b"cret complete\n")
    redactor.flush()
    assert output.getvalue() == b"response token=[REDACTED] complete\n"


def test_isolated_runner_cleans_up_compose_and_redacts_persisted_logs(tmp_path, monkeypatch):
    from io import BytesIO
    import subprocess
    from synlynk import local_pilot_runner

    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt")
    source = tmp_path / "source"
    source.mkdir()
    (source / "test.log").write_text("passed")
    (source / "private.md").write_text("out of scope source must not enter the model mount")
    subprocess.run(["git", "init", "--quiet", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "--all"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "-c", "user.name=Test", "-c", "user.email=test@invalid", "commit", "--quiet", "-m", "fixture"],
        check=True,
    )
    log = tmp_path / "runner.log"
    exit_file = tmp_path / "runner.exit"
    compose_calls = []
    compose_envs = []
    scratch_entries = []
    scratch_files = []
    aider_calls = []
    aider_stdin = []

    def fake_run(argv, env):
        compose_calls.append(argv)
        compose_envs.append(dict(env))
        if env.get("PILOT_WORKTREE"):
            scratch_entries.append(sorted(os.listdir(env["PILOT_WORKTREE"])))
            scratch_files.append(sorted(
                os.path.relpath(os.path.join(root, name), env["PILOT_WORKTREE"])
                for root, _, names in os.walk(env["PILOT_WORKTREE"])
                for name in names
                if ".git" not in os.path.relpath(root, env["PILOT_WORKTREE"]).split(os.sep)
            ))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    class FakeChild:
        def __init__(self, *args, **kwargs):
            self.stdout = BytesIO(b"completion test-secret ok\n")

        def wait(self, *args, **kwargs):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(local_pilot_runner, "_run_captured", fake_run)
    original_popen = local_pilot_runner.subprocess.Popen

    def fake_popen(argv, *args, **kwargs):
        if argv and argv[0] == "docker" and "run" in argv:
            aider_calls.append(argv)
            aider_stdin.append(kwargs["stdin"].read())
            return FakeChild(*args, **kwargs)
        return original_popen(argv, *args, **kwargs)

    monkeypatch.setattr(local_pilot_runner.subprocess, "Popen", fake_popen)
    result = local_pilot_runner.run_isolated_dispatch(
        repo_root=str(tmp_path), source_worktree=str(source), prompt_file=str(prompt), log_file=str(log),
        exit_file=str(exit_file), job_id="job-test", pilot_class="test_summary",
        scope_paths=["test.log"], aider_args=["--model", "openai/ornith"],
        env={"PATH": "/usr/bin", "OPENAI_API_KEY": "test-secret"},
    )
    assert result == 0
    assert log.read_text() == "completion [REDACTED] ok\n"
    assert exit_file.read_text() == "0\n"
    receipt = json.loads((tmp_path / "runner.log.pilot.json").read_text())
    assert receipt["outcome"] == "completed_read_only"
    assert receipt["changed_paths"] == []
    assert compose_envs[0]["PILOT_WORKTREE"] != str(source)
    assert scratch_entries[0] == [".git", "test.log"]
    assert scratch_files[0] == ["test.log"]
    assert aider_stdin == [b"prompt"]
    assert aider_calls[0][aider_calls[0].index("aider") + 1:] == [
        "--model", "openai/ornith",
        "--no-show-model-warnings",
        "--no-pretty",
        "--no-suggest-shell-commands",
        "--message-file", "/dev/stdin",
        "--read", "test.log",
    ]
    assert compose_calls[0][5:8] == ["job-test", "up", "--detach"]
    assert compose_calls[-1][-2:] == ["down", "--remove-orphans"]
