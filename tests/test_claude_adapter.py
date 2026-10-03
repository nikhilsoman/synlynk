import json

from synlynk.harness_adapters.claude import ClaudeAdapter
from synlynk.harness_adapters.request import DispatchRequest


def test_claude_translate_permissions_maps_tools():
    adapter = ClaudeAdapter()
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags[0] == "--allowedTools"


def test_claude_translate_permissions_empty_returns_empty():
    adapter = ClaudeAdapter()
    assert adapter.translate_permissions([], read_only=False) == []


def test_claude_build_cmd_includes_dispatch_flags():
    cmd = ClaudeAdapter().build_cmd(DispatchRequest(agent="claude", task="fix it", permissions=["write:src/"]))
    assert "--allowedTools" in cmd


def test_claude_parse_output_populates_lifecycle_and_compatibility_evidence():
    lifecycle_event = {
        "event_type": "terminal", "job_id": "job-1", "contract_id": "c",
        "event_id": "e-1", "sequence": 1, "harness": "claude", "role": "dev",
        "process_result": {"exit_code": 0},
    }
    raw = "SYNLYNK_TASK_RECEIVED: digest\nSYNLYNK_LIFECYCLE_EVENT: " + json.dumps(lifecycle_event)
    parsed = ClaudeAdapter().parse_output(raw)
    assert len(parsed.lifecycle_events) == 1
    assert parsed.compatibility_evidence["compatibility"] is True
    assert parsed.compatibility_evidence["receipt"] == "digest"


def test_claude_classify_failure_returns_none():
    assert ClaudeAdapter().classify_failure(1, "unrelated error", "") is None


def test_claude_resolve_model():
    assert ClaudeAdapter().resolve_model("fast", None)
