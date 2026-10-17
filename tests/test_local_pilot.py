import json
import os

import pytest

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


def test_promotion_requires_sample_and_90_percent_acceptance():
    waiting = evaluate_promotion_gate(
        current_share=0.20, eligible_jobs=29, accepted_jobs=29,
        serious_incidents=0, latency_stable=True, memory_stable=True,
    )
    assert waiting.next_share == 0.20
    assert waiting.reason == "insufficient_30_job_sample"

    passed = evaluate_promotion_gate(
        current_share=0.20, eligible_jobs=30, accepted_jobs=27,
        serious_incidents=0, latency_stable=True, memory_stable=True,
    )
    assert passed.next_share == 0.35

    failed = evaluate_promotion_gate(
        current_share=0.20, eligible_jobs=30, accepted_jobs=26,
        serious_incidents=0, latency_stable=True, memory_stable=True,
    )
    assert failed.next_share == 0.0
    assert failed.rollback_required


def test_50_percent_gate_requires_75_jobs_stability_and_rollback_drill():
    args = dict(
        current_share=0.35, accepted_jobs=68, serious_incidents=0,
        latency_stable=True, memory_stable=True,
    )
    assert evaluate_promotion_gate(eligible_jobs=74, **args).next_share == 0.35
    assert evaluate_promotion_gate(eligible_jobs=75, **args).reason == "rollback_drill_required"
    promoted = evaluate_promotion_gate(
        eligible_jobs=75, rollback_drill_passed=True, **args
    )
    assert promoted.next_share == 0.50


def test_serious_incident_immediately_rolls_back_to_frontier():
    decision = evaluate_promotion_gate(
        current_share=0.35, eligible_jobs=75, accepted_jobs=75,
        serious_incidents=1, latency_stable=True, memory_stable=True,
        rollback_drill_passed=True,
    )
    assert decision.next_share == 0.0
    assert decision.rollback_required


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
