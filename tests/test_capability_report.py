import sqlite3

import pytest

from synlynk.capability_report import (
    DISCIPLINE_TO_TASK_TYPE,
    _column_exists,
    _dedupe_cost_rows,
    _fetch_rows,
    build_buckets,
)


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE capability_ratings (
            story_id TEXT, agent TEXT, discipline TEXT,
            pr_review_cycles INTEGER, quality REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE cost_entries (
            story_id TEXT, total_cost_usd REAL, pr_number INTEGER, job_id TEXT
        )
        """
    )
    return conn


def test_column_exists_true_and_false():
    conn = _make_conn()
    assert _column_exists(conn, "capability_ratings", "discipline") is True
    assert _column_exists(conn, "capability_ratings", "quality_verified") is False


def test_fetch_rows_without_quality_verified_column():
    conn = _make_conn()
    conn.execute(
        "INSERT INTO capability_ratings VALUES ('s1', 'codex', 'backend', 2, 4.5)"
    )
    conn.execute("INSERT INTO cost_entries VALUES ('s1', 1.23, 100, 'job-1')")
    rows, has_qv = _fetch_rows(conn)
    assert has_qv is False
    assert rows == [("s1", "codex", "backend", 2, None, 1.23, 100, "job-1")]


def test_fetch_rows_with_quality_verified_column():
    conn = _make_conn()
    conn.execute("ALTER TABLE capability_ratings ADD COLUMN quality_verified INTEGER")
    conn.execute(
        "INSERT INTO capability_ratings VALUES ('s1', 'codex', 'backend', 2, 4.5, 1)"
    )
    conn.execute("INSERT INTO cost_entries VALUES ('s1', 1.23, 100, 'job-1')")
    rows, has_qv = _fetch_rows(conn)
    assert has_qv is True
    assert rows == [("s1", "codex", "backend", 2, 1, 1.23, 100, "job-1")]


def test_dedupe_cost_rows_same_pr_number_counted_once():
    rows = [
        ("s1", "codex", "backend", 2, None, 1.00, 100, "job-1"),
        ("s1", "codex", "backend", 2, None, 2.00, 100, "job-2"),
    ]
    deduped = _dedupe_cost_rows(rows)
    assert len(deduped) == 1


def test_dedupe_cost_rows_null_pr_number_falls_back_to_job_id():
    rows = [
        ("s1", "codex", "backend", 2, None, 1.00, None, "job-1"),
        ("s1", "codex", "backend", 2, None, 2.00, None, "job-2"),
    ]
    deduped = _dedupe_cost_rows(rows)
    assert len(deduped) == 2


def test_build_buckets_excludes_unmapped_discipline():
    conn = _make_conn()
    conn.execute(
        "INSERT INTO capability_ratings VALUES ('s1', 'codex', 'docs', 2, 4.5)"
    )
    conn.execute("INSERT INTO cost_entries VALUES ('s1', 1.23, 100, 'job-1')")
    buckets, skipped = build_buckets(conn)
    assert buckets == {}
    assert skipped == 1


def test_build_buckets_groups_by_harness_and_task_type():
    conn = _make_conn()
    conn.execute(
        "INSERT INTO capability_ratings VALUES ('s1', 'codex', 'backend', 2, 4.5)"
    )
    conn.execute("INSERT INTO cost_entries VALUES ('s1', 1.50, 100, 'job-1')")
    conn.execute(
        "INSERT INTO capability_ratings VALUES ('s2', 'codex', 'backend', 4, 4.5)"
    )
    conn.execute("INSERT INTO cost_entries VALUES ('s2', 3.00, 101, 'job-2')")
    buckets, skipped = build_buckets(conn)
    assert skipped == 0
    key = ("codex", "implement")
    assert buckets[key]["cycles"] == [2, 4]
    assert buckets[key]["costs"] == [1.50, 3.00]
    assert buckets[key]["story_ids"] == {"s1", "s2"}
