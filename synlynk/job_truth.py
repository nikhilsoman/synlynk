"""Canonical, side-effect-free job completion decisions and their ledger.

This module is intentionally small.  Adapters and product surfaces can add
observations, but only the functions here derive a terminal decision.
"""

from __future__ import annotations

import json
import hashlib
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping


class TriState(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


CANONICAL_STATUSES = frozenset({
    "completed", "completed_without_changes", "failed_noop_denied",
    "failed_verification", "permission_denied", "circuit_breaker_tripped",
    "cancelled", "killed_zombie", "timed_out", "task_delivery_failed",
    "failed", "unknown", "verifying",
})

# `unknown` and `verifying` are non-terminal projections even though they are
# persisted as decision revisions. Keep this explicit so a new status cannot
# silently enter or leave the cost-audit contract.
TERMINAL_STATUSES = CANONICAL_STATUSES - {"unknown", "verifying"}
TERMINAL_EVENT_SCHEMA = "job-terminal-decision.v1"

STATUS_ALIASES = {
    "succeeded": "completed", "success": "completed",
    "completed_noop": "completed_without_changes",
    "task_noop_denied": "failed_noop_denied",
    "verification_failed": "failed_verification",
    "access_denied": "permission_denied",
    "killed_by_breaker": "circuit_breaker_tripped",
    "done": "completed",
}

TERMINAL_WRITER_MANIFEST = {
    "flat_file_reconciliation": {
        "entrypoint": "_reconcile_jobs_unlocked",
        "adapter": "_record_job_truth_shadow",
    },
    "daemon_reconciliation": {
        "entrypoint": "_reconcile_daemon_jobs",
        "adapter": "_settle_daemon_job_terminal",
    },
    "terminal_json_reconciliation": {
        "entrypoint": "_reconcile_terminal_jobs_json",
        "adapter": "_settle_daemon_job_terminal",
    },
    "zombie_reaper": {
        "entrypoint": "mark_daemon_job_terminal",
        "adapter": "_settle_daemon_job_terminal",
    },
    "stranded_story_reclaimer": {
        "entrypoint": "reclaim_stranded_stories",
        "adapter": "_settle_daemon_job_terminal",
    },
    "queue_dependency_failure": {
        "entrypoint": "_dispatch_ready_jobs",
        "adapter": "_settle_daemon_job_terminal",
    },
}


def validate_terminal_writer_manifest() -> None:
    """Fail closed if a registered terminal writer bypasses the oracle adapter."""
    import inspect
    from synlynk import jobs

    for name, registration in TERMINAL_WRITER_MANIFEST.items():
        entrypoint = getattr(jobs, registration["entrypoint"], None)
        adapter = registration["adapter"]
        adapter_fn = getattr(jobs, adapter, None)
        if adapter == "record_evidence_and_reconcile":
            adapter_fn = record_evidence_and_reconcile
        if entrypoint is None or adapter_fn is None:
            raise AssertionError(f"terminal writer {name} is not registered: {registration}")
        entry_source = inspect.getsource(entrypoint)
        adapter_name = adapter if adapter == "record_evidence_and_reconcile" else adapter
        if adapter_name not in entry_source:
            raise AssertionError(
                f"terminal writer {name} bypasses the shared oracle adapter {adapter_name}"
            )


@dataclass(frozen=True)
class CompletionDecision:
    status: str
    verification_state: str
    reason_code: str
    required_follow_up: str = "none"
    evidence_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def canonical_status(status: str) -> str:
    value = str(status).strip().lower()
    value = STATUS_ALIASES.get(value, value)
    if value not in CANONICAL_STATUSES:
        raise ValueError(f"unknown canonical job status: {status!r}")
    return value


def build_github_effect_contract(
    job_id: str,
    *,
    operation: str,
    target: str,
    expected_actor: str | None = None,
    expected_sha: str | None = None,
    started_at: str | None = None,
    verification_deadline_seconds: int = 300,
    receipt_policy: str = "required",
    local_change_policy: str = "optional",
    contract_version: int = 1,
) -> dict[str, Any]:
    """Build an immutable, versioned contract for a GitHub side effect."""
    kinds = {
        "review": "github_review", "github_review": "github_review", "review_posted": "github_review",
        "comment": "github_comment", "issue_comment": "github_comment",
        "pr": "github_pr_open", "github_pr_open": "github_pr_open",
        "merge": "github_pr_merge", "github_pr_merge": "github_pr_merge", "merged": "github_pr_merge",
        "issue": "github_issue_open", "github_issue_open": "github_issue_open",
    }
    kind = kinds.get(operation.strip().lower(), operation.strip().lower())
    if kind not in {"github_review", "github_comment", "github_pr_open", "github_pr_merge", "github_issue_open"}:
        raise ValueError(f"unsupported GitHub contract operation: {operation!r}")
    if receipt_policy not in {"required", "optional", "waived"}:
        raise ValueError("receipt_policy must be required, optional, or waived")
    if local_change_policy not in {"required", "optional", "forbidden"}:
        raise ValueError("local_change_policy must be required, optional, or forbidden")
    return {
        "contract_id": f"contract-{uuid.uuid4().hex}",
        "job_id": job_id,
        "kind": kind,
        "target": target,
        "expect": "effect_verified",
        "local_change_policy": local_change_policy,
        "receipt_policy": receipt_policy,
        "verification_deadline_seconds": int(verification_deadline_seconds),
        "contract_version": int(contract_version),
        "started_at": started_at,
        "expected_actor": expected_actor,
        "expected_sha": expected_sha,
        "required_predicates": {
            "target_match": True,
            "actor_match": expected_actor is not None,
            "sha_match": expected_sha is not None,
        },
    }


def legacy_unknown_contract(job_id: str, *, started_at: str | None = None) -> dict[str, Any]:
    return {
        "contract_id": f"legacy-{job_id}", "job_id": job_id,
        "kind": "unknown_contract", "target": None, "expect": "unknown",
        "local_change_policy": "optional", "receipt_policy": "optional",
        "verification_deadline_seconds": 300, "contract_version": 1,
        "started_at": started_at, "expected_actor": None, "expected_sha": None,
        "required_predicates": {},
    }


def ensure_effect_contract(conn: sqlite3.Connection, job: Mapping[str, Any]) -> dict[str, Any]:
    """Persist the dispatch contract once and return the immutable snapshot."""
    existing = conn.execute("SELECT * FROM job_effect_contract WHERE job_id=?", (job["id"],)).fetchone()
    if existing is not None:
        return _contract_row(existing)
    operation = job.get("gh_write_expect") or job.get("task_type")
    if job.get("requires_gh_write") and operation:
        try:
            value = build_github_effect_contract(
                job["id"], operation=str(operation), target=job.get("gh_write_target") or "unknown",
                expected_actor=job.get("gh_write_author"), started_at=job.get("started_at"),
            )
        except ValueError:
            value = legacy_unknown_contract(job["id"], started_at=job.get("started_at"))
    else:
        value = legacy_unknown_contract(job["id"], started_at=job.get("started_at"))
    _insert_contract(conn, value)
    return value


def _evidence(e: Mapping[str, Any]) -> tuple[str, str, str]:
    return str(e.get("kind", "observer_error")), str(e.get("result", "unknown")), str(e.get("evidence_id") or e.get("event_id") or "")


def decide_job_outcome(
    contract: Mapping[str, Any],
    evidence: Iterable[Mapping[str, Any]],
    *,
    retry_exhausted: bool = False,
    deadline_expired: bool = False,
) -> CompletionDecision:
    """Pure precedence/tri-state oracle.  Evidence never mutates its inputs."""
    rows = list(evidence)
    ids = tuple(str(e.get("evidence_id") or e.get("event_id")) for e in rows if e.get("evidence_id") or e.get("event_id"))
    if contract.get("kind") == "unknown_contract":
        return CompletionDecision("unknown", "unknown", "unknown_contract", "manual_review", ids)

    def matches(kind: str, result: str = "true") -> list[Mapping[str, Any]]:
        return [e for e in rows if e.get("kind") == kind and e.get("result") == result]

    remote = matches("github_effect") + matches("remote_effect")
    required_predicates = {
        name: bool(required)
        for name, required in (contract.get("required_predicates") or {}).items()
        if required
    }
    predicate_mismatch = any(
        any(e.get(name) is False for e in remote if e.get("result") == "true")
        for name in required_predicates
    )
    predicate_unknown = any(
        not any(e.get(name) is True for e in remote if e.get("result") == "true")
        for name in required_predicates
    )
    verified_remote = any(
        e.get("result") == "true"
        and e.get("causal_match", True)
        and not predicate_mismatch
        and not predicate_unknown
        for e in remote
    )
    if verified_remote:
        warnings = ("receipt_absent",) if any(e.get("kind") == "task_receipt" and e.get("result") == "false" for e in rows) else ()
        return CompletionDecision("completed", "verified", "contract_effect_verified", "none", ids, warnings)
    if remote and predicate_mismatch:
        if deadline_expired or retry_exhausted:
            return CompletionDecision("failed_verification", "failed", "contract_predicate_mismatch", "manual_review", ids)
        return CompletionDecision("verifying", "unknown", "contract_predicate_mismatch", "retry_verification", ids)
    if remote and predicate_unknown:
        if deadline_expired or retry_exhausted:
            return CompletionDecision("failed_verification", "failed", "contract_predicate_unresolved", "manual_review", ids)
        return CompletionDecision("verifying", "unknown", "contract_predicate_unresolved", "retry_verification", ids)
    if any(e.get("kind") == "circuit_breaker" and e.get("result") == "true" and e.get("process_live_at_observation", True) for e in rows):
        return CompletionDecision("circuit_breaker_tripped", "failed", "circuit_breaker_killed_live_process", "none", ids)
    for kind, status, reason in (("cancelled", "cancelled", "explicit_cancellation"), ("timeout", "timed_out", "timeout_observed"), ("zombie", "killed_zombie", "zombie_reaped")):
        if matches(kind):
            return CompletionDecision(status, "failed", reason, "none", ids)
    if matches("permission_denied") and not remote:
        return CompletionDecision("permission_denied", "failed", "verified_permission_denial", "none", ids)
    if any(e.get("result") == "unknown" for e in rows) or (remote and not matches("github_effect")):
        if deadline_expired or retry_exhausted:
            return CompletionDecision("failed_verification", "failed", "verification_budget_exhausted", "manual_review", ids)
        return CompletionDecision("verifying", "unknown", "effect_verification_pending", "retry_verification", ids)
    if any(e.get("kind") == "effect" and e.get("result") == "false" for e in rows):
        if contract.get("local_change_policy") == "optional":
            return CompletionDecision("completed_without_changes", "verified", "explicit_allowed_no_change", "none", ids)
        return CompletionDecision("failed_noop_denied", "failed", "required_effect_absent", "none", ids)
    if any(e.get("kind") == "process_exit" and e.get("result") == "false" for e in rows):
        return CompletionDecision("failed", "failed", "process_exit_nonzero", "none", ids)
    return CompletionDecision("verifying", "unknown", "insufficient_evidence", "retry_verification", ids)


def record_evidence_and_reconcile(
    conn: sqlite3.Connection,
    job_id: str,
    evidence: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
    retry_exhausted: bool = False,
    deadline_expired: bool = False,
    decided_by: str = "job_truth.v1",
    update_compatibility: bool = True,
) -> CompletionDecision:
    """Append one observation and atomically persist the next decision revision."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT * FROM job_effect_contract WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            contract = contract or legacy_unknown_contract(job_id)
            _insert_contract(conn, contract)
        elif contract is not None:
            stored = _contract_row(row)
            if _contract_fingerprint(stored) != _contract_fingerprint(contract):
                raise ValueError(f"effect contract for {job_id} is immutable")
        evidence_id = str(evidence.get("evidence_id") or f"evidence-{uuid.uuid4().hex}")
        source = str(evidence.get("source", "unknown")); attempt = int(evidence.get("attempt", 1) or 1)
        event_id = str(evidence.get("event_id") or evidence_id)
        conn.execute("""INSERT OR IGNORE INTO job_evidence
            (evidence_id, job_id, kind, result, observed_at, source, payload_json,
             confidence, attempt, event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
            evidence_id, job_id, evidence.get("kind", "observer_error"), evidence.get("result", "unknown"),
            evidence.get("observed_at") or _now(), source, json.dumps(dict(evidence), sort_keys=True),
            evidence.get("confidence", "medium"), attempt, event_id))
        contract_row = _contract_row(conn.execute("SELECT * FROM job_effect_contract WHERE job_id=?", (job_id,)).fetchone())
        rows = [dict(zip([d[0] for d in conn.execute("SELECT * FROM job_evidence WHERE job_id=? ORDER BY observed_at, evidence_id", (job_id,)).description], r)) for r in conn.execute("SELECT * FROM job_evidence WHERE job_id=? ORDER BY observed_at, evidence_id", (job_id,)).fetchall()]
        for item in rows:
            try: item.update(json.loads(item.pop("payload_json") or "{}"))
            except (TypeError, json.JSONDecodeError): pass
        decision = decide_job_outcome(contract_row, rows, retry_exhausted=retry_exhausted, deadline_expired=deadline_expired)
        latest = conn.execute("SELECT revision, status, decision_reason FROM job_terminal_decision WHERE job_id=? ORDER BY revision DESC LIMIT 1", (job_id,)).fetchone()
        if latest and (latest[1], latest[2]) == (decision.status, decision.reason_code):
            conn.commit(); return decision
        revision = (latest[0] if latest else 0) + 1
        conn.execute("""INSERT INTO job_terminal_decision
            (job_id, status, exit_code, verification_state, primary_evidence_id,
             evidence_snapshot_json, decision_reason, decided_at, decided_by,
             revision, contract_version, follow_up)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
            job_id, decision.status, evidence.get("exit_code"), decision.verification_state,
            decision.evidence_ids[-1] if decision.evidence_ids else evidence_id,
            json.dumps(list(decision.evidence_ids)), decision.reason_code, _now(), decided_by,
            revision, contract_row.get("contract_version", 1), decision.required_follow_up))
        if decision.status in TERMINAL_STATUSES:
            _append_terminal_outbox(
                conn, job_id=job_id, revision=revision, status=decision.status,
                decision_reason=decision.reason_code,
                decided_at=conn.execute(
                    "SELECT decided_at FROM job_terminal_decision WHERE job_id=? AND revision=?",
                    (job_id, revision),
                ).fetchone()[0],
                effect_contract_version=contract_row.get("contract_version", 1),
            )
        # Compatibility projection only: the decision ledger remains authoritative.
        if update_compatibility and conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='daemon_jobs'").fetchone():
            conn.execute("UPDATE daemon_jobs SET status=?, exit_code=COALESCE(?, exit_code), completed_at=COALESCE(completed_at, ?) WHERE job_id=?", (decision.status, evidence.get("exit_code"), _now(), job_id))
        conn.commit()
        return decision
    except Exception:
        conn.rollback()
        raise


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_terminal_outbox(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    revision: int,
    status: str,
    decision_reason: str,
    decided_at: str,
    effect_contract_version: int,
) -> None:
    """Append a cost-audit input derived from the canonical persisted decision."""
    harness = role = None
    has_jobs = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='daemon_jobs'"
    ).fetchone()
    if has_jobs:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
        selected = [name for name in ("harness", "agent", "role") if name in columns]
        if selected:
            row = conn.execute(
                f"SELECT {', '.join(selected)} FROM daemon_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if row:
                values = dict(zip(selected, row))
                harness = values.get("harness") or values.get("agent")
                role = values.get("role")
    payload = {
        "schema_version": TERMINAL_EVENT_SCHEMA,
        "job_id": job_id,
        "decision_revision": int(revision),
        "decision_status": status,
        "decision_reason": decision_reason,
        "decided_at": decided_at,
        "effect_contract_version": int(effect_contract_version),
        "harness": harness,
        "role": role,
    }
    decision_facts = {
        "job_id": job_id,
        "decision_revision": int(revision),
        "decision_status": status,
        "decision_reason": decision_reason,
        "decided_at": decided_at,
        "effect_contract_version": int(effect_contract_version),
    }
    payload["source_decision_digest"] = hashlib.sha256(
        json.dumps(decision_facts, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    event_id = "decision-" + hashlib.sha256(
        f"{TERMINAL_EVENT_SCHEMA}:{job_id}:{revision}".encode("utf-8")
    ).hexdigest()
    conn.execute(
        """INSERT OR IGNORE INTO job_terminal_outbox
           (event_id, job_id, decision_revision, schema_version, payload_json,
            payload_digest, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (event_id, job_id, revision, TERMINAL_EVENT_SCHEMA, canonical, digest, decided_at),
    )


def ensure_terminal_outbox(conn: sqlite3.Connection) -> int:
    """Backfill missing terminal decision events without changing decisions."""
    rows = conn.execute(
        """SELECT job_id, revision, status, decision_reason, decided_at, contract_version
           FROM job_terminal_decision WHERE status NOT IN ('unknown', 'verifying')
           ORDER BY decided_at, job_id, revision"""
    ).fetchall()
    inserted = 0
    own_transaction = not conn.in_transaction
    if own_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        for job_id, revision, status, reason, decided_at, contract_version in rows:
            before = conn.execute(
                "SELECT 1 FROM job_terminal_outbox WHERE job_id=? AND decision_revision=?",
                (job_id, revision),
            ).fetchone()
            if before:
                continue
            _append_terminal_outbox(
                conn, job_id=job_id, revision=revision, status=status,
                decision_reason=reason, decided_at=decided_at,
                effect_contract_version=contract_version,
            )
            inserted += 1
        if own_transaction:
            conn.commit()
    except Exception:
        if own_transaction:
            conn.rollback()
        raise
    return inserted


def _contract_fingerprint(value: Mapping[str, Any]) -> str:
    # Compare persisted and in-memory forms using the immutable fields only;
    # the builder's deadline-seconds convenience field is not stored verbatim.
    normalized = {
        key: value.get(key)
        for key in ("job_id", "kind", "target", "expect", "local_change_policy",
                    "receipt_policy", "contract_version", "started_at", "expected_actor")
    }
    normalized["required_predicates"] = value.get("required_predicates")
    if normalized["required_predicates"] is None:
        raw = value.get("required_predicates_json", "{}")
        normalized["required_predicates"] = json.loads(raw or "{}") if isinstance(raw, str) else raw
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def _insert_contract(conn: sqlite3.Connection, value: Mapping[str, Any]) -> None:
    conn.execute("""INSERT INTO job_effect_contract
        (contract_id, job_id, kind, target, expect, local_change_policy,
         receipt_policy, verification_deadline_at, contract_version, started_at,
         expected_actor, required_predicates_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
        value["contract_id"], value["job_id"], value["kind"], value.get("target"), value.get("expect"),
        value.get("local_change_policy", "optional"), value.get("receipt_policy", "optional"),
        value.get("verification_deadline_at"), value.get("contract_version", 1), value.get("started_at"),
        value.get("expected_actor"), json.dumps(value.get("required_predicates", {}), sort_keys=True)))


def _contract_row(row: sqlite3.Row | tuple | None) -> dict[str, Any]:
    if row is None: return legacy_unknown_contract("")
    keys = ["contract_id", "job_id", "kind", "target", "expect", "local_change_policy", "receipt_policy", "verification_deadline_at", "contract_version", "started_at", "expected_actor", "required_predicates_json"]
    value = dict(zip(keys, row))
    try: value["required_predicates"] = json.loads(value.pop("required_predicates_json") or "{}")
    except json.JSONDecodeError: value["required_predicates"] = {}
    return value
