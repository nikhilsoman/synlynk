import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from synlynk.events import ActorIdentifier, EventEnvelope
from synlynk.relay_hub import DeviceCredentialStore, RETENTION_POLICIES, category_for_subject, subject_for_event


def test_device_credentials_persist_with_private_files(tmp_path):
    store = DeviceCredentialStore("ws1", tmp_path)
    cred = store.add_device("laptop")
    other = store.add_device("desktop")
    assert cred.device_id != other.device_id
    assert len(cred.token) >= 32 and cred.token != other.token
    assert cred.publish_subjects == cred.subscribe_subjects == ["synlynk.ws1.>"]
    assert cred.revoked is False
    reopened = DeviceCredentialStore("ws1", tmp_path)
    assert reopened.get_device(cred.device_id) == cred
    assert reopened.list_devices() == [cred, other]
    assert reopened.get_device("missing") is None
    path = tmp_path / f"{cred.device_id}.creds"
    assert json.loads(path.read_text())["token"] == cred.token
    assert tmp_path.stat().st_mode & 0o777 == 0o700
    for path in (path, tmp_path / "devices.json", store.write_authorization_config()):
        assert path.stat().st_mode & 0o777 == 0o600


def test_revocation_is_persistent_idempotent_and_excluded(tmp_path):
    store = DeviceCredentialStore("ws1", tmp_path)
    active = store.add_device("laptop")
    revoked = store.add_device("old-vps")
    assert store.revoke_device(revoked.device_id) is True
    assert store.revoke_device(revoked.device_id) is False
    assert store.revoke_device("missing") is False
    store = DeviceCredentialStore("ws1", tmp_path)
    assert store.get_device(revoked.device_id).revoked is True
    block = store.render_authorization_block()
    assert active.token in block and active.device_id in block
    assert revoked.token not in block and revoked.device_id not in block
    assert json.loads((tmp_path / f"{revoked.device_id}.creds").read_text())["revoked"]


def test_registry_workspace_binding_even_when_empty(tmp_path):
    DeviceCredentialStore("ws1", tmp_path)
    with pytest.raises(ValueError, match="workspace"):
        DeviceCredentialStore("ws2", tmp_path)


def test_empty_registry_still_requires_authentication(tmp_path):
    store = DeviceCredentialStore("ws1", tmp_path)
    auth = json.loads(store.render_authorization_block().removeprefix("authorization "))
    # NATS treats an empty users list as authentication disabled.
    assert len(auth["users"]) == 1
    assert auth["users"][0]["permissions"] == {"publish": [], "subscribe": []}
    assert len(auth["users"][0]["password"]) >= 32


def test_registry_rejects_device_path_traversal(tmp_path):
    store = DeviceCredentialStore("ws1", tmp_path)
    cred = store.add_device("laptop")
    path = tmp_path / "devices.json"
    registry = json.loads(path.read_text())
    raw = registry["devices"].pop(cred.device_id)
    raw["device_id"] = "../outside"
    registry["devices"]["../outside"] = raw
    path.write_text(json.dumps(registry))
    with pytest.raises(ValueError, match="identity"):
        store.revoke_device("../outside")


@pytest.mark.parametrize("workspace", ["", "ws.*", ">", "two words", "ws\n"])
def test_credential_store_rejects_unsafe_workspace(tmp_path, workspace):
    with pytest.raises(ValueError, match="workspace"):
        DeviceCredentialStore(workspace, tmp_path)


def test_registry_rejects_cross_workspace_permissions(tmp_path):
    store = DeviceCredentialStore("ws1", tmp_path)
    cred = store.add_device("laptop")
    path = tmp_path / "devices.json"
    registry = json.loads(path.read_text())
    registry["devices"][cred.device_id]["publish_subjects"] = ["synlynk.ws2.>"]
    path.write_text(json.dumps(registry))
    with pytest.raises(ValueError, match="scope"):
        store.render_authorization_block()


def test_atomic_registry_failure_keeps_previous_data(tmp_path, monkeypatch):
    store = DeviceCredentialStore("ws1", tmp_path)
    cred = store.add_device("laptop")
    original = (tmp_path / "devices.json").read_bytes()
    real_replace = os.replace

    def fail_registry(source, destination):
        assert Path(source).stat().st_mode & 0o777 == 0o600
        if Path(destination).name == "devices.json":
            raise OSError("simulated write failure")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_registry)
    with pytest.raises(OSError, match="simulated"):
        store.add_device("desktop")
    assert (tmp_path / "devices.json").read_bytes() == original
    assert store.list_devices() == [cred]
    assert not list(tmp_path.glob("*.tmp"))


def test_secret_symlink_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("do not touch")
    directory = tmp_path / "hub"
    directory.mkdir()
    (directory / "devices.json").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        DeviceCredentialStore("ws1", directory)
    assert outside.read_text() == "do not touch"


@pytest.mark.parametrize("workspace", ["ws1", 'ws"quoted\\name'])
@pytest.mark.parametrize("active", [True, False])
def test_authorization_parses_with_real_nats(tmp_path, workspace, active):
    binary = Path("/private/tmp/synlynk-relay-bin/nats-server")
    if not binary.exists():
        pytest.skip("NATS config validation binary not installed")
    store = DeviceCredentialStore(workspace, tmp_path)
    cred = store.add_device("laptop")
    if not active:
        store.revoke_device(cred.device_id)
    config = store.write_authorization_config()
    result = subprocess.run([str(binary), "-t", "-c", str(config)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "token:" not in config.read_text()


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
