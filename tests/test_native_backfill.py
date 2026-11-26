from synlynk import native_backfill as nb
from tests.test_native_capture_ledger import conn  # noqa: F401


def _manual(conn, day, model="claude-sonnet-4-6", pr=None):
    conn.execute("INSERT INTO cost_entries (session_date, harness, model, input_tokens, output_tokens, total_cost_usd, cost_source, pr_number) "
                 "VALUES (?, 'claude', ?, 120000, 15000, 1.0, 'estimated_manual', ?)", (day, model, pr))


def _derived(conn, day):
    conn.execute("INSERT INTO cost_entries (session_date, harness, model, input_tokens, output_tokens, cost_source, session_id) "
                 "VALUES (?, 'claude', 'claude-sonnet-5-5', 10, 20, 'transcript_derived', 's1')", (day,))


def test_dry_run_changes_nothing_and_reports(conn):
    _manual(conn, "2026-11-24"); _derived(conn, "2026-11-24")
    plan = nb.plan_backfill(conn)
    assert [p.action for p in plan] == ["supersede"]
    assert conn.execute("SELECT estimate_basis FROM cost_entries WHERE cost_source='estimated_manual'").fetchone()[0] is None


def test_apply_supersedes_matched_and_relabels_unmatched_without_touching_values(conn):
    _manual(conn, "2026-11-24"); _manual(conn, "2026-11-20"); _derived(conn, "2026-11-24")
    nb.apply_backfill(conn)
    got = dict(conn.execute("SELECT session_date, estimate_basis FROM cost_entries WHERE cost_source='estimated_manual'").fetchall())
    assert got == {"2026-11-24": "superseded_by_transcript", "2026-11-20": "unverified_estimate"}
    assert conn.execute("SELECT SUM(input_tokens), SUM(total_cost_usd) FROM cost_entries WHERE cost_source='estimated_manual'").fetchone() == (240000, 2.0)


def test_apply_twice_is_a_noop(conn):
    _manual(conn, "2026-11-24"); _derived(conn, "2026-11-24")
    nb.apply_backfill(conn)
    assert nb.plan_backfill(conn) == []


def test_superseded_rows_vanish_from_effective_view(conn):
    _manual(conn, "2026-11-24"); _derived(conn, "2026-11-24")
    nb.apply_backfill(conn)
    assert conn.execute("SELECT COUNT(*) FROM cost_entries_effective WHERE cost_source='estimated_manual'").fetchone()[0] == 0


def test_dispatch_rows_with_job_id_are_never_candidates(conn):
    conn.execute("INSERT INTO cost_entries (session_date, harness, cost_source, job_id) VALUES ('2026-11-24','claude','estimated_manual','job-1')")
    _derived(conn, "2026-11-24")
    assert nb.plan_backfill(conn) == []
