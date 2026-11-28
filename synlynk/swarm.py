"""Swarm runner lifecycle commands and relay integration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List

from synlynk import _get_db, load_config
from synlynk.runners.manager import RunnerManager


def check_orthogonal_files(touched_lists: List[List[str]]) -> bool:
    """Return True if no file path appears in more than one touched-files list."""
    seen = set()
    for touched in touched_lists:
        for path in set(touched):
            if path in seen:
                return False
            seen.add(path)
    return True


@dataclass
class SwarmBatch:
    batch_id: str
    task_ids: List[str] = field(default_factory=list)
    driver: str = "codex"
    runner_ids: List[str] = field(default_factory=list)
    status: str = "running"
    touched_files: List[List[str]] = field(default_factory=list)
    files_touched_by_task: List[List[str]] = field(default_factory=list)

    @property
    def is_orthogonal(self) -> bool:
        return check_orthogonal_files(self.touched_files or self.files_touched_by_task)


@dataclass
class SwarmLease:
    """Lifecycle record for a dedicated vertical swarm host lease."""

    lease_id: str
    epic_id: str
    driver: str
    node_ids: List[str] = field(default_factory=list)
    status: str = "active"
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def calculate_vertical_host_size(task_count: int) -> str:
    """Return the Hetzner server type for a vertical host's task count."""
    if not isinstance(task_count, int) or isinstance(task_count, bool) or task_count < 1:
        raise ValueError("task_count must be a positive integer")
    if task_count <= 3:
        return "cpx21"
    if task_count <= 8:
        return "cpx31"
    return "cpx51"


def _worktree_specs(tasks: List[Any]) -> List[dict]:
    """Assign each milestone task a stable, isolated host-local worktree."""
    specs = []
    for index, task in enumerate(tasks, start=1):
        if isinstance(task, dict):
            task_id = task.get("task_id") or task.get("id") or str(task)
        else:
            task_id = str(task)
        specs.append({"task_id": task_id, "path": f"worktrees/task-{index}"})
    return specs


def cmd_swarm_lease_dispatch(args) -> SwarmLease:
    """Provision one vertical host and stripe its milestone tasks into worktrees."""
    tasks = list(getattr(args, "tasks", None) or [])
    if not tasks:
        raise ValueError("at least one task is required to dispatch a swarm lease")

    driver_name = getattr(args, "driver", "hetzner")
    epic_id = str(getattr(args, "epic"))
    requested_size = getattr(args, "size", "auto")
    size_to_server_type = {
        "small": "cpx21",
        "medium": "cpx31",
        "large": "cpx51",
    }
    server_type = (
        calculate_vertical_host_size(len(tasks))
        if requested_size == "auto"
        else size_to_server_type.get(requested_size, requested_size)
    )
    spec = {
        "epic_id": epic_id,
        "driver": driver_name,
        "task_count": len(tasks),
        "server_type": server_type,
        "worktrees": _worktree_specs(tasks),
    }
    runner_id = _manager().provision(spec, driver_name)
    _publish_progress(runner_id, {
        "status": "leased",
        "epic_id": epic_id,
        "driver": driver_name,
        "task_count": len(tasks),
    })
    return SwarmLease(
        lease_id=runner_id,
        epic_id=epic_id,
        driver=driver_name,
        node_ids=[runner_id],
    )


def _manager():
    return RunnerManager(load_config(), _get_db())


def _publish_progress(runner_id, payload):
    from synlynk.events import ActorIdentifier, EventEnvelope
    from synlynk.relay import RelayBroker
    event = EventEnvelope.create(ActorIdentifier("local", "local", "swarm", "runner", runner_id),
                                "runner_progress", {"runner_id": runner_id, **payload})
    RelayBroker().publish(event)


def cmd_swarm_dispatch(args):
    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")
    manager = _manager()
    ids = []
    for index in range(args.batch_size):
        spec = {"task": args.task, "command": args.task, "driver": args.driver, "batch_index": index}
        runner_id = manager.provision(spec, args.driver)
        ids.append(runner_id)
        _publish_progress(runner_id, {"status": "provisioned", "batch_index": index})
    print(json.dumps({"driver": args.driver, "runner_ids": ids}))


def cmd_swarm_status(args):
    print(json.dumps(_manager().list(include_destroyed=args.all), indent=2))


def cmd_swarm_destroy(args):
    manager = _manager()
    records = manager.list(include_destroyed=False)


def cmd_swarm_lease(args):
    """Lease a dedicated vertical swarm host for an epic (Direct BYOT or Hosted Relay)."""
    driver_name = getattr(args, "driver", "hetzner")
    epic_id = getattr(args, "epic", None)
    size = getattr(args, "size", "auto")
    relay_mode = getattr(args, "relay", False)

    manager = _manager()
    spec = {
        "epic_id": epic_id,
        "size": size,
        "driver": driver_name,
        "relay": relay_mode,
        "command": ["synlynk", "swarm", "worker", "--epic", str(epic_id)],
    }
    runner_id = manager.provision(spec, driver_name)
    _publish_progress(runner_id, {"status": "leased", "epic_id": epic_id, "driver": driver_name})
    result = {
        "lease_id": runner_id,
        "epic_id": epic_id,
        "driver": driver_name,
        "relay": relay_mode,
        "status": "active",
    }
    print(json.dumps(result, indent=2))
    return result

    targets = [r["runner_id"] for r in records] if args.all else ([args.runner_id] if args.runner_id else [])
    destroyed = [runner_id for runner_id in targets if manager.destroy(runner_id)]
    print(json.dumps({"destroyed": destroyed}))
