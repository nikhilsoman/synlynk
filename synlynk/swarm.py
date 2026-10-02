"""Swarm runner lifecycle commands and relay integration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List

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
    targets = [r["runner_id"] for r in records] if args.all else ([args.runner_id] if args.runner_id else [])
    destroyed = [runner_id for runner_id in targets if manager.destroy(runner_id)]
    print(json.dumps({"destroyed": destroyed}))
