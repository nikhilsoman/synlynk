"""Unit tests for DAG failover on circuit breaker trip (Invariant 2)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.jobs import STATUS_CIRCUIT_BREAKER_TRIPPED
from synlynk.launch_dag import LaunchDAG, DAGNode


def test_handle_job_outcome_fails_over_on_circuit_breaker():
    dag = LaunchDAG()

    node = DAGNode(
        node_id="node-cb-test",
        story_id="story-cb-1",
        stage="implement",
        owner_role="builder",
        harness="codex",
        status="running",
        max_retries=2,
    )
    dag.nodes[node.node_id] = node

    # Handle circuit breaker trip
    failed_over = dag.handle_job_outcome(
        node_id="node-cb-test",
        status=STATUS_CIRCUIT_BREAKER_TRIPPED,
        error="Token limit breached: 350,000 > 300,000",
    )

    assert failed_over is True
    assert node.status == "ready"
    assert node.retry_count == 1
    assert "codex" in node.failed_harnesses
    assert node.harness == "agy"  # Next in failover chain: codex -> agy -> claude -> grok
    assert "circuit breaker" in node.error.lower() or "token limit" in node.error.lower()


def test_handle_job_outcome_exhausted_retries_on_circuit_breaker():
    dag = LaunchDAG()

    node = DAGNode(
        node_id="node-cb-exhausted",
        story_id="story-cb-2",
        stage="implement",
        owner_role="builder",
        harness="codex",
        status="running",
        retry_count=2,
        max_retries=2,
    )
    dag.nodes[node.node_id] = node

    failed_over = dag.handle_job_outcome(
        node_id="node-cb-exhausted",
        status=STATUS_CIRCUIT_BREAKER_TRIPPED,
        error="Cost limit breached: $5.50 > $3.00",
    )

    assert failed_over is False
    assert node.status == "failed"
    assert "retries exhausted" in node.error.lower()
