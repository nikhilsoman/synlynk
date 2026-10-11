import sqlite3

import pytest

from synlynk.capability_report import (
    DISCIPLINE_TO_TASK_TYPE,
    _column_exists,
    _dedupe_cost_rows,
    _fetch_rows,
    build_buckets,
    summarize_buckets,
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


def test_summarize_buckets_below_min_sample_size_is_unmeasured():
    buckets = {
        ("agy", "test"): {
            "cycles": [1, 2],
            "costs": [1.0, 2.0],
            "story_ids": {"s1", "s2"},
        },
    }
    summary = summarize_buckets(buckets, min_sample_size=5)
    entry = summary[("agy", "test")]
    assert entry["n"] == 2
    assert entry["measured"] is False


def test_summarize_buckets_meets_min_sample_size_computes_medians():
    buckets = {
        ("codex", "implement"): {
            "cycles": [1, 2, 3, 4, 5],
            "costs": [1.0, 2.0, 3.0, 4.0, 5.0],
            "story_ids": {"s1", "s2", "s3", "s4", "s5"},
        },
    }
    summary = summarize_buckets(buckets, min_sample_size=5)
    entry = summary[("codex", "implement")]
    assert entry["n"] == 5
    assert entry["measured"] is True
    assert entry["median_pr_review_cycles"] == 3
    assert entry["median_total_cost_usd"] == 3.0


def test_summarize_buckets_empty_metric_lists_yield_none_median():
    buckets = {
        ("codex", "implement"): {
            "cycles": [],
            "costs": [],
            "story_ids": {"s1", "s2", "s3", "s4", "s5"},
        },
    }
    summary = summarize_buckets(buckets, min_sample_size=5)
    entry = summary[("codex", "implement")]
    assert entry["median_pr_review_cycles"] is None
    assert entry["median_total_cost_usd"] is None
