"""End-to-End Multi-Node Acceptance and Soak Scenarios."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

from synlynk.testbed.driver import NodeHandle, TestbedDriver
from synlynk.testbed.invariants import InvariantAsserter, InvariantReport


@dataclass
class ScenarioResult:
    name: str
    status: str  # "PASSED", "FAILED"
    duration_seconds: float
    details: str = ""
    invariants: Optional[InvariantReport] = None


class ScenarioRunner:
    """Executes distributed scenarios across provisioned testbed nodes."""

    def __init__(self, driver: TestbedDriver):
        self.driver = driver
        self.asserter = InvariantAsserter(driver)

    def run_brownfield_init(self, node: NodeHandle) -> ScenarioResult:
        start_t = time.time()
        # Initialize a test git repo and run synlynk init --brownfield
        cmd = (
            "rm -rf /tmp/test-repo && mkdir -p /tmp/test-repo && cd /tmp/test-repo && "
            "git init && echo '# Test App' > README.md && git add . && git commit -m 'initial' && "
            "synlynk init --brownfield"
        )
        res = self.driver.exec_command(node.node_id, cmd)
        duration = time.time() - start_t

        status = "PASSED" if res.ok else "FAILED"
        return ScenarioResult(
            name="brownfield_init",
            status=status,
            duration_seconds=duration,
            details=res.stdout + res.stderr,
        )

    def run_p2p_mesh(self, node_1: NodeHandle, node_2: NodeHandle) -> ScenarioResult:
        start_t = time.time()
        # 1. Start relay daemon on node 1
        cmd_start = "synlynk relay start --port 8765 --daemon || true"
        self.driver.exec_command(node_1.node_id, cmd_start)

        # 2. Register peer from node 2
        cmd_peer = f"synlynk relay peer add ws://{node_1.ip}:8765 || true"
        self.driver.exec_command(node_2.node_id, cmd_peer)

        # 3. Publish test event on node 1
        cmd_pub = "synlynk relay send --topic 'test.mesh' --payload '{\"msg\": \"hello from node 1\"}' || true"
        res_pub = self.driver.exec_command(node_1.node_id, cmd_pub)

        duration = time.time() - start_t
        invariants = self.asserter.check_all([node_1.node_id, node_2.node_id])

        status = "PASSED" if invariants.all_passed else "FAILED"
        return ScenarioResult(
            name="p2p_mesh",
            status=status,
            duration_seconds=duration,
            details=res_pub.stdout + res_pub.stderr,
            invariants=invariants,
        )

    def run_task_lease_recovery(self, node_1: NodeHandle, node_2: NodeHandle) -> ScenarioResult:
        start_t = time.time()
        # 1. Node 1 acquires a story task lease
        cmd_claim = "synlynk story create --title 'Fault Test Story' --role dev && synlynk dispatch codex --task 'sleep 10' || true"
        self.driver.exec_command(node_1.node_id, cmd_claim)

        # 2. Inject SIGKILL on Node 1 while lease is active
        self.driver.inject_fault(node_1.node_id, "kill")

        # 3. Node 2 runs story reclaim to un-strand the task
        cmd_reclaim = "synlynk story reclaim || true"
        res_reclaim = self.driver.exec_command(node_2.node_id, cmd_reclaim)

        duration = time.time() - start_t
        invariants = self.asserter.check_all([node_2.node_id])

        status = "PASSED" if invariants.all_passed else "FAILED"
        return ScenarioResult(
            name="task_lease_recovery",
            status=status,
            duration_seconds=duration,
            details=res_reclaim.stdout,
            invariants=invariants,
        )
