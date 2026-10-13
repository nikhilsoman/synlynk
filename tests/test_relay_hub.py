import subprocess
import sys

import pytest

from synlynk.events import ActorIdentifier, EventEnvelope
from synlynk.relay_hub import RETENTION_POLICIES, category_for_subject, subject_for_event


@pytest.mark.parametrize("event_type,suffix", [
    ("review_requested", "job.review_requested"),
    ("agent_started", "job.agent_started"),
    ("agent_completed", "job.agent_completed"),
    ("governs_stage_advanced", "job.governs_stage_advanced"),
    ("task_progress", "job.task_progress"),
    ("runner_progress", "agent.unknown.progress"),
    ("steering_injected", "device.unknown.steering"),
    ("doc_drafted", "doc.drafted"),
    ("doc_updated", "doc.updated"),
    ("hub_disconnected", "device.local.hub_disconnected"),
    ("sync_gap_detected", "device.local.sync_gap_detected"),
    ("goal_realigned", "custom.goal_realigned"),
    ("artifact_published", "custom.artifact_published"),
])
def test_subject_event_taxonomy(event_type, suffix):
    assert subject_for_event("ws1", event_type, {}) == f"synlynk.ws1.{suffix}"


@pytest.mark.parametrize("payload,suffix", [
    ({"harness": "codex", "agent_role": "dev"}, "agent.codex.dev"),
    ({"harness": "codex"}, "agent.codex.unknown"),
    ({"agent_role": "dev"}, "agent.unknown.dev"),
])
def test_progress_payload_metadata(payload, suffix):
    original = dict(payload)
    assert subject_for_event("ws1", "task_progress", payload) == f"synlynk.ws1.{suffix}"
    assert payload == original


@pytest.mark.parametrize("serialized", [False, True])
def test_progress_sender_metadata_takes_precedence(serialized):
    actor = ActorIdentifier("ws1", "m", "dev", "codex", "j1")
    sender = actor.to_dict() if serialized else actor
    payload = {"harness": "other", "agent_role": "other"}
    assert subject_for_event("ws1", "task_progress", payload, sender=sender) == "synlynk.ws1.agent.codex.dev"
    assert subject_for_event("ws1", "runner_progress", {}, sender=sender) == "synlynk.ws1.agent.codex.progress"


def test_partial_sender_falls_back_to_payload_without_mutation():
    sender = {"harness": "codex"}
    payload = {"agent_role": "dev"}
    assert subject_for_event("ws1", "task_progress", payload, sender=sender) == "synlynk.ws1.agent.codex.dev"
    assert sender == {"harness": "codex"}
    assert payload == {"agent_role": "dev"}
    assert subject_for_event("ws1", "task_progress", {}, sender={}) == "synlynk.ws1.job.task_progress"


def test_runner_progress_uses_payload_harness():
    assert subject_for_event("ws1", "runner_progress", {"harness": "codex"}) == "synlynk.ws1.agent.codex.progress"


def test_steering_targets_device():
    assert subject_for_event("ws1", "steering_injected", {"target_device_id": "dev-42"}) == "synlynk.ws1.device.dev-42.steering"


@pytest.mark.parametrize("bad", ["", "a.b", "*", ">", "a b", "a\t", "a\n", "a\u00a0b", "a\x00b", None, 42])
@pytest.mark.parametrize("field", ["workspace_id", "event_type", "target_device_id", "harness", "agent_role"])
def test_subject_segments_reject_injection(field, bad):
    workspace, event, payload = "ws1", "task_progress", {}
    if field == "workspace_id":
        workspace = bad
    elif field == "event_type":
        event = bad
    else:
        payload[field] = bad
        if field == "target_device_id":
            event = "steering_injected"
    with pytest.raises(ValueError, match=field):
        subject_for_event(workspace, event, payload)


@pytest.mark.parametrize("field", ["harness", "agent_role"])
def test_sender_segments_are_validated(field):
    with pytest.raises(ValueError, match=field):
        subject_for_event("ws1", "task_progress", {}, sender={field: "bad.*"})


@pytest.mark.parametrize("category", ["job", "sentinel", "agent", "device", "doc", "custom"])
def test_category_for_subject(category):
    assert category_for_subject(f"synlynk.ws1.{category}.topic") == category


@pytest.mark.parametrize("subject", ["", "synlynk", "synlynk.ws1", "synlynk.ws1.job", "other.ws1.job.topic", "synlynk..job.topic", "synlynk.ws1.unknown.topic", "synlynk.ws1.job.*", "synlynk.ws1.job.bad topic"])
def test_category_for_malformed_subject_falls_back(subject):
    assert category_for_subject(subject) == "custom"


def test_all_retention_budgets():
    assert RETENTION_POLICIES == {
        "job": {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600},
        "sentinel": {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600},
        "agent": {"max_msgs": 2_000, "max_age_seconds": 48 * 3600},
        "device": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
        "doc": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
        "custom": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
    }


@pytest.mark.parametrize("event_type", (
    "hub_disconnected",
    "sync_gap_detected",
    "doc_drafted",
    "doc_updated",
))
def test_hub_event_types_are_accepted_by_envelope(event_type):
    actor = ActorIdentifier(
        workspace_id="ws", member_id="m", agent_role="dev",
        harness="codex", job_id="j1",
    )
    envelope = EventEnvelope.create(actor, event_type, {})
    assert envelope.event_type == event_type


def test_core_cli_import_does_not_require_nats():
    """synlynk's core CLI must import cleanly with no nats-py installed --
    hub features are optional, the base CLI is stdlib-only (CLAUDE.md constraint).
    """
    result = subprocess.run(
        [sys.executable, "-c", "import synlynk; import synlynk.cli"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_relay_hub_module_importable_without_nats_installed():
    """Importing synlynk.relay_hub itself must not require nats-py at import time --
    only calling HubAdapter.connect() should need it.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import synlynk.relay_hub"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
