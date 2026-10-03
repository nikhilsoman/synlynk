import json
import sqlite3

from synlynk.cost_audit import (
    cost_audit_report,
    correct_source_record,
    import_provider_export,
    ingest_source_records,
    reconcile_cost_audit,
)
from synlynk.db_schema import _DB_SCHEMA
from synlynk.job_truth import (
    build_github_effect_contract,
    ensure_terminal_outbox,
    record_evidence_and_reconcile,
)


def ledger():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_DB_SCHEMA)
    conn.execute(
        """CREATE TABLE cost_entries (
           id INTEGER PRIMARY KEY, job_id TEXT, decision_revision INTEGER,
           agent TEXT, harness TEXT, model TEXT, input_tokens INTEGER,
           output_tokens INTEGER, cache_read_tokens INTEGER, total_cost_usd REAL,
           actual_usd REAL, payment_mode TEXT, cost_source TEXT, recorded_at TEXT
        )"""
    )
    return conn


def completed_job(conn, job_id="job-a"):
    contract = build_github_effect_contract(
        job_id, operation="review", target="pr:42", expected_actor="qa",
        expected_sha="abc123",
    )
    record_evidence_and_reconcile(
        conn, job_id,
        {"kind": "github_effect", "result": "true", "source": "gh",
         "event_id": "review-verified", "causal_match": True,
         "target_match": True, "actor_match": True, "sha_match": True},
        contract=contract,
    )


def test_terminal_outbox_reconciles_idempotently_and_missing_cost_does_not_change_status():
    conn = ledger()
    completed_job(conn)
    before = tuple(conn.execute(
        "SELECT status, decision_reason, revision FROM job_terminal_decision WHERE job_id='job-a'"
    ).fetchone())

    first = reconcile_cost_audit(conn, import_legacy=False)
    second = reconcile_cost_audit(conn, import_legacy=False)

    row = conn.execute("SELECT state, reason_code FROM cost_audit_link WHERE job_id='job-a'").fetchone()
    assert tuple(row) == ("missing", "telemetry_absent")
    assert first["reconciled"] == 1
    assert second["reconciled"] == 0
    assert conn.execute("SELECT COUNT(*) FROM cost_audit_event WHERE event_type='decision_observed'").fetchone()[0] == 1
    after = tuple(conn.execute(
        "SELECT status, decision_reason, revision FROM job_terminal_decision WHERE job_id='job-a'"
    ).fetchone())
    assert after == before == ("completed", "contract_effect_verified", 1)


def test_provider_export_replay_and_late_cost_append_correction(tmp_path):
    conn = ledger()
    completed_job(conn)
    reconcile_cost_audit(conn, import_legacy=False)
    before_decision = tuple(conn.execute(
        "SELECT status, decision_reason, revision FROM job_terminal_decision WHERE job_id='job-a'"
    ).fetchone())

    export = tmp_path / "billing.jsonl"
    export.write_text(json.dumps({
        "record_id": "provider-req-1", "job_id": "job-a", "decision_revision": 1,
        "request_id": "request-1", "model": "model-x", "input_tokens": 100,
        "output_tokens": 20, "amount": "0.012500", "currency": "USD",
        "usage_start": "2026-10-03T10:00:00Z", "usage_end": "2026-10-03T10:01:00Z",
    }) + "\n")
    imported = import_provider_export(conn, export, provider="example-provider", source_account="acct-1")
    repeated = import_provider_export(conn, export, provider="example-provider", source_account="acct-1")
    reconcile = reconcile_cost_audit(conn, import_legacy=False)

    assert imported["accepted"] == 1
    assert repeated["duplicates"] == 1
    assert reconcile["reconciled"] == 1
    link = conn.execute(
        "SELECT state, billed_amount_decimal, currency, input_tokens FROM cost_audit_link WHERE job_id='job-a'"
    ).fetchone()
    assert tuple(link) == ("linked", "0.0125", "USD", 100)
    events = conn.execute(
        "SELECT event_type, supersedes_event_id FROM cost_audit_event WHERE job_id='job-a' ORDER BY recorded_at"
    ).fetchall()
    assert any(row[0] == "duplicate_detected" for row in events)
    corrections = [row for row in events if row[0] == "cost_corrected"]
    assert len(corrections) == 1 and corrections[0][1]
    after_decision = tuple(conn.execute(
        "SELECT status, decision_reason, revision FROM job_terminal_decision WHERE job_id='job-a'"
    ).fetchone())
    assert after_decision == before_decision


def test_conflicting_provider_source_identity_is_surfaced_and_not_last_write_wins(tmp_path):
    conn = ledger()
    completed_job(conn)
    records = [
        {"source_record_id": "bill-1", "job_id": "job-a", "decision_revision": 1,
         "amount": "0.10", "currency": "USD"},
    ]
    ingest_source_records(conn, records, source_kind="provider_export", source_account="acct")
    ingest_source_records(conn, [{**records[0], "amount": "0.20"}],
                          source_kind="provider_export", source_account="acct")
    reconcile_cost_audit(conn, import_legacy=False)
    row = conn.execute("SELECT state, reason_code FROM cost_audit_link WHERE job_id='job-a'").fetchone()
    assert tuple(row) == ("conflict", "source_identity_conflict")
    assert conn.execute("SELECT COUNT(*) FROM cost_audit_source_record").fetchone()[0] == 1


def test_source_identity_conflict_marks_original_and_incoming_decisions():
    conn = ledger()
    completed_job(conn, "job-a")
    completed_job(conn, "job-b")
    original = {"source_record_id": "shared-bill", "job_id": "job-a",
                "decision_revision": 1, "amount": "0.10", "currency": "USD"}
    ingest_source_records(conn, [original], source_kind="provider_export", source_account="acct")
    ingest_source_records(
        conn, [{**original, "job_id": "job-b", "amount": "0.20"}],
        source_kind="provider_export", source_account="acct",
    )

    reconcile_cost_audit(conn, import_legacy=False)
    states = dict(conn.execute("SELECT job_id, state FROM cost_audit_link"))
    assert states == {"job-a": "conflict", "job-b": "conflict"}


def test_rejected_source_does_not_persist_untrusted_field_values():
    conn = ledger()
    completed_job(conn)
    secret = "sk-live-super-secret"
    ingest_source_records(
        conn,
        [{"source_record_id": "bad-row", "job_id": "job-a", "decision_revision": 1,
          "amount": secret, "currency": "USD"}],
        source_kind="provider_export", source_account="acct",
    )

    persisted = " ".join(row[0] for row in conn.execute(
        "SELECT payload_json FROM cost_audit_event"
    ))
    assert secret not in persisted


def test_explicit_source_correction_is_append_only_and_resolves_conflict():
    conn = ledger()
    completed_job(conn)
    record = {"source_record_id": "bill-1", "job_id": "job-a", "decision_revision": 1,
              "measure": "provider_billed", "amount": "0.10", "currency": "USD"}
    ingest_source_records(conn, [record], source_kind="provider_export", source_account="acct")
    ingest_source_records(conn, [{**record, "amount": "0.20"}],
                          source_kind="provider_export", source_account="acct")
    reconcile_cost_audit(conn, import_legacy=False)
    original = conn.execute(
        "SELECT payload_digest FROM cost_audit_source_record WHERE source_record_id='bill-1'"
    ).fetchone()[0]

    result = correct_source_record(
        conn, source_kind="provider_export", source_account="acct", source_record_id="bill-1",
        replacement={"amount_decimal": "0.20"}, reason="provider issued corrected billing line",
    )
    reconcile_cost_audit(conn, import_legacy=False)

    row = conn.execute("SELECT state, billed_amount_decimal FROM cost_audit_link WHERE job_id='job-a'").fetchone()
    assert tuple(row) == ("linked", "0.2")
    assert result["event_id"]
    assert conn.execute(
        "SELECT payload_digest FROM cost_audit_source_record WHERE source_record_id='bill-1'"
    ).fetchone()[0] == original
    assert conn.execute(
        "SELECT COUNT(*) FROM cost_audit_event WHERE event_type='cost_corrected'"
    ).fetchone()[0] >= 2


def test_ambiguous_legacy_cost_row_does_not_guess_latest_revision():
    conn = ledger()
    completed_job(conn)
    conn.execute(
        """INSERT INTO job_terminal_decision
           (job_id,status,verification_state,decision_reason,decided_at,decided_by,
            revision,contract_version) VALUES ('job-a','failed','failed','later-review',
            '2026-10-03T11:00:00Z','fixture',2,1)"""
    )
    conn.execute(
        "INSERT INTO cost_entries (id, job_id, model, input_tokens, total_cost_usd, cost_source) "
        "VALUES (1, 'job-a', 'model-x', 100, 0.01, 'estimated_token_rate')"
    )
    ensure_terminal_outbox(conn)
    reconcile_cost_audit(conn)
    rows = conn.execute(
        "SELECT decision_revision, state, reason_code FROM cost_audit_link ORDER BY decision_revision"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        (1, "missing", "legacy_unlinked"), (2, "missing", "legacy_unlinked"),
    ]


def test_legacy_cost_rows_only_bind_when_decision_revision_is_unambiguous():
    conn = ledger()
    completed_job(conn)
    conn.execute(
        "INSERT INTO cost_entries (id, job_id, model, input_tokens, total_cost_usd, cost_source) "
        "VALUES (1, 'job-a', 'model-x', 100, 0.01, 'estimated_token_rate')"
    )
    reconcile_cost_audit(conn)
    row = conn.execute(
        "SELECT state, estimated_amount_decimal, currency FROM cost_audit_link WHERE job_id='job-a'"
    ).fetchone()
    assert tuple(row) == ("linked", "0.01", "USD")
    report = cost_audit_report(conn)
    assert report["coverage"]["by_state"]["linked"] == 1
    assert report["totals_by_currency"]["USD"]["estimated"] == "0.01"


def test_same_request_telemetry_and_billing_do_not_double_count():
    conn = ledger()
    completed_job(conn)
    ingest_source_records(conn, [{
        "source_record_id": "telemetry-1", "job_id": "job-a", "decision_revision": 1,
        "request_id": "request-1", "measure": "provider_billed", "amount": "0.05",
        "currency": "USD", "input_tokens": 300,
    }], source_kind="structured_telemetry", source_account="codex")
    ingest_source_records(conn, [{
        "source_record_id": "billing-1", "job_id": "job-a", "decision_revision": 1,
        "request_id": "request-1", "measure": "provider_billed", "amount": "0.05",
        "currency": "USD", "input_tokens": 300,
    }], source_kind="provider_export", source_account="acct")
    reconcile_cost_audit(conn, import_legacy=False)
    row = conn.execute(
        "SELECT state, billed_amount_decimal, input_tokens FROM cost_audit_link WHERE job_id='job-a'"
    ).fetchone()
    assert tuple(row) == ("linked", "0.05", 300)


def test_provider_row_is_attributed_by_stable_request_id_when_job_id_is_missing():
    conn = ledger()
    completed_job(conn)
    ingest_source_records(conn, [{
        "source_record_id": "telemetry-1", "job_id": "job-a", "decision_revision": 1,
        "request_id": "request-1", "measure": "estimated", "input_tokens": 300,
    }], source_kind="structured_telemetry", source_account="codex")
    ingest_source_records(conn, [{
        "source_record_id": "billing-1", "request_id": "request-1",
        "measure": "provider_billed", "amount": "0.05", "currency": "USD",
    }], source_kind="provider_export", source_account="acct")
    reconcile_cost_audit(conn, import_legacy=False)
    row = conn.execute(
        "SELECT state, estimated_amount_decimal, billed_amount_decimal, input_tokens "
        "FROM cost_audit_link WHERE job_id='job-a'"
    ).fetchone()
    assert tuple(row) == ("linked", None, "0.05", 300)


def test_conflicting_amounts_for_same_request_require_review():
    conn = ledger()
    completed_job(conn)
    ingest_source_records(conn, [{
        "source_record_id": "telemetry-1", "job_id": "job-a", "decision_revision": 1,
        "request_id": "request-1", "measure": "provider_billed", "amount": "0.05",
        "currency": "USD",
    }], source_kind="structured_telemetry", source_account="codex")
    ingest_source_records(conn, [{
        "source_record_id": "billing-1", "job_id": "job-a", "decision_revision": 1,
        "request_id": "request-1", "measure": "provider_billed", "amount": "0.06",
        "currency": "USD",
    }], source_kind="provider_export", source_account="acct")
    reconcile_cost_audit(conn, import_legacy=False)
    row = conn.execute("SELECT state, reason_code FROM cost_audit_link WHERE job_id='job-a'").fetchone()
    assert tuple(row) == ("conflict", "duplicate_request_amount_conflict")


def test_structured_lifecycle_usage_is_snapshotted_and_cost_failure_cannot_set_status():
    conn = ledger()
    completed_job(conn)
    conn.execute(
        """INSERT INTO job_lifecycle_event
           (event_id, job_id, contract_id, contract_version, event_type, sequence,
            harness, role, process_result_json, evidence_refs_json, occurred_at,
            schema_version, accepted)
           VALUES ('usage-event-1','job-a','contract-a',1,'terminal',2,'codex','dev',
            ?, '[]','2026-10-03T10:00:00Z','lifecycle.v1',1)""",
        (json.dumps({"usage": {"input_tokens": 400, "output_tokens": 50,
                               "cost_usd": "0.02", "model": "model-x"}}),),
    )
    before = tuple(conn.execute(
        "SELECT status, decision_reason, revision FROM job_terminal_decision WHERE job_id='job-a'"
    ).fetchone())

    reconcile_cost_audit(conn, import_legacy=False)

    link = conn.execute(
        "SELECT state, estimated_amount_decimal, input_tokens FROM cost_audit_link WHERE job_id='job-a'"
    ).fetchone()
    assert tuple(link) == ("linked", "0.02", 400)
    assert conn.execute(
        "SELECT source_kind FROM cost_audit_source_record WHERE source_record_id='usage-event-1'"
    ).fetchone()[0] == "structured_telemetry"
    after = tuple(conn.execute(
        "SELECT status, decision_reason, revision FROM job_terminal_decision WHERE job_id='job-a'"
    ).fetchone())
    assert after == before


def test_known_model_uses_versioned_rate_catalog_and_unknown_model_stays_unpriced():
    conn = ledger()
    completed_job(conn, "job-priced")
    conn.execute(
        """INSERT INTO job_lifecycle_event
           (event_id, job_id, contract_id, contract_version, event_type, sequence,
            harness, role, process_result_json, evidence_refs_json, occurred_at,
            schema_version, accepted)
           VALUES ('usage-priced','job-priced','contract-a',1,'terminal',2,'codex','dev',
            ?, '[]','2026-10-03T10:00:00Z','lifecycle.v1',1)""",
        (json.dumps({"usage": {"input_tokens": 300, "output_tokens": 100,
                               "model": "claude-sonnet-4-6"}}),),
    )
    conn.commit()
    completed_job(conn, "job-unknown-price")
    conn.execute(
        """INSERT INTO job_lifecycle_event
           (event_id, job_id, contract_id, contract_version, event_type, sequence,
            harness, role, process_result_json, evidence_refs_json, occurred_at,
            schema_version, accepted)
           VALUES ('usage-unpriced','job-unknown-price','contract-b',1,'terminal',2,'codex','dev',
            ?, '[]','2026-10-03T10:00:00Z','lifecycle.v1',1)""",
        (json.dumps({"usage": {"input_tokens": 300, "output_tokens": 100,
                               "model": "unknown-model"}}),),
    )
    conn.commit()

    reconcile_cost_audit(conn, import_legacy=False)

    priced = conn.execute(
        "SELECT state, estimated_amount_decimal, pricing_basis_json FROM cost_audit_link WHERE job_id='job-priced'"
    ).fetchone()
    assert priced[0:2] == ("linked", "0.0024")
    assert json.loads(priced[2])[0]["basis"] == "usd_per_1k_tokens"
    assert json.loads(priced[2])[0]["catalog_version"]
    unpriced = conn.execute(
        "SELECT state, reason_code FROM cost_audit_link WHERE job_id='job-unknown-price'"
    ).fetchone()
    assert tuple(unpriced) == ("missing", "price_unavailable")


def test_corrupt_terminal_outbox_event_is_rejected_without_touching_status():
    conn = ledger()
    completed_job(conn)
    conn.execute("UPDATE job_terminal_outbox SET payload_digest='bad-digest' WHERE job_id='job-a'")
    before = tuple(conn.execute(
        "SELECT status, decision_reason, revision FROM job_terminal_decision WHERE job_id='job-a'"
    ).fetchone())

    result = reconcile_cost_audit(conn, import_legacy=False)

    assert result["outbox_rejected"] == 1
    assert tuple(conn.execute(
        "SELECT status, decision_reason, revision FROM job_terminal_decision WHERE job_id='job-a'"
    ).fetchone()) == before
    assert conn.execute("SELECT state FROM cost_audit_link WHERE job_id='job-a'").fetchone()[0] == "missing"


def test_csv_import_rejects_bad_amount_and_redacts_unrecognized_payload_fields(tmp_path):
    conn = ledger()
    completed_job(conn)
    export = tmp_path / "billing.csv"
    export.write_text(
        "record_id,job_id,decision_revision,amount,currency,prompt,api_key\n"
        "good,job-a,1,0.25,USD,secret prompt,secret token\n"
        "bad,job-a,1,not-money,USD,another prompt,another token\n"
    )
    result = import_provider_export(conn, export, provider="example-provider")
    assert result["accepted"] == 1
    assert result["rejected"] == 1
    serialized = " ".join(row[0] for row in conn.execute(
        "SELECT metadata_json FROM cost_audit_source_record"
    ))
    assert "secret" not in serialized
    assert "api_key" not in serialized
