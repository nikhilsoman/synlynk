import json
import sqlite3
from types import SimpleNamespace

import pytest


def _insert_job(conn, job_id, *, purpose=None, role=None, task_type=None, explicit=None,
                harness="grok", model="grok-4.6"):
    conn.execute(
        """INSERT INTO daemon_jobs
           (job_id, agent, harness, role, task, enqueued_at, resolved_model,
            purpose, task_type, task_type_explicit)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, harness, harness, role, "adapter conformance tests",
         "2026-10-06T21:22:14Z", model, purpose, task_type, explicit),
    )


def test_migration_creates_attestation_table(project_dir, monkeypatch):
    import synlynk

    monkeypatch.chdir(project_dir)
    conn = synlynk._get_db()
    columns = {row[1] for row in conn.execute(
        "PRAGMA table_info(job_provenance_attestations)"
    )}
    assert {"job_id", "role", "task_type", "purpose", "attested_by", "rationale", "source"} <= columns
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 20
    conn.close()


def test_migration_adds_attestation_table_to_existing_v17_database():
    from synlynk.migrations.runner import run_pending_migrations

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY)")
    conn.execute("PRAGMA user_version=17")
    run_pending_migrations(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 20
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='job_provenance_attestations'"
    ).fetchone() == (1,)
    conn.close()


def test_attestation_is_idempotent_and_preserves_dispatch_metadata(project_dir, monkeypatch):
    import synlynk
    from synlynk.provenance import record_job_provenance_attestation

    monkeypatch.chdir(project_dir)
    conn = synlynk._get_db()
    _insert_job(conn, "job-legacy", role="dev", task_type="test", explicit=None)
    conn.commit()

    inserted, record = record_job_provenance_attestation(
        conn, job_id="job-legacy", role="dev", task_type="test",
        attested_by="nikhilsoman", rationale="Owner confirmed --task-type test was supplied.",
    )
    repeated, same_record = record_job_provenance_attestation(
        conn, job_id="job-legacy", role="dev", task_type="test",
        attested_by="nikhilsoman", rationale="Owner confirmed --task-type test was supplied.",
    )

    assert inserted and not repeated
    assert record["purpose"] == "implementation"
    assert record["source"] == "local-cli"
    assert same_record["id"] == record["id"]
    with pytest.raises(ValueError, match="conflicting provenance attestation"):
        record_job_provenance_attestation(
            conn, job_id="job-legacy", role="dev", task_type="test",
            attested_by="nikhilsoman", rationale="different rationale",
        )
    metadata = conn.execute(
        "SELECT role, task_type, task_type_explicit, purpose FROM daemon_jobs WHERE job_id=?",
        ("job-legacy",),
    ).fetchone()
    assert metadata == ("dev", "test", None, None)
    assert conn.execute(
        "SELECT COUNT(*) FROM job_provenance_attestations WHERE job_id=?", ("job-legacy",)
    ).fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(
            "UPDATE job_provenance_attestations SET rationale='rewritten' WHERE job_id=?",
            ("job-legacy",),
        )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM job_provenance_attestations WHERE job_id=?", ("job-legacy",))
    conn.rollback()
    conn.close()


def test_attestation_rejects_missing_job_invalid_pair_and_conflict(project_dir, monkeypatch):
    import synlynk
    from synlynk.provenance import record_job_provenance_attestation

    monkeypatch.chdir(project_dir)
    conn = synlynk._get_db()
    with pytest.raises(ValueError, match="does not exist"):
        record_job_provenance_attestation(
            conn, job_id="missing", role="dev", task_type="test",
            attested_by="nikhilsoman", rationale="confirmed",
        )

    _insert_job(conn, "job-conflict", role="dev", task_type="implement")
    conn.commit()
    with pytest.raises(ValueError, match="conflicts with recorded task type"):
        record_job_provenance_attestation(
            conn, job_id="job-conflict", role="dev", task_type="test",
            attested_by="nikhilsoman", rationale="confirmed",
        )
    with pytest.raises(ValueError, match="not authorized"):
        record_job_provenance_attestation(
            conn, job_id="job-conflict", role="qa", task_type="implement",
            attested_by="nikhilsoman", rationale="confirmed",
        )
    _insert_job(conn, "job-purpose", role="dev", task_type="test", purpose="other")
    conn.commit()
    with pytest.raises(ValueError, match="already has typed purpose"):
        record_job_provenance_attestation(
            conn, job_id="job-purpose", role="dev", task_type="test",
            attested_by="nikhilsoman", rationale="confirmed",
        )
    conn.close()


def test_attestation_cli_requires_exact_confirmation_and_records_operator(project_dir, monkeypatch, capsys):
    import synlynk
    import synlynk.team as team
    from synlynk.provenance import cmd_provenance_attest

    monkeypatch.chdir(project_dir)
    conn = synlynk._get_db()
    _insert_job(conn, "job-cli", role="dev", task_type="test")
    conn.commit()
    conn.close()
    monkeypatch.setattr(team, "get_username", lambda: "nikhilsoman")

    assert cmd_provenance_attest(
        "job-cli", "dev", "test", "Confirmed by the project owner.", "wrong",
    ) == 1
    assert "Attestation refused" in capsys.readouterr().err

    assert cmd_provenance_attest(
        "job-cli", "dev", "test", "Confirmed by the project owner.", "job-cli:dev:test",
    ) == 0
    output = capsys.readouterr().out
    assert "task_type_explicit=None" in output
    assert "attested_by=@nikhilsoman" in output
    assert "Human provenance attestation recorded" in output


def test_attestation_cli_rejects_unknown_operator(project_dir, monkeypatch, capsys):
    import synlynk
    import synlynk.team as team
    from synlynk.provenance import cmd_provenance_attest

    monkeypatch.chdir(project_dir)
    conn = synlynk._get_db()
    _insert_job(conn, "job-unknown-operator", role="dev", task_type="test")
    conn.commit()
    conn.close()
    monkeypatch.setattr(team, "get_username", lambda: "unknown")

    assert cmd_provenance_attest(
        "job-unknown-operator", "dev", "test", "confirmed", "job-unknown-operator:dev:test",
    ) == 1
    assert "could not identify" in capsys.readouterr().err

    conn = synlynk._get_db()
    assert conn.execute(
        "SELECT COUNT(*) FROM job_provenance_attestations"
    ).fetchone()[0] == 0
    conn.close()


def test_provenance_attest_cli_parser():
    from synlynk.cli import build_parser

    args = build_parser(selected_command="provenance").parse_args([
        "provenance", "attest", "job-1", "--role", "dev", "--task-type", "test",
        "--reason", "owner confirmed", "--confirm", "job-1:dev:test",
    ])

    assert args.command == "provenance"
    assert args.provenance_action == "attest"
    assert args.task_type == "test"


def test_conflicting_attestation_does_not_override_typed_dispatch_purpose(project_dir, monkeypatch):
    import synlynk
    import synlynk.db as db

    monkeypatch.chdir(project_dir)
    conn = synlynk._get_db()
    _insert_job(conn, "job-conflicting-attestation", role="dev", task_type="test",
                explicit=True, purpose="implementation")
    conn.execute(
        """INSERT INTO job_provenance_attestations
           (job_id, role, task_type, purpose, attested_by, rationale, source)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("job-conflicting-attestation", "dev", "test", "other", "nikhilsoman",
         "conflicting", "local-cli"),
    )
    conn.commit()

    assert not db._job_has_implementation_purpose(conn, "job-conflicting-attestation")
    conn.close()


def test_pr_check_uses_attested_implementation_for_exact_job_link(project_dir, monkeypatch):
    import synlynk
    import synlynk.db as db
    from synlynk.provenance import record_job_provenance_attestation

    monkeypatch.chdir(project_dir)
    policy_path = project_dir / ".synlynk" / "policy.json"
    policy_path.write_text(json.dumps({
        "overrides": {"merge_authority": {"cross_harness_review_required": True}}
    }))
    monkeypatch.setattr(db, "_cross_harness_review_required", lambda: True)
    monkeypatch.setattr(db.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0,
        stdout=json.dumps({"reviews": [{
            "author": {"login": "qa-app[bot]"},
            "submittedAt": "2026-10-07T01:00:00Z",
        }]}),
    ))
    conn = synlynk._get_db()
    _insert_job(conn, "job-impl", role="dev", task_type="test", explicit=None)
    conn.execute(
        """INSERT INTO daemon_jobs
           (job_id, agent, harness, task, enqueued_at, resolved_model, purpose,
            gh_write_target, gh_write_expect, gh_write_author, started_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("job-review", "claude", "claude", "review", "2026-10-07T00:00:00Z",
         "claude-sonnet-4-6", "review", "pr:2081", "review_posted", "qa-app[bot]",
         "2026-10-07T00:30:00Z"),
    )
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, harness, model, cost_source, job_id, pr_number)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("2026-10-07", "grok", "grok", "grok-4.6", "test", "job-impl", 2081),
    )
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, harness, model, cost_source, job_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("2026-10-07", "claude", "claude", "claude-sonnet-4-6", "test", "job-review"),
    )
    conn.commit()
    record_job_provenance_attestation(
        conn, job_id="job-impl", role="dev", task_type="test",
        attested_by="nikhilsoman", rationale="Owner confirmed the explicit dispatch task type.",
    )

    ok, message = db._cross_harness_review_verdict(conn, 2081)

    assert ok
    assert "implementation grok / grok-4.6 (human attestation)" in message
    assert "reviewed by claude / claude-sonnet-4-6" in message
    conn.close()


def test_pr_check_rejects_unattested_legacy_job(project_dir, monkeypatch):
    import synlynk
    import synlynk.db as db

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(db, "_cross_harness_review_required", lambda: True)
    conn = synlynk._get_db()
    _insert_job(conn, "job-no-attestation", role="dev", task_type="test", explicit=None)
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, harness, model, cost_source, job_id, pr_number)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("2026-10-07", "grok", "grok", "grok-4.6", "test", "job-no-attestation", 2081),
    )
    conn.commit()

    ok, message = db._cross_harness_review_verdict(conn, 2081)

    assert not ok
    assert message == "no implementing job provenance found for PR #2081"
    conn.close()
