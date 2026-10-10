"""Append-only audit of cost evidence associated with job decision revisions.

The audit module consumes canonical job decisions and cost source records. It
never writes job status or terminal decisions.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

from synlynk.job_truth import TERMINAL_STATUSES


SCHEMA_VERSION = "cost-audit.v1"
OUTBOX_SCHEMA_VERSION = "job-terminal-decision.v1"
MEASURES = frozenset({"estimated", "provider_billed", "paid"})
MISSING_REASONS = frozenset({
    "telemetry_absent", "provider_not_supported", "provider_export_delayed",
    "usage_unavailable", "model_unresolved", "price_unavailable",
    "redacted_by_policy", "legacy_unlinked", "source_rejected",
})
_TERMINAL_STATUS_VALUES = tuple(sorted(TERMINAL_STATUSES))
_TERMINAL_STATUS_SQL = ", ".join("?" for _ in _TERMINAL_STATUS_VALUES)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    raw = value if isinstance(value, bytes) else str(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _decimal_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"invalid decimal amount: {value!r}") from None
    if not number.is_finite():
        raise ValueError("amount must be finite")
    return format(number.normalize(), "f")


def _event_id(*parts: Any) -> str:
    return "cost-" + _digest(":|:".join(str(part) for part in parts))


def _safe_reason(value: str) -> str:
    reason = re.sub(r"(?i)\bbearer\s+\S+", "Bearer [redacted]", value.strip())
    reason = re.sub(
        r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+",
        r"\1=[redacted]", reason,
    )
    return reason[:300]


def ingest_source_records(
    conn: sqlite3.Connection,
    records: Iterable[Mapping[str, Any]],
    *,
    source_kind: str,
    source_account: str = "",
    default_measure: str = "provider_billed",
    confidence: str = "high",
    input_digest: str | None = None,
    _commit: bool = True,
) -> dict[str, int]:
    """Append normalized source facts idempotently; unknown fields are dropped."""
    if default_measure not in MEASURES:
        raise ValueError(f"unsupported cost measure: {default_measure}")
    run_id = f"audit-run-{uuid.uuid4().hex}"
    started = _now()
    accepted = duplicate = rejected = 0
    conn.execute(
        """INSERT INTO cost_audit_run
           (run_id, run_kind, source_kind, input_digest, started_at, outcome)
           VALUES (?, 'import', ?, ?, ?, 'running')""",
        (run_id, source_kind, input_digest, started),
    )
    for index, raw in enumerate(records, start=1):
        try:
            if raw.get("_parse_error"):
                raise ValueError("invalid JSONL source row")
            source_record_id = str(raw.get("source_record_id") or raw.get("record_id") or "").strip()
            if not source_record_id:
                raise ValueError("source_record_id is required")
            measure = str(raw.get("measure") or default_measure)
            if measure not in MEASURES:
                raise ValueError(f"unsupported measure {measure!r}")
            row_confidence = str(raw.get("confidence") or confidence)
            if row_confidence not in {"high", "medium", "low", "unknown"}:
                raise ValueError(f"unsupported confidence {row_confidence!r}")
            decision_revision = (
                int(raw["decision_revision"])
                if raw.get("decision_revision") not in (None, "") else None
            )
            if decision_revision is not None and decision_revision < 1:
                raise ValueError("decision_revision must be positive")
            currency = str(raw.get("currency") or "").upper() or None
            if currency and (len(currency) != 3 or not currency.isalpha()):
                raise ValueError("currency must be a 3-letter ISO code")
            amount = _decimal_text(raw.get("amount_decimal", raw.get("amount")))
            safe = {
                "source_kind": source_kind,
                "source_account": source_account,
                "source_record_id": source_record_id,
                "job_id": str(raw["job_id"]) if raw.get("job_id") else None,
                "decision_revision": decision_revision,
                "request_id": str(raw["request_id"]) if raw.get("request_id") else None,
                "measure": measure,
                "provider": str(raw.get("provider") or source_account or source_kind),
                "model": str(raw["model"]) if raw.get("model") else None,
                "input_tokens": _optional_nonnegative_int(raw.get("input_tokens")),
                "output_tokens": _optional_nonnegative_int(raw.get("output_tokens")),
                "cache_read_tokens": _optional_nonnegative_int(raw.get("cache_read_tokens")),
                "amount_decimal": amount,
                "currency": currency,
                "usage_start": str(raw["usage_start"]) if raw.get("usage_start") else None,
                "usage_end": str(raw["usage_end"]) if raw.get("usage_end") else None,
                "confidence": row_confidence,
            }
            pricing_basis = raw.get("pricing_basis")
            if safe["amount_decimal"] is None and measure == "estimated":
                estimated, pricing_basis = _estimate_from_catalog(safe)
                if estimated is not None:
                    safe["amount_decimal"] = estimated
                    safe["currency"] = "USD"
            payload_digest = _digest(_canonical(safe))
            metadata = {"import_row": index}
            if pricing_basis:
                metadata["pricing_basis"] = pricing_basis
            existing = conn.execute(
                """SELECT payload_digest, job_id, decision_revision FROM cost_audit_source_record
                   WHERE source_kind=? AND source_account=? AND source_record_id=?""",
                (source_kind, source_account, source_record_id),
            ).fetchone()
            if existing:
                if existing[0] == payload_digest:
                    duplicate += 1
                    if safe["job_id"] and safe["decision_revision"] is not None:
                        _append_event(
                            conn,
                            _event_id("duplicate-source", source_kind, source_account,
                                      source_record_id, payload_digest),
                            safe["job_id"], safe["decision_revision"], "duplicate_detected",
                            {"reason_code": "duplicate_source_record", "source_id": source_record_id},
                            source_kind=source_kind, source_id=source_record_id,
                        )
                else:
                    rejected += 1
                    if safe["job_id"] and safe["decision_revision"] is not None:
                        conflict_payload = {
                            "reason_code": "source_identity_conflict",
                            "existing_digest": existing[0], "incoming_digest": payload_digest,
                        }
                        conflict_targets = {(safe["job_id"], safe["decision_revision"])}
                        if existing[1] and existing[2] is not None:
                            conflict_targets.add((existing[1], existing[2]))
                        for target_job, target_revision in conflict_targets:
                            if not target_job or target_revision is None:
                                continue
                            _append_event(
                                conn,
                                _event_id("source-identity-conflict", source_kind, source_account,
                                          source_record_id, payload_digest, target_job, target_revision),
                                target_job, target_revision, "conflict_detected",
                                conflict_payload, source_kind=source_kind, source_id=source_record_id,
                            )
                continue
            cursor = conn.execute(
                """INSERT OR IGNORE INTO cost_audit_source_record
                   (source_kind, source_account, source_record_id, job_id,
                    decision_revision, request_id, measure, provider, model,
                    input_tokens, output_tokens, cache_read_tokens,
                    amount_decimal, currency, usage_start, usage_end,
                    confidence, payload_digest, metadata_json, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (safe["source_kind"], safe["source_account"], safe["source_record_id"],
                 safe["job_id"], safe["decision_revision"], safe["request_id"],
                 safe["measure"], safe["provider"], safe["model"], safe["input_tokens"],
                 safe["output_tokens"], safe["cache_read_tokens"], safe["amount_decimal"],
                 safe["currency"], safe["usage_start"], safe["usage_end"], safe["confidence"],
                 payload_digest, _canonical(metadata), _now()),
            )
            if cursor.rowcount:
                accepted += 1
            else:
                duplicate += 1
        except (KeyError, TypeError, ValueError, OverflowError):
            rejected += 1
            _append_rejection(conn, run_id, source_kind, index, raw)
    outcome = "completed" if rejected == 0 else ("partial" if accepted or duplicate else "rejected")
    conn.execute(
        """UPDATE cost_audit_run SET completed_at=?, accepted_count=?,
           duplicate_count=?, rejected_count=?, outcome=?, details_json=? WHERE run_id=?""",
        (_now(), accepted, duplicate, rejected,
         outcome, _canonical({"input_digest": input_digest}), run_id),
    )
    if _commit:
        conn.commit()
    return {"run_id": run_id, "accepted": accepted, "duplicates": duplicate, "rejected": rejected}


def _optional_nonnegative_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError("token counts cannot be negative")
    return parsed


def _estimate_from_catalog(record: Mapping[str, Any]) -> tuple[str | None, dict[str, Any]]:
    model = record.get("model")
    tokens = (record.get("input_tokens"), record.get("output_tokens"), record.get("cache_read_tokens"))
    if not model:
        return None, {"reason_code": "model_unresolved"}
    if not any(value is not None for value in tokens):
        return None, {"reason_code": "usage_unavailable"}
    try:
        from synlynk.costs import _EXPECTED_RATE_UNIT, _load_model_rates
        catalog = _load_model_rates()
        rates = catalog.get("models", {}).get(str(model))
    except (ImportError, AttributeError, TypeError, ValueError):
        return None, {"reason_code": "price_unavailable"}
    if catalog.get("unit") != _EXPECTED_RATE_UNIT or not isinstance(rates, dict):
        return None, {"reason_code": "price_unavailable"}
    try:
        amount = (
            Decimal(record.get("input_tokens") or 0) * Decimal(str(rates["input"]))
            + Decimal(record.get("output_tokens") or 0) * Decimal(str(rates["output"]))
            + Decimal(record.get("cache_read_tokens") or 0) * Decimal(str(rates["cache_read"]))
        ) / Decimal(1000)
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return None, {"reason_code": "price_unavailable"}
    catalog_version = _digest(_canonical(catalog))
    return _decimal_text(amount), {
        "basis": _EXPECTED_RATE_UNIT,
        "catalog_version": catalog_version,
        "rates_updated_at": catalog.get("rates_updated_at"),
        "model": model,
        "rates": {key: str(rates[key]) for key in ("input", "output", "cache_read")},
        "source": "configured_model_rates" if catalog.get("rates_updated_at") else "model_rates_catalog",
    }


def _append_rejection(
    conn: sqlite3.Connection, run_id: str, source_kind: str, index: int,
    raw: Mapping[str, Any],
) -> None:
    # Rejections are audit events only when the row has a usable decision key.
    job_id = str(raw.get("job_id") or "").strip()
    revision = raw.get("decision_revision")
    if not job_id or revision in (None, ""):
        return
    try:
        revision = int(revision)
    except (TypeError, ValueError):
        return
    # Never persist exception text: it can contain arbitrary provider field values.
    payload = {"reason_code": "source_rejected", "run_id": run_id}
    event_id = _event_id("source-rejected", run_id, index)
    _append_event(conn, event_id, job_id, revision, "conflict_detected", payload,
                  source_kind=source_kind, source_id=None)


def read_provider_export(path: str | Path) -> tuple[list[dict[str, Any]], str]:
    """Read the documented JSONL/JSON/CSV interchange without retaining raw data."""
    source_path = Path(path)
    if source_path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("provider export exceeds the 64 MiB import limit")
    raw_bytes = source_path.read_bytes()
    input_digest = _digest(raw_bytes)
    text = raw_bytes.decode("utf-8-sig")
    suffix = source_path.suffix.lower()
    if suffix == ".csv":
        records = list(csv.DictReader(io.StringIO(text, newline="")))
    elif suffix in {".jsonl", ".ndjson"}:
        records = []
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                records.append({"_parse_error": True})
    elif suffix == ".json":
        payload = json.loads(text)
        records = payload if isinstance(payload, list) else payload.get("records", [payload])
    else:
        raise ValueError("provider export must use .csv, .jsonl, .ndjson, or .json")
    if not all(isinstance(row, dict) for row in records):
        raise ValueError("provider export rows must be objects")
    return records, input_digest


def import_provider_export(
    conn: sqlite3.Connection,
    path: str | Path,
    *,
    provider: str,
    source_account: str = "",
) -> dict[str, int]:
    if not provider.strip():
        raise ValueError("provider name is required")
    records, input_digest = read_provider_export(path)
    records = [{**record, "provider": provider} for record in records]
    return ingest_source_records(
        conn, records, source_kind="provider_export", source_account=source_account,
        confidence="high", input_digest=input_digest,
    )


def correct_source_record(
    conn: sqlite3.Connection,
    *,
    source_kind: str,
    source_account: str,
    source_record_id: str,
    replacement: Mapping[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Append a replacement source fact and immutable correction event."""
    reason = _safe_reason(reason)
    if not reason:
        raise ValueError("correction reason is required")
    conn.execute("BEGIN IMMEDIATE")
    try:
        prior = conn.execute(
            """SELECT * FROM cost_audit_source_record
               WHERE source_kind=? AND source_account=? AND source_record_id=?""",
            (source_kind, source_account, source_record_id),
        ).fetchone()
        if prior is None:
            raise ValueError("source record was not found")
        existing = conn.execute(
            """SELECT correction_event_id FROM cost_audit_source_supersession
               WHERE source_kind=? AND source_account=? AND superseded_record_id=?""",
            (source_kind, source_account, source_record_id),
        ).fetchone()
        if existing:
            conn.commit()
            return {"replacement_record_id": None, "event_id": existing[0], "duplicate": True}
        names = [column[1] for column in conn.execute(
            "PRAGMA table_info(cost_audit_source_record)"
        )]
        prior = dict(zip(names, prior))
        proposed = dict(replacement)
        replacement_id = f"{source_record_id}-correction-{_digest(_canonical(proposed))[:16]}"
        source = {
            "source_record_id": replacement_id,
            "job_id": proposed.get("job_id", prior["job_id"]),
            "decision_revision": proposed.get("decision_revision", prior["decision_revision"]),
            "request_id": proposed.get("request_id", prior["request_id"]),
            "measure": proposed.get("measure", prior["measure"]),
            "provider": proposed.get("provider", prior["provider"]),
            "model": proposed.get("model", prior["model"]),
            "input_tokens": proposed.get("input_tokens", prior["input_tokens"]),
            "output_tokens": proposed.get("output_tokens", prior["output_tokens"]),
            "cache_read_tokens": proposed.get("cache_read_tokens", prior["cache_read_tokens"]),
            "amount_decimal": proposed.get("amount_decimal", prior["amount_decimal"]),
            "currency": proposed.get("currency", prior["currency"]),
            "usage_start": proposed.get("usage_start", prior["usage_start"]),
            "usage_end": proposed.get("usage_end", prior["usage_end"]),
            "confidence": proposed.get("confidence", prior["confidence"]),
        }
        job_id = source["job_id"]
        revision = source["decision_revision"]
        if not job_id or revision is None:
            raise ValueError("source corrections require a job_id and decision_revision")
        inserted = ingest_source_records(
            conn, [source], source_kind=source_kind, source_account=source_account,
            default_measure=source["measure"], confidence=source["confidence"],
            _commit=False,
        )
        event_id = _event_id("source-correction", source_kind, source_account,
                             source_record_id, replacement_id)
        previous = conn.execute(
            "SELECT latest_event_id FROM cost_audit_link WHERE job_id=? AND decision_revision=?",
            (job_id, revision),
        ).fetchone()
        payload = {
            "reason_code": "source_corrected", "reason": reason,
            "superseded_source_id": source_record_id,
            "replacement_source_id": replacement_id,
            "occurred_at": _now(),
        }
        conflict_rows = conn.execute(
            """SELECT event_id FROM cost_audit_event WHERE job_id=? AND decision_revision=?
               AND event_type='conflict_detected' AND source_id=?""",
            (job_id, revision, source_record_id),
        ).fetchall()
        payload["superseded_conflict_ids"] = [row[0] for row in conflict_rows]
        _append_event(conn, event_id, job_id, int(revision), "cost_corrected", payload,
                      source_kind=source_kind, source_id=replacement_id,
                      supersedes_event_id=previous[0] if previous else None)
        conn.execute(
            """INSERT INTO cost_audit_source_supersession
               (source_kind, source_account, superseded_record_id, replacement_record_id,
                correction_event_id, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (source_kind, source_account, source_record_id, replacement_id,
             event_id, reason, _now()),
        )
        conn.commit()
        return {"replacement_record_id": replacement_id, "event_id": event_id,
                "duplicate": inserted["accepted"] == 0}
    except Exception:
        conn.rollback()
        raise


def preview_source_correction(
    conn: sqlite3.Connection,
    *,
    source_kind: str,
    source_account: str,
    source_record_id: str,
    replacement: Mapping[str, Any],
    reason: str,
) -> dict[str, Any]:
    reason = _safe_reason(reason)
    if not reason:
        raise ValueError("correction reason is required")
    row = conn.execute(
        """SELECT job_id, decision_revision, measure, provider, model,
                  input_tokens, output_tokens, cache_read_tokens,
                  amount_decimal, currency, confidence
           FROM cost_audit_source_record
           WHERE source_kind=? AND source_account=? AND source_record_id=?""",
        (source_kind, source_account, source_record_id),
    ).fetchone()
    if row is None:
        raise ValueError("source record was not found")
    names = [
        "job_id", "decision_revision", "measure", "provider", "model",
        "input_tokens", "output_tokens", "cache_read_tokens", "amount_decimal",
        "currency", "confidence",
    ]
    current = dict(zip(names, row))
    allowed = set(names) | {"request_id", "usage_start", "usage_end"}
    proposed = {key: value for key, value in replacement.items() if key in allowed}
    if "amount_decimal" in proposed:
        proposed["amount_decimal"] = _decimal_text(proposed["amount_decimal"])
    return {"source_record_id": source_record_id, "current": current,
            "replacement": proposed, "reason": reason}


def _append_event(
    conn: sqlite3.Connection,
    event_id: str,
    job_id: str,
    revision: int,
    event_type: str,
    payload: Mapping[str, Any],
    *,
    source_kind: str | None = None,
    source_id: str | None = None,
    supersedes_event_id: str | None = None,
) -> None:
    canonical = _canonical(dict(payload))
    conn.execute(
        """INSERT OR IGNORE INTO cost_audit_event
           (event_id, audit_id, job_id, decision_revision, schema_version,
            event_type, occurred_at, recorded_at, source_kind, source_id,
            payload_digest, supersedes_event_id, payload_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, f"audit-{_digest(f'{job_id}:{revision}')[:24]}", job_id, revision,
         SCHEMA_VERSION, event_type, str(payload.get("occurred_at") or _now()), _now(),
         source_kind, source_id, _digest(canonical), supersedes_event_id, canonical),
    )


def consume_terminal_outbox(conn: sqlite3.Connection) -> dict[str, int]:
    """Validate and append decision observations from the canonical outbox."""
    accepted = rejected = 0
    rows = conn.execute(
        "SELECT event_id, job_id, decision_revision, schema_version, payload_json, payload_digest "
        "FROM job_terminal_outbox ORDER BY created_at, event_id"
    ).fetchall()
    for event_id, job_id, revision, schema_version, payload_json, expected_digest in rows:
        try:
            payload = json.loads(payload_json)
            if schema_version != OUTBOX_SCHEMA_VERSION or payload.get("schema_version") != OUTBOX_SCHEMA_VERSION:
                raise ValueError("unsupported terminal event schema")
            if payload.get("job_id") != job_id or int(payload.get("decision_revision")) != int(revision):
                raise ValueError("terminal event key mismatch")
            if _digest(_canonical(payload)) != expected_digest:
                raise ValueError("terminal event digest mismatch")
            row = conn.execute(
                "SELECT status, decision_reason, decided_at, contract_version FROM job_terminal_decision WHERE job_id=? AND revision=?",
                (job_id, revision),
            ).fetchone()
            if not row or (row[0], row[1], row[2], row[3]) != (
                payload.get("decision_status"), payload.get("decision_reason"),
                payload.get("decided_at"), payload.get("effect_contract_version"),
            ):
                raise ValueError("terminal event does not match canonical decision")
            decision_facts = {
                "job_id": job_id, "decision_revision": int(revision),
                "decision_status": row[0], "decision_reason": row[1],
                "decided_at": row[2], "effect_contract_version": row[3],
            }
            expected_decision_digest = _digest(_canonical(decision_facts))
            if payload.get("source_decision_digest") != expected_decision_digest:
                raise ValueError("terminal decision digest mismatch")
            terminal_event_id = _event_id("decision-observed", job_id, revision)
            _append_event(conn, terminal_event_id, job_id, int(revision), "decision_observed", {
                "terminal_event_id": event_id,
                "decision_status": row[0],
                "decision_reason": row[1],
                "occurred_at": row[2],
            }, source_kind="job_terminal_outbox", source_id=event_id)
            accepted += 1
        except (ValueError, TypeError, json.JSONDecodeError):
            rejected += 1
    conn.commit()
    return {"accepted": accepted, "rejected": rejected}


def import_legacy_cost_entries(conn: sqlite3.Connection) -> dict[str, int]:
    """Snapshot legacy ledger rows without guessing a decision revision."""
    tables = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cost_entries'"
    ).fetchone()
    if not tables:
        return {"accepted": 0, "duplicates": 0, "rejected": 0}
    columns = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    needed = {"id", "job_id"}
    if not needed.issubset(columns):
        return {"accepted": 0, "duplicates": 0, "rejected": 0}
    names = [name for name in (
        "id", "job_id", "decision_revision", "agent", "harness", "model",
        "input_tokens", "output_tokens", "cache_read_tokens", "total_cost_usd",
        "actual_usd", "payment_mode", "cost_source", "recorded_at",
    ) if name in columns]
    rows = conn.execute(f"SELECT {', '.join(names)} FROM cost_entries WHERE job_id IS NOT NULL")
    records = []
    for row in rows.fetchall():
        item = dict(zip(names, row))
        explicit_revision = item.get("decision_revision")
        decision_revision = explicit_revision
        if decision_revision is None:
            candidate = conn.execute(
                f"SELECT COUNT(*) FROM job_terminal_decision WHERE job_id=? AND status IN ({_TERMINAL_STATUS_SQL})",
                (item["job_id"], *_TERMINAL_STATUS_VALUES),
            ).fetchone()[0]
            if candidate == 1:
                decision_revision = conn.execute(
                    f"SELECT revision FROM job_terminal_decision WHERE job_id=? AND status IN ({_TERMINAL_STATUS_SQL})",
                    (item["job_id"], *_TERMINAL_STATUS_VALUES),
                ).fetchone()[0]
        source = item.get("cost_source") or "legacy_unknown"
        measure = "provider_billed" if source == "actual" else "estimated"
        amount = item.get("actual_usd") if measure == "provider_billed" and item.get("actual_usd") is not None else item.get("total_cost_usd")
        records.append({
            "source_record_id": f"cost-entry-{item['id']}",
            "job_id": item["job_id"],
            "decision_revision": decision_revision,
            "measure": measure,
            "provider": item.get("harness") or item.get("agent") or "unknown",
            "model": item.get("model"),
            "input_tokens": item.get("input_tokens"),
            "output_tokens": item.get("output_tokens"),
            "cache_read_tokens": item.get("cache_read_tokens"),
            "amount_decimal": amount,
            "currency": "USD" if amount is not None else None,
            "confidence": "medium" if decision_revision is not None else "low",
            "recorded_at": item.get("recorded_at"),
        })
    return ingest_source_records(
        conn, records, source_kind="legacy_local_ledger", default_measure="estimated",
        confidence="low",
    )


def import_structured_usage_events(conn: sqlite3.Connection) -> dict[str, int]:
    """Normalize usage dimensions from accepted lifecycle process results."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='job_lifecycle_event'"
    ).fetchone()
    if not exists:
        return {"accepted": 0, "duplicates": 0, "rejected": 0}
    columns = {row[1] for row in conn.execute("PRAGMA table_info(job_lifecycle_event)")}
    required = {"event_id", "job_id", "process_result_json", "accepted"}
    if not required.issubset(columns):
        return {"accepted": 0, "duplicates": 0, "rejected": 0}
    names = [name for name in (
        "event_id", "job_id", "process_result_json", "harness", "occurred_at",
    ) if name in columns]
    rows = conn.execute(
        f"SELECT {', '.join(names)} FROM job_lifecycle_event WHERE accepted=1"
    ).fetchall()
    records = []
    for row in rows:
        item = dict(zip(names, row))
        if conn.execute(
            """SELECT 1 FROM cost_audit_source_record
               WHERE source_kind='structured_telemetry' AND source_account=?
                 AND source_record_id=?""",
            ("", item["event_id"]),
        ).fetchone():
            continue
        try:
            process = json.loads(item.get("process_result_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        usage = process.get("usage") if isinstance(process.get("usage"), dict) else process
        input_tokens = usage.get("input_tokens", usage.get("in_tokens"))
        output_tokens = usage.get("output_tokens", usage.get("out_tokens"))
        cache_tokens = usage.get("cache_read_tokens", usage.get("cache_tokens"))
        amount = usage.get("provider_amount", usage.get("cost_usd"))
        if all(value in (None, "") for value in (input_tokens, output_tokens, cache_tokens, amount)):
            continue
        explicit_revision = usage.get("decision_revision") or process.get("decision_revision")
        records.append({
            "source_record_id": item["event_id"],
            "job_id": item["job_id"],
            "decision_revision": explicit_revision,
            "request_id": usage.get("request_id") or process.get("request_id"),
            "measure": usage.get("measure") or ("provider_billed" if usage.get("provider_amount") is not None else "estimated"),
            "provider": usage.get("provider") or item.get("harness") or "unknown",
            "model": usage.get("model") or process.get("model"),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_tokens,
            "amount_decimal": amount,
            "currency": usage.get("currency") or ("USD" if amount is not None else None),
            "usage_start": usage.get("usage_start") or item.get("occurred_at"),
            "usage_end": usage.get("usage_end") or item.get("occurred_at"),
            "confidence": "high" if explicit_revision is not None else "medium",
        })
    return ingest_source_records(
        conn, records, source_kind="structured_telemetry",
        default_measure="estimated", confidence="medium",
    )


def reconcile_cost_audit(conn: sqlite3.Connection, *, import_legacy: bool = True) -> dict[str, int]:
    """Consume terminal decisions and rebuild one auditable outcome per revision."""
    outbox = consume_terminal_outbox(conn)
    telemetry = import_structured_usage_events(conn)
    legacy = import_legacy_cost_entries(conn) if import_legacy else {"accepted": 0, "duplicates": 0, "rejected": 0}
    decisions = conn.execute(
        f"""SELECT d.job_id, d.revision, d.decided_at
            FROM job_terminal_decision d
            WHERE d.status IN ({_TERMINAL_STATUS_SQL})
            ORDER BY d.decided_at, d.job_id, d.revision""",
        _TERMINAL_STATUS_VALUES,
    ).fetchall()
    reconciled = 0
    for job_id, revision, decided_at in decisions:
        state, reason, sources = _outcome_for_decision(conn, job_id, revision)
        latest_event = conn.execute(
            "SELECT latest_event_id FROM cost_audit_link WHERE job_id=? AND decision_revision=?",
            (job_id, revision),
        ).fetchone()
        prior_event = latest_event[0] if latest_event else None
        source_ids = [int(row["id"]) for row in sources]
        totals = _aggregate_sources(sources)
        pricing_basis = []
        for source in sources:
            try:
                basis = json.loads(source["metadata_json"] or "{}").get("pricing_basis")
            except (TypeError, json.JSONDecodeError):
                basis = None
            if basis and basis not in pricing_basis:
                pricing_basis.append(basis)
        snapshot = {
            "state": state, "reason_code": reason, "source_ids": source_ids,
            "input_tokens": totals["input_tokens"], "output_tokens": totals["output_tokens"],
            "cache_read_tokens": totals["cache_read_tokens"],
            "estimated_amount_decimal": totals["estimated"],
            "billed_amount_decimal": totals["provider_billed"],
            "paid_amount_decimal": totals["paid"], "currency": totals["currency"],
            "pricing_basis": pricing_basis,
            "occurred_at": decided_at,
        }
        snapshot_digest = _digest(_canonical(snapshot))
        if prior_event:
            old = conn.execute(
                "SELECT payload_digest FROM cost_audit_event WHERE event_id=?", (prior_event,)
            ).fetchone()
            if old and old[0] == snapshot_digest:
                continue
        event_type = "cost_corrected" if prior_event else (
            "cost_linked" if state == "linked" else "cost_missing"
            if state in {"missing", "pending"} else "reconciliation_completed"
        )
        event_id = _event_id("projection", job_id, revision, snapshot_digest)
        _append_event(conn, event_id, job_id, revision, event_type, snapshot,
                      source_kind="cost_audit_reconciler",
                      source_id=",".join(map(str, source_ids)) or None,
                      supersedes_event_id=prior_event)
        conn.execute(
            """INSERT INTO cost_audit_link
               (job_id, decision_revision, state, reason_code, source_ids_json,
                input_tokens, output_tokens, cache_read_tokens, estimated_amount_decimal,
                billed_amount_decimal, paid_amount_decimal, currency, confidence,
                pricing_basis_json, reconciled_at, latest_event_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(job_id, decision_revision) DO UPDATE SET
                state=excluded.state, reason_code=excluded.reason_code,
                source_ids_json=excluded.source_ids_json, input_tokens=excluded.input_tokens,
                output_tokens=excluded.output_tokens, cache_read_tokens=excluded.cache_read_tokens,
                estimated_amount_decimal=excluded.estimated_amount_decimal,
                billed_amount_decimal=excluded.billed_amount_decimal,
                paid_amount_decimal=excluded.paid_amount_decimal, currency=excluded.currency,
                confidence=excluded.confidence, pricing_basis_json=excluded.pricing_basis_json,
                reconciled_at=excluded.reconciled_at,
                latest_event_id=excluded.latest_event_id""",
            (job_id, revision, state, reason, _canonical(source_ids), totals["input_tokens"],
             totals["output_tokens"], totals["cache_read_tokens"], totals["estimated"],
             totals["provider_billed"], totals["paid"], totals["currency"], totals["confidence"],
             _canonical(pricing_basis), _now(), event_id),
        )
        reconciled += 1
    conn.commit()
    return {"decisions": len(decisions), "reconciled": reconciled,
            "outbox_rejected": outbox["rejected"], "legacy_imported": legacy["accepted"],
            "legacy_duplicates": legacy["duplicates"],
            "telemetry_imported": telemetry["accepted"],
            "telemetry_duplicates": telemetry["duplicates"]}


def _outcome_for_decision(conn: sqlite3.Connection, job_id: str, revision: int):
    all_revisions = conn.execute(
        f"SELECT COUNT(*) FROM job_terminal_decision WHERE job_id=? AND status IN ({_TERMINAL_STATUS_SQL})",
        (job_id, *_TERMINAL_STATUS_VALUES),
    ).fetchone()[0]
    cursor = conn.execute(
        """SELECT * FROM cost_audit_source_record
           WHERE ((job_id=? AND decision_revision=?)
              OR (job_id=? AND decision_revision IS NULL AND ?=1))
             AND NOT EXISTS (
               SELECT 1 FROM cost_audit_source_supersession s
               WHERE s.source_kind=cost_audit_source_record.source_kind
                 AND s.source_account=cost_audit_source_record.source_account
                 AND s.superseded_record_id=cost_audit_source_record.source_record_id
             )
           ORDER BY source_kind, source_account, source_record_id""",
        (job_id, revision, job_id, all_revisions),
    )
    names = [column[0] for column in cursor.description]
    rows = [dict(zip(names, row)) for row in cursor.fetchall()]
    request_ids = {row["request_id"] for row in rows if row["request_id"]}
    attribution_conflict = False
    known_ids = {row["id"] for row in rows}
    for request_id in sorted(request_ids):
        related_cursor = conn.execute(
            """SELECT * FROM cost_audit_source_record
               WHERE request_id=? AND NOT EXISTS (
                 SELECT 1 FROM cost_audit_source_supersession s
                 WHERE s.source_kind=cost_audit_source_record.source_kind
                   AND s.source_account=cost_audit_source_record.source_account
                   AND s.superseded_record_id=cost_audit_source_record.source_record_id
               )""",
            (request_id,),
        )
        related = [dict(zip(names, row)) for row in related_cursor.fetchall()]
        for row in related:
            if row["job_id"] not in (None, job_id) or row["decision_revision"] not in (None, revision):
                attribution_conflict = True
            if row["id"] not in known_ids:
                rows.append(row)
                known_ids.add(row["id"])
    if attribution_conflict:
        return "conflict", "request_id_attribution_conflict", rows
    conflict_rows = conn.execute(
        """SELECT event_id, payload_json FROM cost_audit_event
           WHERE job_id=? AND decision_revision=? AND event_type='conflict_detected'""",
        (job_id, revision),
    ).fetchall()
    resolved = set()
    for (payload_json,) in conn.execute(
        """SELECT payload_json FROM cost_audit_event WHERE job_id=? AND decision_revision=?
           AND event_type='cost_corrected'""",
        (job_id, revision),
    ).fetchall():
        try:
            resolved.update(json.loads(payload_json).get("superseded_conflict_ids", []))
        except (TypeError, json.JSONDecodeError):
            pass
    if any(event_id not in resolved for event_id, _ in conflict_rows):
        return "conflict", "source_identity_conflict", rows
    if not rows:
        unlinked = conn.execute(
            "SELECT COUNT(*) FROM cost_audit_source_record WHERE job_id=? AND decision_revision IS NULL",
            (job_id,),
        ).fetchone()[0]
        return "missing", "legacy_unlinked" if unlinked else "telemetry_absent", []
    amounts = {row["currency"] for row in rows if row["amount_decimal"] is not None}
    measures = {row["measure"] for row in rows if row["amount_decimal"] is not None}
    if len(amounts) > 1:
        return "conflict", "mixed_currency", rows
    request_amounts: dict[tuple[str, str, str], set[str]] = {}
    request_tokens: dict[tuple[str, str], set[int]] = {}
    for row in rows:
        request_id = row["request_id"]
        amount = row["amount_decimal"]
        if request_id and amount is not None:
            key = (request_id, row["measure"], row["currency"] or "")
            request_amounts.setdefault(key, set()).add(amount)
        if request_id:
            for dimension in ("input_tokens", "output_tokens", "cache_read_tokens"):
                value = row[dimension]
                if value is not None:
                    request_tokens.setdefault((request_id, dimension), set()).add(value)
    if any(len(values) > 1 for values in request_amounts.values()):
        return "conflict", "duplicate_request_amount_conflict", rows
    if any(len(values) > 1 for values in request_tokens.values()):
        return "conflict", "request_token_attribution_conflict", rows
    if not measures and not any(
        value is not None for row in rows
        for value in (row["input_tokens"], row["output_tokens"], row["cache_read_tokens"])
    ):
        return "missing", "usage_unavailable", rows
    if not measures:
        reasons = set()
        for row in rows:
            try:
                pricing = json.loads(row["metadata_json"] or "{}").get("pricing_basis", {})
            except (TypeError, json.JSONDecodeError):
                pricing = {}
            if pricing.get("reason_code"):
                reasons.add(pricing["reason_code"])
        return "missing", "model_unresolved" if "model_unresolved" in reasons else "price_unavailable", rows
    if any(row["confidence"] == "low" for row in rows):
        return "conflict", "low_confidence_attribution", rows
    return "linked", None, rows


def _aggregate_sources(rows) -> dict[str, Any]:
    sums: dict[str, Decimal] = {measure: Decimal(0) for measure in MEASURES}
    present = set()
    seen_amounts = set()
    for row in rows:
        measure = row["measure"]
        amount = row["amount_decimal"]
        if amount is not None:
            dedupe_key = (
                row["request_id"], measure, row["currency"], amount,
            ) if row["request_id"] else None
            if dedupe_key is not None and dedupe_key in seen_amounts:
                continue
            if dedupe_key is not None:
                seen_amounts.add(dedupe_key)
            sums[measure] += Decimal(amount)
            present.add(measure)
    currencies = {row["currency"] for row in rows if row["amount_decimal"] is not None and row["currency"]}
    confidence_order = {"low": 0, "medium": 1, "high": 2}
    confidence = min((row["confidence"] for row in rows), key=lambda x: confidence_order.get(x, -1), default="unknown")
    # Providers often export the same request represented by structured
    # telemetry. Merge token dimensions once per request, keeping a populated
    # value when the other source has no token count.
    token_groups: dict[str, dict[str, int | None]] = {}
    for row in rows:
        request_id = row["request_id"] or f"source:{row['id']}"
        group = token_groups.setdefault(request_id, {
            "input_tokens": None, "output_tokens": None, "cache_read_tokens": None,
        })
        for dimension in group:
            if group[dimension] is None and row[dimension] is not None:
                group[dimension] = row[dimension]
    return {
        "input_tokens": _sum_optional(token_groups.values(), "input_tokens"),
        "output_tokens": _sum_optional(token_groups.values(), "output_tokens"),
        "cache_read_tokens": _sum_optional(token_groups.values(), "cache_read_tokens"),
        "estimated": _decimal_text(sums["estimated"]) if "estimated" in present else None,
        "provider_billed": _decimal_text(sums["provider_billed"]) if "provider_billed" in present else None,
        "paid": _decimal_text(sums["paid"]) if "paid" in present else None,
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "confidence": confidence,
    }


def _sum_optional(rows, key: str) -> int | None:
    values = [row[key] for row in rows if row[key] is not None]
    return sum(values) if values else None


def cost_audit_report(conn: sqlite3.Connection) -> dict[str, Any]:
    cursor = conn.execute(
        """SELECT l.job_id, l.decision_revision, d.status AS decision_status, d.decided_at,
                  l.state, l.reason_code, l.input_tokens, l.output_tokens,
                  l.cache_read_tokens, l.estimated_amount_decimal,
                  l.billed_amount_decimal, l.paid_amount_decimal, l.currency,
                  l.confidence, l.pricing_basis_json, l.reconciled_at, l.source_ids_json
           FROM cost_audit_link l JOIN job_terminal_decision d
             ON d.job_id=l.job_id AND d.revision=l.decision_revision
           ORDER BY d.decided_at, l.job_id, l.decision_revision"""
    )
    names = [column[0] for column in cursor.description]
    rows = [dict(zip(names, row)) for row in cursor.fetchall()]
    totals: dict[str, dict[str, Decimal]] = {}
    groups: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        currency = row["currency"] or "unpriced"
        bucket = totals.setdefault(currency, {name: Decimal(0) for name in ("estimated", "billed", "paid")})
        for measure, column in (("estimated", "estimated_amount_decimal"),
                                ("billed", "billed_amount_decimal"),
                                ("paid", "paid_amount_decimal")):
            if row[column] is not None:
                bucket[measure] += Decimal(row[column])
        try:
            source_ids = json.loads(row.get("source_ids_json") or "[]")
        except json.JSONDecodeError:
            source_ids = []
        providers, models = set(), set()
        if source_ids:
            placeholders = ",".join("?" for _ in source_ids)
            source_rows = conn.execute(
                f"SELECT provider, model FROM cost_audit_source_record WHERE id IN ({placeholders})",
                source_ids,
            ).fetchall()
            providers.update(item[0] for item in source_rows if item[0])
            models.update(item[1] for item in source_rows if item[1])
        outbox_row = conn.execute(
            "SELECT payload_json FROM job_terminal_outbox WHERE job_id=? AND decision_revision=?",
            (row["job_id"], row["decision_revision"]),
        ).fetchone()
        try:
            outbox_payload = json.loads(outbox_row[0]) if outbox_row else {}
        except json.JSONDecodeError:
            outbox_payload = {}
        row["date"] = str(row["decided_at"] or "")[:10]
        row["harness"] = outbox_payload.get("harness") or "unknown"
        row["providers"] = sorted(providers)
        row["models"] = sorted(models)
        key = (row["date"], row["harness"], ",".join(sorted(providers)),
               ",".join(sorted(models)), row["confidence"], row["state"], currency)
        group = groups.setdefault(key, {
            "date": key[0], "harness": key[1], "providers": key[2] or "unknown",
            "models": key[3] or "unknown", "confidence": key[4], "state": key[5],
            "currency": currency, "decisions": 0,
            "estimated": Decimal(0), "provider_billed": Decimal(0), "paid": Decimal(0),
        })
        group["decisions"] += 1
        for measure, column in (("estimated", "estimated_amount_decimal"),
                                ("provider_billed", "billed_amount_decimal"),
                                ("paid", "paid_amount_decimal")):
            if row[column] is not None:
                group[measure] += Decimal(row[column])
    corrections = []
    resolved_conflicts = set()
    for event_id, payload_json in conn.execute(
        "SELECT event_id, payload_json FROM cost_audit_event WHERE event_type='cost_corrected'"
    ).fetchall():
        try:
            payload = json.loads(payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        resolved_conflicts.update(payload.get("superseded_conflict_ids", []))
        corrections.append({"event_id": event_id, "payload": payload})
    anomalies = []
    for event_id, job_id, revision, event_type, source_id, payload_json in conn.execute(
        """SELECT event_id, job_id, decision_revision, event_type, source_id, payload_json
           FROM cost_audit_event WHERE event_type IN ('duplicate_detected','conflict_detected')
           ORDER BY recorded_at, event_id"""
    ).fetchall():
        try:
            payload = json.loads(payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        anomalies.append({
            "event_id": event_id, "job_id": job_id, "decision_revision": revision,
            "event_type": event_type, "source_id": source_id,
            "reason_code": payload.get("reason_code", "unspecified"),
            "resolved": event_id in resolved_conflicts,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "decisions": [dict(row) for row in rows],
        "coverage": {
            "total": len(rows),
            "by_state": {state: sum(1 for row in rows if row["state"] == state)
                         for state in ("linked", "missing", "pending", "conflict")},
        },
        "anomalies": anomalies,
        "corrections": corrections,
        "groups": [
            {**group, **{name: _decimal_text(group[name]) for name in ("estimated", "provider_billed", "paid")}}
            for _, group in sorted(groups.items())
        ],
        "totals_by_currency": {
            currency: {name: _decimal_text(amount) for name, amount in measures.items()}
            for currency, measures in totals.items()
        },
    }


def cmd_cost_audit_reconcile() -> dict[str, int]:
    from synlynk import _get_db
    from synlynk.job_truth import ensure_terminal_outbox

    conn = _get_db()
    try:
        ensure_terminal_outbox(conn)
        return reconcile_cost_audit(conn)
    finally:
        conn.close()


def cmd_cost_audit_import(path: str, provider: str, source_account: str = "") -> dict[str, Any]:
    from synlynk import _get_db
    from synlynk.job_truth import ensure_terminal_outbox
    conn = _get_db()
    try:
        imported = import_provider_export(conn, path, provider=provider, source_account=source_account)
        ensure_terminal_outbox(conn)
        reconciled = reconcile_cost_audit(conn)
        return {"import": imported, "reconciliation": reconciled}
    finally:
        conn.close()


def cmd_cost_audit_report() -> dict[str, Any]:
    from synlynk import _get_db
    conn = _get_db()
    try:
        report = cost_audit_report(conn)
        print(json.dumps(report, indent=2, sort_keys=True))
        return report
    finally:
        conn.close()


def cmd_cost_audit_correct(
    source_kind: str,
    source_account: str,
    source_record_id: str,
    replacement_path: str,
    reason: str,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    from synlynk import _get_db
    replacement = json.loads(Path(replacement_path).read_text(encoding="utf-8"))
    if not isinstance(replacement, dict):
        raise ValueError("replacement file must contain one JSON object")
    conn = _get_db()
    try:
        if apply:
            correction = correct_source_record(
                conn, source_kind=source_kind, source_account=source_account,
                source_record_id=source_record_id, replacement=replacement, reason=reason,
            )
            return {"correction": correction, "reconciliation": reconcile_cost_audit(conn)}
        return preview_source_correction(
            conn, source_kind=source_kind, source_account=source_account,
            source_record_id=source_record_id, replacement=replacement, reason=reason,
        )
    finally:
        conn.close()
