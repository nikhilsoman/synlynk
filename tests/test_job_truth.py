import json
import sqlite3
import threading

from synlynk.db_schema import _DB_SCHEMA
from synlynk.job_truth import (
    EffectContract,
    TERMINAL_WRITER_MANIFEST,
    assert_terminal_writer_manifest,
    build_github_effect_contract,
    canonical_status,
    decide_job_outcome,
    legacy_default_contract,
    record_evidence_and_reconcile,
)


def _db(tmp_path, name="truth.db"):
    conn = sqlite3.connect(tmp_path / name, timeout=30, check_same_thread=False)
    conn.executescript(_DB_SCHEMA)
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at) VALUES (?, ?, ?, ?, ?)",
        ("job-1", "qa", "review", "running", "2026-10-03T00:00:00Z"),
    )
    conn.commit()
    return conn


def test_closed_status_aliases_and_manifest():
    assert canonical_status("success") == "completed"
    assert canonical_status("not-a-status") == "unknown"
    assert TERMINAL_WRITER_MANIFEST
    assert_terminal_writer_manifest()


def test_contract_builder_round_trip_is_versioned_and_immutable():
    contract = build_github_effect_contract(
        "job-1", "review", "pr:1947", expected_actor="qa", expected_sha="abc123", expected_id="review-9"
    )
    assert contract.kind == "github_review"
    assert contract.contract_version == 1
    payload = contract.as_dict()
    assert payload["required_predicates"]
    assert legacy_default_contract("legacy").kind == "unknown_contract"


def test_oracle_remote_effect_beats_missing_receipt_permission_and_exit():
    contract = build_github_effect_contract("job-1", "review", "pr:1947", expected_actor="qa")
    decision = decide_job_outcome(contract, [
        {"evidence_id": "exit", "kind": "process_exit", "result": "false"},
        {"evidence_id": "receipt", "kind": "task_receipt", "result": "false"},
        {"evidence_id": "denial", "kind": "permission_denied", "result": "true"},
        {"evidence_id": "gh", "kind": "github_effect", "result": "true", "causal": True,
         "target_match": True, "actor_match": True},
    ])
    assert decision.status == "completed"
    assert decision.verification_state == "verified"
    assert decision.warnings == ("receipt_missing",)


def test_oracle_first_remote_miss_is_verifying_then_expires():
    contract = build_github_effect_contract("job-1", "review", "pr:1947")
    evidence = [{"kind": "github_effect", "result": "unknown", "evidence_id": "miss"}]
    assert decide_job_outcome(contract, evidence).status == "verifying"
    assert decide_job_outcome(contract, evidence, retry_attempt=3, deadline_reached=True).status == "failed_verification"


def test_reconciliation_is_append_only_duplicate_safe_and_correctable(tmp_path):
    conn = _db(tmp_path)
    contract = build_github_effect_contract("job-1", "review", "pr:1947")
    miss = {"event_id": "read-1", "source": "gh", "attempt": 1, "kind": "github_effect", "result": "unknown"}
    first = record_evidence_and_reconcile(conn, "job-1", miss, contract=contract)
    duplicate = record_evidence_and_reconcile(conn, "job-1", miss, contract=contract)
    assert first.revision == duplicate.revision == 1
    assert conn.execute("SELECT COUNT(*) FROM job_evidence").fetchone()[0] == 1
    landed = {"event_id": "read-2", "source": "gh", "attempt": 2, "kind": "github_effect", "result": "true", "causal": True, "target_match": True, "actor_match": True}
    corrected = record_evidence_and_reconcile(conn, "job-1", landed, contract=contract)
    assert corrected.status == "completed"
    assert corrected.revision == 2
    assert conn.execute("SELECT COUNT(*) FROM job_terminal_decision").fetchone()[0] == 2
    assert conn.execute("SELECT kind FROM job_effect_contract WHERE job_id='job-1'").fetchone()[0] == "github_review"


def test_concurrent_reconciliation_has_one_evidence_per_event(tmp_path):
    path = tmp_path / "concurrent.db"
    conn = _db(tmp_path, "concurrent.db")
    conn.close()
    contract = build_github_effect_contract("job-1", "review", "pr:1947")
    errors = []

    def worker():
        db = sqlite3.connect(path, timeout=30)
        try:
            record_evidence_and_reconcile(db, "job-1", {"event_id": "same", "source": "gh", "attempt": 1, "kind": "github_effect", "result": "true", "causal": True, "target_match": True, "actor_match": True}, contract=contract)
        except Exception as exc:
            errors.append(exc)
        finally:
            db.close()

    # Seed through the same file after _db has initialized its schema.
    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    check = sqlite3.connect(path)
    assert check.execute("SELECT COUNT(*) FROM job_evidence").fetchone()[0] == 1
    assert check.execute("SELECT COUNT(*) FROM job_terminal_decision").fetchone()[0] == 1
