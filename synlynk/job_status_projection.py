"""Machine-readable job truth projections, metrics, and rollout controls."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping

from synlynk.job_truth import STATUS_ALIASES, canonical_status

PROJECTION_SCHEMA = "job-status-truth.v1"
ROLLOUT_MODES = frozenset({"off", "shadow", "authoritative"})


def rollout_mode(env: Mapping[str, str] | None = None) -> str:
    value = (env or os.environ).get("SYNLYNK_JOB_TRUTH_MODE", "shadow").strip().lower()
    return value if value in ROLLOUT_MODES else "shadow"


def _row_dict(row) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()} if hasattr(row, "keys") else dict(row)


def _json(value, default):
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return default


def _legacy_canonical(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return canonical_status(value)
    except ValueError:
        return None


def compare_legacy_status(legacy_status: str | None, oracle_status: str | None) -> dict[str, Any]:
    """Compare statuses at the boundary; aliases never enter the ledger."""
    legacy = _legacy_canonical(legacy_status)
    oracle = _legacy_canonical(oracle_status)
    if legacy is None:
        return {"disagreement": True, "reason_code": "legacy_status_unmapped", "legacy_status": legacy_status, "oracle_status": oracle}
    if oracle is None:
        return {"disagreement": True, "reason_code": "oracle_decision_missing", "legacy_status": legacy_status, "oracle_status": oracle_status}
    if legacy == oracle:
        reason = "status_match" if legacy_status == oracle_status else "legacy_alias_normalized"
        return {"disagreement": False, "reason_code": reason, "legacy_status": legacy_status, "oracle_status": oracle}
    if legacy in {"failed", "failed_verification", "task_delivery_failed", "permission_denied", "timed_out", "killed_zombie"} and oracle == "completed":
        reason = "false_failure"
    elif legacy == "completed" and oracle in {"failed", "failed_verification", "permission_denied", "failed_noop_denied"}:
        reason = "false_success"
    else:
        reason = "status_disagreement"
    return {"disagreement": True, "reason_code": reason, "legacy_status": legacy_status, "oracle_status": oracle}


def _confidence(decision: Mapping[str, Any] | None) -> str:
    if not decision:
        return "unknown"
    if decision.get("verification_state") == "verified":
        return "high"
    if decision.get("verification_state") == "unknown":
        return "low"
    return "medium"


def project_job_status(conn, job_id: str) -> dict[str, Any]:
    """Return the versioned status/evidence contract for one job."""
    daemon = _row_dict(conn.execute("SELECT * FROM daemon_jobs WHERE job_id=?", (job_id,)).fetchone())
    contract = _row_dict(conn.execute("SELECT * FROM job_effect_contract WHERE job_id=?", (job_id,)).fetchone()) or {
        "kind": "unknown_contract", "contract_version": 1, "required_predicates_json": "{}"
    }
    contract["required_predicates"] = _json(contract.pop("required_predicates_json", "{}"), {})
    evidence = []
    for row in conn.execute(
        "SELECT evidence_id, kind, result, observed_at, source, confidence, attempt, event_id, payload_json "
        "FROM job_evidence WHERE job_id=? ORDER BY observed_at, evidence_id", (job_id,)
    ).fetchall():
        item = _row_dict(row)
        payload = _json(item.pop("payload_json"), {})
        item.update({key: payload[key] for key in ("target", "target_match", "actor_match", "sha_match", "expected_actor", "causal_match", "reason") if key in payload})
        evidence.append(item)
    decisions = [_row_dict(row) for row in conn.execute(
        "SELECT * FROM job_terminal_decision WHERE job_id=? ORDER BY revision", (job_id,)
    ).fetchall()]
    latest = decisions[-1] if decisions else None
    canonical = latest.get("status") if latest else None
    legacy = daemon.get("status") if daemon else None
    shadow = compare_legacy_status(legacy, canonical)
    by_kind = Counter(item["kind"] for item in evidence)
    by_result = Counter(item["result"] for item in evidence)
    predicates = {}
    for name, required in contract.get("required_predicates", {}).items():
        matching = [item for item in evidence if item.get("kind") in {"github_effect", "remote_effect"} and item.get(name) is True]
        predicates[name] = {"required": bool(required), "result": True if matching else "unknown"}
    return {
        "schema": PROJECTION_SCHEMA,
        "job_id": job_id,
        "status": canonical,
        "legacy_status": legacy,
        "legacy_alias": STATUS_ALIASES.get(str(legacy).lower()) if legacy else None,
        "lifecycle_state": "terminal" if latest and canonical not in {"verifying", "unknown"} else ("verifying" if latest else "unobserved"),
        "verification_state": latest.get("verification_state") if latest else "unknown",
        "verification_confidence": _confidence(latest),
        "reason_code": latest.get("decision_reason") if latest else "oracle_decision_missing",
        "contract": contract,
        "contract_predicates": predicates,
        "evidence_summary": {"total": len(evidence), "by_kind": dict(by_kind), "by_result": dict(by_result), "evidence_ids": [item["evidence_id"] for item in evidence]},
        "decision_revision": latest.get("revision") if latest else None,
        "correction_history": [{"revision": item["revision"], "status": item["status"], "reason_code": item["decision_reason"]} for item in decisions[:-1]],
        "shadow_comparison": shadow,
        "rollout_mode": rollout_mode(),
    }


def record_shadow_comparison(conn, job_id: str) -> dict[str, Any]:
    projection = project_job_status(conn, job_id)
    shadow = projection["shadow_comparison"]
    conn.execute(
        "INSERT OR REPLACE INTO job_status_shadow "
        "(job_id, legacy_status, oracle_status, reason_code, disagreement, harness, effect_kind, observed_at) "
        "SELECT ?, ?, ?, ?, ?, harness, ?, CURRENT_TIMESTAMP FROM daemon_jobs WHERE job_id=?",
        (job_id, shadow["legacy_status"], shadow["oracle_status"], shadow["reason_code"], int(shadow["disagreement"]), projection["contract"].get("kind"), job_id),
    )
    conn.commit()
    return shadow


def job_truth_metrics(conn) -> dict[str, Any]:
    """Return bounded pilot metrics with harness/effect dimensions."""
    rows = [dict(row) for row in conn.execute("SELECT job_id, legacy_status, oracle_status, reason_code, disagreement, harness, effect_kind, observed_at FROM job_status_shadow").fetchall()]
    reasons = Counter(row["reason_code"] for row in rows)
    disagreements = defaultdict(Counter)
    for row in rows:
        if row["disagreement"]:
            disagreements[row["harness"] or "unknown"][row["effect_kind"] or "unknown"] += 1
    retries = conn.execute("SELECT COALESCE(SUM(attempt - 1), 0) FROM job_evidence").fetchone()[0]
    missing = conn.execute("SELECT COUNT(*) FROM job_effect_contract WHERE kind='unknown_contract'").fetchone()[0]
    ages = []
    for (value,) in conn.execute("SELECT decided_at FROM job_terminal_decision WHERE verification_state='unknown'").fetchall():
        try:
            ages.append(max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(value)).total_seconds()))
        except (TypeError, ValueError):
            pass
    return {
        "schema": PROJECTION_SCHEMA, "samples": len(rows),
        "false_failure": reasons["false_failure"], "false_success": reasons["false_success"],
        "unknown_verifying_age_seconds": {"count": len(ages), "max": max(ages, default=0), "average": sum(ages) / len(ages) if ages else 0},
        "verification_retries": int(retries or 0), "contract_missing": int(missing or 0),
        "disagreements_by_harness_effect": {harness: dict(values) for harness, values in disagreements.items()},
    }


def promotion_gate(metrics: Mapping[str, Any], *, minimum_samples: int = 100) -> dict[str, Any]:
    checks = {
        "sample_window": int(metrics.get("samples", 0)) >= minimum_samples,
        "zero_false_failure": int(metrics.get("false_failure", 0)) == 0,
        "zero_false_success": int(metrics.get("false_success", 0)) == 0,
        "no_missing_contract": int(metrics.get("contract_missing", 0)) == 0,
    }
    return {"eligible": all(checks.values()), "checks": checks, "rollback_on": [key for key, passed in checks.items() if not passed]}
