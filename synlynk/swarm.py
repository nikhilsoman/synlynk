"""Swarm runner lifecycle commands and relay integration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List

from synlynk import _get_db, load_config
from synlynk.events import emit_event
from synlynk.runners.manager import RunnerManager


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def cmd_swarm_lease(args):
    """Lease a dedicated vertical swarm host for an epic (Direct BYOT or Hosted Relay)."""
    manager = _manager()
    lease_action = getattr(args, "lease_action", None)
    if lease_action == "list":
        leases = manager.list(include_destroyed=getattr(args, "all", False))
        print(json.dumps(leases, indent=2))
        return leases
    if lease_action == "destroy":
        return _destroy_leases(manager, getattr(args, "runner_id", None), getattr(args, "all", False))

    driver_name = getattr(args, "driver", "hetzner")
    epic_id = getattr(args, "epic", None)
    size = getattr(args, "size", "auto")
    relay_mode = getattr(args, "relay", False)

    node_count = max(1, int(getattr(args, "nodes", 1)))
    runner_ids = []
    for node_index in range(node_count):
        spec = {
            "epic_id": epic_id,
            "size": size,
            "driver": driver_name,
            "relay": relay_mode,
            "node_index": node_index,
            "drain_on_empty": bool(getattr(args, "drain_on_empty", False)),
            "command": ["synlynk", "swarm", "worker", "--epic", str(epic_id)],
        }
        runner_id = manager.provision(spec, driver_name)
        runner_ids.append(runner_id)
        _publish_progress(runner_id, {"status": "leased", "epic_id": epic_id, "driver": driver_name})

    result = {
        "lease_id": runner_ids[0],
        "runner_ids": runner_ids,
        "epic_id": epic_id,
        "driver": driver_name,
        "relay": relay_mode,
        "status": "active",
    }
    print(json.dumps(result, indent=2))
    return result


def _destroy_leases(manager, runner_id=None, destroy_all=False):
    records = manager.list(include_destroyed=False)
    if destroy_all:
        targets = records
    elif runner_id:
        targets = [record for record in records if record.get("runner_id") == runner_id]
    else:
        targets = []

    destroyed = []
    for record in targets:
        lease_id = record["runner_id"]
        completion = _emit_lease_completed(manager, record)
        if manager.destroy(lease_id, record.get("driver")):
            destroyed.append(lease_id)
            if completion is not None:
                completion["destroyed_at"] = _now()
    result = {"destroyed": destroyed}
    print(json.dumps(result))
    return result


def _emit_lease_completed(manager, record):
    """Emit the billing seam for a destroyed runner, best-effort on result details."""
    spec = record.get("job_spec") or "{}"
    try:
        spec = json.loads(spec) if isinstance(spec, str) else dict(spec)
    except (TypeError, ValueError):
        spec = {}

    try:
        result = manager.driver(record.get("driver")).collect_results(record["runner_id"]) or {}
    except Exception:
        result = {}
    server = result.get("server") or {}
    server_type = (server.get("server_type") or {}).get("name") or spec.get("server_type") or spec.get("size")
    location = ((server.get("datacenter") or {}).get("location") or {}).get("name") or spec.get("location")
    provisioned = _parse_time(record.get("provisioned_at"))
    active_seconds = max(0, int((_parse_time(_now()) - provisioned).total_seconds())) if provisioned else 0
    hourly_rates = {"cpx21": 0.010, "cpx31": 0.019, "cpx51": 0.045, "cax41": 0.038}
    payload = {
        "lease_id": record["runner_id"],
        "workspace_id": spec.get("workspace_id", "local"),
        "epic_id": spec.get("epic_id"),
        "provider": record.get("driver"),
        "server_id": server.get("id", record["runner_id"]),
        "server_type": server_type,
        "location": location,
        "provisioned_at": record.get("provisioned_at"),
        "active_seconds": active_seconds,
        "raw_compute_cost_eur": round(active_seconds / 3600 * hourly_rates.get(server_type, 0.0), 4),
        "exit_code": result.get("exit_code"),
        "tasks_completed": result.get("tasks_completed", spec.get("tasks_completed", 0)),
    }
    emit_event("milestone_lease_completed", payload, emitted_by="synlynk.swarm")
    try:
        from synlynk.events import ActorIdentifier, EventEnvelope
        from synlynk.relay import RelayBroker

        actor = ActorIdentifier("local", str(payload["workspace_id"]), "backend", "synlynk", payload["lease_id"])
        RelayBroker().publish(EventEnvelope.create(actor, "milestone_lease_completed", payload))
    except Exception:
        pass
    return payload


def _parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
