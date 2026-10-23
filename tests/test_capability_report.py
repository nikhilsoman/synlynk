import json as _json
import hashlib
import os
import sqlite3
import shutil
import subprocess
import sys

import pytest

from synlynk.capability_report import (
    DISCIPLINE_TO_TASK_TYPE,
    _column_exists,
    _dedupe_cost_rows,
    _fetch_rows,
    build_buckets,
    format_text_report,
    propose_diff,
    summarize_buckets,
)

CURRENT_TASK_ALLOCATION = {
    "implement": {"harness": "claude", "fallback": []},
}

CANONICAL_STATE_DB = os.path.expanduser("~/.synlynk/workspaces/synlynk/state.db")


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE capability_ratings (
            story_id TEXT, agent TEXT, discipline TEXT,
            pr_review_cycles INTEGER, dispatch_rework INTEGER,
            micro_rework INTEGER, quality REAL
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
        "INSERT INTO capability_ratings VALUES ('s1', 'codex', 'backend', 2, 1, 0, 4.5)"
    )
    conn.execute("INSERT INTO cost_entries VALUES ('s1', 1.23, 100, 'job-1')")
    rows, has_qv = _fetch_rows(conn)
    assert has_qv is False
    assert rows == [("s1", "codex", "backend", 2, 1, 0, None, 1.23, 100, "job-1")]


def test_fetch_rows_with_quality_verified_column():
    conn = _make_conn()
    conn.execute("ALTER TABLE capability_ratings ADD COLUMN quality_verified INTEGER")
    conn.execute(
        "INSERT INTO capability_ratings VALUES ('s1', 'codex', 'backend', 2, 1, 0, 4.5, 1)"
    )
    conn.execute("INSERT INTO cost_entries VALUES ('s1', 1.23, 100, 'job-1')")
    rows, has_qv = _fetch_rows(conn)
    assert has_qv is True
    assert rows == [("s1", "codex", "backend", 2, 1, 0, 1, 1.23, 100, "job-1")]


def test_dedupe_cost_rows_same_pr_number_counted_once():
    rows = [
        ("s1", "codex", "backend", 2, 0, 0, None, 1.00, 100, "job-1"),
        ("s1", "codex", "backend", 2, 0, 0, None, 2.00, 100, "job-2"),
    ]
    deduped = _dedupe_cost_rows(rows)
    assert len(deduped) == 1


def test_dedupe_cost_rows_null_pr_number_falls_back_to_job_id():
    rows = [
        ("s1", "codex", "backend", 2, 0, 0, None, 1.00, None, "job-1"),
        ("s1", "codex", "backend", 2, 0, 0, None, 2.00, None, "job-2"),
    ]
    deduped = _dedupe_cost_rows(rows)
    assert len(deduped) == 2


def test_build_buckets_excludes_unmapped_discipline():
    conn = _make_conn()
    conn.execute(
        "INSERT INTO capability_ratings VALUES ('s1', 'codex', 'ml', 2, 0, 0, 4.5)"
    )
    conn.execute("INSERT INTO cost_entries VALUES ('s1', 1.23, 100, 'job-1')")
    buckets, skipped = build_buckets(conn)
    assert buckets == {}
    assert skipped == 1


def test_build_buckets_groups_by_harness_and_task_type():
    conn = _make_conn()
    conn.execute(
        "INSERT INTO capability_ratings VALUES ('s1', 'codex', 'backend', 2, 1, 0, 4.5)"
    )
    conn.execute("INSERT INTO cost_entries VALUES ('s1', 1.50, 100, 'job-1')")
    conn.execute(
        "INSERT INTO capability_ratings VALUES ('s2', 'codex', 'backend', 4, 0, 1, 4.5)"
    )
    conn.execute("INSERT INTO cost_entries VALUES ('s2', 3.00, 101, 'job-2')")
    buckets, skipped = build_buckets(conn)
    assert skipped == 0
    key = ("codex", "implement")
    assert buckets[key]["cycles"] == [2, 4]
    assert buckets[key]["costs"] == [1.50, 3.00]
    assert buckets[key]["dispatch_rework"] == [1, 0]
    assert buckets[key]["micro_rework"] == [0, 1]
    assert buckets[key]["story_ids"] == {"s1", "s2"}


def test_summarize_buckets_below_min_sample_size_is_unmeasured():
    buckets = {
        ("agy", "test"): {
            "cycles": [1, 2],
            "costs": [1.0, 2.0],
            "dispatch_rework": [0, 1],
            "micro_rework": [0, 0],
            "story_ids": {"s1", "s2"},
        },
    }
    summary = summarize_buckets(buckets, min_sample_size=5)
    entry = summary[("agy", "test")]
    assert entry["n"] == 2
    assert entry["measured"] is False


def test_summarize_buckets_meets_min_sample_size_computes_medians_and_rates():
    buckets = {
        ("codex", "implement"): {
            "cycles": [1, 2, 3, 4, 5],
            "costs": [1.0, 2.0, 3.0, 4.0, 5.0],
            "dispatch_rework": [1, 0, 0, 1, 0],
            "micro_rework": [0, 0, 0, 0, 1],
            "story_ids": {"s1", "s2", "s3", "s4", "s5"},
        },
    }
    summary = summarize_buckets(buckets, min_sample_size=5)
    entry = summary[("codex", "implement")]
    assert entry["n"] == 5
    assert entry["measured"] is True
    assert entry["median_pr_review_cycles"] == 3
    assert entry["median_total_cost_usd"] == 3.0
    assert entry["dispatch_rework_rate"] == 40.0
    assert entry["micro_rework_rate"] == 20.0


def test_summarize_buckets_empty_metric_lists_yield_none_median_and_rate():
    buckets = {
        ("codex", "implement"): {
            "cycles": [],
            "costs": [],
            "dispatch_rework": [],
            "micro_rework": [],
            "story_ids": {"s1", "s2", "s3", "s4", "s5"},
        },
    }
    summary = summarize_buckets(buckets, min_sample_size=5)
    entry = summary[("codex", "implement")]
    assert entry["median_pr_review_cycles"] is None
    assert entry["median_total_cost_usd"] is None
    assert entry["dispatch_rework_rate"] is None
    assert entry["micro_rework_rate"] is None


def test_summarize_buckets_all_zero_rework_yields_zero_rate_not_none():
    buckets = {
        ("claude", "implement"): {
            "cycles": [0, 0, 0, 0, 0],
            "costs": [1.0, 1.0, 1.0, 1.0, 1.0],
            "dispatch_rework": [0, 0, 0, 0, 0],
            "micro_rework": [0, 0, 0, 0, 0],
            "story_ids": {"s1", "s2", "s3", "s4", "s5"},
        },
    }
    summary = summarize_buckets(buckets, min_sample_size=5)
    entry = summary[("claude", "implement")]
    assert entry["dispatch_rework_rate"] == 0.0
    assert entry["micro_rework_rate"] == 0.0


def test_propose_diff_promotes_harness_clearing_rework_rate_margin():
    summary = {
        ("claude", "implement"): {
            "n": 12,
            "measured": True,
            "dispatch_rework_rate": 25.0,
            "median_total_cost_usd": 3.10,
        },
        ("codex", "implement"): {
            "n": 18,
            "measured": True,
            "dispatch_rework_rate": 10.0,
            "median_total_cost_usd": 1.80,
        },
    }
    proposals = propose_diff(summary, CURRENT_TASK_ALLOCATION, min_sample_size=5)
    assert len(proposals) == 1
    assert proposals[0]["proposed_harness"] == "codex"
    assert proposals[0]["current_harness"] == "claude"


def test_propose_diff_no_change_on_split_result():
    summary = {
        ("claude", "implement"): {
            "n": 12,
            "measured": True,
            "dispatch_rework_rate": 5.0,
            "median_total_cost_usd": 5.00,
        },
        ("codex", "implement"): {
            "n": 18,
            "measured": True,
            "dispatch_rework_rate": 20.0,
            "median_total_cost_usd": 1.00,
        },
    }
    proposals = propose_diff(summary, CURRENT_TASK_ALLOCATION, min_sample_size=5)
    assert proposals == []


def test_propose_diff_skips_unmeasured_candidate():
    summary = {
        ("claude", "implement"): {
            "n": 12,
            "measured": True,
            "dispatch_rework_rate": 25.0,
            "median_total_cost_usd": 3.10,
        },
        ("grok", "implement"): {
            "n": 2,
            "measured": False,
            "dispatch_rework_rate": 5.0,
            "median_total_cost_usd": 0.50,
        },
    }
    proposals = propose_diff(summary, CURRENT_TASK_ALLOCATION, min_sample_size=5)
    assert proposals == []


def test_propose_diff_skips_unmeasured_current():
    summary = {
        ("claude", "implement"): {
            "n": 2,
            "measured": False,
            "dispatch_rework_rate": 25.0,
            "median_total_cost_usd": 3.10,
        },
        ("codex", "implement"): {
            "n": 18,
            "measured": True,
            "dispatch_rework_rate": 10.0,
            "median_total_cost_usd": 1.80,
        },
    }
    proposals = propose_diff(summary, CURRENT_TASK_ALLOCATION, min_sample_size=5)
    assert proposals == []


def test_propose_diff_margin_boundary_exact_pass_and_near_miss():
    summary_exact = {
        ("claude", "implement"): {
            "n": 12, "measured": True,
            "dispatch_rework_rate": 20.0, "median_total_cost_usd": 3.10,
        },
        ("codex", "implement"): {
            "n": 18, "measured": True,
            "dispatch_rework_rate": 10.0, "median_total_cost_usd": 1.80,
        },
    }
    assert len(propose_diff(summary_exact, CURRENT_TASK_ALLOCATION, min_sample_size=5)) == 1

    summary_near_miss = {
        ("claude", "implement"): {
            "n": 12, "measured": True,
            "dispatch_rework_rate": 20.0, "median_total_cost_usd": 3.10,
        },
        ("codex", "implement"): {
            "n": 18, "measured": True,
            "dispatch_rework_rate": 10.1, "median_total_cost_usd": 1.80,
        },
    }
    assert propose_diff(summary_near_miss, CURRENT_TASK_ALLOCATION, min_sample_size=5) == []


def test_propose_diff_both_zero_rework_rate_produces_no_proposal():
    summary = {
        ("claude", "implement"): {
            "n": 12,
            "measured": True,
            "dispatch_rework_rate": 0.0,
            "median_total_cost_usd": 3.10,
        },
        ("codex", "implement"): {
            "n": 18,
            "measured": True,
            "dispatch_rework_rate": 0.0,
            "median_total_cost_usd": 1.80,
        },
    }
    assert propose_diff(summary, CURRENT_TASK_ALLOCATION, min_sample_size=5) == []


def test_propose_diff_fires_on_rework_rate_gap_despite_tied_pr_review_cycles():
    summary = {
        ("claude", "implement"): {
            "n": 476,
            "measured": True,
            "median_pr_review_cycles": 0,
            "dispatch_rework_rate": 2.3,
            "median_total_cost_usd": 1.80,
        },
        ("codex", "implement"): {
            "n": 656,
            "measured": True,
            "median_pr_review_cycles": 0,
            "dispatch_rework_rate": 21.7,
            "median_total_cost_usd": 3.10,
        },
    }
    proposals = propose_diff(
        summary, {"implement": {"harness": "codex", "fallback": []}}, min_sample_size=5
    )
    assert len(proposals) == 1
    assert proposals[0]["proposed_harness"] == "claude"


def test_format_text_report_no_proposals():
    text = format_text_report([], {}, skipped_no_mapping=0)
    assert "No routing changes proposed" in text
    assert "dispatch_rework_rate" in text


def test_format_text_report_with_proposal_matches_example_shape():
    proposals = [
        {
            "task_type": "implement",
            "current_harness": "claude",
            "current": {
                "n": 12,
                "dispatch_rework_rate": 25.0,
                "micro_rework_rate": 0.0,
                "median_total_cost_usd": 3.10,
            },
            "proposed_harness": "codex",
            "proposed": {
                "n": 18,
                "dispatch_rework_rate": 10.0,
                "micro_rework_rate": 0.5,
                "median_total_cost_usd": 1.80,
            },
        }
    ]
    text = format_text_report(proposals, {}, skipped_no_mapping=3)
    assert (
        "implement: claude (current, n=12, rework_rate=25.0%, "
        "micro_rework_rate=0.0, cost=$3.10) -> "
        "codex (n=18, rework_rate=10.0%, micro_rework_rate=0.5, cost=$1.80)"
    ) in text
    assert "3 rows skipped" in text


def test_cli_capability_report_runs_without_error(tmp_path, monkeypatch):
    policy_dir = tmp_path / ".synlynk"
    policy_dir.mkdir()
    (policy_dir / "policy.json").write_text(
        _json.dumps(
            {
                "capability_policy": {"min_sample_size": 5},
                "overrides": {"dev_authority": {"task_allocation": {}}},
            }
        )
    )
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE capability_ratings (story_id TEXT, agent TEXT, discipline TEXT, pr_review_cycles INTEGER, quality REAL)"
    )
    conn.execute(
        "CREATE TABLE cost_entries (story_id TEXT, total_cost_usd REAL, pr_number INTEGER, job_id TEXT)"
    )
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    env = os.environ.copy()
    repo_root = str(__file__).rsplit("/tests/", 1)[0]
    env["PYTHONPATH"] = os.pathsep.join(
        [repo_root, env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    result = subprocess.run(
        [sys.executable, "-m", "synlynk", "capability", "report"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "rows skipped" in result.stdout


@pytest.mark.skipif(
    not os.path.exists(CANONICAL_STATE_DB),
    reason="canonical state.db not present in this environment",
)
def test_capability_report_against_real_db_copy_does_not_mutate_source(tmp_path, monkeypatch):
    copy_path = tmp_path / "state.db"
    shutil.copy2(CANONICAL_STATE_DB, copy_path)
    before = hashlib.md5(copy_path.read_bytes()).hexdigest()

    policy_dir = tmp_path / ".synlynk"
    policy_dir.mkdir()
    policy_dir.joinpath("policy.json").write_text(
        _json.dumps(
            {
                "capability_policy": {"min_sample_size": 5},
                "overrides": {
                    "dev_authority": {
                        "task_allocation": {
                            "implement": {"harness": "codex", "fallback": []}
                        }
                    }
                },
            }
        )
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(copy_path))
    from synlynk.capability_report import cmd_capability_report

    cmd_capability_report(as_json=True)

    after = hashlib.md5(copy_path.read_bytes()).hexdigest()
    assert before == after, "capability report must not mutate the state.db it reads"


def test_build_buckets_maps_expanded_disciplines():
    conn = _make_conn()
    conn.execute("INSERT INTO capability_ratings VALUES ('s1', 'agy', 'docs', 1, 0, 0, 4.5)")
    conn.execute("INSERT INTO cost_entries VALUES ('s1', 1.0, 100, 'job-1')")
    conn.execute("INSERT INTO capability_ratings VALUES ('s2', 'codex', 'security', 2, 0, 0, 4.5)")
    conn.execute("INSERT INTO cost_entries VALUES ('s2', 2.0, 101, 'job-2')")
    conn.execute("INSERT INTO capability_ratings VALUES ('s3', 'codex', 'PROG', 1, 0, 0, 4.5)")
    conn.execute("INSERT INTO cost_entries VALUES ('s3', 3.0, 102, 'job-3')")
    conn.execute("INSERT INTO capability_ratings VALUES ('s4', 'grok', 'devops', 1, 0, 0, 4.5)")
    conn.execute("INSERT INTO cost_entries VALUES ('s4', 4.0, 103, 'job-4')")
    buckets, skipped = build_buckets(conn)
    assert skipped == 0
    assert ("agy", "content") in buckets
    assert ("codex", "refactor") in buckets
    assert ("codex", "implement") in buckets
    assert ("grok", "infra") in buckets


def test_fetch_rows_excludes_seed_and_local_records():
    conn = _make_conn()
    conn.execute("INSERT INTO capability_ratings VALUES ('real-1', 'codex', 'backend', 2, 0, 0, 4.5)")
    conn.execute("INSERT INTO cost_entries VALUES ('real-1', 1.0, 100, 'job-1')")
    # Synthetic seed by quality
    conn.execute("INSERT INTO capability_ratings VALUES ('seed-qual', 'codex', 'backend', 2, 0, 0, 0.6)")
    conn.execute("INSERT INTO cost_entries VALUES ('seed-qual', 1.0, 101, 'job-2')")
    # Local agent
    conn.execute("INSERT INTO capability_ratings VALUES ('local-1', 'local', 'backend', 2, 0, 0, 4.5)")
    conn.execute("INSERT INTO cost_entries VALUES ('local-1', 1.0, 102, 'job-3')")
    # Seed story ID
    conn.execute("INSERT INTO capability_ratings VALUES ('seed-story-1', 'codex', 'backend', 2, 0, 0, 4.5)")
    conn.execute("INSERT INTO cost_entries VALUES ('seed-story-1', 1.0, 103, 'job-4')")
    conn.execute("INSERT INTO capability_ratings VALUES ('local-seed-01', 'codex', 'backend', 2, 0, 0, 4.5)")
    conn.execute("INSERT INTO cost_entries VALUES ('local-seed-01', 1.0, 104, 'job-5')")

    rows, _ = _fetch_rows(conn)
    story_ids = [r[0] for r in rows]
    assert story_ids == ["real-1"]


def test_apply_proposals_updates_policy(tmp_path):
    from synlynk.capability_report import apply_proposals
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(_json.dumps({
        "overrides": {
            "dev_authority": {
                "task_allocation": {
                    "content": {"harness": "codex", "fallback": []}
                }
            }
        }
    }))
    proposals = [
        {
            "task_type": "content",
            "current_harness": "codex",
            "proposed_harness": "agy",
        }
    ]
    applied = apply_proposals(proposals, policy_path=str(policy_path))
    assert applied is True
    updated = _json.loads(policy_path.read_text())
    alloc = updated["overrides"]["dev_authority"]["task_allocation"]["content"]
    assert alloc["harness"] == "agy"
    assert "codex" in alloc["fallback"]
