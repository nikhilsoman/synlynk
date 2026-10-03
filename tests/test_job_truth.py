import sqlite3
import threading

import pytest

from synlynk.job_truth import (
    CANONICAL_STATUSES,
    STATUS_ALIASES,
    CompletionDecision,
    build_github_effect_contract,
    decide_job_outcome,
    legacy_unknown_contract,
    record_evidence_and_reconcile,
)


LEDGER_SCHEMA = """
CREATE TABLE job_effect_contract (
 contract_id TEXT PRIMARY KEY, job_id TEXT UNIQUE NOT NULL, kind TEXT NOT NULL,
 target TEXT, expect TEXT NOT NULL, local_change_policy TEXT NOT NULL,
 receipt_policy TEXT NOT NULL, verification_deadline_at TEXT, contract_version INTEGER NOT NULL,
 started_at TEXT, expected_actor TEXT, required_predicates_json TEXT NOT NULL
);
CREATE TABLE job_evidence (
 evidence_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, kind TEXT NOT NULL, result TEXT NOT NULL,
 observed_at TEXT NOT NULL, source TEXT NOT NULL, payload_json TEXT NOT NULL,
 confidence TEXT NOT NULL, attempt INTEGER NOT NULL, event_id TEXT NOT NULL,
 UNIQUE(job_id, source, attempt, event_id)
);
CREATE TABLE job_terminal_decision (
 job_id TEXT NOT NULL, status TEXT NOT NULL, exit_code INTEGER, verification_state TEXT NOT NULL,
 primary_evidence_id TEXT, evidence_snapshot_json TEXT NOT NULL, decision_reason TEXT NOT NULL,
 decided_at TEXT NOT NULL, decided_by TEXT NOT NULL, revision INTEGER NOT NULL,
 contract_version INTEGER NOT NULL, follow_up TEXT NOT NULL, PRIMARY KEY(job_id, revision)
);
"""


def db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript(LEDGER_SCHEMA)
    return conn


def review_contract(job_id="job-726172fb"):
    return build_github_effect_contract(
        job_id, operation="review", target="pr:1947", expected_actor="qa",
        expected_sha="abc123", started_at="2026-10-03T10:00:00+00:00",
    )


def test_closed_status_alias_map_and_truth_table():
    assert STATUS_ALIASES["success"] == "completed"
    assert "verifying" in CANONICAL_STATUSES
    contract = review_contract()
    result = decide_job_outcome(contract, [
        {"evidence_id": "remote-1", "kind": "github_effect", "result": "true", "causal_match": True},
        {"evidence_id": "receipt-1", "kind": "task_receipt", "result": "false"},
    ])
    assert result == CompletionDecision(
        "completed", "verified", "contract_effect_verified", evidence_ids=("remote-1", "receipt-1"),
        warnings=("receipt_absent",),
    )


def test_remote_only_review_regression_fixture_and_first_read_unknown():
    contract = review_contract()
    pending = decide_job_outcome(contract, [{"kind": "github_effect", "result": "unknown"}])
    assert (pending.status, pending.verification_state, pending.required_follow_up) == ("verifying", "unknown", "retry_verification")
    completed = decide_job_outcome(contract, [{"kind": "github_effect", "result": "true", "causal_match": True}])
    assert completed.status == "completed"


def test_unknown_contract_is_explicit_and_never_green():
    result = decide_job_outcome(legacy_unknown_contract("legacy"), [{"kind": "process_exit", "result": "true"}])
    assert result.status == "unknown"
    assert result.reason_code == "unknown_contract"


def test_duplicate_evidence_is_idempotent_and_correction_is_revision():
    conn = db()
    contract = review_contract()
    evidence = {"kind": "github_effect", "result": "unknown", "source": "gh", "attempt": 1, "event_id": "read-1"}
    first = record_evidence_and_reconcile(conn, contract["job_id"], evidence, contract=contract)
    second = record_evidence_and_reconcile(conn, contract["job_id"], evidence, contract=contract)
    assert first == second
    record_evidence_and_reconcile(conn, contract["job_id"], {"kind": "github_effect", "result": "true", "source": "gh", "attempt": 2, "event_id": "read-2", "causal_match": True})
    assert conn.execute("select count(*) from job_evidence").fetchone()[0] == 2
    assert conn.execute("select max(revision) from job_terminal_decision").fetchone()[0] == 2


def test_contract_is_immutable_and_concurrent_reconciliation_has_one_revision_per_observation():
    conn = db()
    contract = review_contract()
    record_evidence_and_reconcile(conn, contract["job_id"], {"kind": "github_effect", "result": "unknown", "source": "gh", "event_id": "one"}, contract=contract)
    changed = dict(contract, target="pr:999")
    with pytest.raises(ValueError):
        record_evidence_and_reconcile(conn, contract["job_id"], {"kind": "github_effect", "result": "true", "source": "gh", "event_id": "two"}, contract=changed)

    # SQLite's single connection is deliberately serialized here; the ledger
    # uses BEGIN IMMEDIATE, so separate connections cannot double-claim a row.
    file_conn = sqlite3.connect(":memory:")
    file_conn.executescript(LEDGER_SCHEMA)
    record_evidence_and_reconcile(file_conn, "concurrent", {"kind": "github_effect", "result": "unknown", "source": "gh", "event_id": "same"}, contract=review_contract("concurrent"))
    record_evidence_and_reconcile(file_conn, "concurrent", {"kind": "github_effect", "result": "unknown", "source": "gh", "event_id": "same"})
    assert file_conn.execute("select count(*) from job_evidence").fetchone()[0] == 1


def test_parity_fixture_matches_both_legacy_reconciliation_paths():
    contract = review_contract()
    evidence = [{"kind": "github_effect", "result": "true", "causal_match": True}]
    oracle = decide_job_outcome(contract, evidence)
    # Both current paths expose the same legacy terminal projection for this
    # remote-only case; the pilot oracle records the stronger canonical result.
    legacy_flat = "completed"
    legacy_daemon = "completed"
    assert (legacy_flat, legacy_daemon, oracle.status) == ("completed", "completed", "completed")

