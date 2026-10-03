"""Durable job-effect contracts and the pure completion oracle.

This module deliberately has no network or process side effects.  Observers
append evidence and call :func:`record_evidence_and_reconcile`; only that
entry point writes a terminal decision to the canonical ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import sqlite3
import uuid
from typing import Any, Iterable, Mapping

TRUTH_TABLE_VERSION = 1
TRI_STATE = ("true", "false", "unknown")

CANONICAL_STATUSES = frozenset({
    "queued", "running", "observing", "verifying", "completed",
    "completed_without_changes", "failed", "failed_noop_denied",
    "failed_verification", "task_delivery_failed", "permission_denied",
    "timed_out", "killed_zombie", "circuit_breaker_tripped", "cancelled",
    "unknown",
})
STATUS_ALIASES = {
    "succeeded": "completed", "success": "completed",
    "completed_noop": "completed_without_changes",
    "task_noop_denied": "failed_noop_denied",
    "verification_failed": "failed_verification",
    "access_denied": "permission_denied",
    "killed_by_breaker": "circuit_breaker_tripped",
}

TERMINAL_WRITER_MANIFEST = {
    "synlynk.job_truth.record_evidence_and_reconcile": "canonical_ledger",
}

TERMINAL_STATUSES = frozenset(CANONICAL_STATUSES - {"queued", "running", "observing", "verifying", "unknown"})


@dataclass(frozen=True)
class EffectContract:
    job_id: str
    kind: str
    target: str | None = None
    expect: str | None = None
    local_change_policy: str = "optional"
    receipt_policy: str = "required"
    verification_deadline_at: str | None = None
    contract_version: int = TRUTH_TABLE_VERSION
    started_at: str | None = None
    expected_actor: str | None = None
    expected_sha: str | None = None
    expected_id: str | None = None
    required_predicates: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id, "kind": self.kind, "target": self.target,
            "expect": self.expect, "local_change_policy": self.local_change_policy,
            "receipt_policy": self.receipt_policy,
            "verification_deadline_at": self.verification_deadline_at,
            "contract_version": self.contract_version, "started_at": self.started_at,
            "expected_actor": self.expected_actor, "expected_sha": self.expected_sha,
            "expected_id": self.expected_id,
            "required_predicates": list(self.required_predicates),
        }


def build_github_effect_contract(
    job_id: str, operation: str, target: str, *, expected_actor: str | None = None,
    expected_sha: str | None = None, expected_id: str | None = None,
    started_at: str | None = None, verification_deadline_at: str | None = None,
    receipt_policy: str = "required",
) -> EffectContract:
    """Build an immutable v1 contract for a GitHub review/comment/PR/issue."""
    aliases = {"review": "github_review", "comment": "github_comment", "pr": "github_pr_open", "issue": "github_issue"}
    kind = aliases.get(operation, operation if operation.startswith("github_") else f"github_{operation}")
    expect = {"github_review": "review_posted", "github_comment": "comment_posted",
              "github_pr_open": "pr_opened", "github_issue": "issue_opened"}.get(kind)
    predicates = ({"name": "target_match", "result": "true"}, {"name": "causal_actor", "result": "true"})
    if expected_sha:
        predicates += ({"name": "head_sha_match", "result": "true"},)
    if expected_id:
        predicates += ({"name": "effect_id_match", "result": "true"},)
    return EffectContract(job_id=job_id, kind=kind, target=target, expect=expect,
                          receipt_policy=receipt_policy, verification_deadline_at=verification_deadline_at,
                          started_at=started_at, expected_actor=expected_actor, expected_sha=expected_sha,
                          expected_id=expected_id, required_predicates=predicates)


def build_effect_contract(job_id: str, *, kind: str = "unknown_contract", **kwargs: Any) -> EffectContract:
    """Build a contract, preserving an explicit unknown state for legacy jobs."""
    if kind.startswith("github_") or kind in {"review", "comment", "pr", "issue"}:
        return build_github_effect_contract(job_id, kind.removeprefix("github_"), kwargs.pop("target", ""), **kwargs)
    return EffectContract(job_id=job_id, kind=kind, **{k: v for k, v in kwargs.items() if k in EffectContract.__dataclass_fields__})


def legacy_default_contract(job_id: str, *, task_class: str | None = None, started_at: str | None = None) -> EffectContract:
    kind = "read_only_report" if (task_class or "").lower() in {"analysis", "read_only", "readonly"} else "unknown_contract"
    return EffectContract(job_id=job_id, kind=kind, started_at=started_at)


def canonical_status(status: str | None) -> str:
    """Normalize compatibility aliases only at the API boundary."""
    value = str(status or "unknown").strip()
    return STATUS_ALIASES.get(value, value if value in CANONICAL_STATUSES else "unknown")


def assert_terminal_writer_manifest() -> None:
    """Guardrail used by tests to keep new terminal writers registered."""
    if not TERMINAL_WRITER_MANIFEST:
        raise AssertionError("terminal writer manifest must contain the canonical writer")


@dataclass(frozen=True)
class JobDecision:
    status: str
    verification_state: str
    reason_code: str
    required_follow_up: str
    evidence_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    revision: int | None = None


def _evidence(e: Mapping[str, Any], kind: str | None = None) -> bool:
    return (kind is None or e.get("kind") == kind) and e.get("result") == "true"


def decide_job_outcome(contract: EffectContract | Mapping[str, Any], evidence: Iterable[Mapping[str, Any]], *, retry_attempt: int = 0, max_attempts: int = 3, deadline_reached: bool = False) -> JobDecision:
    """Pure precedence/tri-state oracle.  Strong effects outrank weak signals."""
    c = contract if isinstance(contract, EffectContract) else EffectContract(**{k: contract.get(k) for k in EffectContract.__dataclass_fields__ if k in contract})
    rows = list(evidence)
    ids = tuple(str(e.get("evidence_id")) for e in rows if e.get("evidence_id"))
    if c.kind == "unknown_contract":
        return JobDecision("unknown", "unknown", "unknown_contract", "manual_review", ids)
    remote = [e for e in rows if e.get("kind") == "github_effect"]
    remote_true = [e for e in remote if e.get("result") == "true" and e.get("causal") is not False and e.get("target_match") is not False and e.get("actor_match") is not False and e.get("sha_match") is not False]
    if remote_true and all(e.get("result") == "true" for e in rows if e.get("required", False)):
        receipt_warning = "receipt_missing" if any(e.get("kind") == "task_receipt" and e.get("result") == "false" for e in rows) else None
        return JobDecision("completed", "verified", "verified_remote_effect", "none", ids, (receipt_warning,) if receipt_warning else ())
    if any(_evidence(e, "circuit_breaker") for e in rows) and not remote_true:
        return JobDecision("circuit_breaker_tripped", "failed", "breaker_killed_live_process", "none", ids)
    if any(e.get("kind") in {"cancelled", "timeout", "zombie"} and e.get("result") == "true" for e in rows) and not remote_true:
        kind = next(e["kind"] for e in rows if e.get("kind") in {"cancelled", "timeout", "zombie"} and e.get("result") == "true")
        return JobDecision({"timeout": "timed_out", "zombie": "killed_zombie", "cancelled": "cancelled"}[kind], "failed", kind, "none", ids)
    if any(e.get("kind") == "permission_denied" and e.get("result") == "true" for e in rows) and not remote_true:
        return JobDecision("permission_denied", "failed", "verified_permission_denied", "none", ids)
    if remote and not remote_true and any(e.get("result") == "unknown" for e in remote) and not deadline_reached:
        return JobDecision("verifying", "unknown", "remote_effect_unavailable", "retry_verification", ids)
    if remote and not remote_true and (deadline_reached or retry_attempt >= max_attempts):
        return JobDecision("failed_verification", "failed", "remote_effect_not_verified", "manual_review", ids)
    if c.local_change_policy == "required" and any(e.get("kind") == "git_effect" and e.get("result") == "true" for e in rows):
        return JobDecision("completed", "verified", "verified_local_effect", "none", ids)
    if c.local_change_policy == "forbidden" or c.kind == "explicit_noop":
        return JobDecision("completed_without_changes", "verified", "explicit_noop", "none", ids)
    if any(e.get("kind") == "process_exit" and e.get("result") == "true" for e in rows):
        return JobDecision("failed_noop_denied", "failed", "required_effect_absent", "none", ids)
    return JobDecision("unknown", "unknown", "insufficient_evidence", "retry_verification", ids)


def record_evidence_and_reconcile(conn: sqlite3.Connection, job_id: str, evidence: Mapping[str, Any], *, contract: EffectContract | None = None, now: str | None = None) -> JobDecision:
    """Append one observation and atomically persist the current decision."""
    now = now or datetime.now(timezone.utc).isoformat()
    conn.execute("BEGIN IMMEDIATE")
    try:
        if contract is not None:
            conn.execute("""INSERT OR IGNORE INTO job_effect_contract
                (job_id, kind, target, expect, local_change_policy, receipt_policy, verification_deadline_at,
                 contract_version, started_at, expected_actor, expected_sha, expected_id, required_predicates_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (job_id, contract.kind, contract.target, contract.expect,
                contract.local_change_policy, contract.receipt_policy, contract.verification_deadline_at, contract.contract_version,
                contract.started_at, contract.expected_actor, contract.expected_sha, contract.expected_id, json.dumps(contract.required_predicates, sort_keys=True)))
            # The insert trigger creates an explicit legacy placeholder for
            # every daemon job.  Dispatch metadata may refine that placeholder
            # exactly once, before any evidence exists; thereafter contracts
            # are immutable.
            conn.execute("""UPDATE job_effect_contract SET kind=?, target=?, expect=?,
                local_change_policy=?, receipt_policy=?, verification_deadline_at=?,
                contract_version=?, started_at=?, expected_actor=?, expected_sha=?,
                expected_id=?, required_predicates_json=?
                WHERE job_id=? AND kind='unknown_contract'
                  AND NOT EXISTS (SELECT 1 FROM job_evidence WHERE job_id=?)""",
                (contract.kind, contract.target, contract.expect, contract.local_change_policy,
                 contract.receipt_policy, contract.verification_deadline_at, contract.contract_version,
                 contract.started_at, contract.expected_actor, contract.expected_sha, contract.expected_id,
                 json.dumps(contract.required_predicates, sort_keys=True), job_id, job_id))
        row = conn.execute("SELECT * FROM job_effect_contract WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            contract = legacy_default_contract(job_id)
            conn.execute("INSERT INTO job_effect_contract (job_id, kind, contract_version, required_predicates_json) VALUES (?, ?, ?, ?)", (job_id, contract.kind, contract.contract_version, "[]"))
        duplicate = conn.execute("SELECT evidence_id FROM job_evidence WHERE job_id=? AND source=? AND attempt=? AND event_id=?", (job_id, evidence.get("source", "unknown"), int(evidence.get("attempt", 1)), evidence.get("event_id", ""))).fetchone()
        evidence_id = duplicate[0] if duplicate else str(evidence.get("evidence_id") or uuid.uuid4())
        if duplicate:
            previous = conn.execute("SELECT status, verification_state, decision_reason, follow_up, evidence_snapshot_json, revision FROM job_terminal_decision WHERE job_id=? ORDER BY revision DESC LIMIT 1", (job_id,)).fetchone()
            conn.commit()
            if previous:
                return JobDecision(previous[0], previous[1], previous[2], previous[3], tuple(json.loads(previous[4])), revision=previous[5])
        if not duplicate:
            conn.execute("""INSERT INTO job_evidence
                (evidence_id, job_id, kind, result, observed_at, source, payload_json, confidence, attempt, event_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (evidence_id, job_id, evidence.get("kind", "observer_error"), evidence.get("result", "unknown"), evidence.get("observed_at", now), evidence.get("source", "unknown"), json.dumps(dict(evidence), sort_keys=True), evidence.get("confidence", "medium"), int(evidence.get("attempt", 1)), evidence.get("event_id", "")))
        c_row = conn.execute("SELECT kind, target, expect, local_change_policy, receipt_policy, verification_deadline_at, contract_version, started_at, expected_actor, expected_sha, expected_id, required_predicates_json FROM job_effect_contract WHERE job_id=?", (job_id,)).fetchone()
        keys = ("kind", "target", "expect", "local_change_policy", "receipt_policy", "verification_deadline_at", "contract_version", "started_at", "expected_actor", "expected_sha", "expected_id", "required_predicates")
        c_values = dict(zip(keys, c_row))
        c_values["required_predicates"] = tuple(json.loads(c_values["required_predicates"] or "[]")) if isinstance(c_values["required_predicates"], str) else tuple(c_values["required_predicates"] or ())
        c = EffectContract(job_id, **c_values)
        rows = [dict(zip([d[0] for d in conn.execute("SELECT * FROM job_evidence LIMIT 0").description], r)) for r in conn.execute("SELECT * FROM job_evidence WHERE job_id=? ORDER BY rowid", (job_id,)).fetchall()]
        decision = decide_job_outcome(c, rows)
        current = conn.execute("SELECT COALESCE(MAX(revision), 0) FROM job_terminal_decision WHERE job_id=?", (job_id,)).fetchone()[0]
        revision = int(current) + 1
        conn.execute("INSERT INTO job_terminal_decision (job_id, status, verification_state, primary_evidence_id, evidence_snapshot_json, decision_reason, decided_at, decided_by, revision, contract_version, follow_up) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (job_id, decision.status, decision.verification_state, evidence_id, json.dumps(decision.evidence_ids), decision.reason_code, now, f"job_truth/{TRUTH_TABLE_VERSION}", revision, c.contract_version, decision.required_follow_up))
        conn.execute("UPDATE daemon_jobs SET status=?, completed_at=CASE WHEN ? IN ({}) THEN COALESCE(completed_at, ?) ELSE completed_at END WHERE job_id=?".format(",".join("?" for _ in TERMINAL_STATUSES)), (decision.status, decision.status, *TERMINAL_STATUSES, now, job_id))
        conn.commit()
        return JobDecision(**{**decision.__dict__, "revision": revision})
    except Exception:
        conn.rollback()
        raise
