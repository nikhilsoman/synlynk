from argparse import Namespace

from synlynk.swarm import (
    SwarmLease,
    calculate_vertical_host_size,
    cmd_swarm_lease_dispatch,
)


def test_calculate_vertical_host_size():
    assert calculate_vertical_host_size(1) == "cpx21"
    assert calculate_vertical_host_size(3) == "cpx21"
    assert calculate_vertical_host_size(4) == "cpx31"
    assert calculate_vertical_host_size(8) == "cpx31"
    assert calculate_vertical_host_size(9) == "cpx51"
    assert calculate_vertical_host_size(16) == "cpx51"
    assert calculate_vertical_host_size(32) == "cpx51"


def test_lease_dispatch_stripes_tasks_into_worktrees_and_sizes_host(monkeypatch):
    provisioned = {}

    class MockManager:
        def provision(self, spec, driver):
            provisioned["spec"] = spec
            provisioned["driver"] = driver
            return "runner-123"

    monkeypatch.setattr("synlynk.swarm._manager", lambda: MockManager())
    monkeypatch.setattr("synlynk.swarm._publish_progress", lambda *_args: None)

    lease = cmd_swarm_lease_dispatch(
        Namespace(
            epic="epic-123",
            tasks=["task-a", "task-b", "task-c", "task-d"],
            driver="hetzner",
            size="auto",
        )
    )

    assert isinstance(lease, SwarmLease)
    assert lease.lease_id == "runner-123"
    assert lease.epic_id == "epic-123"
    assert lease.node_ids == ["runner-123"]
    assert provisioned["driver"] == "hetzner"
    assert provisioned["spec"]["server_type"] == "cpx31"
    assert provisioned["spec"]["task_count"] == 4
    assert provisioned["spec"]["worktrees"] == [
        {"task_id": "task-a", "path": "worktrees/task-1"},
        {"task_id": "task-b", "path": "worktrees/task-2"},
        {"task_id": "task-c", "path": "worktrees/task-3"},
        {"task_id": "task-d", "path": "worktrees/task-4"},
    ]
