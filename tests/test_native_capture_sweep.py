import pytest

from synlynk import native_capture as nc
from tests.native_capture_fixtures import assistant, write
from tests.test_native_capture_ledger import conn  # noqa: F401  (reuse fixture)


def test_is_dispatch_slug():
    assert nc.is_dispatch_slug("-Users-n-dev-synlynk-worktrees-job-4ca44bdb")
    assert nc.is_dispatch_slug("-Users-n-dev-synlynk--worktrees-job-1")
    assert not nc.is_dispatch_slug("-Users-n-dev-synlynk")
    assert not nc.is_dispatch_slug("-Users-n-dev-synlynk--claude-worktrees-feature-x")


def test_sweep_skips_dispatch_dirs_and_job_sessions(conn, tmp_path):
    base = tmp_path / "projects"
    native = base / "-Users-n-dev-synlynk"
    job = base / "-Users-n-dev-synlynk-worktrees-job-1"
    native.mkdir(parents=True); job.mkdir(parents=True)
    write(native / "s1.jsonl", [assistant("m1")])
    write(job / "s2.jsonl", [assistant("m2")])
    write(native / "s3.jsonl", [assistant("m3")])
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, session_id, job_id) VALUES ('2026-11-24','dispatch','s3','job-9')")
    summary = nc.sweep(conn, base)
    got = {r[0] for r in conn.execute("SELECT session_id FROM cost_entries WHERE cost_source='transcript_derived'")}
    assert got == {"s1"}
    assert summary["skipped_dispatch"] == 2


def test_sweep_skips_finalized_unchanged_transcripts(conn, tmp_path):
    base = tmp_path / "projects" / "-Users-n-dev-synlynk"
    base.mkdir(parents=True)
    p = write(base / "s1.jsonl", [assistant("m1")])
    nc.capture(conn, "s1", p, final=True)
    assert nc.sweep(conn, tmp_path / "projects")["captured"] == 0


def test_reconcile_flags_sessions_with_both_row_kinds(conn):
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, session_id) VALUES ('2026-11-24','transcript_derived','sX')")
    conn.execute("INSERT INTO cost_entries (session_date, cost_source, session_id, job_id) VALUES ('2026-11-24','dispatch','sX','job-1')")
    assert nc.reconcile(conn) == ["sX"]
