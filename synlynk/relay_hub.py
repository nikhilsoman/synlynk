"""Opt-in NATS-backed hub bridge for the local relay (synlynk/relay.py).

Credential model deviation from the design spec (docs/superpowers/specs/
2026-10-12-personal-hosted-relay-design.md): per-device bearer tokens scoped
via NATS `authorization { users: [...] }` permission blocks, not nkey+JWT.
Real nkey/JWT minting needs the `nsc` toolchain and is deferred until a
multi-tenant managed hub actually requires it. See plan's "Decision Flagged
for Review" section for full rationale.

`nats-py` is an optional dependency (pyproject.toml `[hub]` extra) and is
imported lazily inside functions that need it, so importing this module
(or synlynk's core CLI) never requires it to be installed.
"""

from __future__ import annotations

from collections.abc import Mapping

from synlynk.events import ActorIdentifier


def _import_nats():
    try:
        import nats  # noqa: F401
        return nats
    except ImportError as exc:
        raise RuntimeError(
            "Hub features require the optional 'hub' extra: "
            "pip install 'synlynk[hub]'"
        ) from exc


RETENTION_POLICIES = {
    "job": {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600},
    "sentinel": {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600},
    "agent": {"max_msgs": 2_000, "max_age_seconds": 48 * 3600},
    "device": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
    "doc": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
    "custom": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
}

_EVENT_SUFFIXES = {
    "review_requested": "job.review_requested",
    "agent_started": "job.agent_started",
    "agent_completed": "job.agent_completed",
    "governs_stage_advanced": "job.governs_stage_advanced",
    "doc_drafted": "doc.drafted",
    "doc_updated": "doc.updated",
    "hub_disconnected": "device.local.hub_disconnected",
    "sync_gap_detected": "device.local.sync_gap_detected",
}


def _subject_segment(value: str, field: str) -> str:
    """Require one literal subject token; never normalize an invalid identity."""
    if not isinstance(value, str) or not value or any(
        char in ".*>" or char.isspace() or not char.isprintable()
        for char in value
    ):
        raise ValueError(f"{field} must be a non-empty literal subject segment")
    return value


def subject_for_event(
    workspace_id: str,
    event_type: str,
    payload: dict,
    sender: ActorIdentifier | Mapping | None = None,
) -> str:
    """Translate an event into a concrete workspace-scoped publish subject.

    Sender identity takes precedence over payload metadata, with missing keys
    falling back to the payload, then 'unknown'. Explicit invalid values fail.
    Plain task_progress remains a job event; runner_progress uses the spec's
    agent.<harness>.progress route. This does not validate EventEnvelope types.
    """
    workspace_id = _subject_segment(workspace_id, "workspace_id")
    event_type = _subject_segment(event_type, "event_type")
    suffix = _EVENT_SUFFIXES.get(event_type, f"custom.{event_type}")
    if event_type in {"task_progress", "runner_progress"}:
        metadata = sender.to_dict() if isinstance(sender, ActorIdentifier) else sender
        metadata = metadata if metadata is not None else {}
        identity = {
            key: _subject_segment(metadata.get(key, payload.get(key, "unknown")), key)
            for key in ("harness", "agent_role")
        }
        if event_type == "runner_progress":
            suffix = f"agent.{identity['harness']}.progress"
        elif any(key in metadata or key in payload for key in identity):
            suffix = f"agent.{identity['harness']}.{identity['agent_role']}"
        else:
            suffix = "job.task_progress"
    elif event_type == "steering_injected":
        device = _subject_segment(payload.get("target_device_id", "unknown"), "target_device_id")
        suffix = f"device.{device}.steering"
    return f"synlynk.{workspace_id}.{suffix}"


def category_for_subject(subject: str) -> str:
    """Return a known category of a concrete subject, or custom if malformed."""
    parts = subject.split(".")
    if len(parts) < 4 or parts[0] != "synlynk" or parts[2] not in RETENTION_POLICIES:
        return "custom"
    try:
        for part in parts:
            _subject_segment(part, "subject")
    except ValueError:
        return "custom"
    return parts[2]
