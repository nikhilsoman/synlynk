# synlynk capability report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `synlynk capability report` CLI command that reads `capability_ratings`/`cost_entries` from the canonical `state.db`, buckets them by harness × task_type, applies the `min_sample_size` gate from `.synlynk/policy.json`, and prints a proposed `task_allocation` diff — a report only, never an auto-write.

**Architecture:** One new module, `synlynk/capability_report.py`, holds all bucketing/median/diff logic as small pure functions (easy to unit-test without a real DB) plus a thin `cmd_capability_report()` entry point that opens the DB read-only and loads `.synlynk/policy.json`. `synlynk/cli.py` gets a new `capability report` subparser following the exact pattern of the existing `capability sweep` subparser.

**Tech Stack:** Python 3 stdlib only (`sqlite3`, `statistics`, `json`) — matches the rest of the `synlynk/` codebase (no new dependencies).

---

## Corrected fact vs. the design spec

The design spec (`docs/superpowers/specs/2026-10-11-synlynk-capability-report-design.md`) refers to "`.synlynk/policy.json`'s `task_allocation` block" and "`capability_policy` block" as if both were top-level. Reading the live file shows the actual nesting:

```
.synlynk/policy.json
├── capability_policy          (top-level: mode, min_sample_size, metrics, metric_source, blocking_dependency, not_yet_calibrated, generator_status, note)
└── overrides
    └── dev_authority
        └── task_allocation    (task_type -> {harness, fallback, [calibration_eligible], [note]})
```

`min_sample_size` is read from `policy["capability_policy"]["min_sample_size"]`. The current routing table is read from `policy["overrides"]["dev_authority"]["task_allocation"]`. Every task below uses these real paths, not the spec's shorthand.

## File Structure

- **Create:** `synlynk/capability_report.py` — bucketing, median computation, diff-proposal logic, text/JSON formatting, and the `cmd_capability_report()` entry point. One file, one responsibility: turning rows from the two tables into a routing proposal.
- **Modify:** `synlynk/cli.py` — add the `report` subparser under the existing `capability` subcommand (next to `sweep`, around line 1718), and the dispatch branch (around line 2880-2882).
- **Test:** `tests/test_capability_report.py` — unit tests for every pure function in `capability_report.py`, plus one integration test against a temp copy of the real `state.db`.

---

### Task 1: Discipline-to-task_type mapping and bucket builder

**Files:**
- Create: `synlynk/capability_report.py`
- Test: `tests/test_capability_report.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_capability_report.py
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
        ("s1", "codex", "backend", 2, None, 2.00, 100, "job-2"),  # same pr_number=100
    ]
    deduped = _dedupe_cost_rows(rows)
    assert len(deduped) == 1


def test_dedupe_cost_rows_null_pr_number_falls_back_to_job_id():
    rows = [
        ("s1", "codex", "backend", 2, None, 1.00, None, "job-1"),
        ("s1", "codex", "backend", 2, None, 2.00, None, "job-2"),
    ]
    deduped = _dedupe_cost_rows(rows)
    assert len(deduped) == 2  # different job_id, both kept


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
    key = ("codex", "implement")  # backend -> implement
    assert buckets[key]["cycles"] == [2, 4]
    assert buckets[key]["costs"] == [1.50, 3.00]
    assert buckets[key]["story_ids"] == {"s1", "s2"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_capability_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.capability_report'`

- [ ] **Step 3: Write the implementation**

```python
# synlynk/capability_report.py
"""Generate a task_allocation routing proposal from capability_ratings/cost_entries.

Read-only: never writes to .synlynk/policy.json or state.db. See
docs/superpowers/specs/2026-10-11-synlynk-capability-report-design.md (gh:#1993).
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict

# discipline (capability_ratings.discipline) -> task_type (policy.json's
# overrides.dev_authority.task_allocation key). None means "no mapping yet,
# exclude rather than guess" -- see the design spec's Approach step 2.
DISCIPLINE_TO_TASK_TYPE = {
    "testing": "test",
    "backend": "implement",
    "frontend": "implement",
    "cli": "cli-plumbing",
    "devops": "infra",
    "architecture": "review",
    "docs": None,
    "security": None,
    "ml": None,
    "PROG": None,
}


def _column_exists(conn, table: str, column: str) -> bool:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    return column in cols


def _fetch_rows(conn):
    """Return (rows, has_quality_verified).

    Each row: (story_id, harness, discipline, pr_review_cycles,
    quality_verified, total_cost_usd, pr_number, job_id).
    """
    has_quality_verified = _column_exists(conn, "capability_ratings", "quality_verified")
    qv_select = "cr.quality_verified" if has_quality_verified else "NULL"
    query = (
        "SELECT cr.story_id, cr.agent, cr.discipline, cr.pr_review_cycles, "
        f"{qv_select}, ce.total_cost_usd, ce.pr_number, ce.job_id "
        "FROM capability_ratings cr JOIN cost_entries ce ON cr.story_id = ce.story_id"
    )
    rows = conn.execute(query).fetchall()
    return [tuple(row) for row in rows], has_quality_verified


def _dedupe_cost_rows(rows):
    """One cost contribution per (story_id, pr_number) when pr_number is set,
    else per (story_id, job_id). Avoids double-counting a story with both a
    dispatch cost-log row and a reviewer-logged backfill row for the same PR.
    """
    seen = set()
    deduped = []
    for row in rows:
        story_id, _harness, _discipline, _cycles, _qv, _cost, pr_number, job_id = row
        key = (story_id, "pr", pr_number) if pr_number is not None else (story_id, "job", job_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def build_buckets(conn):
    """Return (buckets, skipped_no_mapping).

    buckets: {(harness, task_type): {"cycles": [...], "costs": [...], "story_ids": {...}}}
    """
    rows, _has_quality_verified = _fetch_rows(conn)
    rows = _dedupe_cost_rows(rows)
    buckets = defaultdict(lambda: {"cycles": [], "costs": [], "story_ids": set()})
    skipped_no_mapping = 0
    for story_id, harness, discipline, cycles, _qv, cost, _pr_number, _job_id in rows:
        task_type = DISCIPLINE_TO_TASK_TYPE.get(discipline)
        if task_type is None:
            skipped_no_mapping += 1
            continue
        bucket = buckets[(harness, task_type)]
        if cycles is not None:
            bucket["cycles"].append(cycles)
        if cost is not None:
            bucket["costs"].append(cost)
        bucket["story_ids"].add(story_id)
    return dict(buckets), skipped_no_mapping
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_capability_report.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/capability_report.py tests/test_capability_report.py
git commit -m "feat(capability): bucket capability_ratings/cost_entries by harness x task_type (gh:#1993)"
```

---

### Task 2: Sample-size gate and median summary

**Files:**
- Modify: `synlynk/capability_report.py`
- Test: `tests/test_capability_report.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_capability_report.py`:

```python
from synlynk.capability_report import summarize_buckets


def test_summarize_buckets_below_min_sample_size_is_unmeasured():
    buckets = {
        ("agy", "test"): {"cycles": [1, 2], "costs": [1.0, 2.0], "story_ids": {"s1", "s2"}},
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
        ("codex", "implement"): {"cycles": [], "costs": [], "story_ids": {"s1", "s2", "s3", "s4", "s5"}},
    }
    summary = summarize_buckets(buckets, min_sample_size=5)
    entry = summary[("codex", "implement")]
    assert entry["median_pr_review_cycles"] is None
    assert entry["median_total_cost_usd"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_capability_report.py -v -k summarize_buckets`
Expected: FAIL with `ImportError: cannot import name 'summarize_buckets'`

- [ ] **Step 3: Write the implementation**

Append to `synlynk/capability_report.py`:

```python
def summarize_buckets(buckets: dict, min_sample_size: int) -> dict:
    """Return {(harness, task_type): {"n", "measured", "median_pr_review_cycles",
    "median_total_cost_usd"}}.

    n is the count of distinct story_ids in the bucket -- the sample for the
    min_sample_size gate. pr_review_cycles is counted regardless of
    quality_verified (it's a review-round count, not a quality score, so the
    quality-score fallback described in gh:#1993's comment thread doesn't
    apply to it -- see the design spec's Schema section).
    """
    summary = {}
    for key, data in buckets.items():
        n = len(data["story_ids"])
        summary[key] = {
            "n": n,
            "measured": n >= min_sample_size,
            "median_pr_review_cycles": statistics.median(data["cycles"]) if data["cycles"] else None,
            "median_total_cost_usd": statistics.median(data["costs"]) if data["costs"] else None,
        }
    return summary
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_capability_report.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/capability_report.py tests/test_capability_report.py
git commit -m "feat(capability): apply min_sample_size gate and compute medians (gh:#1993)"
```

---

### Task 3: Diff proposal against current task_allocation

**Files:**
- Modify: `synlynk/capability_report.py`
- Test: `tests/test_capability_report.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_capability_report.py`:

```python
from synlynk.capability_report import propose_diff

CURRENT_TASK_ALLOCATION = {
    "implement": {"harness": "claude", "fallback": []},
}


def test_propose_diff_promotes_strictly_better_harness():
    summary = {
        ("claude", "implement"): {
            "n": 12, "measured": True, "median_pr_review_cycles": 2.5, "median_total_cost_usd": 3.10,
        },
        ("codex", "implement"): {
            "n": 18, "measured": True, "median_pr_review_cycles": 1.5, "median_total_cost_usd": 1.80,
        },
    }
    proposals = propose_diff(summary, CURRENT_TASK_ALLOCATION, min_sample_size=5)
    assert len(proposals) == 1
    assert proposals[0]["proposed_harness"] == "codex"
    assert proposals[0]["current_harness"] == "claude"


def test_propose_diff_no_change_on_split_result():
    # Cheaper but more review cycles -- inconclusive, not a recommendation.
    summary = {
        ("claude", "implement"): {
            "n": 12, "measured": True, "median_pr_review_cycles": 1.0, "median_total_cost_usd": 5.00,
        },
        ("codex", "implement"): {
            "n": 18, "measured": True, "median_pr_review_cycles": 2.0, "median_total_cost_usd": 1.00,
        },
    }
    proposals = propose_diff(summary, CURRENT_TASK_ALLOCATION, min_sample_size=5)
    assert proposals == []


def test_propose_diff_skips_unmeasured_candidate():
    summary = {
        ("claude", "implement"): {
            "n": 12, "measured": True, "median_pr_review_cycles": 2.5, "median_total_cost_usd": 3.10,
        },
        ("grok", "implement"): {
            "n": 2, "measured": False, "median_pr_review_cycles": 0.5, "median_total_cost_usd": 0.50,
        },
    }
    proposals = propose_diff(summary, CURRENT_TASK_ALLOCATION, min_sample_size=5)
    assert proposals == []


def test_propose_diff_skips_unmeasured_current():
    summary = {
        ("claude", "implement"): {
            "n": 2, "measured": False, "median_pr_review_cycles": 2.5, "median_total_cost_usd": 3.10,
        },
        ("codex", "implement"): {
            "n": 18, "measured": True, "median_pr_review_cycles": 1.5, "median_total_cost_usd": 1.80,
        },
    }
    proposals = propose_diff(summary, CURRENT_TASK_ALLOCATION, min_sample_size=5)
    assert proposals == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_capability_report.py -v -k propose_diff`
Expected: FAIL with `ImportError: cannot import name 'propose_diff'`

- [ ] **Step 3: Write the implementation**

Append to `synlynk/capability_report.py`:

```python
def propose_diff(summary: dict, current_task_allocation: dict, min_sample_size: int) -> list:
    """Return a list of proposed harness swaps.

    A swap is only proposed when the candidate harness clears
    min_sample_size AND beats the current harness's median on BOTH metrics
    (lower pr_review_cycles AND lower total_cost_usd). A split result
    (cheaper but slower, or vice versa) is inconclusive and reported as no
    change -- see the design spec's Approach step 5.
    """
    by_task_type = defaultdict(dict)
    for (harness, task_type), entry in summary.items():
        by_task_type[task_type][harness] = entry

    proposals = []
    for task_type, current in current_task_allocation.items():
        current_harness = current.get("harness")
        candidates = by_task_type.get(task_type, {})
        current_entry = candidates.get(current_harness)
        if current_entry is None or not current_entry["measured"]:
            continue
        for harness, entry in candidates.items():
            if harness == current_harness or not entry["measured"]:
                continue
            cycles_ok = (
                entry["median_pr_review_cycles"] is not None
                and current_entry["median_pr_review_cycles"] is not None
                and entry["median_pr_review_cycles"] < current_entry["median_pr_review_cycles"]
            )
            cost_ok = (
                entry["median_total_cost_usd"] is not None
                and current_entry["median_total_cost_usd"] is not None
                and entry["median_total_cost_usd"] < current_entry["median_total_cost_usd"]
            )
            if cycles_ok and cost_ok:
                proposals.append(
                    {
                        "task_type": task_type,
                        "current_harness": current_harness,
                        "current": current_entry,
                        "proposed_harness": harness,
                        "proposed": entry,
                    }
                )
    return proposals
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_capability_report.py -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/capability_report.py tests/test_capability_report.py
git commit -m "feat(capability): propose task_allocation diff on strictly-better harness (gh:#1993)"
```

---

### Task 4: Output formatting and the cmd_capability_report entry point

**Files:**
- Modify: `synlynk/capability_report.py`
- Test: `tests/test_capability_report.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_capability_report.py`:

```python
import json as _json

from synlynk.capability_report import format_text_report


def test_format_text_report_no_proposals():
    text = format_text_report([], {}, skipped_no_mapping=0)
    assert "No routing changes proposed" in text


def test_format_text_report_with_proposal_matches_example_shape():
    proposals = [
        {
            "task_type": "implement",
            "current_harness": "claude",
            "current": {"n": 12, "median_pr_review_cycles": 2.5, "median_total_cost_usd": 3.10},
            "proposed_harness": "codex",
            "proposed": {"n": 18, "median_pr_review_cycles": 1.5, "median_total_cost_usd": 1.80},
        }
    ]
    text = format_text_report(proposals, {}, skipped_no_mapping=3)
    assert "implement: claude (current, n=12, cycles=2.5, cost=$3.10) -> codex (n=18, cycles=1.5, cost=$1.80)" in text
    assert "3 rows skipped" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_capability_report.py -v -k format_text_report`
Expected: FAIL with `ImportError: cannot import name 'format_text_report'`

- [ ] **Step 3: Write the implementation**

Append to `synlynk/capability_report.py`:

```python
def format_text_report(proposals: list, summary: dict, skipped_no_mapping: int) -> str:
    lines = []
    if not proposals:
        lines.append(
            "No routing changes proposed (no harness clears min_sample_size "
            "with a strictly better median on both metrics)."
        )
    for p in proposals:
        current, proposed = p["current"], p["proposed"]
        lines.append(
            f"{p['task_type']}: {p['current_harness']} (current, n={current['n']}, "
            f"cycles={current['median_pr_review_cycles']}, "
            f"cost=${current['median_total_cost_usd']:.2f}) -> "
            f"{p['proposed_harness']} (n={proposed['n']}, "
            f"cycles={proposed['median_pr_review_cycles']}, "
            f"cost=${proposed['median_total_cost_usd']:.2f})"
        )
    lines.append(f"\n{skipped_no_mapping} rows skipped (discipline has no task_type mapping).")
    return "\n".join(lines)


def _load_policy(path: str = ".synlynk/policy.json") -> dict:
    with open(path) as f:
        return json.load(f)


def cmd_capability_report(as_json: bool = False) -> None:
    """Entry point for `synlynk capability report`. Read-only: opens state.db
    via _get_db(read_only=True), never mutates it or .synlynk/policy.json.
    """
    from synlynk import _get_db

    policy = _load_policy()
    min_sample_size = policy["capability_policy"]["min_sample_size"]
    current_task_allocation = policy["overrides"]["dev_authority"]["task_allocation"]

    conn = _get_db(read_only=True)
    try:
        buckets, skipped_no_mapping = build_buckets(conn)
    finally:
        conn.close()

    summary = summarize_buckets(buckets, min_sample_size)
    proposals = propose_diff(summary, current_task_allocation, min_sample_size)

    if as_json:
        print(json.dumps({"proposals": proposals, "skipped_no_mapping": skipped_no_mapping}, indent=2, default=str))
    else:
        print(format_text_report(proposals, summary, skipped_no_mapping))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_capability_report.py -v`
Expected: PASS (16 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/capability_report.py tests/test_capability_report.py
git commit -m "feat(capability): add text/JSON formatting and cmd_capability_report entry point (gh:#1993)"
```

---

### Task 5: Wire the `capability report` CLI subcommand

**Files:**
- Modify: `synlynk/cli.py:1706-1718` (subparser registration), `synlynk/cli.py:2880-2882` (dispatch)
- Test: `tests/test_capability_report.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_capability_report.py`:

```python
import subprocess
import sys


def test_cli_capability_report_runs_without_error(tmp_path, monkeypatch):
    # Minimal policy.json so cmd_capability_report has something to read.
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
    conn.execute("CREATE TABLE cost_entries (story_id TEXT, total_cost_usd REAL, pr_number INTEGER, job_id TEXT)")
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    result = subprocess.run(
        [sys.executable, "-m", "synlynk", "capability", "report"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "rows skipped" in result.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_capability_report.py -v -k test_cli_capability_report_runs_without_error`
Expected: FAIL (argparse error: `invalid choice: 'report'`, or no such subcommand)

- [ ] **Step 3: Wire the subparser**

In `synlynk/cli.py`, immediately after the existing `sweep_parser` block (after line 1718, before the blank line preceding `instructions_parser` at line 1720):

```python
    report_parser = capability_sub.add_parser(
        "report",
        help="Generate a task_allocation routing proposal from capability_ratings/cost_entries",
    )
    report_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output the proposal as JSON instead of text",
    )
```

- [ ] **Step 4: Wire the dispatch branch**

In `synlynk/cli.py`, replace the existing capability dispatch block:

```python
    elif args.command == "capability":
        if args.capability_action == "sweep":
            cmd_capability_sweep(cost_cap_override=getattr(args, "cost_cap", None))
```

with:

```python
    elif args.command == "capability":
        if args.capability_action == "sweep":
            cmd_capability_sweep(cost_cap_override=getattr(args, "cost_cap", None))
        elif args.capability_action == "report":
            from synlynk.capability_report import cmd_capability_report
            cmd_capability_report(as_json=getattr(args, "as_json", False))
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_capability_report.py -v`
Expected: PASS (17 tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_capability_report.py
git commit -m "feat(cli): wire 'synlynk capability report' subcommand (gh:#1993)"
```

---

### Task 6: Integration test against a copy of the real state.db

**Files:**
- Test: `tests/test_capability_report.py`

- [ ] **Step 1: Write the integration test**

Append to `tests/test_capability_report.py`:

```python
import hashlib
import os
import shutil


CANONICAL_STATE_DB = os.path.expanduser("~/.synlynk/workspaces/synlynk/state.db")


@pytest.mark.skipif(
    not os.path.exists(CANONICAL_STATE_DB),
    reason="canonical state.db not present in this environment",
)
def test_capability_report_against_real_db_copy_does_not_mutate_source(tmp_path):
    # Copy first -- never open the canonical file read-write from a test.
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
                        "task_allocation": {"implement": {"harness": "codex", "fallback": []}}
                    }
                },
            }
        )
    )

    import os as _os

    _os.chdir(tmp_path)
    _os.environ["SYNLYNK_STATE_DB_PATH"] = str(copy_path)
    try:
        from synlynk.capability_report import cmd_capability_report

        cmd_capability_report(as_json=True)  # must complete without raising
    finally:
        del _os.environ["SYNLYNK_STATE_DB_PATH"]

    after = hashlib.md5(copy_path.read_bytes()).hexdigest()
    assert before == after, "capability report must not mutate the state.db it reads"
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_capability_report.py -v -k real_db_copy`
Expected: PASS. If the environment lacks the canonical `state.db` (e.g. a fresh CI container), the test is skipped rather than failing — this is intentional, per the `skipif` guard.

- [ ] **Step 3: Run the full test file one more time**

Run: `pytest tests/test_capability_report.py -v`
Expected: PASS (18 tests, or 17 + 1 skip outside the dev machine)

- [ ] **Step 4: Commit**

```bash
git add tests/test_capability_report.py
git commit -m "test(capability): verify capability report never mutates the real state.db (gh:#1993)"
```

---

## Self-Review

**1. Spec coverage:**
- Problem / blocking dependencies: both resolved before this plan was written (#1926 closed, #1831 closed this session) — nothing to implement here, just confirmed.
- Schema / `quality_verified` handling: Task 1's `_fetch_rows` detects the column via `PRAGMA table_info` and degrades to `NULL` when absent — matches spec exactly. Task 2's docstring explicitly notes `pr_review_cycles` is counted regardless of `quality_verified`, matching the spec's explicit carve-out.
- `DISCIPLINE_TO_TASK_TYPE` mapping with exclusion + skipped count: Task 1.
- `min_sample_size` gate: Task 2.
- Dedupe-on-`pr_number` (fallback to `job_id`): Task 1's `_dedupe_cost_rows`.
- Proposed diff, both-metrics-better rule, no auto-write: Task 3.
- Text + `--json` output: Task 4.
- CLI wiring matching the `sweep` pattern: Task 5.
- Never opens the canonical DB read-write: `cmd_capability_report` uses `_get_db(read_only=True)` exclusively (Task 4); Task 6 proves it with an md5 check against a real copy.

**2. Placeholder scan:** None — every step has complete, runnable code and exact commands.

**3. Type consistency:** `build_buckets` returns `(buckets, skipped_no_mapping)` in Task 1 and is consumed with that exact signature in Task 4's `cmd_capability_report`. `summarize_buckets(buckets, min_sample_size)` signature from Task 2 matches its Task 4 call site. `propose_diff(summary, current_task_allocation, min_sample_size)` from Task 3 matches its Task 4 call site. `format_text_report(proposals, summary, skipped_no_mapping)` from Task 4 matches its test calls.

## Execution Handoff

Per this project's Default Agent Role policy and gh:#1993's own routing note ("Routes to Codex/Agy per the (now-provisional, still-default) implementation split"), implementation should be dispatched via `synlynk dispatch --force-harness codex` (fallback `agy`), not implemented by Claude directly.

Before dispatch, a story must be created and linked to a GOVERNS goal for 100% GOVERNS adherence (Hardened PR Review Policy). `goal-079e2f37` is the existing goal this session already linked gh:#2076's story (`story-fa106e5a`) under — confirm via `synlynk goal list` / `synlynk story list` whether it's still the best fit for this Empirical Capability Assessment Policy workstream (it covers Wave-4/#1708-adjacent provider-aggregator work, which is a different thread; a dedicated goal for the empirical-capability-review-policy workstream, as referenced in project memory `gh1927-held-pending-decide-panel.md`, may be a better fit — search before creating a new one).

This is a single, self-contained plan (one new module + one CLI wire-up) — no sub-plan decomposition needed. Recommended execution: **Subagent-Driven** (`superpowers:subagent-driven-development`), since tasks are small, sequential, and each is independently testable.
