import json

from synlynk.harness_adapters.agy import AgyAdapter


def test_agy_translate_permissions_read_only_uses_plan_mode():
    adapter = AgyAdapter()
    flags = adapter.translate_permissions(["read:*"], read_only=False)
    assert flags == ["--mode", "plan"]


def test_agy_translate_permissions_no_permissions_returns_empty():
    adapter = AgyAdapter()
    assert adapter.translate_permissions([], read_only=False) == []


def test_agy_translate_permissions_write_grant_uses_sandbox():
    adapter = AgyAdapter()
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags == ["--sandbox"]


def test_agy_classify_failure_credit_exhaustion_regression_fixture():
    """Regression fixture: this session's 429 RESOURCE_EXHAUSTED AI credits balance."""
    adapter = AgyAdapter()
    raw = 'RESOURCE_EXHAUSTED (code 429) "Your AI credits balance is too low to continue."'
    result = adapter.classify_failure(exit_code=1, stderr=raw, raw_text=raw)
    assert result.value == "quota_exhausted"


def test_agy_parse_output_populates_lifecycle_and_compatibility_evidence():
    lifecycle_event = {
        "event_type": "terminal",
        "job_id": "job-1",
        "contract_id": "c",
        "event_id": "e-1",
        "sequence": 1,
        "harness": "agy",
        "role": "dev",
        "process_result": {"exit_code": 0},
    }
    raw = "SYNLYNK_TASK_RECEIVED: digest\nSYNLYNK_LIFECYCLE_EVENT: " + json.dumps(lifecycle_event)

    parsed = AgyAdapter().parse_output(raw)

    assert len(parsed.lifecycle_events) == 1
    assert parsed.compatibility_evidence["compatibility"] is True
    assert parsed.compatibility_evidence["receipt"] == "digest"
