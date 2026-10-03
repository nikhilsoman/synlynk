import json
import sqlite3
from unittest.mock import patch

from synlynk.harness_adapters.codex import CodexAdapter
from synlynk.lifecycle import ingest_output, make_event, parse_output


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE job_lifecycle_event (
            event_id TEXT PRIMARY KEY, job_id TEXT, contract_id TEXT,
            contract_version INTEGER, event_type TEXT, sequence INTEGER,
            harness TEXT, role TEXT, process_result_json TEXT,
            evidence_refs_json TEXT, occurred_at TEXT, schema_version TEXT,
            compatibility INTEGER, accepted INTEGER, rejection_reason TEXT
        )"""
    )
    return conn


def _line(event):
    return "SYNLYNK_LIFECYCLE_EVENT: " + json.dumps(event)


def test_lifecycle_schema_contains_contract_process_and_evidence_fields():
    event = make_event("queued", "job-1", contract_id="contract-1", sequence=0,
                       harness="codex", role="dev", process_result={"pid": 42},
                       evidence_refs=("receipt-1",))
    payload = event.as_dict()
    assert payload["schema_version"] == "lifecycle.v1"
    assert payload["contract_id"] == "contract-1"
    assert payload["process_result"] == {"pid": 42}
    assert payload["evidence_refs"] == ["receipt-1"]


def test_ingestion_is_idempotent_and_retains_out_of_order_observation():
    conn = _conn()
    first = _line({"event_type": "running", "job_id": "job-1", "contract_id": "c",
                   "event_id": "e-2", "sequence": 2, "harness": "codex", "role": "dev"})
    result = ingest_output(conn, first + "\n" + first)
    assert result["events"][0]["accepted"] is True
    assert result["events"][1]["duplicate"] is True

    older = _line({"event_type": "queued", "job_id": "job-1", "contract_id": "c",
                   "event_id": "e-1", "sequence": 1, "harness": "codex", "role": "dev"})
    result = ingest_output(conn, older)
    assert result["events"][0]["accepted"] is False
    row = conn.execute("SELECT accepted, rejection_reason FROM job_lifecycle_event WHERE event_id='e-1'").fetchone()
    assert row == (0, "out_of_order")


def test_adapter_marks_task_receipt_as_compatibility_evidence_only():
    event = _line({"event_type": "terminal", "job_id": "job-1", "contract_id": "c",
                   "event_id": "e-3", "sequence": 3, "harness": "codex", "role": "qa",
                   "process_result": {"exit_code": 0}})
    parsed = CodexAdapter().parse_output("SYNLYNK_TASK_RECEIVED: digest\n" + event)
    assert len(parsed.lifecycle_events) == 1
    assert parsed.compatibility_evidence["compatibility"] is True
    assert parsed.compatibility_evidence["receipt"] == "digest"


def test_parser_ignores_legacy_text_as_lifecycle_event():
    assert parse_output("status: OK (exit 0)\nSYNLYNK_TASK_RECEIVED: digest") == ()


def test_remote_only_qa_review_completes_without_local_receipt_or_diff():
    from synlynk.verify_effects import verify_job_effects

    with patch("synlynk.verify_effects.gh_write_verified", return_value=True) as verified:
        result = verify_job_effects(
            task_class="review", expected_gh_effect="review_posted",
            receipt_path="/missing/receipt.json",
            gh_verify_kwargs={"target": "pr:1955", "expect_author": "qa",
                              "expected_sha": "abc123"},
        )
    assert result.verified is True
    assert result.status == "completed"
    assert result.evidence == {}
    assert verified.call_args.kwargs["expected_sha"] == "abc123"
