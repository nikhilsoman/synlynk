import json
import sqlite3

import pytest

from synlynk.job_status_projection import (
    compare_legacy_status,
    job_truth_metrics,
    project_job_status,
    promotion_gate,
    rollout_mode,
)


def ledger():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE daemon_jobs (
        job_id TEXT PRIMARY KEY, status TEXT, harness TEXT, enqueued_at TEXT
    );
    CREATE TABLE job_effect_contract (
        job_id TEXT PRIMARY KEY, kind TEXT, contract_version INTEGER,
        required_predicates_json TEXT
    );
    CREATE TABLE job_evidence (
        evidence_id TEXT, job_id TEXT, kind TEXT, result TEXT,
        observed_at TEXT, source TEXT, confidence TEXT, attempt INTEGER,
        event_id TEXT, payload_json TEXT
    );
    CREATE TABLE job_terminal_decision (
        job_id TEXT, status TEXT, verification_state TEXT,
        decision_reason TEXT, revision INTEGER, decided_at TEXT
    );
    CREATE TABLE job_status_shadow (
        job_id TEXT PRIMARY KEY, legacy_status TEXT, oracle_status TEXT,
        reason_code TEXT, disagreement INTEGER, harness TEXT,
        effect_kind TEXT, observed_at TEXT
    );
    """)
    return conn


def test_aliases_are_boundary_only_and_false_failure_has_reason_code():
    assert compare_legacy_status("done", "completed")["reason_code"] == "legacy_alias_normalized"
    result = compare_legacy_status("task_delivery_failed", "completed")
    assert result["disagreement"] is True
    assert result["reason_code"] == "false_failure"


def test_projection_exposes_contract_predicates_evidence_revision_and_corrections():
    conn = ledger()
    conn.execute("INSERT INTO daemon_jobs VALUES ('job-1', 'task_delivery_failed', 'codex', '2026-10-03T10:00:00')")
    conn.execute("INSERT INTO job_effect_contract VALUES ('job-1', 'github_review', 1, ?)", (json.dumps({"target_match": True}),))
    conn.execute("INSERT INTO job_evidence VALUES ('e-1', 'job-1', 'github_effect', 'true', '2026-10-03T10:01:00+00:00', 'gh', 'high', 2, 'read-2', ?)", (json.dumps({"target_match": True, "causal_match": True}),))
    conn.execute("INSERT INTO job_terminal_decision VALUES ('job-1', 'verifying', 'unknown', 'effect_verification_pending', 1, '2026-10-03T10:00:00+00:00')")
    conn.execute("INSERT INTO job_terminal_decision VALUES ('job-1', 'completed', 'verified', 'contract_effect_verified', 2, '2026-10-03T10:01:00+00:00')")
    projection = project_job_status(conn, "job-1")
    assert projection["schema"] == "job-status-truth.v1"
    assert projection["status"] == "completed"
    assert projection["legacy_status"] == "task_delivery_failed"
    assert projection["verification_confidence"] == "high"
    assert projection["contract_predicates"]["target_match"]["result"] is True
    assert projection["decision_revision"] == 2
    assert projection["correction_history"][0]["status"] == "verifying"
    assert projection["shadow_comparison"]["reason_code"] == "false_failure"


def test_metrics_and_promotion_gate_report_rollout_blockers():
    conn = ledger()
    conn.execute("INSERT INTO job_status_shadow VALUES ('job-1', 'failed', 'completed', 'false_failure', 1, 'grok', 'github_review', '2026-10-03T10:00:00')")
    conn.execute("INSERT INTO job_effect_contract VALUES ('job-1', 'github_review', 1, '{}')")
    conn.execute("INSERT INTO job_evidence VALUES ('e-1', 'job-1', 'github_effect', 'unknown', '2026-10-03T10:00:00+00:00', 'gh', 'low', 3, 'read-3', '{}')")
    metrics = job_truth_metrics(conn)
    assert metrics["false_failure"] == 1
    assert metrics["verification_retries"] == 2
    gate = promotion_gate(metrics, minimum_samples=1)
    assert gate["eligible"] is False
    assert "zero_false_failure" in gate["rollback_on"]


@pytest.mark.parametrize("metric, expected", [
    ({"unknown_verifying_age_seconds": {"max": 301, "count": 0}}, "verification_age_slo"),
    ({"verification_retries": 4}, "verification_retries_slo"),
    ({"unknown_verifying_age_seconds": {"max": 0, "count": 1}}, "unknown_verifying_slo"),
    ({"disagreement_reasons": {"status_disagreement": 1}}, "harness_effect_agreement"),
])
def test_promotion_gate_fails_closed_for_each_verification_blocker(metric, expected):
    metrics = {"samples": 100, "false_failure": 0, "false_success": 0,
               "contract_missing": 0, "verification_retries": 0,
               "unknown_verifying_age_seconds": {"max": 0, "count": 0},
               "disagreement_reasons": {}}
    metrics.update(metric)
    gate = promotion_gate(metrics)
    assert gate["eligible"] is False
    assert expected in gate["rollback_on"]
    assert gate["reason_codes"]


def test_promotion_gate_allows_only_explicit_reason_coded_exclusions():
    metrics = {"samples": 100, "false_failure": 0, "false_success": 0,
               "contract_missing": 0, "verification_retries": 0,
               "unknown_verifying_age_seconds": {"max": 0, "count": 0},
               "disagreement_reasons": {"documented_legacy_alias": 1}}
    blocked = promotion_gate(metrics)
    allowed = promotion_gate(metrics, allowed_disagreement_reason_codes=frozenset({"documented_legacy_alias"}))
    assert blocked["eligible"] is False
    assert allowed["eligible"] is True


def test_promotion_gate_blocks_legacy_disagreement_metrics_without_reasons():
    metrics = {"samples": 100, "false_failure": 0, "false_success": 0,
               "contract_missing": 0, "verification_retries": 0,
               "unknown_verifying_age_seconds": {"max": 0, "count": 0},
               "disagreements_by_harness_effect": {"grok": {"github_review": 1}}}
    gate = promotion_gate(metrics)
    assert gate["eligible"] is False
    assert "harness_effect_agreement" in gate["rollback_on"]


def test_rollout_mode_defaults_to_shadow_and_rejects_unknown_values():
    assert rollout_mode({}) == "shadow"
    assert rollout_mode({"SYNLYNK_JOB_TRUTH_MODE": "authoritative"}) == "authoritative"
    assert rollout_mode({"SYNLYNK_JOB_TRUTH_MODE": "unsafe"}) == "shadow"
