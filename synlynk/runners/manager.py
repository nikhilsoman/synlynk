"""Driver registry and durable swarm-runner records."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from synlynk import load_config
from synlynk.runners.base import SwarmRunnerDriver


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunnerManager:
    """Load configured drivers and keep their lifecycle visible in SQLite."""

    def __init__(self, config=None, conn=None):
        self.config = config if config is not None else load_config()
        self.conn = conn
        self.drivers = {}
        self._load_drivers()

    def _load_drivers(self):
        from synlynk.runners.local import LocalRunnerDriver

        runner_config = self.config.get("swarm_runners", {})
        enabled = runner_config.get("enabled", ["local"])
        if isinstance(enabled, str):
            enabled = [enabled]
        if "local" in enabled:
            self.drivers["local"] = LocalRunnerDriver(
                timeout_seconds=runner_config.get("timeout_seconds", 900)
            )
        if "fly" in enabled or "fly" in runner_config:
            from synlynk.runners.fly import FlyRunnerDriver
            self.drivers["fly"] = FlyRunnerDriver(runner_config.get("fly", {}))

    def driver(self, name=None) -> SwarmRunnerDriver:
        name = name or self.config.get("swarm_runners", {}).get("default", "local")
        try:
            return self.drivers[name]
        except KeyError as exc:
            raise ValueError(f"Unknown swarm runner driver {name!r}") from exc

    get_driver = driver

    def provision(self, job_spec, driver=None) -> str:
        driver_name = driver or job_spec.get("driver") or self.config.get("swarm_runners", {}).get("default", "local")
        impl = self.driver(driver_name)
        runner_id = impl.provision(job_spec)
        if self.conn is not None:
            self.conn.execute(
                "INSERT OR REPLACE INTO swarm_runners "
                "(runner_id, driver, status, job_spec, provisioned_at) VALUES (?, ?, ?, ?, ?)",
                (runner_id, driver_name, "running", json.dumps(job_spec), _now()),
            )
            self.conn.commit()
        return runner_id

    def list(self, *, include_destroyed=False):
        if self.conn is None:
            return []
        query = "SELECT * FROM swarm_runners"
        if not include_destroyed:
            query += " WHERE status != 'destroyed'"
        query += " ORDER BY provisioned_at DESC"
        cursor = self.conn.execute(query)
        return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]

    def destroy(self, runner_id, driver=None) -> bool:
        impl = self.driver(driver or self._record(runner_id).get("driver"))
        result = bool(impl.destroy(runner_id))
        if result and self.conn is not None:
            self.conn.execute(
                "UPDATE swarm_runners SET status='destroyed', destroyed_at=? WHERE runner_id=?",
                (_now(), runner_id),
            )
            self.conn.commit()
        return result

    def _record(self, runner_id):
        if self.conn is None:
            return {}
        cursor = self.conn.execute("SELECT * FROM swarm_runners WHERE runner_id=?", (runner_id,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Unknown swarm runner {runner_id!r}")
        return dict(zip([column[0] for column in cursor.description], row))
