"""Unit tests for Autonomous Milestone Failover on No-Op Completion (Invariant 1)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.jobs import (
    STATUS_COMPLETED_WITHOUT_CHANGES,
    STATUS_FAILED_NOOP_DENIED,
    STATUS_FAILED_VERIFICATION,
)
from synlynk.launch_dag import DAGNode, LaunchDAG


def test_dag_node_has_failover_fields():
    node = DAGNode(
        node_id="impl:story-1",
        story_id="story-1",
        stage="implement",
        harness="codex",
    )
    assert hasattr(node, "retry_count")
    assert hasattr(node, "max_retries")
    assert hasattr(node, "failed_harnesses")
    assert node.retry_count == 0
    assert node.max_retries >= 1
    assert isinstance(node.failed_harnesses, list)


def test_launch_dag_failover_on_completed_without_changes():
    dag = LaunchDAG()
    stories = [{
        "story_id": "story-001",
        "title": "Implement feature X",
        "role": "builder",
    }]
    dag.build_from_stories(stories)
    impl_node = dag.get_node("impl:story-001")
    assert impl_node is not None
    assert impl_node.harness == "codex"
    
    token = dag.claim_node("impl:story-001")
    assert token is not None
    assert impl_node.status == "running"
    
    # Trigger no-op completion
    handled = dag.handle_job_outcome("impl:story-001", STATUS_COMPLETED_WITHOUT_CHANGES)
    assert handled is True
    
    # Verify node was failed over to secondary harness and reset to ready
    assert impl_node.status == "ready"
    assert impl_node.harness != "codex"
    assert "codex" in impl_node.failed_harnesses
    assert impl_node.retry_count == 1
    assert impl_node.lease_token is None


def test_launch_dag_failover_on_failed_noop_denied():
    dag = LaunchDAG()
    stories = [{
        "story_id": "story-002",
        "title": "Review PR",
        "role": "qa",
    }]
    dag.build_from_stories(stories)
    rev_node = dag.get_node("review:story-002")
    assert rev_node is not None
    
    dag.claim_node("review:story-002")
    handled = dag.handle_job_outcome("review:story-002", STATUS_FAILED_NOOP_DENIED)
    assert handled is True
    assert rev_node.status == "ready"
    assert rev_node.retry_count == 1


def test_launch_dag_failover_exhaustion_fails_node():
    dag = LaunchDAG()
    stories = [{
        "story_id": "story-003",
        "title": "Implement feature Y",
        "role": "builder",
    }]
    dag.build_from_stories(stories)
    impl_node = dag.get_node("impl:story-003")
    impl_node.max_retries = 2
    
    # Attempt 1
    dag.claim_node("impl:story-003")
    dag.handle_job_outcome("impl:story-003", STATUS_COMPLETED_WITHOUT_CHANGES)
    assert impl_node.retry_count == 1
    assert impl_node.status == "ready"
    
    # Attempt 2
    dag.claim_node("impl:story-003")
    dag.handle_job_outcome("impl:story-003", STATUS_COMPLETED_WITHOUT_CHANGES)
    assert impl_node.retry_count == 2
    assert impl_node.status == "ready"
    
    # Attempt 3 (exhausted)
    dag.claim_node("impl:story-003")
    dag.handle_job_outcome("impl:story-003", STATUS_COMPLETED_WITHOUT_CHANGES)
    assert impl_node.status in ("failed", "awaiting_approval")
    assert impl_node.retry_count >= 2


def test_launch_dag_successful_outcome_advances_node():
    dag = LaunchDAG()
    stories = [{
        "story_id": "story-004",
        "title": "Implement feature Z",
        "role": "builder",
    }]
    dag.build_from_stories(stories)
    impl_node = dag.get_node("impl:story-004")
    
    dag.claim_node("impl:story-004")
    dag.handle_job_outcome("impl:story-004", "succeeded")
    assert impl_node.status == "done"
    
    # Review node should now be ready
    rev_node = dag.get_node("review:story-004")
    assert rev_node.status == "ready"
