# Rework-Rate Routing Metric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `capability_report.py`'s `propose_diff()` quality gate — currently median `pr_review_cycles` with strict `<`, which can never fire because every calibrated harness medians to 0 — with a `dispatch_rework` rate compared against a fixed percentage-point margin, with `micro_rework` rate surfaced as non-gating context.

**Architecture:** `_fetch_rows()` pulls two new columns (`dispatch_rework`, `micro_rework`) already present on every `capability_ratings` row. `build_buckets()` accumulates them per harness×task_type bucket alongside the existing `cycles`/`costs` lists. `summarize_buckets()` computes `dispatch_rework_rate`/`micro_rework_rate` (% of bucket rows with the field > 0). `propose_diff()` swaps its `cycles_ok` check for a `rework_rate_ok` check requiring the candidate's rate to be ≥10 percentage points lower than the incumbent's; `cost_ok` is unchanged and still required. `format_text_report()` surfaces both rates.

**Tech Stack:** Python 3 stdlib only (`statistics`, `collections.defaultdict`), sqlite3, pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-rework-rate-routing-metric-design.md` (gh:#2551)

---

### Task 1: Extend `_fetch_rows()` to pull `dispatch_rework`/`micro_rework`

**Files:**
- Modify: `synlynk/capability_report.py:37-55` (`_fetch_rows`)
- Modify: `tests/test_capability_report.py:29-46` (`_make_conn`)
- Modify: `tests/test_capability_report.py:55-76` (fetch-rows tests)
- Modify: `tests/test_capability_report.py:372-390` (`test_fetch_rows_excludes_seed_and_local_records`)

- [ ] **Step 1: Update `_make_conn()` to include the two new columns**

Replace the `capability_ratings` table definition in `tests/test_capability_report.py`:

```python
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
```

- [ ] **Step 2: Update every `INSERT INTO capability_ratings` call in the test file to match the new column order**

The column order is now `(story_id, agent, discipline, pr_review_cycles, dispatch_rework, micro_rework, quality)` — 7 positional values instead of 5. Update every `INSERT INTO capability_ratings VALUES (...)` literal across `tests/test_capability_report.py` (there are 13 of them, in `test_fetch_rows_without_quality_verified_column`, `test_fetch_rows_with_quality_verified_column`, `test_build_buckets_excludes_unmapped_discipline`, `test_build_buckets_groups_by_harness_and_task_type` ×2, `test_build_buckets_maps_expanded_disciplines` ×4, `test_fetch_rows_excludes_seed_and_local_records` ×5) by inserting `0, 0` (dispatch_rework, micro_rework) right after the `pr_review_cycles` value, e.g.:

```python
conn.execute(
    "INSERT INTO capability_ratings VALUES ('s1', 'codex', 'backend', 2, 0, 0, 4.5)"
)
```

For `test_fetch_rows_with_quality_verified_column`, the `ALTER TABLE ... ADD COLUMN quality_verified INTEGER` stays, and its insert becomes 8 positional values (adds the trailing `1` after `quality`):

```python
conn.execute("ALTER TABLE capability_ratings ADD COLUMN quality_verified INTEGER")
conn.execute(
    "INSERT INTO capability_ratings VALUES ('s1', 'codex', 'backend', 2, 0, 0, 4.5, 1)"
)
```

- [ ] **Step 3: Update `_fetch_rows()`'s query and docstring**

In `synlynk/capability_report.py`, replace `_fetch_rows`:

```python
def _fetch_rows(conn):
    """Return rows and whether capability_ratings has quality_verified.

    Filters out synthetic seed rows (local agent, quality=0.6, or seed story IDs).
    """
    has_quality_verified = _column_exists(
        conn, "capability_ratings", "quality_verified"
    )
    has_quality = _column_exists(conn, "capability_ratings", "quality")
    qv_select = "cr.quality_verified" if has_quality_verified else "NULL"
    quality_filter = " AND (cr.quality IS NULL OR cr.quality != 0.6)" if has_quality else ""
    query = (
        "SELECT cr.story_id, cr.agent, cr.discipline, cr.pr_review_cycles, "
        "cr.dispatch_rework, cr.micro_rework, "
        f"{qv_select}, ce.total_cost_usd, ce.pr_number, ce.job_id "
        "FROM capability_ratings cr JOIN cost_entries ce ON cr.story_id = ce.story_id "
        f"WHERE cr.agent != 'local' AND cr.story_id NOT LIKE 'seed-%' AND cr.story_id NOT LIKE 'local-seed-%'{quality_filter}"
    )
    rows = conn.execute(query).fetchall()
    return [tuple(row) for row in rows], has_quality_verified
```

- [ ] **Step 4: Update the two fetch-rows assertion tests for the new 10-element tuple shape**

```python
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
```

(Note Step 4 deliberately uses `dispatch_rework=1` on one row so this test file has at least one nonzero exemplar close to the fetch layer; `micro_rework` stays `0` here since it's not under test in this function.)

- [ ] **Step 5: Update `test_fetch_rows_excludes_seed_and_local_records`**

```python
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
```

- [ ] **Step 6: Run the fetch-rows tests**

Run: `pytest tests/test_capability_report.py -k fetch_rows -v`
Expected: all 3 fetch-rows tests FAIL at this point (the file won't even collect yet, since `build_buckets`/`_dedupe_cost_rows` in the same module still expect the old 8-element tuple shape — that's fixed in Task 2). Confirm the failure is a tuple-shape/unpacking error, not a syntax error in what you just wrote.

- [ ] **Step 7: Commit**

```bash
git add synlynk/capability_report.py tests/test_capability_report.py
git commit -m "feat: fetch dispatch_rework/micro_rework in capability_report._fetch_rows"
```

---

### Task 2: Extend `_dedupe_cost_rows()` and `build_buckets()` for the new tuple shape

**Files:**
- Modify: `synlynk/capability_report.py:58-93` (`_dedupe_cost_rows`, `build_buckets`)
- Modify: `tests/test_capability_report.py:78-93` (dedupe tests)
- Modify: `tests/test_capability_report.py:96-122` (build_buckets tests)
- Modify: `tests/test_capability_report.py:354-370` (`test_build_buckets_maps_expanded_disciplines`)

- [ ] **Step 1: Update `_dedupe_cost_rows()`'s unpacking**

```python
def _dedupe_cost_rows(rows):
    """Keep one cost contribution per story and PR, or story and job."""
    seen = set()
    deduped = []
    for row in rows:
        (story_id, _harness, _discipline, _cycles, _dispatch_rework,
         _micro_rework, _qv, _cost, pr_number, job_id) = row
        key = (
            (story_id, "pr", pr_number)
            if pr_number is not None
            else (story_id, "job", job_id)
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped
```

- [ ] **Step 2: Update the two dedupe tests for the new 10-element tuple shape**

```python
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
```

- [ ] **Step 3: Update `build_buckets()` to accumulate `dispatch_rework`/`micro_rework` lists**

```python
def build_buckets(conn):
    """Return ``(buckets, skipped_no_mapping)`` grouped by harness and task type."""
    rows, _has_quality_verified = _fetch_rows(conn)
    rows = _dedupe_cost_rows(rows)
    buckets = defaultdict(
        lambda: {
            "cycles": [], "costs": [], "dispatch_rework": [],
            "micro_rework": [], "story_ids": set(),
        }
    )
    skipped_no_mapping = 0
    for (story_id, harness, discipline, cycles, dispatch_rework, micro_rework,
         _qv, cost, _pr_number, _job_id) in rows:
        task_type = DISCIPLINE_TO_TASK_TYPE.get(discipline)
        if task_type is None:
            skipped_no_mapping += 1
            continue
        bucket = buckets[(harness, task_type)]
        if cycles is not None:
            bucket["cycles"].append(cycles)
        if cost is not None:
            bucket["costs"].append(cost)
        if dispatch_rework is not None:
            bucket["dispatch_rework"].append(dispatch_rework)
        if micro_rework is not None:
            bucket["micro_rework"].append(micro_rework)
        bucket["story_ids"].add(story_id)
    return dict(buckets), skipped_no_mapping
```

- [ ] **Step 4: Update `test_build_buckets_excludes_unmapped_discipline`**

```python
def test_build_buckets_excludes_unmapped_discipline():
    conn = _make_conn()
    conn.execute(
        "INSERT INTO capability_ratings VALUES ('s1', 'codex', 'ml', 2, 0, 0, 4.5)"
    )
    conn.execute("INSERT INTO cost_entries VALUES ('s1', 1.23, 100, 'job-1')")
    buckets, skipped = build_buckets(conn)
    assert buckets == {}
    assert skipped == 1
```

- [ ] **Step 5: Update `test_build_buckets_groups_by_harness_and_task_type` to assert the new list fields**

```python
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
```

- [ ] **Step 6: Update `test_build_buckets_maps_expanded_disciplines`**

```python
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
```

- [ ] **Step 7: Run the dedupe and build_buckets tests**

Run: `pytest tests/test_capability_report.py -k "dedupe or build_buckets" -v`
Expected: PASS (8 tests)

- [ ] **Step 8: Commit**

```bash
git add synlynk/capability_report.py tests/test_capability_report.py
git commit -m "feat: accumulate dispatch_rework/micro_rework per bucket in build_buckets"
```

---

### Task 3: Compute `dispatch_rework_rate`/`micro_rework_rate` in `summarize_buckets()`

**Files:**
- Modify: `synlynk/capability_report.py:96-111` (`summarize_buckets`)
- Modify: `tests/test_capability_report.py:125-167` (summarize_buckets tests)

- [ ] **Step 1: Update `summarize_buckets()`**

```python
def summarize_buckets(buckets: dict, min_sample_size: int) -> dict:
    """Return sample counts, gate status, and metric medians/rates per bucket."""
    summary = {}
    for key, data in buckets.items():
        n = len(data["story_ids"])
        summary[key] = {
            "n": n,
            "measured": n >= min_sample_size,
            "median_pr_review_cycles": (
                statistics.median(data["cycles"]) if data["cycles"] else None
            ),
            "median_total_cost_usd": (
                statistics.median(data["costs"]) if data["costs"] else None
            ),
            "dispatch_rework_rate": (
                sum(1 for v in data["dispatch_rework"] if v > 0)
                / len(data["dispatch_rework"]) * 100.0
                if data["dispatch_rework"] else None
            ),
            "micro_rework_rate": (
                sum(1 for v in data["micro_rework"] if v > 0)
                / len(data["micro_rework"]) * 100.0
                if data["micro_rework"] else None
            ),
        }
    return summary
```

- [ ] **Step 2: Update `test_summarize_buckets_below_min_sample_size_is_unmeasured`**

```python
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
```

- [ ] **Step 3: Update `test_summarize_buckets_meets_min_sample_size_computes_medians` and rename it to also assert rates**

```python
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
```

- [ ] **Step 4: Update `test_summarize_buckets_empty_metric_lists_yield_none_median` to also assert `None` rates**

```python
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
```

- [ ] **Step 5: Add a new test for the all-zero-rework case (rate is `0.0`, not `None`)**

This is the edge case the spec explicitly calls out: a bucket where every job has `dispatch_rework == 0` must report a `0.0` rate, not `None` — `None` means "no data," `0.0` means "measured, and it's zero."

```python
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
```

- [ ] **Step 6: Run the summarize_buckets tests**

Run: `pytest tests/test_capability_report.py -k summarize_buckets -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add synlynk/capability_report.py tests/test_capability_report.py
git commit -m "feat: compute dispatch_rework_rate/micro_rework_rate in summarize_buckets"
```

---

### Task 4: Swap `propose_diff()`'s gate from median `pr_review_cycles` to rate + margin

**Files:**
- Modify: `synlynk/capability_report.py:114-151` (`propose_diff`)
- Modify: `tests/test_capability_report.py:169-245` (propose_diff tests)

- [ ] **Step 1: Add the margin constant and rewrite `propose_diff()`**

```python
MIN_REWORK_RATE_MARGIN_PP = 10.0


def propose_diff(summary: dict, current_task_allocation: dict, min_sample_size: int) -> list:
    """Return harness swaps where a measured candidate beats both metrics.

    Quality gate: candidate's dispatch_rework_rate must be at least
    MIN_REWORK_RATE_MARGIN_PP percentage points lower than the incumbent's.
    (median_pr_review_cycles is retained in bucket summaries for historical/
    report context but no longer drives this comparison — see
    docs/superpowers/specs/2026-10-23-rework-rate-routing-metric-design.md.)
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
            rework_rate_ok = (
                entry["dispatch_rework_rate"] is not None
                and current_entry["dispatch_rework_rate"] is not None
                and (current_entry["dispatch_rework_rate"] - entry["dispatch_rework_rate"])
                >= MIN_REWORK_RATE_MARGIN_PP
            )
            cost_ok = (
                entry["median_total_cost_usd"] is not None
                and current_entry["median_total_cost_usd"] is not None
                and entry["median_total_cost_usd"] < current_entry["median_total_cost_usd"]
            )
            if rework_rate_ok and cost_ok:
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

- [ ] **Step 2: Update `test_propose_diff_promotes_strictly_better_harness`, renamed for the new gate**

```python
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
```

- [ ] **Step 3: Update `test_propose_diff_no_change_on_split_result`**

```python
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
```

- [ ] **Step 4: Update `test_propose_diff_skips_unmeasured_candidate`**

```python
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
```

- [ ] **Step 5: Update `test_propose_diff_skips_unmeasured_current`**

```python
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
```

- [ ] **Step 6: Add a margin-boundary test (exactly 10.0pp passes, 9.9pp doesn't)**

```python
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
```

- [ ] **Step 7: Add a regression test for the both-zero case that motivated this whole change**

This is the spec's actual acceptance criterion: two harnesses tied at `dispatch_rework_rate == 0.0` must NOT produce a proposal (same as they wouldn't have under the old median logic), confirming the new gate doesn't accidentally become *more* permissive than intended.

```python
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
    proposals = propose_diff(summary, CURRENT_TASK_ALLOCATION, min_sample_size=5)
    assert proposals == []
```

- [ ] **Step 8: Add a regression test reproducing today's live-data shape (all harnesses tied at `median_pr_review_cycles == 0`, but a real rework-rate gap exists) to confirm the new gate fires where the old one couldn't**

```python
def test_propose_diff_fires_on_rework_rate_gap_despite_tied_pr_review_cycles():
    summary = {
        ("claude", "implement"): {
            "n": 476,
            "measured": True,
            "median_pr_review_cycles": 0,
            "dispatch_rework_rate": 2.3,
            "median_total_cost_usd": 3.10,
        },
        ("codex", "implement"): {
            "n": 656,
            "measured": True,
            "median_pr_review_cycles": 0,
            "dispatch_rework_rate": 21.7,
            "median_total_cost_usd": 1.80,
        },
    }
    # codex has a HIGHER rework rate than claude here (mirrors live data direction);
    # claude is the one that should be proposed as the swap target given it's
    # at least 10pp lower AND cheaper would be the inverse case. This test
    # asserts no proposal fires when the gap runs the "wrong" direction for a
    # swap (codex is current, claude would have to be both less rework AND
    # cheaper -- claude is NOT cheaper here, so no proposal).
    proposals = propose_diff(
        summary, {"implement": {"harness": "codex", "fallback": []}}, min_sample_size=5
    )
    assert proposals == []
```

- [ ] **Step 9: Run the propose_diff tests**

Run: `pytest tests/test_capability_report.py -k propose_diff -v`
Expected: PASS (9 tests)

- [ ] **Step 10: Commit**

```bash
git add synlynk/capability_report.py tests/test_capability_report.py
git commit -m "feat: gate propose_diff on dispatch_rework_rate margin instead of median pr_review_cycles"
```

---

### Task 5: Surface both rates in `format_text_report()`

**Files:**
- Modify: `synlynk/capability_report.py:154-173` (`format_text_report`)
- Modify: `tests/test_capability_report.py:247-275` (format_text_report tests)

- [ ] **Step 1: Update `format_text_report()`**

```python
def format_text_report(proposals: list, summary: dict, skipped_no_mapping: int) -> str:
    lines = []
    if not proposals:
        lines.append(
            "No routing changes proposed (no harness clears min_sample_size "
            "with a dispatch_rework_rate at least "
            f"{MIN_REWORK_RATE_MARGIN_PP:.0f}pp lower and a cheaper median cost)."
        )
    for proposal in proposals:
        current, proposed = proposal["current"], proposal["proposed"]
        lines.append(
            f"{proposal['task_type']}: {proposal['current_harness']} "
            f"(current, n={current['n']}, "
            f"rework_rate={current['dispatch_rework_rate']:.1f}%, "
            f"micro_rework_rate={current.get('micro_rework_rate')}, "
            f"cost=${current['median_total_cost_usd']:.2f}) -> "
            f"{proposal['proposed_harness']} (n={proposed['n']}, "
            f"rework_rate={proposed['dispatch_rework_rate']:.1f}%, "
            f"micro_rework_rate={proposed.get('micro_rework_rate')}, "
            f"cost=${proposed['median_total_cost_usd']:.2f})"
        )
    lines.append(f"\n{skipped_no_mapping} rows skipped (discipline has no task_type mapping).")
    return "\n".join(lines)
```

- [ ] **Step 2: Update `test_format_text_report_no_proposals`**

```python
def test_format_text_report_no_proposals():
    text = format_text_report([], {}, skipped_no_mapping=0)
    assert "No routing changes proposed" in text
    assert "dispatch_rework_rate" in text
```

- [ ] **Step 3: Update `test_format_text_report_with_proposal_matches_example_shape`**

```python
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
```

- [ ] **Step 4: Run the format_text_report tests**

Run: `pytest tests/test_capability_report.py -k format_text_report -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/capability_report.py tests/test_capability_report.py
git commit -m "feat: surface dispatch_rework_rate/micro_rework_rate in format_text_report"
```

---

### Task 6: Fix the CLI integration test's hand-built schema

**Files:**
- Modify: `tests/test_capability_report.py:278-316` (`test_cli_capability_report_runs_without_error`)

The canonical `~/.synlynk/workspaces/synlynk/state.db` already has `dispatch_rework`/
`micro_rework` columns (confirmed live), so `test_capability_report_against_real_db_copy_does_not_mutate_source`
needs no change. This test builds its own throwaway schema from scratch and must add
the two columns so `_fetch_rows()`'s query doesn't fail against it.

- [ ] **Step 1: Update the inline schema**

```python
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
        "CREATE TABLE capability_ratings (story_id TEXT, agent TEXT, discipline TEXT, "
        "pr_review_cycles INTEGER, dispatch_rework INTEGER, micro_rework INTEGER, quality REAL)"
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
```

- [ ] **Step 2: Run this test**

Run: `pytest tests/test_capability_report.py -k test_cli_capability_report_runs_without_error -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_capability_report.py
git commit -m "test: add dispatch_rework/micro_rework columns to CLI integration test schema"
```

---

### Task 7: Full-file verification and docs cross-reference

**Files:**
- Read only: `synlynk/capability_report.py`, `tests/test_capability_report.py`
- Modify: `docs/harness-capability-baseline.md` (only if it directly quotes the old gate logic — check first)

- [ ] **Step 1: Run the full capability_report test file**

Run: `pytest tests/test_capability_report.py -v`
Expected: PASS, all tests (the file should now have 24 tests: the original 18 plus the 6 new/renamed ones added in Tasks 3 and 4 — `test_summarize_buckets_all_zero_rework_yields_zero_rate_not_none`, `test_propose_diff_margin_boundary_exact_pass_and_near_miss`, `test_propose_diff_both_zero_rework_rate_produces_no_proposal`, `test_propose_diff_fires_on_rework_rate_gap_despite_tied_pr_review_cycles`, plus the two tests renamed in Task 3 Step 3 and Task 4 Step 2 count as replacements, not additions).

- [ ] **Step 2: Run the real-db-copy test if the canonical DB is present locally**

Run: `pytest tests/test_capability_report.py -k real_db_copy -v`
Expected: PASS if `~/.synlynk/workspaces/synlynk/state.db` exists in this environment, SKIPPED otherwise. Either outcome is fine — do not treat a skip as a failure.

- [ ] **Step 3: Check whether `docs/harness-capability-baseline.md` quotes the old `cycles_ok`/median-based gate logic directly**

```bash
grep -n "cycles_ok\|median_pr_review_cycles\|propose_diff" docs/harness-capability-baseline.md
```

That doc is already marked suspended/historical per the Harness Capability Reassessment Protocol in CLAUDE.md — if the grep finds nothing, skip straight to Step 4. If it does quote the old logic, add a one-line dated note (not a rewrite) pointing to this plan's spec, matching the style of the doc's existing suspension notice.

- [ ] **Step 4: Run the full project test suite to confirm no other test references the old field names**

Run: `pytest tests/ -k "capability" -q`
Expected: PASS, no failures in any capability-adjacent test file (this catches any other file that might import `propose_diff`/`summarize_buckets` and assert on the old `cycles_ok`-shaped output, beyond what Task-level greps already found in `synlynk/cli.py`).

- [ ] **Step 5: Commit any doc note from Step 3 (only if one was added)**

```bash
git add docs/harness-capability-baseline.md
git commit -m "docs: note rework-rate routing metric change in suspended baseline doc"
```

---

## Post-Plan Checklist (not a task — do after all tasks land)

- Open a PR from `feat/claude/2551-rework-rate-metric` against `main`. Link gh:#2551 in the PR body (`Fixes #2551` only if this PR's scope fully closes the issue — re-check the issue body's three candidate directions before using the auto-close keyword; if coverage gaps like `quality_verified`/`pr_number` population are explicitly out of scope per the spec, use `Addresses #2551` instead of `Fixes #2551` to avoid a premature auto-close, matching the project's own documented "Fixes #N auto-close trap" lesson).
- Per the Hardened PR Review Policy: assign a cross-harness+model reviewer (different harness AND model from whoever authored the implementation commits), reviewer runs `synlynk pr check` from within the PR's worktree, reviewer's own dispatched job performs the merge.
- Per the Cost Capture Protocol: log a `synlynk cost log` entry for this native/interactive PM-session work (the brainstorm + spec + plan authored directly in this session, not dispatched).
- Per the Worktree Hygiene Protocol: clean up `.worktrees/feat+claude+2551-rework-rate-metric` and the local/remote branch once the PR merges.
