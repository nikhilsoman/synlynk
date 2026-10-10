"""Versioned structured lifecycle telemetry and its append-only ingestion.

Lifecycle events are observations.  They may describe a terminal decision or
correction, but they never settle the job themselves; ``job_truth`` remains
the sole terminal decision writer.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "lifecycle.v1"
EVENT_TYPES = frozenset(
    {"queued", "running", "observing", "verifying", "terminal", "correction"}
)
_ORDER = {name: index for index, name in enumerate(("queued", "running", "observing", "verifying", "terminal", "correction"))}
EVENT_PREFIX = "SYNLYNK_LIFECYCLE_EVENT:"


@dataclass(frozen=True)
class LifecycleEvent:
    event_type: str
    job_id: str
    contract_id: str
    contract_version: int
    event_id: str
    sequence: int
    harness: str
    role: str
    process_result: Mapping[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    occurred_at: str = ""
    schema_version: str = SCHEMA_VERSION
    compatibility: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported lifecycle schema: {self.schema_version!r}")
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported lifecycle event type: {self.event_type!r}")
        if not self.job_id or not self.contract_id or not self.event_id:
            raise ValueError("lifecycle events require job_id, contract_id, and event_id")
        if self.sequence < 0:
            raise ValueError("lifecycle event sequence must be non-negative")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "job_id": self.job_id,
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "event_id": self.event_id,
            "sequence": self.sequence,
            "harness": self.harness,
            "role": self.role,
            "process_result": dict(self.process_result),
            "evidence_refs": list(self.evidence_refs),
            "occurred_at": self.occurred_at or _now(),
            "compatibility": self.compatibility,
        }


def make_event(
    event_type: str,
    job_id: str,
    *,
    contract_id: str = "unknown_contract",
    contract_version: int = 1,
    sequence: int = 0,
    harness: str = "unknown",
    role: str = "unknown",
    process_result: Mapping[str, Any] | None = None,
    evidence_refs: Iterable[str] = (),
    event_id: str | None = None,
    occurred_at: str | None = None,
    compatibility: bool = False,
) -> LifecycleEvent:
    return LifecycleEvent(
        event_type=event_type,
        job_id=job_id,
        contract_id=contract_id,
        contract_version=int(contract_version),
        event_id=event_id or f"event-{uuid.uuid4().hex}",
        sequence=int(sequence),
        harness=harness,
        role=role,
        process_result=dict(process_result or {}),
        evidence_refs=tuple(str(ref) for ref in evidence_refs),
        occurred_at=occurred_at or _now(),
        compatibility=compatibility,
    )


def parse_output(raw_text: str) -> tuple[LifecycleEvent, ...]:
    """Parse only explicit structured events from harness output.

    Text such as ``SYNLYNK_TASK_RECEIVED`` is deliberately not parsed as a
    lifecycle event; callers can retain it as compatibility evidence.
    """
    events: list[LifecycleEvent] = []
    for line in (raw_text or "").splitlines():
        candidate = line.strip()
        if candidate.startswith(EVENT_PREFIX):
            candidate = candidate[len(EVENT_PREFIX):].strip()
        elif not (candidate.startswith("{") and '"event_type"' in candidate):
            continue
        try:
            payload = json.loads(candidate)
            if not isinstance(payload, dict):
                continue
            events.append(
                make_event(
                    payload["event_type"], payload["job_id"],
                    contract_id=payload.get("contract_id", "unknown_contract"),
                    contract_version=payload.get("contract_version", 1),
                    event_id=payload.get("event_id"), sequence=payload.get("sequence", 0),
                    harness=payload.get("harness", "unknown"), role=payload.get("role", "unknown"),
                    process_result=payload.get("process_result") or {},
                    evidence_refs=payload.get("evidence_refs") or (),
                    occurred_at=payload.get("occurred_at"),
                    compatibility=bool(payload.get("compatibility", False)),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return tuple(events)


def compatibility_evidence(raw_text: str) -> dict[str, Any]:
    """Return legacy receipt/text evidence without treating it as lifecycle truth."""
    lines = (raw_text or "").splitlines()
    receipt = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("SYNLYNK_TASK_RECEIVED:")), None)
    return {
        "kind": "legacy_stdout",
        "result": "true" if receipt else "unknown",
        "source": "legacy_stdout",
        "compatibility": True,
        "receipt": receipt,
        "parse_failures": sum(1 for line in lines if line.startswith(EVENT_PREFIX) and _json_invalid(line)),
    }


def ingest_events(conn: sqlite3.Connection, events: Iterable[LifecycleEvent]) -> list[dict[str, Any]]:
    """Idempotently append events; retain out-of-order observations as rejected."""
    results = []
    for event in events:
        payload = event.as_dict()
        existing = conn.execute("SELECT event_id FROM job_lifecycle_event WHERE event_id=?", (event.event_id,)).fetchone()
        if existing:
            results.append({"event_id": event.event_id, "accepted": False, "duplicate": True})
            continue
        latest = conn.execute(
            "SELECT MAX(sequence) FROM job_lifecycle_event WHERE job_id=? AND accepted=1", (event.job_id,)
        ).fetchone()[0]
        accepted = latest is None or event.sequence > latest
        reason = None if accepted else "out_of_order"
        conn.execute(
            """INSERT INTO job_lifecycle_event
               (event_id, job_id, contract_id, contract_version, event_type, sequence,
                harness, role, process_result_json, evidence_refs_json, occurred_at,
                schema_version, compatibility, accepted, rejection_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event.event_id, event.job_id, event.contract_id, event.contract_version,
             event.event_type, event.sequence, event.harness, event.role,
             json.dumps(event.process_result, sort_keys=True), json.dumps(list(event.evidence_refs)),
             payload["occurred_at"], event.schema_version, int(event.compatibility), int(accepted), reason),
        )
        results.append({"event_id": event.event_id, "accepted": accepted, "reason": reason})
    conn.commit()
    return results


def ingest_output(conn: sqlite3.Connection, raw_text: str) -> dict[str, Any]:
    events = parse_output(raw_text)
    return {"events": ingest_events(conn, events), "compatibility": compatibility_evidence(raw_text)}


def _json_invalid(line: str) -> bool:
    try:
        json.loads(line[len(EVENT_PREFIX):].strip())
        return False
    except (TypeError, ValueError, json.JSONDecodeError):
        return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
