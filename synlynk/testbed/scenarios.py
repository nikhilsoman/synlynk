"""End-to-End Multi-Node Acceptance and Soak Scenarios."""
from __future__ import annotations

import os
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

    def __init__(self, driver: Optional[TestbedDriver] = None):
        self.driver = driver
        self.asserter = InvariantAsserter(driver) if driver is not None else None

    def run_brownfield_init(self, node: NodeHandle) -> ScenarioResult:
        start_t = time.time()
        uid = os.getuid() if hasattr(os, "getuid") else "0"
        repo_dir = f"/tmp/synlynk-{uid}/test-repo"
        # Initialize a test git repo and run synlynk init --brownfield
        cmd = (
            f"rm -rf {repo_dir} && mkdir -p -m 0700 {repo_dir} && cd {repo_dir} && "
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

    def run_state_db_wal_soak(
        self,
        db_path: str,
        writers: int = 24,
        readers: int = 8,
        ops_per_writer: int = 8,
        executor: str = "thread",
    ) -> ScenarioResult:
        """Local (no VM) soak of 20–50 concurrent writers against isolated state.db."""
        from synlynk.testbed.state_db_soak import SoakConfig, run_state_db_soak

        start_t = time.time()
        report = run_state_db_soak(
            SoakConfig(
                db_path=db_path,
                writers=writers,
                readers=readers,
                ops_per_writer=ops_per_writer,
                executor=executor,
            )
        )
        duration = time.time() - start_t
        return ScenarioResult(
            name="state_db_wal_soak",
            status="PASSED" if report.passed else "FAILED",
            duration_seconds=duration,
            details=report.to_json(),
        )

    def run_review_gate_matrix(self, conn) -> List[ScenarioResult]:
        """Local (no VM) matrix proving which identity shapes satisfy cross-harness review.

        Team identities are paired with a distinct teammate reviewer (the realistic
        case); solo/edge identities are paired with themselves, since that is the
        literal condition this scenario reproduces -- one harness account, no second identity to review with.
        Caller is responsible for cwd (policy.json lookup) and for
        passing an already-migrated connection, matching
        synlynk.db._cross_harness_review_verdict's own contract.
        """
        from synlynk.db import _cross_harness_review_verdict
        from synlynk.testbed.identities import STANDARD_IDENTITIES, SOLO_AND_EDGE_IDENTITIES

        alice = STANDARD_IDENTITIES["node-1"]
        bob = STANDARD_IDENTITIES["node-2"]
        charlie = STANDARD_IDENTITIES["node-3"]
        solo_claude = SOLO_AND_EDGE_IDENTITIES["solo_claude"]
        gateway_poweruser = SOLO_AND_EDGE_IDENTITIES["gateway_poweruser"]
        ci_headless = SOLO_AND_EDGE_IDENTITIES["ci_headless"]

        pairings = [
            (9001, alice, charlie),
            (9002, bob, charlie),
            (9003, charlie, alice),
            (9004, solo_claude, solo_claude),
            (9005, gateway_poweruser, gateway_poweruser),
            (9006, ci_headless, ci_headless),
        ]

        results: List[ScenarioResult] = []
        for pr_number, implementer, reviewer in pairings:
            start_t = time.time()
            conn.execute(
                "INSERT INTO cost_entries (session_date, agent, harness, model, cost_source, pr_number) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("2026-11-21", implementer.harness, implementer.harness, implementer.model, "test", pr_number),
            )
            conn.execute(
                "INSERT INTO cost_entries (session_date, agent, harness, model, cost_source, pr_number, agent_role) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("2026-11-21", reviewer.harness, reviewer.harness, reviewer.model, "test", pr_number, "qa"),
            )
            conn.commit()
            ok, message = _cross_harness_review_verdict(conn, pr_number)
            duration = time.time() - start_t
            results.append(ScenarioResult(
                name=f"review_gate_matrix:{implementer.username}",
                status="PASSED" if ok else "FAILED",
                duration_seconds=duration,
                details=message,
            ))
        return results
