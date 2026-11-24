"""Tests for the parallel worktree swarm engine's orthogonal file check."""

from synlynk.swarm import SwarmBatch, check_orthogonal_files


def test_check_orthogonal_files_non_overlapping_returns_true():
    touched_lists = [
        ["a.py", "b.py"],
        ["c.py", "d.py"],
        ["e.py"],
    ]
    assert check_orthogonal_files(touched_lists) is True


def test_check_orthogonal_files_overlapping_returns_false():
    touched_lists = [
        ["a.py", "b.py"],
        ["b.py", "c.py"],
    ]
    assert check_orthogonal_files(touched_lists) is False


def test_check_orthogonal_files_empty_list_returns_true():
    assert check_orthogonal_files([]) is True


def test_check_orthogonal_files_single_list_returns_true():
    assert check_orthogonal_files([["a.py", "b.py"]]) is True


def test_check_orthogonal_files_duplicate_within_same_list_still_orthogonal():
    touched_lists = [
        ["a.py", "a.py"],
        ["b.py"],
    ]
    assert check_orthogonal_files(touched_lists) is True


def test_swarm_batch_dataclass_initialization():
    batch = SwarmBatch(
        batch_id="batch-1",
        driver="codex",
        runner_ids=["r1", "r2"],
        touched_files=[["a.py"], ["b.py"]],
    )
    assert batch.batch_id == "batch-1"
    assert batch.driver == "codex"
    assert batch.runner_ids == ["r1", "r2"]
    assert batch.touched_files == [["a.py"], ["b.py"]]


def test_swarm_batch_is_orthogonal_default():
    batch = SwarmBatch(
        batch_id="batch-2",
        driver="claude",
        runner_ids=["r1"],
        touched_files=[["a.py"]],
    )
    assert batch.is_orthogonal is True


def test_swarm_batch_initialization_with_task_ids():
    batch = SwarmBatch(batch_id="swarm-001", task_ids=["task-1", "task-2"])
    assert batch.batch_id == "swarm-001"
    assert len(batch.task_ids) == 2
    assert batch.status == "running"


def test_swarm_lease_cli_parser():
    """Verify that CLI parser recognizes 'swarm lease' arguments."""
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["swarm", "lease", "--epic", "epic-abc", "--driver", "hetzner", "--size", "large", "--relay"])
    assert args.command == "swarm"
    assert args.swarm_action == "lease"
    assert args.epic == "epic-abc"
    assert args.driver == "hetzner"
    assert args.size == "large"
    assert args.relay is True


def test_cmd_swarm_lease_execution(monkeypatch):
    """Verify cmd_swarm_lease provisions runner through RunnerManager."""
    from argparse import Namespace
    from synlynk.swarm import cmd_swarm_lease

    class MockManager:
        def provision(self, spec, driver):
            assert spec["epic_id"] == "epic-999"
            assert driver == "hetzner"
            return "runner-hetzner-123"

    monkeypatch.setattr("synlynk.swarm._manager", lambda: MockManager())
    monkeypatch.setattr("synlynk.swarm._publish_progress", lambda r_id, p: None)

    args = Namespace(epic="epic-999", driver="hetzner", size="auto", relay=False)
    result = cmd_swarm_lease(args)
    assert result["lease_id"] == "runner-hetzner-123"
    assert result["epic_id"] == "epic-999"
    assert result["driver"] == "hetzner"
    assert result["status"] == "active"


