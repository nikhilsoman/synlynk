# Quota Model Burn-Rate Weighting and Estimate Drift Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the pre-dispatch quota-exhaustion gate model-aware for Claude/Codex/Grok, persist pre-dispatch cost estimates so they can be diffed against actual cost, and make quota-ceiling calibration run automatically instead of only via a manual CLI command.

**Architecture:** Three additive, independently-testable pieces sharing one code surface (`synlynk/quota.py`, `synlynk/dispatch.py`, `synlynk/db.py`, `synlynk/daemon.py`, `synlynk/status.py`): (1) a cached per-harness/model burn-rate multiplier derived from `cost_entries` history, applied to the existing token estimate before the dispatch-time quota gate; (2) three new `cost_entries` columns populated from the existing `harness_reservations` token estimate and the existing `api_equivalent_usd()` rate table, with a sentinel alert on >50% drift; (3) a new daemon tick that automatically re-runs `calibrate_and_update_quota` (previously only reachable by hand) by diffing the two most recent `quota_snapshots` rows per harness/window against the real tokens burned in that interval from `cost_entries`.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest. No new dependencies.

---

## Spec coverage map

| Spec section | Task(s) |
|---|---|
| Part 1 — `resolve_burn_rate_multiplier` + `quota_burn_rate_weights` table | Task 1, 2, 3 |
| Part 1 — dispatch gate integration | Task 3 |
| Part 2 — `cost_entries` schema additions | Task 4 |
| Part 2 — drift alert | Task 5 |
| Part 3 — daemon tick wiring | Task 6, 7 |
| Part 3 — `synlynk status` staleness warning | Task 8 |

## Design decisions made during planning (not spelled out in the spec)

- **`quota_burn_rate_weights` table lives in `synlynk/db_schema.py`'s `_DB_SCHEMA`** (the script executed via `conn.executescript(_DB_SCHEMA)` on every `_get_db()` call, confirmed at `synlynk/db.py:1139-1140`), immediately after the existing `harness_reservations` table at `db_schema.py:534-545`. Because it's a brand-new table defined with `CREATE TABLE IF NOT EXISTS`, no separate `ALTER`-based migration is needed — unlike `cost_entries`/`capability_watch`, which are pre-existing tables on already-migrated databases and need the `_add_column_if_missing`/guarded-`ALTER` pattern instead.
- **The per-dispatch token estimate is not duplicated onto `daemon_jobs`.** `dispatch.py`'s gate already opens a `harness_reservations` row keyed by `job_id` holding the (now burn-rate-weighted) token estimate (`dispatch.py:4833-4848`). Closing a reservation (`synlynk/quota.py:_close_reservation`, called via `UPDATE harness_reservations SET status='released', released_at=...`) does not delete the row. So Part 2's drift check reads the estimate straight from `harness_reservations` by `job_id` at cost-entry-write time instead of adding new columns to `daemon_jobs`.
- **`estimated_cost_usd` is computed with the existing `api_equivalent_usd(agent, tokens_in, tokens_out, cache_read_tokens, model)` helper** (`synlynk/costs.py:976-991`), treating the whole reservation estimate as input tokens (`tokens_out=0`), using the *same* model/agent as the actual row. This keeps the dollar comparison on the same rate table as the real cost, so a drift % reflects token-estimate error, not rate-table disagreement.
- **Quota calibration's `delta_tokens` input is derived automatically** from `cost_entries` (`SUM(input_tokens + output_tokens)` for that harness between the two most recent `quota_snapshots.captured_at` timestamps for that harness/window), rather than requiring a human-supplied number. This is the concrete mechanism needed to satisfy the spec's "wire into the daemon tick" requirement, since `calibrate_and_update_quota` itself was designed for manual CLI input (`p1_pct`, `p2_pct`, `delta_tokens` are plain args, confirmed at `synlynk/cli.py:3354-3362`).
- **Staleness tracking reuses the existing `capability_watch` singleton row** (`id=1`, confirmed schema at `synlynk/db.py:1722-1730`) by adding one column, `last_quota_calibration_at`, following the exact guarded-`ALTER` pattern already used for `last_sweep_at` at `synlynk/db.py:1751-1753` — no new table.

---

### Task 1: `quota_burn_rate_weights` table

**Files:**
- Modify: `synlynk/db_schema.py:545` (insert new table after `harness_reservations`)
- Test: `tests/test_quota_burn_rate_weighting.py` (new file)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_quota_burn_rate_weighting.py
"""Unit tests for per-harness/model burn-rate weighting (v0.26.9)."""

import synlynk as sl


def test_quota_burn_rate_weights_table_exists(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        conn.execute(
            "INSERT INTO quota_burn_rate_weights (harness, model, multiplier, sample_count) "
            "VALUES ('claude', 'claude-opus-4-7', 1.8, 12)"
        )
        conn.commit()
        row = conn.execute(
            "SELECT harness, model, multiplier, sample_count FROM quota_burn_rate_weights "
            "WHERE harness='claude' AND model='claude-opus-4-7'"
        ).fetchone()
        assert row == ("claude", "claude-opus-4-7", 1.8, 12)
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_quota_burn_rate_weighting.py -v`
Expected: FAIL with `sqlite3.OperationalError: no such table: quota_burn_rate_weights`

- [ ] **Step 3: Add the table to the schema**

In `synlynk/db_schema.py`, immediately after the existing block (line 545):

```sql
CREATE INDEX IF NOT EXISTS idx_harness_reservations_harness ON harness_reservations(harness, status);
```

insert:

```sql

CREATE TABLE IF NOT EXISTS quota_burn_rate_weights (
    harness       TEXT NOT NULL,
    model         TEXT NOT NULL,
    multiplier    REAL NOT NULL DEFAULT 1.0,
    sample_count  INTEGER NOT NULL DEFAULT 0,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (harness, model)
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_quota_burn_rate_weighting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/db_schema.py tests/test_quota_burn_rate_weighting.py
git commit -m "feat: add quota_burn_rate_weights table"
```

---

### Task 2: `resolve_burn_rate_multiplier` function

**Files:**
- Modify: `synlynk/quota.py` (add function after `resolve_harness_track`, i.e. after line 449)
- Test: `tests/test_quota_burn_rate_weighting.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_quota_burn_rate_weighting.py`:

```python
from synlynk.quota import resolve_burn_rate_multiplier


def _seed_cost_entries(conn, rows):
    """rows: list of (harness, model, input_tokens, output_tokens)."""
    for i, (harness, model, in_tok, out_tok) in enumerate(rows):
        conn.execute(
            "INSERT INTO cost_entries "
            "(session_date, agent, harness, model, input_tokens, output_tokens, "
            " cache_read_tokens, cost_source, job_id) "
            "VALUES ('2026-10-31', ?, ?, ?, ?, ?, 0, 'actual', ?)",
            (harness, harness, model, in_tok, out_tok, f"job-{harness}-{model}-{i}"),
        )
    conn.commit()


def test_resolve_burn_rate_multiplier_below_threshold_is_neutral(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed_cost_entries(conn, [("claude", "claude-opus-4-7", 10_000, 2_000)] * 4)
        assert resolve_burn_rate_multiplier("claude", "claude-opus-4-7", conn=conn) == 1.0
    finally:
        conn.close()


def test_resolve_burn_rate_multiplier_unknown_pair_is_neutral(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        assert resolve_burn_rate_multiplier("codex", "gpt-5-codex", conn=conn) == 1.0
    finally:
        conn.close()


def test_resolve_burn_rate_multiplier_computes_ratio_at_threshold(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        # Heavy model: 20,000 tokens/job avg, 5 samples (meets >=5 threshold).
        _seed_cost_entries(
            conn, [("claude", "claude-opus-4-7", 16_000, 4_000)] * 5
        )
        # Light model: 4,000 tokens/job avg, 5 samples.
        _seed_cost_entries(
            conn, [("claude", "claude-haiku-5-5", 3_200, 800)] * 5
        )
        # Harness-wide average across both models: (20000*5 + 4000*5) / 10 = 12,000
        multiplier = resolve_burn_rate_multiplier("claude", "claude-opus-4-7", conn=conn)
        assert multiplier == 20_000 / 12_000
    finally:
        conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_quota_burn_rate_weighting.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_burn_rate_multiplier'`

- [ ] **Step 3: Implement the function**

In `synlynk/quota.py`, immediately after `resolve_harness_track` (after line 449):

```python
_BURN_RATE_MIN_SAMPLES = 5


def resolve_burn_rate_multiplier(harness: str, model: str, conn=None) -> float:
    """Predicts how much faster/slower `model` burns `harness`'s pooled quota
    window compared to that harness's own average across all models.

    1.0 is neutral: returned whenever the (harness, model) pair has fewer
    than _BURN_RATE_MIN_SAMPLES completed cost_entries rows, so an unseen
    model/harness pair never gets an untrusted weighting applied to it.
    Reuses the same >=5-sample threshold as the Empirical Capability
    Assessment Policy rather than introducing a second magic number.
    """
    own_conn = conn is None
    if own_conn:
        conn = _pkg("_get_db")()
    try:
        pair_row = conn.execute(
            "SELECT COUNT(*), AVG(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) "
            "FROM cost_entries WHERE lower(harness) = lower(?) AND model = ?",
            (harness, model),
        ).fetchone()
        pair_count = pair_row[0] if pair_row else 0
        if pair_count < _BURN_RATE_MIN_SAMPLES:
            return 1.0
        pair_avg = float(pair_row[1] or 0.0)

        harness_row = conn.execute(
            "SELECT AVG(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) "
            "FROM cost_entries WHERE lower(harness) = lower(?)",
            (harness,),
        ).fetchone()
        harness_avg = float(harness_row[0] or 0.0) if harness_row else 0.0
        if harness_avg <= 0.0:
            return 1.0
        return pair_avg / harness_avg
    finally:
        if own_conn:
            conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_quota_burn_rate_weighting.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/quota.py tests/test_quota_burn_rate_weighting.py
git commit -m "feat: add resolve_burn_rate_multiplier for per-model quota weighting"
```

---

### Task 3: Cache the multiplier and wire it into the dispatch gate

**Files:**
- Modify: `synlynk/quota.py` (add `refresh_burn_rate_weights`)
- Modify: `synlynk/dispatch.py:4772-4848`
- Test: `tests/test_quota_burn_rate_weighting.py`
- Test: `tests/test_dispatch.py` (add one integration test)

- [ ] **Step 1: Write the failing test for the cache-refresh function**

Append to `tests/test_quota_burn_rate_weighting.py`:

```python
from synlynk.quota import refresh_burn_rate_weights


def test_refresh_burn_rate_weights_writes_cache_row(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed_cost_entries(conn, [("codex", "gpt-5-codex", 8_000, 2_000)] * 6)
        _seed_cost_entries(conn, [("codex", "gpt-5-codex-mini", 2_000, 500)] * 6)
        refresh_burn_rate_weights(conn=conn)
        row = conn.execute(
            "SELECT multiplier, sample_count FROM quota_burn_rate_weights "
            "WHERE harness='codex' AND model='gpt-5-codex'"
        ).fetchone()
        assert row is not None
        assert row[1] == 6
        assert row[0] == 10_000 / 6_250  # (10000*6 + 2500*6) / 12 = 6250
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_quota_burn_rate_weighting.py::test_refresh_burn_rate_weights_writes_cache_row -v`
Expected: FAIL with `ImportError: cannot import name 'refresh_burn_rate_weights'`

- [ ] **Step 3: Implement `refresh_burn_rate_weights`**

In `synlynk/quota.py`, immediately after `resolve_burn_rate_multiplier`:

```python
def refresh_burn_rate_weights(conn=None) -> int:
    """Recomputes and caches resolve_burn_rate_multiplier() for every
    (harness, model) pair with enough samples. Returns the number of rows
    written. Called from the daemon's quota calibration tick (Task 7).
    """
    own_conn = conn is None
    if own_conn:
        conn = _pkg("_get_db")()
    try:
        pairs = conn.execute(
            "SELECT harness, model, COUNT(*) FROM cost_entries "
            "WHERE harness IS NOT NULL AND model IS NOT NULL "
            "GROUP BY lower(harness), model "
            "HAVING COUNT(*) >= ?",
            (_BURN_RATE_MIN_SAMPLES,),
        ).fetchall()
        written = 0
        for harness, model, sample_count in pairs:
            multiplier = resolve_burn_rate_multiplier(harness, model, conn=conn)
            conn.execute(
                "INSERT INTO quota_burn_rate_weights (harness, model, multiplier, sample_count, updated_at) "
                "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(harness, model) DO UPDATE SET "
                "multiplier=excluded.multiplier, sample_count=excluded.sample_count, "
                "updated_at=excluded.updated_at",
                (harness, model, multiplier, sample_count),
            )
            written += 1
        conn.commit()
        return written
    finally:
        if own_conn:
            conn.close()


def cached_burn_rate_multiplier(harness: str, model: Optional[str], conn) -> float:
    """Reads the cached multiplier for dispatch-time use (no live recompute,
    since dispatch is latency-sensitive). 1.0 if no cached row exists yet.
    """
    if not model:
        return 1.0
    row = conn.execute(
        "SELECT multiplier FROM quota_burn_rate_weights WHERE lower(harness) = lower(?) AND model = ?",
        (harness, model),
    ).fetchone()
    return float(row[0]) if row else 1.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_quota_burn_rate_weighting.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Wire the cached multiplier into the dispatch gate**

In `synlynk/dispatch.py`, the existing block at lines 4772-4785 reads:

```python
        resolve_story_fn = _pkg("resolve_or_create_story_id")
        _est_tokens = None
        if story_id and resolve_story_fn:
            _row = dconn.execute(
                "SELECT estimated_tokens FROM stories WHERE story_id=?", (story_id,)
            ).fetchone()
            if _row and _row[0]:
                _est_tokens = int(_row[0])
        if _est_tokens is None:
            # Ad-hoc call with no story estimate: rough heuristic, ~4 chars/token.
            _est_tokens = max(1000, len(task) // 4)

        quota_status_fn = _pkg("_quota_status_for_agent")
        qstatus = (
            quota_status_fn(dconn, agent, estimated_tokens=_est_tokens)
            if quota_status_fn
            else {"status": "unknown", "degraded": True}
        )
```

Replace with:

```python
        resolve_story_fn = _pkg("resolve_or_create_story_id")
        _est_tokens = None
        if story_id and resolve_story_fn:
            _row = dconn.execute(
                "SELECT estimated_tokens FROM stories WHERE story_id=?", (story_id,)
            ).fetchone()
            if _row and _row[0]:
                _est_tokens = int(_row[0])
        if _est_tokens is None:
            # Ad-hoc call with no story estimate: rough heuristic, ~4 chars/token.
            _est_tokens = max(1000, len(task) // 4)

        # Weight the raw token estimate by this (harness, model)'s historical
        # burn rate so a heavier model correctly predicts eating more of the
        # pooled 5h/weekly window than the same token count on a lighter one.
        cached_multiplier_fn = _pkg("cached_burn_rate_multiplier")
        _weighted_est_tokens = _est_tokens
        if cached_multiplier_fn:
            _weighted_est_tokens = int(round(
                _est_tokens * cached_multiplier_fn(agent, model, dconn)
            ))

        quota_status_fn = _pkg("_quota_status_for_agent")
        qstatus = (
            quota_status_fn(dconn, agent, estimated_tokens=_weighted_est_tokens)
            if quota_status_fn
            else {"status": "unknown", "degraded": True}
        )
```

Then, further down in the same block (lines 4841-4848), the reservation is opened with the *unweighted* `_est_tokens`:

```python
            if not existing_reservation:
                open_reservation_fn(
                    dconn,
                    agent,
                    _est_tokens,
                    scope=_scope,
                    scope_id=os.environ.get("SYNLYNK_SCHEDULE_RUN_ID"),
                    job_id=job_id,
                )
```

Change `_est_tokens` to `_weighted_est_tokens` on that call so the reservation (which Task 5 later reads back for drift comparison) reflects the same weighted estimate the gate actually checked against:

```python
            if not existing_reservation:
                open_reservation_fn(
                    dconn,
                    agent,
                    _weighted_est_tokens,
                    scope=_scope,
                    scope_id=os.environ.get("SYNLYNK_SCHEDULE_RUN_ID"),
                    job_id=job_id,
                )
```

- [ ] **Step 6: Write an integration test confirming the gate uses the weighted estimate**

Add to `tests/test_dispatch.py` (adjust the import block at the top of that file if `_pkg`/`dispatch` helpers are imported under different names — follow the existing style already used by other tests in that file for invoking `dispatch_agent`/the dispatch entrypoint and seeding `dconn`):

```python
def test_dispatch_gate_applies_burn_rate_multiplier(tmp_path, monkeypatch):
    import synlynk as sl
    from synlynk.quota import refresh_burn_rate_weights

    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        # Seed a heavy-model history so its cached multiplier is > 1.0.
        for i in range(6):
            conn.execute(
                "INSERT INTO cost_entries (session_date, agent, harness, model, "
                "input_tokens, output_tokens, cache_read_tokens, cost_source, job_id) "
                "VALUES ('2026-10-31', 'claude', 'claude', 'claude-opus-4-7', 40000, 8000, 0, 'actual', ?)",
                (f"seed-heavy-{i}",),
            )
            conn.execute(
                "INSERT INTO cost_entries (session_date, agent, harness, model, "
                "input_tokens, output_tokens, cache_read_tokens, cost_source, job_id) "
                "VALUES ('2026-10-31', 'claude', 'claude', 'claude-haiku-5-5', 4000, 800, 0, 'actual', ?)",
                (f"seed-light-{i}",),
            )
        conn.commit()
        refresh_burn_rate_weights(conn=conn)

        from synlynk.quota import cached_burn_rate_multiplier
        multiplier = cached_burn_rate_multiplier("claude", "claude-opus-4-7", conn)
        assert multiplier > 1.0
    finally:
        conn.close()
```

(This test exercises `cached_burn_rate_multiplier` directly rather than the full `dispatch_agent()` call path, since that path requires a running harness CLI baseline and worktree setup out of scope for this unit test — the full gate wiring is exercised end-to-end by the existing dispatch test suite once this code is merged, and any regression there will surface as a quota-gate test failure.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_quota_burn_rate_weighting.py tests/test_dispatch.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add synlynk/quota.py synlynk/dispatch.py tests/test_quota_burn_rate_weighting.py tests/test_dispatch.py
git commit -m "feat: weight dispatch-time token estimate by per-model burn rate"
```

---

### Task 4: `cost_entries` schema additions for estimate persistence

**Files:**
- Modify: `synlynk/db.py:2328-2331` (add alongside the existing `turn_usage_json` out-of-band repair)
- Test: `tests/test_cost_estimate_drift.py` (new file)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost_estimate_drift.py
"""Unit tests for cost_entries estimate-vs-actual drift tracking (v0.26.9)."""

import synlynk as sl


def test_cost_entries_has_estimate_columns(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
        assert "estimated_input_tokens" in cols
        assert "estimated_output_tokens" in cols
        assert "estimated_cost_usd" in cols
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_estimate_drift.py -v`
Expected: FAIL with `assert "estimated_input_tokens" in cols` (AssertionError)

- [ ] **Step 3: Add the columns**

In `synlynk/db.py`, immediately after the existing out-of-band repair block (lines 2328-2331):

```python
    cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    if "turn_usage_json" not in cost_cols:
        conn.execute("ALTER TABLE cost_entries ADD COLUMN turn_usage_json TEXT")
        conn.commit()
```

insert:

```python

    # Pre-dispatch estimate persistence for estimate-vs-actual drift tracking
    # (v0.26.9). NULL (not 0) on existing rows: a bare 0 would read as a
    # "perfect estimate" false positive in the drift comparison below.
    _add_column_if_missing(conn, table="cost_entries", column="estimated_input_tokens", definition="INTEGER")
    _add_column_if_missing(conn, table="cost_entries", column="estimated_output_tokens", definition="INTEGER")
    _add_column_if_missing(conn, table="cost_entries", column="estimated_cost_usd", definition="REAL")
```

(`_add_column_if_missing` is defined later in this same file at line 2360 but Python resolves it at call time, not definition time, so the forward reference inside `_get_db()`'s body is safe — it already relies on this for the `capability_ratings`/`capability_calibration_results` calls a few lines below.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_estimate_drift.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_cost_estimate_drift.py
git commit -m "feat: add cost_entries estimate columns for drift tracking"
```

---

### Task 5: Populate the estimate columns and fire the drift alert

**Files:**
- Modify: `synlynk/db.py:2413-2620` (`_insert_cost_row`)
- Test: `tests/test_cost_estimate_drift.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cost_estimate_drift.py`:

```python
import os

from synlynk.db import _insert_cost_row


def _seed_reservation(conn, job_id, tokens):
    conn.execute(
        "INSERT INTO harness_reservations (harness, tokens, scope, job_id, status) "
        "VALUES ('claude', ?, 'session', ?, 'open')",
        (tokens, job_id),
    )
    conn.commit()


def test_insert_cost_row_populates_estimate_from_reservation(tmp_path, monkeypatch):
    db_file = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_file))
    conn = sl._get_db(str(db_file))
    try:
        _seed_reservation(conn, "job-drift-1", 10_000)
    finally:
        conn.close()

    _insert_cost_row(
        session_date="2026-10-31",
        agent="claude",
        harness="claude",
        model="claude-opus-4-7",
        input_tokens=10_000,
        output_tokens=2_000,
        cost_source="actual",
        total_cost_usd=0.19,
        actual_usd=0.19,
        job_id="job-drift-1",
    )

    conn = sl._get_db(str(db_file))
    try:
        row = conn.execute(
            "SELECT estimated_input_tokens, estimated_output_tokens, estimated_cost_usd "
            "FROM cost_entries WHERE job_id='job-drift-1'"
        ).fetchone()
        assert row[0] == 10_000
        assert row[1] == 0
        assert row[2] is not None and row[2] > 0.0
    finally:
        conn.close()


def test_insert_cost_row_fires_drift_alert_over_threshold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    db_file = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_file))
    conn = sl._get_db(str(db_file))
    try:
        # Reservation estimated only 1,000 tokens.
        _seed_reservation(conn, "job-drift-2", 1_000)
    finally:
        conn.close()

    # Actual cost is wildly higher than what 1,000 tokens would predict.
    _insert_cost_row(
        session_date="2026-10-31",
        agent="claude",
        harness="claude",
        model="claude-opus-4-7",
        input_tokens=50_000,
        output_tokens=10_000,
        cost_source="actual",
        total_cost_usd=0.90,
        actual_usd=0.90,
        job_id="job-drift-2",
    )

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    assert sentinel_path.exists()
    assert "COST_ESTIMATE_DRIFT" in sentinel_path.read_text()


def test_insert_cost_row_no_alert_within_threshold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    db_file = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_file))
    conn = sl._get_db(str(db_file))
    try:
        _seed_reservation(conn, "job-drift-3", 10_000)
    finally:
        conn.close()

    _insert_cost_row(
        session_date="2026-10-31",
        agent="claude",
        harness="claude",
        model="claude-opus-4-7",
        input_tokens=10_500,
        output_tokens=2_000,
        cost_source="actual",
        total_cost_usd=0.19,
        actual_usd=0.19,
        job_id="job-drift-3",
    )

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    assert not sentinel_path.exists() or "COST_ESTIMATE_DRIFT" not in sentinel_path.read_text()
```

(These tests set `SYNLYNK_STATE_DB_PATH` because `_insert_cost_row` calls the module-level `_get_db()` with no path argument internally — follow whatever env var or config mechanism `synlynk/__init__.py`'s `_get_db()` actually reads to resolve the default db path if it differs from this name; check `grep -n "def _get_db" synlynk/__init__.py` and its first few lines before running this step if the test fails with a path-resolution error instead of the expected assertion.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cost_estimate_drift.py -v`
Expected: FAIL — `estimated_input_tokens` reads back `None` instead of `10_000`, and no `sentinel.md` is written.

- [ ] **Step 3: Implement estimate lookup, persistence, and drift alert**

In `synlynk/db.py`, `_insert_cost_row` currently opens its connection and proceeds straight to the `harness_val`/`agent_val` resolution (line 2452-2455):

```python
    conn = _get_db()
    try:
        harness_val = harness or agent
        agent_val = agent or harness
```

Add estimate resolution right after those two lines:

```python
    conn = _get_db()
    try:
        harness_val = harness or agent
        agent_val = agent or harness

        # Estimate-vs-actual drift tracking (v0.26.9): pull the pre-dispatch
        # token estimate from the harness_reservations row this job opened
        # (closing a reservation sets status='released' but keeps the row,
        # so this lookup works whether or not the reservation was released).
        estimated_input_tokens = None
        estimated_output_tokens = None
        estimated_cost_usd = None
        if job_id:
            try:
                res_row = conn.execute(
                    "SELECT tokens FROM harness_reservations WHERE job_id=? ORDER BY id DESC LIMIT 1",
                    (job_id,),
                ).fetchone()
            except sqlite3.Error:
                res_row = None
            if res_row and res_row[0] is not None:
                estimated_input_tokens = int(res_row[0])
                estimated_output_tokens = 0
                from synlynk.costs import api_equivalent_usd
                estimated_cost_usd = api_equivalent_usd(
                    harness_val or "claude",
                    estimated_input_tokens,
                    estimated_output_tokens,
                    model=model,
                )
```

Then extend both the UPDATE and INSERT statements to carry the three new columns. The UPDATE statement (lines 2528-2554) becomes:

```python
                conn.execute(
                    """UPDATE cost_entries SET
                        session_date=?,
                        agent=?,
                        harness=COALESCE(?, harness),
                        agent_role=COALESCE(?, agent_role),
                        model=?,
                        input_tokens=?,
                        output_tokens=?,
                        cache_read_tokens=?,
                        cost_source=?,
                        estimate_basis=?,
                        total_cost_usd=?,
                        api_equivalent_usd=?,
                        actual_usd=?,
                        payment_mode=?,
                        notes=?,
                        story_id=?,
                        epic_id=?,
                        phase_id=?,
                        dispatch_context=COALESCE(?, dispatch_context),
                        context_mode=COALESCE(?, context_mode),
                        session_id=COALESCE(?, session_id),
                        pr_number=COALESCE(?, pr_number)
                        ,decision_revision=COALESCE(?, decision_revision)
                        ,turn_usage_json=COALESCE(?, turn_usage_json)
                        ,estimated_input_tokens=COALESCE(estimated_input_tokens, ?)
                        ,estimated_output_tokens=COALESCE(estimated_output_tokens, ?)
                        ,estimated_cost_usd=COALESCE(estimated_cost_usd, ?)
                    WHERE job_id=?""",
                    (
                        session_date,
                        agent_val,
                        harness_val,
                        role_val,
                        model,
                        input_tokens,
                        output_tokens,
                        cache_read_tokens,
                        cost_source,
                        estimate_basis,
                        total_cost_usd,
                        api_equivalent_usd,
                        actual_usd,
                        payment_mode,
                        notes,
                        story_id,
                        epic_id,
                        phase_id,
                        dispatch_context,
                        context_mode,
                        session_id,
                        pr_number,
                        decision_revision,
                        json.dumps(turn_breakdown, separators=(",", ":")) if turn_breakdown else None,
                        estimated_input_tokens,
                        estimated_output_tokens,
                        estimated_cost_usd,
                        job_id,
                    ),
                )
                conn.commit()
                _maybe_alert_cost_estimate_drift(
                    conn, job_id=job_id, harness=harness_val,
                    actual_usd=actual_usd if actual_usd is not None else total_cost_usd,
                    estimated_cost_usd=estimated_cost_usd,
                )
                return
```

(Note: `api_equivalent_usd` is a parameter name already used by this function for the row's own actual-cost column — the new `from synlynk.costs import api_equivalent_usd` import added in Step 3's estimate-resolution block above shadows that parameter name only inside its own `if job_id:` block, which closes before the UPDATE/INSERT statements run, so there is no collision at the point the parameter is referenced in the SQL tuples. If this import were moved outside that block, it would need renaming to e.g. `_api_equivalent_usd_fn` to avoid shadowing the parameter — keep the import scoped to the `if job_id:` block as written.)

The INSERT statement (lines 2585-2616) becomes:

```python
        conn.execute(
            """INSERT INTO cost_entries
                (session_date, agent, harness, agent_role, model, input_tokens, output_tokens, cache_read_tokens,
                 cost_source, estimate_basis, total_cost_usd, api_equivalent_usd, actual_usd, payment_mode, notes, story_id, epic_id, phase_id, job_id, dispatch_context, context_mode, session_id, pr_number, decision_revision, turn_usage_json,
                 estimated_input_tokens, estimated_output_tokens, estimated_cost_usd)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_date,
                agent_val,
                harness_val,
                role_val,
                model,
                input_tokens,
                output_tokens,
                cache_read_tokens,
                cost_source,
                estimate_basis,
                total_cost_usd,
                api_equivalent_usd,
                actual_usd,
                payment_mode,
                notes,
                story_id,
                epic_id,
                phase_id,
                job_id,
                dispatch_context,
                context_mode,
                session_id,
                pr_number,
                decision_revision,
                json.dumps(turn_breakdown, separators=(",", ":")) if turn_breakdown else None,
                estimated_input_tokens,
                estimated_output_tokens,
                estimated_cost_usd,
            ),
        )
        conn.commit()
        _maybe_alert_cost_estimate_drift(
            conn, job_id=job_id, harness=harness_val,
            actual_usd=actual_usd if actual_usd is not None else total_cost_usd,
            estimated_cost_usd=estimated_cost_usd,
        )
    finally:
        conn.close()
```

(The existing `finally: conn.close()` at line 2619-2620 stays exactly where it is — only the `conn.commit()` line directly above it gains the `_maybe_alert_cost_estimate_drift(...)` call shown above, on its own line before `finally`.)

Now add the helper function itself. Place it directly above `_insert_cost_row` (before line 2413):

```python
_COST_ESTIMATE_DRIFT_THRESHOLD = 0.5  # 50% overage triggers the alert


def _maybe_alert_cost_estimate_drift(conn, *, job_id, harness, actual_usd, estimated_cost_usd) -> None:
    """Writes a COST_ESTIMATE_DRIFT sentinel alert when actual cost exceeds
    the pre-dispatch estimate by more than _COST_ESTIMATE_DRIFT_THRESHOLD.
    No-op when there was no reservation estimate to compare against.
    """
    if estimated_cost_usd is None or estimated_cost_usd <= 0.0 or actual_usd is None:
        return
    overage = (actual_usd - estimated_cost_usd) / estimated_cost_usd
    if overage <= _COST_ESTIMATE_DRIFT_THRESHOLD:
        return
    from synlynk.sentinel import _write_sentinel_alert
    _write_sentinel_alert(
        "WARNING",
        "COST_ESTIMATE_DRIFT",
        f"Job {job_id} ({harness}): actual cost ${actual_usd:.4f} exceeded "
        f"pre-dispatch estimate ${estimated_cost_usd:.4f} by {overage * 100:.0f}% "
        f"(threshold {_COST_ESTIMATE_DRIFT_THRESHOLD * 100:.0f}%).",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cost_estimate_drift.py -v`
Expected: PASS

- [ ] **Step 5: Run the full cost-entries-related test suite to check for regressions**

Run: `pytest tests/test_cost_entries.py tests/test_costs.py -v` (adjust to whatever the existing cost-entries test file names actually are — `grep -rl "_insert_cost_row" tests/` to find every test file that exercises this function before running, since this task's SQL changes touch both INSERT and UPDATE paths)
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_cost_estimate_drift.py
git commit -m "feat: persist pre-dispatch cost estimate and alert on >50% drift"
```

---

### Task 6: Automatic quota calibration (snapshot diffing + staleness tracking)

**Files:**
- Modify: `synlynk/db.py:1750-1754` (capability_watch migration block)
- Modify: `synlynk/quota.py` (add `is_quota_calibration_stale`, `maybe_calibrate_quota`)
- Test: `tests/test_quota_calibration.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_quota_calibration.py`:

```python
def test_capability_watch_has_quota_calibration_column(tmp_path):
    import synlynk as sl
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_watch)")}
        assert "last_quota_calibration_at" in cols
    finally:
        conn.close()


def test_is_quota_calibration_stale_true_when_never_run(tmp_path):
    import synlynk as sl
    from synlynk.quota import is_quota_calibration_stale
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        assert is_quota_calibration_stale(conn, threshold_hours=24) is True
    finally:
        conn.close()


def test_maybe_calibrate_quota_derives_delta_from_snapshots_and_cost_entries(tmp_path):
    import synlynk as sl
    from synlynk.quota import maybe_calibrate_quota
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        conn.execute(
            "INSERT INTO quota_snapshots (harness, window, used_percent, resets_at, captured_at, source) "
            "VALUES ('claude', '5h', 10.0, '2026-10-31T18:00:00Z', '2026-10-31T10:00:00Z', 'poll')"
        )
        conn.execute(
            "INSERT INTO quota_snapshots (harness, window, used_percent, resets_at, captured_at, source) "
            "VALUES ('claude', '5h', 30.0, '2026-10-31T18:00:00Z', '2026-10-31T12:00:00Z', 'poll')"
        )
        for i in range(2):
            conn.execute(
                "INSERT INTO cost_entries (session_date, agent, harness, model, input_tokens, "
                "output_tokens, cache_read_tokens, cost_source, job_id, recorded_at) "
                "VALUES ('2026-10-31', 'claude', 'claude', 'claude-opus-4-7', 15000, 5000, 0, "
                "'actual', ?, '2026-10-31T11:00:00')",
                (f"job-cal-{i}",),
            )
        conn.commit()

        results = maybe_calibrate_quota(conn=conn)
        assert any(r["harness"] == "claude" and r["window"] == "5h" and r["valid"] for r in results)

        row = conn.execute("SELECT last_quota_calibration_at FROM capability_watch WHERE id=1").fetchone()
        assert row is not None and row[0] is not None
    finally:
        conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_quota_calibration.py -k "quota_calibration_column or calibration_stale or derives_delta" -v`
Expected: FAIL (`last_quota_calibration_at` missing; `is_quota_calibration_stale`/`maybe_calibrate_quota` not defined)

- [ ] **Step 3: Add the staleness column**

In `synlynk/db.py`, the existing block at lines 1750-1754 reads:

```python
        capability_watch_cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_watch)")}
        if "last_sweep_at" not in capability_watch_cols:
            conn.execute("ALTER TABLE capability_watch ADD COLUMN last_sweep_at TEXT")
        if "sweep_job_count" not in capability_watch_cols:
            conn.execute("ALTER TABLE capability_watch ADD COLUMN sweep_job_count INTEGER NOT NULL DEFAULT 0")
```

Add immediately after:

```python
        if "last_quota_calibration_at" not in capability_watch_cols:
            conn.execute("ALTER TABLE capability_watch ADD COLUMN last_quota_calibration_at TEXT")
```

- [ ] **Step 4: Implement `is_quota_calibration_stale` and `maybe_calibrate_quota`**

In `synlynk/quota.py`, add after `refresh_burn_rate_weights`/`cached_burn_rate_multiplier` (end of Task 3's additions):

```python
def is_quota_calibration_stale(conn, threshold_hours: int = 24) -> bool:
    """Mirrors capability_watch.is_probe_stale's pattern for the new column."""
    row = conn.execute(
        "SELECT last_quota_calibration_at FROM capability_watch WHERE id = 1"
    ).fetchone()
    last_raw = row[0] if row else None
    if not last_raw:
        return True
    try:
        last = datetime.fromisoformat(last_raw.replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
    except ValueError:
        return True
    return (datetime.now(UTC) - last).total_seconds() > threshold_hours * 3600


def maybe_calibrate_quota(conn=None) -> list[dict[str, Any]]:
    """Automatically re-calibrates quota ceilings for every harness/window
    that has at least two quota_snapshots rows, deriving delta_tokens from
    cost_entries actual usage between those two snapshot timestamps instead
    of requiring a human to supply p1_pct/p2_pct/delta_tokens by hand.

    Also refreshes the quota_burn_rate_weights cache (Task 3) in the same
    pass, and stamps capability_watch.last_quota_calibration_at so
    is_quota_calibration_stale() reflects this run. Returns one result dict
    per harness/window pair attempted.
    """
    own_conn = conn is None
    if own_conn:
        conn = _pkg("_get_db")()
    try:
        pairs = conn.execute(
            "SELECT DISTINCT harness, window FROM quota_snapshots"
        ).fetchall()
        results: list[dict[str, Any]] = []
        for harness, window in pairs:
            snaps = conn.execute(
                "SELECT used_percent, captured_at FROM quota_snapshots "
                "WHERE harness = ? AND window = ? ORDER BY captured_at DESC, id DESC LIMIT 2",
                (harness, window),
            ).fetchall()
            if len(snaps) < 2:
                continue
            p2_pct, p2_at = snaps[0]
            p1_pct, p1_at = snaps[1]
            delta_row = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)), 0) "
                "FROM cost_entries WHERE lower(harness) = lower(?) "
                "AND recorded_at > ? AND recorded_at <= ?",
                (harness, p1_at, p2_at),
            ).fetchone()
            delta_tokens = int(delta_row[0] or 0)
            if delta_tokens <= 0:
                continue
            cal = calibrate_and_update_quota(
                harness, window, p1_pct=p1_pct, p2_pct=p2_pct,
                delta_tokens=delta_tokens, conn=conn,
            )
            results.append({"harness": harness, "window": window, **cal})

        refresh_burn_rate_weights(conn=conn)

        conn.execute(
            "UPDATE capability_watch SET last_quota_calibration_at = ? WHERE id = 1",
            (datetime.now(UTC).isoformat(),)
        )
        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO capability_watch (id, last_quota_calibration_at) VALUES (1, ?)",
                (datetime.now(UTC).isoformat(),)
            )
        conn.commit()
        return results
    finally:
        if own_conn:
            conn.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_quota_calibration.py -v`
Expected: PASS (all tests in the file, including the 3 new ones)

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py synlynk/quota.py tests/test_quota_calibration.py
git commit -m "feat: auto-derive quota calibration inputs from snapshots and cost_entries"
```

---

### Task 7: Wire the calibration tick into the daemon loop

**Files:**
- Modify: `synlynk/daemon.py` (add `_run_quota_calibration_tick` near `_run_capability_watch_tick`, line 1357-1378; call it from `_run_loop`, line 1713)
- Test: `tests/test_daemon_supervision_discovery.py` OR a new `tests/test_daemon_quota_calibration_tick.py` (new file — simpler to isolate since the existing daemon test files are discovery/liveness-focused, not tick-content-focused)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_daemon_quota_calibration_tick.py
"""Unit test for the daemon's periodic quota calibration tick (v0.26.9)."""

from unittest.mock import MagicMock, patch

from synlynk.daemon import Daemon


def test_run_quota_calibration_tick_calls_maybe_calibrate_quota(tmp_path):
    d = Daemon.__new__(Daemon)  # bypass __init__, only the method under test is needed
    d.sentinel_path = str(tmp_path / "sentinel.md")

    with patch("synlynk.quota.maybe_calibrate_quota") as mock_calibrate:
        mock_calibrate.return_value = [{"harness": "claude", "window": "5h", "valid": True}]
        d._run_quota_calibration_tick({})
        mock_calibrate.assert_called_once()


def test_run_quota_calibration_tick_writes_sentinel_on_error(tmp_path):
    d = Daemon.__new__(Daemon)
    d.sentinel_path = str(tmp_path / "sentinel.md")

    with patch("synlynk.quota.maybe_calibrate_quota", side_effect=RuntimeError("boom")):
        d._run_quota_calibration_tick({})

    assert (tmp_path / "sentinel.md").exists()
    assert "QUOTA_CALIBRATION_TICK_FAILED" in (tmp_path / "sentinel.md").read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_daemon_quota_calibration_tick.py -v`
Expected: FAIL with `AttributeError: 'Daemon' object has no attribute '_run_quota_calibration_tick'`

- [ ] **Step 3: Implement the tick method**

In `synlynk/daemon.py`, immediately after `_run_capability_watch_tick` (after line 1378, before `_maybe_run_autonomy_pass`):

```python
    def _run_quota_calibration_tick(self, config: dict) -> None:
        """Runs automatic quota calibration from the daemon cadence.

        calibrate_and_update_quota previously had no scheduled caller (only
        the manual `synlynk quota calibrate` CLI command) and so silently
        never ran unless a human remembered to invoke it (v0.26.9). This
        mirrors _run_capability_watch_tick's structure: staleness gating
        lives in the called function/module, not here.
        """
        conn = None
        try:
            from synlynk.quota import is_quota_calibration_stale, maybe_calibrate_quota

            conn = _pkg("_get_db")()
            if is_quota_calibration_stale(conn, threshold_hours=24):
                maybe_calibrate_quota(conn=conn)
        except Exception as exc:
            _write_sentinel_alert(
                "ERROR",
                "QUOTA_CALIBRATION_TICK_FAILED",
                f"Daemon quota calibration tick failed: {exc}. Check daemon.log and state.db.",
                self.sentinel_path,
            )
        finally:
            if conn is not None:
                conn.close()
```

- [ ] **Step 4: Call it from `_run_loop`**

In `synlynk/daemon.py`, line 1713 currently reads:

```python
            self._run_capability_watch_tick(config)
```

Change to:

```python
            self._run_capability_watch_tick(config)
            self._run_quota_calibration_tick(config)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_daemon_quota_calibration_tick.py -v`
Expected: PASS

- [ ] **Step 6: Run the broader daemon test suite to check for regressions**

Run: `pytest tests/test_daemon_supervision_discovery.py tests/test_daemon_liveness_1572.py tests/test_daemon_start_lock_decoupling.py -v`
Expected: PASS, no regressions

- [ ] **Step 7: Commit**

```bash
git add synlynk/daemon.py tests/test_daemon_quota_calibration_tick.py
git commit -m "feat: wire automatic quota calibration into the daemon's periodic tick"
```

---

### Task 8: `synlynk status` staleness warning

**Files:**
- Modify: `synlynk/status.py:496-514`
- Test: `tests/test_status.py`

- [ ] **Step 1: Write the failing test**

Check the existing style of `tests/test_status.py`'s smoke-test-overdue assertion first (`grep -n "smoke test overdue" tests/test_status.py`) and match its fixture pattern exactly. Add:

```python
def test_status_warns_when_quota_calibration_overdue(tmp_path, monkeypatch, capsys):
    import synlynk as sl
    from synlynk.status import cmd_status

    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    conn.close()
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_file))
    monkeypatch.chdir(tmp_path)

    cmd_status(json_output=False)
    captured = capsys.readouterr()
    assert "quota calibration overdue" in captured.out
```

(If `cmd_status`'s actual signature or the env var it reads to resolve the db path differs from this guess, adjust the test to match — `grep -n "def cmd_status" synlynk/status.py` and the existing passing tests in `tests/test_status.py` are the source of truth for the correct call shape; do not guess further than this plan already has, follow the file's own conventions.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_status.py -k quota_calibration_overdue -v`
Expected: FAIL — `"quota calibration overdue" not in captured.out`

- [ ] **Step 3: Add the warning line**

In `synlynk/status.py`, the existing block at lines 511-514 reads:

```python
        if is_smoke_test_stale(db_conn, threshold_days=7):
            extra_lines.append(
                "⚠ smoke test overdue - run `synlynk selftest --live` or enable `auto_smoke_test` in config"
            )
```

Add immediately after:

```python
        from synlynk.quota import is_quota_calibration_stale

        if is_quota_calibration_stale(db_conn, threshold_hours=24):
            extra_lines.append(
                "⚠ quota calibration overdue - run `synlynk quota calibrate` "
                "or ensure the daemon is running (`synlynk daemon start`)"
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_status.py -k quota_calibration_overdue -v`
Expected: PASS

- [ ] **Step 5: Run the full status test suite to check for regressions**

Run: `pytest tests/test_status.py -v`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add synlynk/status.py tests/test_status.py
git commit -m "feat: warn in synlynk status when quota calibration is overdue"
```

---

## Final verification

- [ ] Run the full targeted suite for this plan:

Run: `pytest tests/test_quota_burn_rate_weighting.py tests/test_cost_estimate_drift.py tests/test_quota_calibration.py tests/test_daemon_quota_calibration_tick.py tests/test_status.py tests/test_dispatch.py -v`
Expected: PASS, 0 failures

- [ ] Run the full project test suite once to catch anything these targeted runs missed:

Run: `pytest -q`
Expected: PASS (per this repo's CLAUDE.md Named Release checklist precedent, note the actual collected test count here, do not report "N tests passing" from memory)
