"""Machine-readable job truth projections, metrics, and rollout controls."""

from __future__ import annotations

import json
import math
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping

from synlynk.job_truth import STATUS_ALIASES, canonical_status

PROJECTION_SCHEMA = "job-status-truth.v1"
ROLLOUT_MODES = frozenset({"off", "shadow", "authoritative"})
DEFAULT_MAX_UNKNOWN_AGE_SECONDS = 300
DEFAULT_MAX_VERIFICATION_RETRIES = 3
DEFAULT_MAX_UNKNOWN_VERIFYING = 0


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
    # The normal DB helper returns tuple rows.  The projection reader also
    # supports the Row-based test/integration connections, so provide that
    # shape locally without changing the caller's connection configuration.
    previous_row_factory = conn.row_factory
    if previous_row_factory is None:
        conn.row_factory = sqlite3.Row
    try:
        projection = project_job_status(conn, job_id)
    finally:
        conn.row_factory = previous_row_factory
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
    disagreement_reasons = Counter()
    for row in rows:
        if row["disagreement"]:
            disagreements[row["harness"] or "unknown"][row["effect_kind"] or "unknown"] += 1
            disagreement_reasons[row["reason_code"] or "unexplained_disagreement"] += 1
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
        "disagreement_reasons": dict(disagreement_reasons),
    }


def promotion_gate(
    metrics: Mapping[str, Any],
    *,
    minimum_samples: int = 100,
    max_unknown_age_seconds: int = DEFAULT_MAX_UNKNOWN_AGE_SECONDS,
    max_verification_retries: int = DEFAULT_MAX_VERIFICATION_RETRIES,
    max_unknown_verifying: int = DEFAULT_MAX_UNKNOWN_VERIFYING,
    allowed_disagreement_reason_codes: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Fail closed unless rollout metrics satisfy every promotion SLO.

    Disagreement exclusions are deliberately explicit and reason-coded.  An
    absent allow-list means every disagreement is a blocker.
    """
    missing_metrics: list[str] = []

    def required_int(name: str) -> int | None:
        value = metrics.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            missing_metrics.append(name)
            return None
        return int(value)

    age = metrics.get("unknown_verifying_age_seconds")
    if not isinstance(age, Mapping):
        missing_metrics.extend(("verification_age", "unknown_verifying_count"))
        unknown_age = None
        unknown_count = None
    else:
        unknown_age = age.get("max")
        unknown_count = age.get("count")
        if (
            isinstance(unknown_age, bool)
            or not isinstance(unknown_age, (int, float))
            or not math.isfinite(unknown_age)
        ):
            missing_metrics.append("verification_age")
            unknown_age = None
        if (
            isinstance(unknown_count, bool)
            or not isinstance(unknown_count, (int, float))
            or not math.isfinite(unknown_count)
        ):
            missing_metrics.append("unknown_verifying_count")
            unknown_count = None

    raw_disagreement_reasons = metrics.get("disagreement_reasons")
    if raw_disagreement_reasons is None and "disagreement_reasons" in metrics:
        missing_metrics.append("harness_effect_agreement")
        disagreement_reasons = {}
    elif raw_disagreement_reasons is not None and not isinstance(raw_disagreement_reasons, Mapping):
        missing_metrics.append("harness_effect_agreement")
        disagreement_reasons = {}
    else:
        disagreement_reasons = {
            str(reason): int(count or 0)
            for reason, count in (raw_disagreement_reasons or {}).items()
        }
    raw_disagreements = metrics.get("disagreements_by_harness_effect")
    if raw_disagreements is None and "disagreements_by_harness_effect" in metrics:
        missing_metrics.append("harness_effect_agreement")
    elif raw_disagreements is not None and not isinstance(raw_disagreements, Mapping):
        missing_metrics.append("harness_effect_agreement")
    disagreement_metrics_present = (
        ("disagreement_reasons" in metrics and isinstance(raw_disagreement_reasons, Mapping))
        or ("disagreements_by_harness_effect" in metrics and isinstance(raw_disagreements, Mapping))
    )
    if not disagreement_metrics_present:
        missing_metrics.append("harness_effect_agreement")
    elif not disagreement_reasons and raw_disagreements:
        disagreement_reasons = {
            "unexplained_harness_effect_disagreement": sum(
                int(count or 0)
                for effects in raw_disagreements.values()
                for count in effects.values()
            )
        }
    unexplained_disagreements = sum(
        count for reason, count in disagreement_reasons.items()
        if reason not in allowed_disagreement_reason_codes
    )
    false_failure = required_int("false_failure")
    false_success = required_int("false_success")
    verification_retries = required_int("verification_retries")
    contract_missing = required_int("contract_missing")
    checks = {
        "sample_window": int(metrics.get("samples", 0)) >= minimum_samples,
        "zero_false_failure": false_failure == 0,
        "zero_false_success": false_success == 0,
        "no_missing_contract": contract_missing == 0,
        "verification_age_slo": unknown_age is not None and unknown_age <= max_unknown_age_seconds,
        "verification_retries_slo": verification_retries is not None and verification_retries <= max_verification_retries,
        "unknown_verifying_slo": unknown_count is not None and unknown_count <= max_unknown_verifying,
        "harness_effect_agreement": disagreement_metrics_present and unexplained_disagreements == 0,
    }
    reason_codes = {
        "sample_window": "insufficient_sample_window",
        "zero_false_failure": "false_failure_observed",
        "zero_false_success": "false_success_observed",
        "no_missing_contract": "missing_contract_observed",
        "verification_age_slo": "verification_age_slo_breached",
        "verification_retries_slo": "verification_retries_exceeded",
        "unknown_verifying_slo": "unknown_verifying_exceeded",
        "harness_effect_agreement": "unexplained_harness_effect_disagreement",
    }
    rollback_on = [key for key, passed in checks.items() if not passed]
    missing_reason_codes = {
        "verification_age": "verification_age_missing_or_unknown",
        "verification_retries": "verification_retries_missing_or_unknown",
        "unknown_verifying_count": "unknown_verifying_count_missing_or_unknown",
        "false_failure": "false_failure_metric_missing_or_unknown",
        "false_success": "false_success_metric_missing_or_unknown",
        "contract_missing": "contract_coverage_metric_missing_or_unknown",
        "harness_effect_agreement": "harness_effect_disagreement_metric_missing_or_unknown",
    }
    reason_code_list = [reason_codes[key] for key in rollback_on]
    reason_code_list.extend(missing_reason_codes[name] for name in missing_metrics)
    return {
        "eligible": not rollback_on,
        "checks": checks,
        "rollback_on": rollback_on,
        "reason_codes": reason_code_list,
        "thresholds": {
            "minimum_samples": minimum_samples,
            "max_unknown_age_seconds": max_unknown_age_seconds,
            "max_verification_retries": max_verification_retries,
            "max_unknown_verifying": max_unknown_verifying,
            "allowed_disagreement_reason_codes": sorted(allowed_disagreement_reason_codes),
        },
    }
