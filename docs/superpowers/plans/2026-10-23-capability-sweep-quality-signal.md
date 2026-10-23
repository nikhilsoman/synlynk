# Capability Sweep Quality Signal — Implementation Plan

**Spec:** [2026-10-10-capability-sweep-quality-signal-design.md](../specs/2026-10-10-capability-sweep-quality-signal-design.md)
**Issue:** gh:#2170  
**Story:** story-issue-2170  
**Status:** ready for build  

## Current State on `origin/main` (59ba52eb)

A read of origin/main confirms that spec sections 1, 2, and 4 are **already shipped**:

| Spec section | Status | Evidence |
|:---|:---|:---|
| §1 — `quality_verified` in verdict dict | ✅ Shipped | `capability_sweep.py:439-456` |
| §1 — stderr warning with raw-output dump | ✅ Shipped | `capability_sweep.py:441-450` |
| §2 — `capability_calibration_results.quality_verified` column + idempotent migration | ✅ Shipped | `db.py:1693-1697`, writes at `:226-238` |
| §2 — `capability_ratings.quality_verified` column + idempotent migration | ✅ Shipped | `db.py:2340-2342` (`_add_column_if_missing`), writes at `:508-523` |
| §2 — `_run_sweep` threads `quality_verified` through `capability_ratings` INSERT | ✅ Shipped | `capability_sweep.py:508-523` |
| §4 — No changes to verifier prompt or parser | ✅ N/A (scoped out) | — |

What remains **un-shipped** (the "remaining gap") is:

| Spec section | Status | Gap |
|:---|:---|:---|
| §3 — Downstream consumers skip unverified rows by default | ❌ Not done | `capability_scores` VIEW (`db_schema.py:592-614`) does not filter `quality_verified=0`. `_fetch_rows` in `capability_report.py` reads but does not filter `quality_verified`. The Empirical Capability Assessment Policy's sample-size gate (`≥5 merged jobs`) does not exclude unverified rows. |
| §2 — `_seed_capability_ledger_from_baseline` does not write `quality_verified` | ⚠️ Partial | The INSERT at `:557-575` omits `quality_verified`; SQLite defaults to `NULL` (not 0 or 1). Downstream consumers treating `NULL` as "unverified" is correct but should be explicit. |

## Tasks

### Task 0 — Baseline: run existing tests (gate)

**Files:** none  
**Action:** `pytest -q tests/test_capability_sweep.py tests/test_db.py` on origin/main — confirm green before any edits.  
**Exit criterion:** all pass, zero failures.

---

### Task 1 — `capability_scores` VIEW filters out unverified rows

The `capability_scores` view in `db_schema.py` is the routing-decision source. It currently aggregates **all** `capability_ratings` rows regardless of `quality_verified`. Rows where the verifier's output was unparseable (fallback 5.0, `quality_verified=0/NULL`) must be excluded from the weighted average that drives harness/model routing.

**File:** `synlynk/db_schema.py`

**Change:** Add a `WHERE` clause to the `capability_scores` view:

```sql
WHERE split_model = 0
  AND (quality_verified IS NULL OR quality_verified != 0)
```

The `IS NULL` allowance is deliberate: historical rows written before the `quality_verified` column existed have `NULL`, and those are pre-existing organic data that was verified (the column simply didn't exist yet). Only rows explicitly stamped `0` (= fallback fired, parsing failed) are excluded.

> [!IMPORTANT]
> The view is `CREATE VIEW IF NOT EXISTS`, so a schema migration that drops-and-recreates the view is needed. Check the existing pattern in `db.py` — `_DB_SCORES_VIEW` is run via `conn.executescript()` at migration time. Add `DROP VIEW IF EXISTS capability_scores` before the `CREATE VIEW` in `_DB_SCORES_VIEW` to ensure the updated definition takes effect on existing databases.

**Migration file:** `synlynk/db.py` — add the `DROP VIEW` + re-execute `_DB_SCORES_VIEW` in the migration block (follow the existing idempotent pattern).

**Tests to add/modify:**

| Test | File | What it asserts |
|:---|:---|:---|
| `test_capability_scores_view_excludes_quality_verified_zero` | `tests/test_capability_sweep.py` | Insert two `capability_ratings` rows — one with `quality_verified=1`, one with `quality_verified=0`. Query `capability_scores` view. Assert only the `quality_verified=1` row is counted. |
| `test_capability_scores_view_includes_null_quality_verified` | `tests/test_capability_sweep.py` | Insert a row with `quality_verified=NULL` (pre-migration organic data). Assert it is included in the view. |

---

### Task 2 — `capability_report` `_fetch_rows` filters unverified rows from report metrics

The report generator (`capability_report.py`) already reads `quality_verified` but does not filter on it. The spec (§3) requires unverified rows to be "no signal" — not averaged into reported quality.

**File:** `synlynk/capability_report.py`

**Change:** When `has_quality_verified` is `True`, add a filter to the query:

```python
qv_filter = " AND (cr.quality_verified IS NULL OR cr.quality_verified != 0)" if has_quality_verified else ""
```

Append `qv_filter` to the existing `WHERE` clause in `_fetch_rows`.

**Tests to add/modify:**

| Test | File | What it asserts |
|:---|:---|:---|
| `test_report_fetch_rows_excludes_unverified` | `tests/test_capability_report.py` | Seed DB with verified + unverified rows. Call `_fetch_rows`. Assert unverified rows are absent from returned list. |
| `test_report_fetch_rows_includes_null_verified` | `tests/test_capability_report.py` | Seed DB with `quality_verified=NULL` row. Assert it is included. |

---

### Task 3 — `_seed_capability_ledger_from_baseline` writes `quality_verified=NULL` explicitly (documentation, no behavior change)

**File:** `synlynk/capability_sweep.py`

**Change:** No code change required — SQLite already defaults the omitted column to `NULL`, and the `NULL` semantics in Task 1/2 treat that as "include." However, add a code comment at line ~557 (the `INSERT INTO capability_ratings` in `_seed_capability_ledger_from_baseline`) documenting that `quality_verified` is intentionally omitted (defaults to NULL, meaning "pre-migration baseline data, included in routing"):

```python
# quality_verified intentionally omitted — defaults to NULL,
# which downstream views treat as "verified" (pre-migration data).
```

**Tests:** No new test needed — existing `test_seed_from_baseline_only_when_ledger_empty` already validates this path.

---

### Task 4 — `capability_pack` skips unverified rows in pack generation

**File:** `synlynk/capability_pack.py`

**Change:** The query at line ~80 already reads `quality_verified` but uses `MAX(COALESCE(cr.quality_verified, 0))`. Verify whether this correctly excludes unverified rows from the pack. If the current SQL aggregates unverified rows into the quality figure, add a `WHERE quality_verified IS NULL OR quality_verified != 0` filter to the subquery.

**Tests to add/modify:**

| Test | File | What it asserts |
|:---|:---|:---|
| `test_capability_pack_excludes_unverified_quality` | `tests/test_capability_pack.py` | Seed DB with verified + unverified rows. Generate pack. Assert only verified quality is reflected. |

---

### Task 5 — Add `#2170` dependency comment to `#1993` code path

**File:** `synlynk/capability_report.py`

**Change:** Add a comment near the top of `_fetch_rows` or the module docstring:

```python
# Depends on quality_verified column (gh:#2170).
# Rows with quality_verified=0 are excluded from all quality metrics;
# see docs/superpowers/specs/2026-10-10-capability-sweep-quality-signal-design.md §3.
```

---

## Telemetry & Provenance Behavior

- **No new telemetry is introduced.** The `quality_verified` field is a provenance marker on existing data paths.
- The stderr warning (`[sweep] WARNING: verifier … had no parseable …`) is already shipped. It produces a diagnostic dump of the first 2000 chars of raw verifier output, enabling root-cause diagnosis on the next live sweep run (the "evidence" that Approach C depends on).
- `quality_verified` flows into `capability_calibration_results` (per-task provenance) and `capability_ratings` (per-story aggregate), both readable via `synlynk capability report` and `synlynk capability pack`.

## Failure Handling

| Failure mode | Current behavior (origin/main) | After this plan |
|:---|:---|:---|
| Verifier output unparseable | `quality=5.0`, `quality_verified=False`, warning to stderr with raw output dump | Same — **plus** the 5.0 row is excluded from the `capability_scores` view, report metrics, and pack generation. The fallback no longer pollutes routing. |
| `extract_verifier_meta` raises | Returns `None` → treated as unparseable (same path as above) | Same |
| Migration column already exists (concurrent startup) | `_add_column_if_missing` catches `duplicate column name` `OperationalError` and suppresses it | Same — no change to migration code |
| VIEW already exists with old definition | ❌ `CREATE VIEW IF NOT EXISTS` is a no-op | ✅ `DROP VIEW IF EXISTS` + `CREATE VIEW` ensures updated definition |

## Migration & Backfill Boundaries

- **Migration:** Tasks 1–2 modify a VIEW and a query, not a table schema. The only schema migration already shipped is `ALTER TABLE … ADD COLUMN quality_verified` (idempotent). The VIEW drop/recreate in Task 1 is the only new migration action.
- **Backfill:** Explicitly out of scope (per spec §"Out of scope"). Historical rows with `quality_verified=NULL` are treated as verified (pre-migration organic data). Historical rows with `quality_verified=0` (written by sweeps after the §1/§2 fix shipped) are correctly excluded. A future backfill pass may re-verify historical rows, but that is tracked separately on gh:#2170.
- **No data deletion.** Unverified rows remain in the tables; they are filtered at query time, not purged.

## Verification Gates

| Gate | Command | Pass criterion |
|:---|:---|:---|
| Pre-edit baseline | `pytest -q tests/test_capability_sweep.py tests/test_db.py` | All pass |
| Post–Task 1 | `pytest -q tests/test_capability_sweep.py tests/test_db.py` | All pass including new view-filter tests |
| Post–Task 2 | `pytest -q tests/test_capability_sweep.py tests/test_capability_report.py` | All pass including new report-filter tests |
| Post–Task 4 | `pytest -q tests/test_capability_pack.py` | All pass including new pack-filter test |
| Full suite | `pytest -q` | No regressions |

## Files Modified (summary)

| File | Action | Task |
|:---|:---|:---|
| `synlynk/db_schema.py` | Edit `_DB_SCORES_VIEW` — add `quality_verified` filter | T1 |
| `synlynk/db.py` | Add `DROP VIEW IF EXISTS capability_scores` before view recreation | T1 |
| `synlynk/capability_report.py` | Add `quality_verified` filter to `_fetch_rows` query + dependency comment | T2, T5 |
| `synlynk/capability_pack.py` | Verify/fix `quality_verified` filter in pack query | T4 |
| `synlynk/capability_sweep.py` | Add documentation comment in `_seed_capability_ledger_from_baseline` | T3 |
| `tests/test_capability_sweep.py` | Add 2 view-filter tests | T1 |
| `tests/test_capability_report.py` | Add 2 report-filter tests | T2 |
| `tests/test_capability_pack.py` | Add 1 pack-filter test | T4 |

## Ordering & Dependencies

```
T0 (baseline gate)
 └─► T1 (view filter) ── independent
 └─► T2 (report filter) ── independent, can parallel T1
 └─► T3 (comment only) ── independent
 └─► T4 (pack filter) ── independent
 └─► T5 (comment only) ── part of T2 file edit
```

Tasks 1–5 are mutually independent and can be dispatched in parallel.

## Out of Scope (per spec, restated for implementer)

- Fixing *why* the verifier's output doesn't parse (Approach B — deferred until A's evidence is available from a real sweep run).
- Backfilling/auditing historical rows.
- `synlynk capability report` implementation (gh:#1993) — only the filter contract is established here.
- Altering roadmap or release dates.
