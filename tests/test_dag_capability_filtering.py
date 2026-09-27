import pytest
from synlynk.capability_probe import CAP_SHELL, CAP_GH_WRITE
from synlynk.launch_dag import LaunchDAG, _next_failover_harness, DAGNode


def test_next_failover_harness_skips_incapable_harness():
    # If a task requires shell and gh-write, failover from codex must NOT select grok even if grok is next in chain
    next_h = _next_failover_harness(
        current="codex",
        failed_list=[],
        required_capabilities={CAP_SHELL, CAP_GH_WRITE},
    )
    assert next_h in ("agy", "claude")
    assert next_h != "grok"


def test_launch_dag_build_from_stories_filters_incapable_harness():
    dag = LaunchDAG()
    story = {
        "story_id": "story-gh-ops",
        "title": "Review and merge pull requests",
        "role": "marketing", # marketing normally defaults to agy or grok
        "requires_gh_write": True,
    }
    dag.build_from_stories([story])
    
    impl_node = dag.get_node("impl:story-gh-ops")
    assert impl_node is not None
    # Node should be capable of gh write
    assert impl_node.harness in ("codex", "agy", "claude")
    assert impl_node.harness != "grok"


def test_launch_dag_failover_on_outcome_respects_capabilities():
    dag = LaunchDAG()
    node = DAGNode(
        node_id="impl:test",
        story_id="test",
        stage="implement",
        harness="codex",
        required_capabilities={CAP_SHELL, CAP_GH_WRITE},
    )
    dag.nodes[node.node_id] = node

    # When codex trips breaker, it should failover to agy or claude, not grok
    dag.handle_job_outcome("impl:test", "circuit_breaker_tripped")
    assert node.harness in ("agy", "claude")
    assert node.harness != "grok"
