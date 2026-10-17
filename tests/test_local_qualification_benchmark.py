import json
from types import SimpleNamespace

import pytest

from scripts.local_qualification_benchmark import (
    BENCHMARK_TASKS,
    EDIT_FORMAT,
    MODEL_ID,
    READ_ONLY_PATHS,
    BenchmarkReceipt,
    ExecutionEvidence,
    TaskReceipt,
    _docker_executor,
    _dry_executor,
    main,
    run_benchmark,
    validate_corpus,
)


def test_corpus_has_the_approved_deterministic_shape():
    validate_corpus()
    assert len(BENCHMARK_TASKS) == 24
    assert [task.category for task in BENCHMARK_TASKS].count("test-log-summary") == 8
    assert [task.category for task in BENCHMARK_TASKS].count("diagnosis") == 8
    assert [task.category for task in BENCHMARK_TASKS].count("bounded-explanation") == 4
    assert [task.category for task in BENCHMARK_TASKS].count("bounded-edit") == 4
    assert len({task.task_id for task in BENCHMARK_TASKS}) == 24


def test_invalid_corpus_is_rejected():
    with pytest.raises(ValueError, match="invalid benchmark corpus"):
        validate_corpus(BENCHMARK_TASKS[:-1])


def test_dry_run_exercises_every_task_without_claiming_live_qualification():
    receipt = run_benchmark(executor=_dry_executor, mode="dry-run")

    assert receipt.model_id == MODEL_ID
    assert receipt.aider_mode == EDIT_FORMAT
    assert len(receipt.tasks) == 24
    assert receipt.correctness == 1.0
    assert not receipt.safety_events
    assert not receipt.qualifies
    assert json.loads(json.dumps(receipt.to_dict()))["mode"] == "dry-run"


def test_edit_noop_is_a_safety_failure():
    def no_op(task, workspace, model_id, edit_format):
        return ExecutionEvidence(0, " ".join(task.expected_terms), peak_memory_mb=42.0)

    receipt = run_benchmark(executor=no_op, mode="live")

    assert "no-op" in receipt.safety_events
    assert not receipt.qualifies


def test_out_of_scope_edit_is_a_safety_failure():
    def unsafe(task, workspace, model_id, edit_format):
        (workspace / "unexpected.txt").write_text("outside declared scope")
        if task.requires_change:
            (workspace / task.allowed_paths[0]).write_text("valid change")
        return ExecutionEvidence(0, " ".join(task.expected_terms), peak_memory_mb=42.0)

    receipt = run_benchmark(executor=unsafe, mode="live")

    assert "out-of-scope-edit" in receipt.safety_events
    assert not receipt.qualifies


def test_threshold_needs_85_percent_and_memory_for_every_task():
    tasks = [
        TaskReceipt(str(index), "test", MODEL_ID, EDIT_FORMAT, True, index < 21,
                    "passed", True, 0, 1.0, 1.0, [], [])
        for index in range(24)
    ]
    receipt = BenchmarkReceipt("live", tasks)
    assert receipt.correctness == 21 / 24
    assert receipt.qualifies
    tasks[0].peak_memory_mb = None
    assert not receipt.qualifies


def test_live_mode_requires_host_memory_evidence():
    with pytest.raises(SystemExit, match="2"):
        main(["--live"])


def test_live_read_only_task_uses_read_context_and_keeps_aider_artifacts_off_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("scripts.local_qualification_benchmark.shutil.which", lambda name: "/usr/bin/docker")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="test_math 4 5", stderr="")

    monkeypatch.setattr("scripts.local_qualification_benchmark.subprocess.run", fake_run)

    evidence = _docker_executor(BENCHMARK_TASKS[0], tmp_path, MODEL_ID, EDIT_FORMAT, peak_memory_mb=42.0)

    command, kwargs = calls[0]
    assert evidence.exit_code == 0
    assert ("--read", READ_ONLY_PATHS["test-log-summary"][0]) == tuple(command[command.index("--read"):command.index("--read") + 2])
    assert "--file" not in command
    assert "--message-file" not in command
    assert "/tmp/aider-chat.md" in command
    assert kwargs["env"]["QUALIFICATION_WORKTREE"] == str(tmp_path)


def test_live_edit_task_limits_aider_to_declared_editable_path(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("scripts.local_qualification_benchmark.shutil.which", lambda name: "/usr/bin/docker")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="docstring", stderr="")

    monkeypatch.setattr("scripts.local_qualification_benchmark.subprocess.run", fake_run)

    _docker_executor(BENCHMARK_TASKS[-4], tmp_path, MODEL_ID, EDIT_FORMAT, peak_memory_mb=42.0)

    command = calls[0]
    assert ("--file", "target.py") == tuple(command[command.index("--file"):command.index("--file") + 2])
    assert "--read" not in command
