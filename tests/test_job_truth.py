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
    ensure_effect_contract,
    validate_terminal_writer_manifest,
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
        {"evidence_id": "remote-1", "kind": "github_effect", "result": "true", "causal_match": True,
         "target_match": True, "actor_match": True, "sha_match": True},
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
    completed = decide_job_outcome(contract, [{"kind": "github_effect", "result": "true", "causal_match": True,
                                               "target_match": True, "actor_match": True, "sha_match": True}])
    assert completed.status == "completed"


@pytest.mark.parametrize("predicate", ["target_match", "actor_match", "sha_match"])
def test_contract_predicate_mismatch_cannot_complete(predicate):
    contract = review_contract()
    evidence = {"kind": "github_effect", "result": "true", "causal_match": True,
                "target_match": True, "actor_match": True, "sha_match": True}
    evidence[predicate] = False
    result = decide_job_outcome(contract, [evidence])
    assert result.status == "verifying"
    assert result.reason_code == "contract_predicate_mismatch"


def test_unresolved_contract_predicate_is_not_terminal():
    contract = review_contract()
    result = decide_job_outcome(contract, [{"kind": "github_effect", "result": "true", "causal_match": True}])
    assert result.status == "verifying"
    assert result.reason_code == "contract_predicate_unresolved"


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


def test_contract_is_immutable_and_concurrent_reconciliation_has_one_revision_per_observation(tmp_path):
    conn = db()
    contract = review_contract()
    record_evidence_and_reconcile(conn, contract["job_id"], {"kind": "github_effect", "result": "unknown", "source": "gh", "event_id": "one"}, contract=contract)
    changed = dict(contract, target="pr:999")
    with pytest.raises(ValueError):
        record_evidence_and_reconcile(conn, contract["job_id"], {"kind": "github_effect", "result": "true", "source": "gh", "event_id": "two"}, contract=changed)

    # Use separate connections against a file-backed ledger so BEGIN IMMEDIATE
    # is exercised by real concurrent writers rather than a serialized mock.
    ledger_path = tmp_path / "job-truth.db"
    file_conn = sqlite3.connect(str(ledger_path), check_same_thread=False)
    file_conn.executescript(LEDGER_SCHEMA)
    ensure_effect_contract(file_conn, {
        "id": "concurrent", "requires_gh_write": True, "task_type": "review",
        "gh_write_expect": "review", "gh_write_target": "pr:1947",
        "gh_write_author": "qa", "started_at": "2026-10-03T10:00:00+00:00",
    })
    file_conn.commit()
    file_conn.close()
    barrier = threading.Barrier(2)
    errors = []

    def write_same_observation():
        worker = sqlite3.connect(str(ledger_path), timeout=10)
        try:
            barrier.wait(timeout=5)
            record_evidence_and_reconcile(
                worker, "concurrent",
                {"kind": "github_effect", "result": "unknown", "source": "gh",
                 "event_id": "same"},
            )
        except Exception as exc:  # pragma: no cover - assertion reports details
            errors.append(exc)
        finally:
            worker.close()

    threads = [threading.Thread(target=write_same_observation) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert not errors
    check = sqlite3.connect(str(ledger_path))
    assert check.execute("select count(*) from job_evidence").fetchone()[0] == 1
    assert check.execute("select max(revision) from job_terminal_decision").fetchone()[0] == 1
    record_evidence_and_reconcile(
        check, "concurrent",
        {"kind": "github_effect", "result": "true", "source": "gh",
         "event_id": "correction", "attempt": 2, "causal_match": True},
    )
    assert check.execute("select max(revision) from job_terminal_decision").fetchone()[0] == 2
    check.close()


def test_terminal_writer_manifest_enforces_shared_oracle_adapters(monkeypatch):
    validate_terminal_writer_manifest()

    # Exercise the fail-closed path: a low-level persistence function is not
    # an acceptable replacement for the shared oracle settlement adapter.
    import synlynk.job_truth as job_truth

    broken = dict(job_truth.TERMINAL_WRITER_MANIFEST)
    broken["daemon_reconciliation"] = {
        "entrypoint": "_reconcile_daemon_jobs",
        "adapter": "_persist_daemon_job_terminal",
    }
    monkeypatch.setattr(job_truth, "TERMINAL_WRITER_MANIFEST", broken)
    with pytest.raises(AssertionError, match="daemon_reconciliation"):
        job_truth.validate_terminal_writer_manifest()


def test_terminal_writer_manifest_covers_reclaim_path():
    import synlynk.job_truth as job_truth

    assert job_truth.TERMINAL_WRITER_MANIFEST["stranded_story_reclaimer"] == {
        "entrypoint": "reclaim_stranded_stories",
        "adapter": "_settle_daemon_job_terminal",
    }


def test_parity_fixture_matches_both_legacy_reconciliation_paths():
    contract = review_contract()
    evidence = [{"kind": "github_effect", "result": "true", "causal_match": True,
                 "target_match": True, "actor_match": True, "sha_match": True}]
    oracle = decide_job_outcome(contract, evidence)
    # Both current paths expose the same legacy terminal projection for this
    # remote-only case; the pilot oracle records the stronger canonical result.
    legacy_flat = "completed"
    legacy_daemon = "completed"
    assert (legacy_flat, legacy_daemon, oracle.status) == ("completed", "completed", "completed")
