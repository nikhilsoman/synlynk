import json
import os
import sqlite3
import subprocess
import tempfile
import hashlib

import pytest


@pytest.fixture
def ledger_conn():
    return sqlite3.connect(":memory:")


def _sample(job_id: str, *, cohort: str = "validation") -> dict:
    return {
        "job_id": job_id,
        "cohort": cohort,
        "task_class": "test_summary",
        "task_digest": f"digest-{job_id}",
        "receipt": {"job_id": job_id, "isolated": True},
    }


@pytest.fixture
def resume_identity_key(tmp_path, monkeypatch):
    key_path = tmp_path / "identity.key"
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_path)],
        check=True,
        capture_output=True,
    )
    from synlynk import local_pilot_ledger

    monkeypatch.setattr(local_pilot_ledger, "_host_identity_public_key_path", lambda: str(key_path) + ".pub")
    return str(key_path)


def _signed_resume_payload(key_path: str, payload=None) -> dict:
    payload = payload or {"approved": True}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as message:
        message.write(canonical)
        message_path = message.name
    try:
        result = subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", key_path, "-n", "synlynk-local-pilot-resume", message_path],
            check=True,
            capture_output=True,
            text=True,
        )
        del result
        with open(message_path + ".sig", encoding="utf-8") as signature_file:
            signature = signature_file.read()
    finally:
        for path in (message_path, message_path + ".sig"):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
    return {"approval_payload": payload, "signature": signature}


def _resume_authorization_payload(conn, key_path: str, **overrides) -> dict:
    from synlynk.local_pilot_ledger import resume_authorization_context

    context = resume_authorization_context(conn)
    preflight_receipt = {"result": "passed"}
    authorization = {
        **context,
        "config_fingerprint": "disabled-20-percent-one-concurrent",
        "remediation_reference": "issue-2342",
        "verification_reference": "review-2349",
        "preflight_receipt": preflight_receipt,
        "preflight_receipt_digest": hashlib.sha256(
            json.dumps(preflight_receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }
    authorization.update(overrides)
    signed = _signed_resume_payload(key_path, authorization)
    return {
        "signed_payload": {
            "authorization": signed["approval_payload"],
            "signature": signed["signature"],
        }
    }


def test_migration_seeds_the_immutable_historical_cohort_once(ledger_conn):
    from synlynk.local_pilot_ledger import load_pilot_status
    from synlynk.migrations.runner import run_pending_migrations

    run_pending_migrations(ledger_conn)
    first_status = load_pilot_status(ledger_conn)

    run_pending_migrations(ledger_conn)
    second_status = load_pilot_status(ledger_conn)

    expected = {"cohort": "historical", "accepted": 8, "eligible": 12}
    assert first_status["historical"] == expected
    assert second_status["historical"] == expected
    assert ledger_conn.execute(
        "SELECT COUNT(*) FROM local_pilot_cohort_summaries WHERE cohort = 'historical'"
    ).fetchone()[0] == 1


def test_admission_rejects_duplicate_jobs_and_unknown_cohorts(ledger_conn):
    from synlynk.local_pilot_ledger import ensure_local_pilot_ledger, record_admission

    ensure_local_pilot_ledger(ledger_conn)
    record_admission(ledger_conn, _sample("job-1"))

    with pytest.raises(ValueError, match="duplicate job_id"):
        record_admission(ledger_conn, _sample("job-1"))
    with pytest.raises(ValueError, match="unknown cohort"):
        record_admission(ledger_conn, _sample("job-2", cohort="unknown"))


def test_outcome_recording_rejects_unknown_verdicts(ledger_conn):
    from synlynk.local_pilot_ledger import (
        ensure_local_pilot_ledger,
        record_admission,
        record_quality_verdict,
        record_safety_outcome,
    )

    ensure_local_pilot_ledger(ledger_conn)
    record_admission(ledger_conn, _sample("job-1"))

    with pytest.raises(ValueError, match="unknown safety verdict"):
        record_safety_outcome(ledger_conn, "job-1", "unsafe-ish", "bad", None)
    with pytest.raises(ValueError, match="unknown quality verdict"):
        record_quality_verdict(ledger_conn, "job-1", "codex", "maybe", "bad", "rule")


def test_pause_local_pilot_uses_the_approved_configuration_helper(ledger_conn, monkeypatch):
    """Bypassing the helper could write the wrong split config surface."""
    from synlynk.local_pilot_ledger import ensure_local_pilot_ledger, pause_local_pilot

    updates = []
    monkeypatch.setattr("synlynk.load_workspace", lambda: {"local_pilot": {"enabled": True, "share": 0.2}})
    monkeypatch.setattr("synlynk._update_config", lambda update: updates.append(update))

    ensure_local_pilot_ledger(ledger_conn)
    pause_local_pilot("host_execution", conn=ledger_conn)

    assert updates == [{"local_pilot": {"enabled": False, "share": 0.2, "pause_reason": "host_execution"}}]


def test_pause_revokes_active_resume_authorization_before_disabling_config(
    ledger_conn, resume_identity_key, monkeypatch
):
    """A safety pause must leave neither config nor durable authority active."""
    from synlynk.local_pilot_ledger import (
        activate_resume_authorization,
        active_resume_authorization,
        create_resume_authorization,
        ensure_local_pilot_ledger,
        pause_local_pilot,
    )

    ensure_local_pilot_ledger(ledger_conn)
    staged = create_resume_authorization(
        ledger_conn, _resume_authorization_payload(ledger_conn, resume_identity_key),
    )
    activate_resume_authorization(ledger_conn, staged["authorization_id"])
    updates = []
    monkeypatch.setattr("synlynk.load_workspace", lambda: {"local_pilot": {"enabled": True, "share": 0.2}})

    def update_config(update):
        # This is the ordering boundary: config replacement cannot observe an
        # active authority that a concurrent resume might otherwise preserve.
        assert active_resume_authorization(ledger_conn) is None
        updates.append(update)

    monkeypatch.setattr("synlynk._update_config", update_config)

    pause_local_pilot("post_watermark_safety_failure", conn=ledger_conn)

    assert active_resume_authorization(ledger_conn) is None
    assert updates == [{"local_pilot": {
        "enabled": False, "share": 0.2, "pause_reason": "post_watermark_safety_failure",
    }}]


def test_later_review_preserves_an_earlier_jobs_evidence(ledger_conn):
    from synlynk.local_pilot_ledger import (
        ensure_local_pilot_ledger,
        record_admission,
        record_quality_verdict,
        record_safety_outcome,
    )

    ensure_local_pilot_ledger(ledger_conn)
    earlier = record_admission(ledger_conn, _sample("job-1"))
    record_safety_outcome(ledger_conn, "job-1", "passed", "isolated", {"safe": True})
    record_admission(ledger_conn, _sample("job-2"))
    record_quality_verdict(ledger_conn, "job-2", "codex", "accepted", "correct", "qualified")

    stored = ledger_conn.execute(
        "SELECT receipt_digest, safety_verdict, safety_reason, quality_verdict "
        "FROM local_pilot_evidence WHERE job_id = 'job-1'"
    ).fetchone()
    assert stored == (earlier["receipt_digest"], "passed", "isolated", "pending")


def test_database_rejects_deleting_evidence_or_mutating_or_deleting_history(ledger_conn):
    """Removing audit rows or changing the fixed 8/12 record must fail in SQLite."""
    from synlynk.local_pilot_ledger import ensure_local_pilot_ledger, record_admission

    ensure_local_pilot_ledger(ledger_conn)
    record_admission(ledger_conn, _sample("job-1"))

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        ledger_conn.execute("DELETE FROM local_pilot_evidence WHERE job_id = 'job-1'")
    with pytest.raises(sqlite3.IntegrityError, match="historical"):
        ledger_conn.execute(
            "UPDATE local_pilot_cohort_summaries SET accepted = 0 WHERE cohort = 'historical'"
        )
    with pytest.raises(sqlite3.IntegrityError, match="historical"):
        ledger_conn.execute("DELETE FROM local_pilot_cohort_summaries WHERE cohort = 'historical'")


def test_status_separates_pending_rejected_and_safety_failed_samples(ledger_conn):
    """Changing status to count raw admissions as eligible would break this ledger view."""
    from synlynk.local_pilot_ledger import (
        ensure_local_pilot_ledger,
        load_pilot_status,
        record_admission,
        record_quality_verdict,
        record_safety_outcome,
    )

    ensure_local_pilot_ledger(ledger_conn)
    record_admission(ledger_conn, _sample("pending"))
    record_admission(ledger_conn, _sample("rejected"))
    record_safety_outcome(ledger_conn, "rejected", "passed", "contained", {"safe": True})
    record_quality_verdict(ledger_conn, "rejected", "codex", "rejected", "incorrect", "qualified")
    record_admission(ledger_conn, _sample("unsafe"))
    record_safety_outcome(ledger_conn, "unsafe", "failed", "scope drift", {"safe": False})

    assert load_pilot_status(ledger_conn)["validation"] == {
        "cohort": "validation",
        "accepted": 0,
        "eligible": 0,
        "pending": 1,
        "rejected": 1,
        "safety_failed": 1,
    }


def test_expansion_status_reports_only_the_run_after_its_latest_quality_rejection(ledger_conn):
    """A status view that reports all accepts as consecutive would bypass the reset gate."""
    from synlynk.local_pilot_ledger import (
        ensure_local_pilot_ledger,
        load_pilot_status,
        record_admission,
        record_quality_verdict,
        record_safety_outcome,
    )

    ensure_local_pilot_ledger(ledger_conn)
    for job_id, verdict in (("accepted-before-reset", "accepted"), ("reset", "rejected"), ("accepted-after-reset", "accepted")):
        record_admission(ledger_conn, _sample(job_id, cohort="expansion"))
        record_safety_outcome(ledger_conn, job_id, "passed", "contained", {"safe": True})
        record_quality_verdict(ledger_conn, job_id, "codex", verdict, "reviewed", "qualified")

    expansion = load_pilot_status(ledger_conn)["expansion"]
    assert expansion["accepted"] == 2
    assert expansion["rejected"] == 1
    assert expansion["consecutive_accepted"] == 1


def test_resume_authorization_is_immutable_and_sets_the_active_epoch(ledger_conn, resume_identity_key):
    """Recovery must add a durable fact, never rewrite the safety ledger."""
    from synlynk.local_pilot_ledger import (
        activate_resume_authorization,
        create_resume_authorization,
        ensure_local_pilot_ledger,
        record_admission,
        record_safety_outcome,
    )

    ensure_local_pilot_ledger(ledger_conn)
    record_admission(ledger_conn, _sample("before-resume"))
    record_safety_outcome(ledger_conn, "before-resume", "failed", "scope drift", {"safe": False})
    authorization = create_resume_authorization(
        ledger_conn,
        _resume_authorization_payload(ledger_conn, resume_identity_key, authorization_id="resume-1"),
    )
    active = activate_resume_authorization(ledger_conn, authorization["authorization_id"])

    assert authorization["state"] == "activating"
    assert active["state"] == "active"
    assert active["safety_watermark"] == 1
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        ledger_conn.execute(
            "UPDATE local_pilot_resume_authorizations SET remediation_reference = 'rewritten' "
            "WHERE authorization_id = 'resume-1'"
        )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        ledger_conn.execute(
            "DELETE FROM local_pilot_resume_authorizations WHERE authorization_id = 'resume-1'"
        )


def test_status_keeps_historical_failures_and_counts_only_active_epoch_evidence(ledger_conn, resume_identity_key):
    """Pre-incident samples must not advance the post-resume validation lane."""
    from synlynk.local_pilot_ledger import (
        activate_resume_authorization,
        create_resume_authorization,
        ensure_local_pilot_ledger,
        load_pilot_status,
        record_admission,
        record_quality_verdict,
        record_safety_outcome,
    )

    ensure_local_pilot_ledger(ledger_conn)
    record_admission(ledger_conn, _sample("historical-failure"))
    record_safety_outcome(ledger_conn, "historical-failure", "failed", "scope drift", {"safe": False})
    record_admission(ledger_conn, _sample("old-accept"))
    record_safety_outcome(ledger_conn, "old-accept", "passed", "contained", {"safe": True})
    record_quality_verdict(ledger_conn, "old-accept", "codex", "accepted", "correct", "qualified")
    authorization = create_resume_authorization(
        ledger_conn,
        _resume_authorization_payload(ledger_conn, resume_identity_key),
    )
    activate_resume_authorization(ledger_conn, authorization["authorization_id"])
    record_admission(ledger_conn, _sample("new-accept"))
    record_safety_outcome(ledger_conn, "new-accept", "passed", "contained", {"safe": True})
    record_quality_verdict(ledger_conn, "new-accept", "codex", "accepted", "correct", "qualified")

    status = load_pilot_status(ledger_conn)

    assert status["historical_safety_failures"] == 1
    assert status["active_epoch_safety_failures"] == 0
    assert status["active_authorization"]["authorization_id"] == authorization["authorization_id"]
    assert status["validation"]["accepted"] == 1


def test_resume_authorization_requires_a_valid_host_signed_payload(ledger_conn, resume_identity_key):
    """An arbitrary JSON object must not become a durable resume authority."""
    from synlynk.local_pilot_ledger import create_resume_authorization, ensure_local_pilot_ledger

    ensure_local_pilot_ledger(ledger_conn)
    unsigned = {"signed_payload": {"authorization": {}}}
    malformed = {"signed_payload": {"approval_payload": {"approved": True}}}
    invalid = _resume_authorization_payload(ledger_conn, resume_identity_key)
    invalid["signed_payload"]["authorization"]["config_fingerprint"] = "tampered"
    failed_preflight = _resume_authorization_payload(ledger_conn, resume_identity_key, preflight_receipt={"result": "failed"})

    for payload in (unsigned, malformed, invalid, failed_preflight):
        with pytest.raises(ValueError):
            create_resume_authorization(ledger_conn, payload)


def test_resume_signature_binds_every_authority_field(ledger_conn, resume_identity_key):
    """A valid generic signature cannot be replayed with altered authorization metadata."""
    from synlynk.local_pilot_ledger import create_resume_authorization, ensure_local_pilot_ledger

    ensure_local_pilot_ledger(ledger_conn)
    signed = _signed_resume_payload(resume_identity_key, {"approved": True})
    for field, replacement in (
        ("authorization_id", "replayed-id"),
        ("config_fingerprint", "attacker-config"),
        ("remediation_reference", "attacker-remediation"),
        ("verification_reference", "attacker-verification"),
        ("preflight_receipt", {"result": "passed", "attacker": True}),
    ):
        payload = _resume_authorization_payload(ledger_conn, resume_identity_key)
        payload["signed_payload"]["authorization"][field] = replacement
        with pytest.raises(ValueError):
            create_resume_authorization(ledger_conn, payload)


def test_migration_27_reconciles_legacy_multiple_staged_authorizations(ledger_conn):
    """A v26 ledger must upgrade by failing surplus staged rows before indexing."""
    from synlynk.migrations.m0026_local_pilot_resume_authorization import MIGRATION as migration_26
    from synlynk.migrations.m0027_local_pilot_resume_lifecycle_serialization import MIGRATION as migration_27

    migration_26.up(ledger_conn)
    for authorization_id in ("first", "second"):
        ledger_conn.execute(
            """INSERT INTO local_pilot_resume_authorizations
               (authorization_id, created_at, signed_payload_json, signed_payload_digest,
                config_fingerprint, remediation_reference, verification_reference, safety_watermark,
                preflight_receipt_json, preflight_receipt_digest, state)
               VALUES (?, 'now', '{}', 'digest', 'config', 'remediation', 'verification', 0,
                       '{}', 'digest', 'activating')""",
            (authorization_id,),
        )

    migration_27.up(ledger_conn)

    assert ledger_conn.execute(
        "SELECT authorization_id, state, terminal_reason FROM local_pilot_resume_authorizations ORDER BY rowid"
    ).fetchall() == [
        ("first", "activating", None),
        ("second", "failed", "migration_27_reconciled_surplus_activating_authorization"),
    ]


def test_migration_27_fails_staged_legacy_authorization_when_active_exists(ledger_conn):
    """A v26 active row cannot coexist with any staged recovery after upgrade."""
    from synlynk.migrations.m0026_local_pilot_resume_authorization import MIGRATION as migration_26
    from synlynk.migrations.m0027_local_pilot_resume_lifecycle_serialization import MIGRATION as migration_27

    migration_26.up(ledger_conn)
    for authorization_id, state, activated_at in (("active", "active", "now"), ("staged", "activating", None)):
        ledger_conn.execute(
            """INSERT INTO local_pilot_resume_authorizations
               (authorization_id, created_at, signed_payload_json, signed_payload_digest,
                config_fingerprint, remediation_reference, verification_reference, safety_watermark,
                preflight_receipt_json, preflight_receipt_digest, state, activated_at)
               VALUES (?, 'now', '{}', 'digest', 'config', 'remediation', 'verification', 0,
                       '{}', 'digest', ?, ?)""",
            (authorization_id, state, activated_at),
        )

    migration_27.up(ledger_conn)

    assert ledger_conn.execute(
        "SELECT authorization_id, state, terminal_reason FROM local_pilot_resume_authorizations ORDER BY rowid"
    ).fetchall() == [
        ("active", "active", None),
        ("staged", "failed", "migration_27_reconciled_surplus_activating_authorization"),
    ]
    with pytest.raises(sqlite3.IntegrityError):
        ledger_conn.execute(
            """INSERT INTO local_pilot_resume_authorizations
            (authorization_id, created_at, signed_payload_json, signed_payload_digest,
             config_fingerprint, remediation_reference, verification_reference, safety_watermark,
             preflight_receipt_json, preflight_receipt_digest, state)
            VALUES ('new-stage', 'now', '{}', 'digest', 'config', 'remediation', 'verification', 0,
                    '{}', 'digest', 'activating')"""
        )


def test_resume_authorization_lifecycle_is_serialized_and_reconcilable(ledger_conn, resume_identity_key):
    """Only one staged/active record exists and terminal transitions are explicit."""
    from synlynk.local_pilot_ledger import (
        activate_resume_authorization,
        active_resume_authorization,
        create_resume_authorization,
        ensure_local_pilot_ledger,
        fail_resume_authorization,
        revoke_active_resume_authorization,
    )

    ensure_local_pilot_ledger(ledger_conn)
    first = create_resume_authorization(
        ledger_conn, _resume_authorization_payload(ledger_conn, resume_identity_key, authorization_id="first")
    )
    with pytest.raises(ValueError, match="activation in progress"):
        create_resume_authorization(ledger_conn, _resume_authorization_payload(ledger_conn, resume_identity_key))
    failed = fail_resume_authorization(ledger_conn, first["authorization_id"], "config write failed")
    assert failed["state"] == "failed"
    assert failed["terminal_reason"] == "config write failed"

    active = activate_resume_authorization(
        ledger_conn,
        create_resume_authorization(
            ledger_conn, _resume_authorization_payload(ledger_conn, resume_identity_key, authorization_id="second")
        )["authorization_id"],
    )
    assert active_resume_authorization(ledger_conn)["authorization_id"] == active["authorization_id"]
    with pytest.raises(ValueError, match="authorization is already active"):
        create_resume_authorization(ledger_conn, _resume_authorization_payload(ledger_conn, resume_identity_key))
    revoked = revoke_active_resume_authorization(ledger_conn, "new safety failure")
    assert revoked["state"] == "revoked"
    assert active_resume_authorization(ledger_conn) is None
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        ledger_conn.execute(
            "UPDATE local_pilot_resume_authorizations SET state = 'active' WHERE authorization_id = 'first'"
        )


def test_active_epoch_excludes_pre_resume_expansion_counters(ledger_conn, resume_identity_key):
    """An old expansion run cannot make the recovered pilot promotion-eligible."""
    from synlynk.local_pilot_ledger import (
        activate_resume_authorization,
        create_resume_authorization,
        ensure_local_pilot_ledger,
        load_pilot_status,
        record_admission,
        record_quality_verdict,
        record_safety_outcome,
    )

    ensure_local_pilot_ledger(ledger_conn)
    for index in range(10):
        job_id = f"old-expansion-{index}"
        record_admission(ledger_conn, _sample(job_id, cohort="expansion"))
        record_safety_outcome(ledger_conn, job_id, "passed", "contained", {"safe": True})
        record_quality_verdict(ledger_conn, job_id, "codex", "accepted", "correct", "qualified")
    record_admission(ledger_conn, _sample("old-expansion-rejected", cohort="expansion"))
    record_safety_outcome(ledger_conn, "old-expansion-rejected", "passed", "contained", {"safe": True})
    record_quality_verdict(ledger_conn, "old-expansion-rejected", "codex", "rejected", "incorrect", "qualified")
    record_admission(ledger_conn, _sample("old-expansion-pending", cohort="expansion"))
    record_admission(ledger_conn, _sample("old-expansion-unsafe", cohort="expansion"))
    record_safety_outcome(ledger_conn, "old-expansion-unsafe", "failed", "scope drift", {"safe": False})
    authorization = create_resume_authorization(ledger_conn, _resume_authorization_payload(ledger_conn, resume_identity_key))
    activate_resume_authorization(ledger_conn, authorization["authorization_id"])

    expansion = load_pilot_status(ledger_conn)["expansion"]

    assert expansion == {
        "cohort": "expansion", "accepted": 0, "eligible": 0, "pending": 0,
        "rejected": 0, "safety_failed": 0, "consecutive_accepted": 0,
    }


def test_ensure_uses_migration_history_and_rolls_back_a_failed_migration(ledger_conn, monkeypatch):
    """A failed schema install must leave neither schema nor migration history behind."""
    from synlynk.local_pilot_ledger import ensure_local_pilot_ledger
    from synlynk.migrations import Migration
    from synlynk.migrations import runner as migration_runner

    def fail_after_schema_creation(conn):
        conn.execute("CREATE TABLE local_pilot_atomicity_probe (id INTEGER PRIMARY KEY)")
        raise RuntimeError("forced migration failure")

    monkeypatch.setattr(
        migration_runner,
        "MIGRATIONS",
        [Migration(version=24, name="atomicity_probe", up=fail_after_schema_creation)],
    )

    with pytest.raises(RuntimeError, match="forced migration failure"):
        ensure_local_pilot_ledger(ledger_conn)

    assert ledger_conn.execute("PRAGMA user_version").fetchone()[0] == 0
    assert ledger_conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'local_pilot_atomicity_probe'"
    ).fetchone() is None
    assert ledger_conn.execute("SELECT COUNT(*) FROM migration_history").fetchone()[0] == 0


def test_local_pilot_reviewer_selection_uses_frontier_order_and_excludes_local_and_author(ledger_conn):
    """Selecting Local or the author would defeat independent factual review."""
    from synlynk.local_pilot_ledger import select_local_pilot_reviewer

    selection = select_local_pilot_reviewer(
        ledger_conn,
        author_harness="codex",
        eligible=["local", "claude", "codex", "agy", "grok"],
    )

    assert selection.candidates == ("grok", "claude", "agy")
    assert selection.reviewer == "grok"
    assert selection.reason == "selected grok as highest-ranked eligible frontier reviewer"


def test_local_pilot_review_requires_safety_and_persists_a_secret_free_factual_brief(ledger_conn):
    """A safety-pending job must not produce a reviewer brief or reveal credentials."""
    from synlynk.local_pilot_ledger import (
        ensure_local_pilot_ledger,
        record_admission,
        record_safety_outcome,
        start_local_pilot_review,
    )

    ensure_local_pilot_ledger(ledger_conn)
    sample = _sample("review-job")
    sample["receipt"] = {
        **sample["receipt"],
        "author_harness": "codex",
        "task_intent": "Summarize the selected tests",
        "expected_factual_claims": ["lists failures", "names affected paths"],
        "answer_log_reference": "logs/review-job.log",
        "OPENAI_API_KEY": "must-not-appear",
    }
    record_admission(ledger_conn, sample)

    with pytest.raises(ValueError, match="passed safety receipt"):
        start_local_pilot_review(ledger_conn, "review-job")

    record_safety_outcome(ledger_conn, "review-job", "passed", "contained", {"safe": True})
    brief = start_local_pilot_review(ledger_conn, "review-job")

    assert brief == {
        "job_id": "review-job",
        "reviewer": "grok",
        "selection_reason": "selected grok as highest-ranked eligible frontier reviewer",
        "task_intent": "Summarize the selected tests",
        "expected_factual_claims": ["lists failures", "names affected paths"],
        "local_answer_log_reference": "logs/review-job.log",
        "automated_receipt_result": "passed",
    }
    stored = ledger_conn.execute(
        "SELECT candidate_json, selected_harness, selection_reason FROM local_pilot_review_selections "
        "WHERE job_id = 'review-job'"
    ).fetchone()
    assert stored == (
        '["grok","claude","agy"]',
        "grok",
        "selected grok as highest-ranked eligible frontier reviewer",
    )


def test_record_local_pilot_review_only_changes_quality_once_for_the_selected_reviewer(ledger_conn):
    """Wrong/duplicate reviews must not mutate safety or operational pilot settings."""
    from synlynk.local_pilot_ledger import (
        ensure_local_pilot_ledger,
        record_admission,
        record_local_pilot_review,
        record_safety_outcome,
        start_local_pilot_review,
    )

    ensure_local_pilot_ledger(ledger_conn)
    sample = _sample("verdict-job")
    sample["receipt"] = {**sample["receipt"], "author_harness": "codex"}
    record_admission(ledger_conn, sample)
    record_safety_outcome(ledger_conn, "verdict-job", "passed", "contained", {"safe": True})
    start_local_pilot_review(ledger_conn, "verdict-job")

    with pytest.raises(ValueError, match="selected reviewer"):
        record_local_pilot_review(ledger_conn, "verdict-job", "claude", "accept", "looks right")
    with pytest.raises(ValueError, match="rationale is required"):
        record_local_pilot_review(ledger_conn, "verdict-job", "grok", "accept", "  ")
    with pytest.raises(ValueError, match="unknown review verdict"):
        record_local_pilot_review(ledger_conn, "verdict-job", "grok", "maybe", "unclear")

    result = record_local_pilot_review(ledger_conn, "verdict-job", "grok", "accept", "claims checked")

    assert result["quality_verdict"] == "accepted"
    assert result["safety_verdict"] == "passed"
    with pytest.raises(ValueError, match="already recorded"):
        record_local_pilot_review(ledger_conn, "verdict-job", "grok", "reject", "changed mind")
