import json

import pytest

from scripts.local_qualification_benchmark import (
    BENCHMARK_TASKS,
    EDIT_FORMAT,
    MODEL_ID,
    BenchmarkReceipt,
    ExecutionEvidence,
    TaskReceipt,
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
