import json

from synlynk.harness_adapters.muse import MuseAdapter
from synlynk.harness_adapters.request import DispatchRequest


def test_muse_translate_permissions_empty_returns_empty():
    adapter = MuseAdapter()
    assert adapter.translate_permissions([], read_only=False) == []


def test_muse_translate_permissions_grants_return_empty():
    adapter = MuseAdapter()
    assert adapter.translate_permissions(["write:src/", "read:*"], read_only=False) == []


def test_muse_build_cmd_includes_exec_flags():
    adapter = MuseAdapter()
    req = DispatchRequest(agent="muse", task="implement feature", permissions=["write:src/"])
    cmd = adapter.build_cmd(req)
    assert "--json" in cmd
    assert "--approval-mode" in cmd
    assert "never" in cmd
    assert "--dangerously-skip-permissions" not in cmd
    assert "--always-approve" not in cmd
    assert "--non-interactive" not in cmd
    assert "-C" not in cmd


def test_muse_build_cmd_skip_permissions():
    adapter = MuseAdapter()
    req = DispatchRequest(agent="muse", task="implement feature", skip_permissions=True)
    cmd = adapter.build_cmd(req)
    assert "--json" in cmd
    assert "--approval-mode" in cmd
    assert "never" in cmd
    assert "--dangerously-skip-permissions" not in cmd
    assert "--always-approve" not in cmd


def test_muse_classify_failure():
    adapter = MuseAdapter()
    assert adapter.classify_failure(1, "missing api key", "").value == "auth_expired"
    assert adapter.classify_failure(1, "429 rate limit exceeded", "").value == "quota_exhausted"
    assert adapter.classify_failure(1, "sandbox access denied", "").value == "sandbox_denied"
    assert adapter.classify_failure(0, "", "all good") is None


def test_muse_parse_output_populates_lifecycle_and_compatibility_evidence():
    lifecycle_event = {
        "event_type": "terminal",
        "job_id": "job-1",
        "contract_id": "c",
        "event_id": "e-1",
        "sequence": 1,
        "harness": "muse",
        "role": "dev",
        "process_result": {"exit_code": 0},
    }
    raw = "SYNLYNK_TASK_RECEIVED: digest\nSYNLYNK_LIFECYCLE_EVENT: " + json.dumps(lifecycle_event)

    parsed = MuseAdapter().parse_output(raw)

    assert len(parsed.lifecycle_events) == 1
    assert parsed.compatibility_evidence["compatibility"] is True
    assert parsed.compatibility_evidence["receipt"] == "digest"


def test_muse_resolve_model():
    adapter = MuseAdapter()
    assert adapter.resolve_model("pro", None) == "muse-spark-1.3"
    assert adapter.resolve_model("fast", None) == "muse-spark-1.3"
