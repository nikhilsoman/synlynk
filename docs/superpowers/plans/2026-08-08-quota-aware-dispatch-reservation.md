# Quota-Aware Dispatch Reservation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared `agent_reservations` ledger, consulted from every dispatch path (force-agent, ad-hoc, daemon-queued, batch-scheduled), that closes the existing quota-bypass and fall-through bugs and auto-defers (never hard-fails) when headroom is insufficient.

**Architecture:** A new SQLite table (`agent_reservations`) tracks in-flight token commitments per harness. `_quota_status_for_agent()` subtracts open reservations from telemetry-derived headroom. `dispatch_agent()` opens a reservation before firing and consults quota unconditionally (removing the `story_id and not force_agent` gate). `_dispatch_ready_jobs()` and `_enqueue_plan()` are fixed/extended to use the same gate. Reservations release on job settlement in `_reconcile_daemon_jobs()`. A reactive-correction hook (`_force_exhaust_quota()`) wires the existing but currently-dead-ended `QUOTA_EXHAUSTED` sentinel detector to actually zero headroom. Three narrow TPM hook functions round out the design's forward-compatibility surface.

**Tech Stack:** Python 3 stdlib, SQLite (`synlynk/db.py`, `synlynk/__init__.py` schema), pytest with `tmp_path` + `monkeypatch.chdir` fixtures (see `tests/conftest.py`).

**Spec:** `docs/superpowers/specs/2026-08-08-quota-aware-dispatch-reservation-design.md` — read in full before starting; every task below implements one concrete piece of it.

---

## Naming discipline (read before touching any code)

Per the spec's "Naming Collision" section: every new function/column introduced in this plan uses `harness: str` for the core CLI binary identity (`claude`/`agy`/`codex`/`grok`/`local`) and `role: str` for the functional-taxonomy dimension (`tpm`/`pm`/`dev`/...). Never let one flow into a parameter or column typed for the other. Existing `agent`-named columns/params (`daemon_jobs.agent`, `agent_quotas.agent`, `dispatch_agent(agent, ...)`) are untouched — only the **new** `agent_reservations.harness` column and new function signatures use `harness`.

---

### Task 1: `agent_reservations` table + `daemon_jobs.blocked_reason` column

**Files:**
- Modify: `synlynk/__init__.py:920-937` (daemon_jobs CREATE TABLE), `synlynk/__init__.py:957-973` (after agent_quotas CREATE TABLE — primary schema)
- Modify: `synlynk/db.py:288-303` (daemon_jobs migration-safety block), `synlynk/db.py:723-737` (agent_quotas re-assert block — add matching re-assert for agent_reservations)
- Test: `tests/test_agent_quota_tracking.py`

- [ ] **Step 1: Write the failing test for fresh-DB schema**

```python
def test_agent_reservations_table_exists(project_dir):
    import synlynk as sl
    conn = sl._get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agent_reservations)")}
    assert cols == {
        "id", "harness", "tokens", "scope", "scope_id", "job_id",
        "status", "created_at", "released_at",
    }
    daemon_cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    assert "blocked_reason" in daemon_cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_quota_tracking.py::test_agent_reservations_table_exists -v`
Expected: FAIL — `sqlite3.OperationalError: no such table: agent_reservations` (or empty `cols` set).

- [ ] **Step 3: Add the table to the primary schema in `synlynk/__init__.py`**

Insert immediately after the `agent_quotas` block (after the line `CREATE INDEX IF NOT EXISTS idx_agent_quotas_agent ON agent_quotas(agent);` at `synlynk/__init__.py:973`):

```sql

-- Reservation ledger: an open row represents tokens committed against a
-- harness before real usage lands in agent_quotas via telemetry (#XXX
-- quota-aware dispatch reservation). Released once the matching daemon_jobs
-- row settles (done/failed/timed_out) and real usage has been recorded.
-- Reservations older than 24h are treated as expired at READ time (lazy
-- expiry, see _open_reservations_sum) rather than physically deleted.
CREATE TABLE IF NOT EXISTS agent_reservations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    harness        TEXT NOT NULL,
    tokens         INTEGER NOT NULL,
    scope          TEXT NOT NULL,
    scope_id       TEXT,
    job_id         TEXT,
    status         TEXT NOT NULL DEFAULT 'open',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    released_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agent_reservations_harness ON agent_reservations(harness, status);
```

Also add `blocked_reason` to the `daemon_jobs` CREATE TABLE at `synlynk/__init__.py:920-937` (for fresh DBs), inserting after the `dispatch_context TEXT` line:

```sql
    dispatch_context TEXT,
    blocked_reason TEXT
);
```
(replace the existing closing `);` on the line after `dispatch_context TEXT` — the column list gains one more entry before the closing paren.)

- [ ] **Step 4: Add the migration-safety re-assert copies in `synlynk/db.py`**

After the `agent_quotas` re-assert block (`synlynk/db.py:723-737`, ending with the closing `""")` of the `CREATE TABLE IF NOT EXISTS agent_quotas` statement), add:

```python
    # Quota-aware dispatch reservation: agent_reservations base table
    # (also in _DB_SCHEMA; re-assert for older DBs)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_reservations (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            harness        TEXT NOT NULL,
            tokens         INTEGER NOT NULL,
            scope          TEXT NOT NULL,
            scope_id       TEXT,
            job_id         TEXT,
            status         TEXT NOT NULL DEFAULT 'open',
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            released_at    TIMESTAMP
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_reservations_harness "
        "ON agent_reservations(harness, status)"
    )
```

And add the `blocked_reason` migration next to the existing `daemon_jobs` column migrations at `synlynk/db.py:288-303`, following the exact pattern used for `dispatch_context`:

```python
    if "blocked_reason" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN blocked_reason TEXT")
        except sqlite3.OperationalError:
            pass
```
(insert this block right after the existing `dispatch_context` block, still inside the same `if`/`try` sequence using the already-computed `daemon_job_cols` set from line 288.)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_agent_quota_tracking.py::test_agent_reservations_table_exists -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py synlynk/db.py tests/test_agent_quota_tracking.py
git commit -m "feat: add agent_reservations table and daemon_jobs.blocked_reason column"
```

---

### Task 2: Reservation lifecycle functions in `synlynk/quota.py`

**Files:**
- Modify: `synlynk/quota.py` (add functions after `_upsert_agent_quota`, i.e. after line 455)
- Modify: `synlynk/__init__.py:85-95` (re-export new functions)
- Test: `tests/test_agent_quota_tracking.py`

- [ ] **Step 1: Write failing tests for open/release/sum**

```python
def test_open_release_reservation_lifecycle(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    rid = sl._open_reservation(conn, "claude", 5000, scope="adhoc")
    assert isinstance(rid, int)

    row = conn.execute(
        "SELECT harness, tokens, scope, scope_id, job_id, status FROM agent_reservations WHERE id=?",
        (rid,),
    ).fetchone()
    assert row == ("claude", 5000, "adhoc", None, None, "open")

    assert sl._open_reservations_sum(conn, "claude") == 5000
    assert sl._open_reservations_sum(conn, "codex") == 0

    sl._release_reservation(conn, rid)
    status, released_at = conn.execute(
        "SELECT status, released_at FROM agent_reservations WHERE id=?", (rid,)
    ).fetchone()
    assert status == "released"
    assert released_at is not None
    assert sl._open_reservations_sum(conn, "claude") == 0


def test_open_reservations_sum_ignores_expired(project_dir):
    import synlynk as sl
    import time

    conn = sl._get_db()
    rid = sl._open_reservation(conn, "claude", 3000, scope="adhoc")
    # Simulate a reservation opened >24h ago (lazy expiry, not physical delete)
    stale = time.strftime(
        "%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - 25 * 3600)
    )
    conn.execute(
        "UPDATE agent_reservations SET created_at=? WHERE id=?", (stale, rid)
    )
    conn.commit()
    assert sl._open_reservations_sum(conn, "claude") == 0
    # Row itself is untouched (status still 'open') -- lazy, not physical
    status = conn.execute(
        "SELECT status FROM agent_reservations WHERE id=?", (rid,)
    ).fetchone()[0]
    assert status == "open"


def test_open_reservation_with_scope_id_and_job_id(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    rid = sl._open_reservation(
        conn, "agy", 2000, scope="plan", scope_id="run-abc123", job_id="job-xyz"
    )
    row = conn.execute(
        "SELECT scope, scope_id, job_id FROM agent_reservations WHERE id=?", (rid,)
    ).fetchone()
    assert row == ("plan", "run-abc123", "job-xyz")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agent_quota_tracking.py -k "reservation" -v`
Expected: FAIL — `AttributeError: module 'synlynk' has no attribute '_open_reservation'`

- [ ] **Step 3: Implement the functions in `synlynk/quota.py`**

Insert after `_upsert_agent_quota` (after line 455, before `_project_request_quota_from_config`):

```python
_RESERVATION_EXPIRY_SECONDS = 24 * 3600  # comfortably > longest QUOTA_TYPES window (5h)


def _open_reservation(
    conn,
    harness: str,
    tokens: int,
    scope: str,
    scope_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> int:
    """Opens an agent_reservations row. Returns the new reservation id.

    scope is one of 'plan' | 'session' | 'adhoc' (not validated here -- callers
    are internal and already constrained by the design's dispatch-time flow).
    """
    cur = conn.execute(
        "INSERT INTO agent_reservations (harness, tokens, scope, scope_id, job_id, status) "
        "VALUES (?, ?, ?, ?, ?, 'open')",
        (harness, int(tokens), scope, scope_id, job_id),
    )
    conn.commit()
    return cur.lastrowid


def _release_reservation(conn, reservation_id: int) -> None:
    """Marks a reservation released. Idempotent -- releasing twice is a no-op
    on the second call since the WHERE clause only matches status='open'."""
    conn.execute(
        "UPDATE agent_reservations SET status='released', released_at=CURRENT_TIMESTAMP "
        "WHERE id=? AND status='open'",
        (reservation_id,),
    )
    conn.commit()


def _open_reservations_sum(conn, harness: str) -> int:
    """Sums tokens from open, non-expired reservations for one harness.

    Lazy expiry: a reservation older than _RESERVATION_EXPIRY_SECONDS is
    excluded from the sum on read, not physically mutated -- avoids an extra
    write on every dispatch just to sweep abandoned reservations.
    """
    cutoff = datetime.now(UTC).timestamp() - _RESERVATION_EXPIRY_SECONDS
    cutoff_iso = datetime.fromtimestamp(cutoff, UTC).strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute(
        "SELECT COALESCE(SUM(tokens), 0) FROM agent_reservations "
        "WHERE harness=? AND status='open' AND created_at >= ?",
        (harness, cutoff_iso),
    ).fetchone()
    return int(row[0] or 0)
```

- [ ] **Step 4: Re-export the new functions from `synlynk/__init__.py`**

Modify the `from synlynk.quota import (...)` block at `synlynk/__init__.py:85-95` to add the three new names (alphabetically among the existing underscore-prefixed names):

```python
from synlynk.quota import (
    _estimate_story_cost_usd,
    _open_reservation,
    _open_reservations_sum,
    _project_request_quota_from_config,
    _quota_headroom,
    _quota_status_for_agent,
    _read_agent_quota_rows,
    _refresh_agent_quotas_from_telemetry,
    _release_reservation,
    _upsert_agent_quota,
    cmd_quota,
    refresh_agent_quotas_from_telemetry,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_agent_quota_tracking.py -k "reservation" -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/quota.py synlynk/__init__.py tests/test_agent_quota_tracking.py
git commit -m "feat: add reservation lifecycle functions (open/release/sum)"
```

---

### Task 3: Subtract open reservations from `_quota_status_for_agent()` headroom

**Files:**
- Modify: `synlynk/quota.py:539-663` (`_quota_status_for_agent`)
- Test: `tests/test_agent_quota_tracking.py`

- [ ] **Step 1: Write failing test**

```python
def test_quota_status_subtracts_open_reservations(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "claude", "5h", limit_tokens=10_000, used_tokens=0, unit="tokens", conn=conn
    )
    # No reservations yet: full headroom, small ask fits
    status = sl._quota_status_for_agent(conn, "claude", estimated_tokens=9_000)
    assert status["status"] == "ok"
    assert status["headroom"] == 10_000

    # Reserve 6,000 -- headroom should now read as 4,000
    sl._open_reservation(conn, "claude", 6_000, scope="adhoc")
    status = sl._quota_status_for_agent(conn, "claude", estimated_tokens=3_000)
    assert status["status"] == "ok"
    assert status["headroom"] == 4_000

    # A further ask that only fits telemetry-headroom but not reservation-adjusted
    # headroom must be rejected
    status = sl._quota_status_for_agent(conn, "claude", estimated_tokens=5_000)
    assert status["status"] == "exhausted"
    assert status["headroom"] == 4_000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_quota_tracking.py::test_quota_status_subtracts_open_reservations -v`
Expected: FAIL — headroom reported as `10_000` in the second assertion (reservations not yet subtracted).

- [ ] **Step 3: Modify `_quota_status_for_agent()`**

In `synlynk/quota.py`, inside the `for row in rows:` loop (starting at line 602), the `unit == "tokens"` branch (lines 605-625) currently uses `row["headroom"]` directly. Change it to subtract open reservations for that harness once per call, before the loop. Replace the block starting right after `need_requests = max(1, int(estimated_requests or 1))` (line 598) and before `min_token_headroom = None` (line 599):

```python
    need_tokens = int(estimated_tokens) if estimated_tokens else 0
    need_requests = max(1, int(estimated_requests or 1))
    reserved = _pkg("_open_reservations_sum")(conn, agent)
    min_token_headroom = None
    min_request_headroom = None

    for row in rows:
        unit = row["unit"]
        headroom = row["headroom"]
        if unit == "tokens":
            headroom = max(0, headroom - reserved)
```

Then in the same `unit == "tokens"` branch, all subsequent uses of `headroom` in that branch (the `min_token_headroom` comparisons, the two `return` dicts at lines ~611-617 and ~619-625) already reference the local `headroom` variable, so they pick up the adjusted value automatically once the line above overwrites it -- no other line in the `tokens` branch needs to change. The `requests` branch (`elif unit == "requests":`) is untouched: reservations are token-denominated only per the spec, so request-unit headroom is not adjusted.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_quota_tracking.py::test_quota_status_subtracts_open_reservations -v`
Expected: PASS

- [ ] **Step 5: Run the full quota test file to check for regressions**

Run: `pytest tests/test_agent_quota_tracking.py -v`
Expected: all pass (existing tests use no reservations, so `_open_reservations_sum` returns 0 and headroom math is unchanged for them).

- [ ] **Step 6: Commit**

```bash
git add synlynk/quota.py tests/test_agent_quota_tracking.py
git commit -m "fix: subtract open reservations from quota headroom"
```

---

### Task 4: `_force_exhaust_quota()` + wire into sentinel's `QUOTA_EXHAUSTED` detection

**Files:**
- Modify: `synlynk/quota.py` (add function after `_open_reservations_sum`)
- Modify: `synlynk/__init__.py:85-95` (re-export)
- Modify: `synlynk/sentinel.py:475-486` (`check_sentinel_patterns`)
- Test: `tests/test_agent_quota_tracking.py`, new sentinel test in `tests/test_sentinel_quota_exhaustion.py`

- [ ] **Step 1: Write failing test for `_force_exhaust_quota` itself**

```python
def test_force_exhaust_quota_zeroes_headroom_not_running_jobs(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=50_000, used_tokens=1_000, unit="tokens", conn=conn
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, started_at) "
        "VALUES ('job-running-1', 'codex', 'do work', 'running', '2026-08-08T00:00:00', '2026-08-08T00:00:00')"
    )
    conn.commit()

    sl._force_exhaust_quota(conn, "codex", "5h")

    row = conn.execute(
        "SELECT limit_tokens, used_tokens FROM agent_quotas WHERE agent='codex' AND quota_type='5h'"
    ).fetchone()
    assert row[1] == row[0]  # used == limit -> headroom 0

    status = sl._quota_status_for_agent(conn, "codex", estimated_tokens=1)
    assert status["status"] == "exhausted"

    # running job must be untouched
    job_status = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id='job-running-1'"
    ).fetchone()[0]
    assert job_status == "running"


def test_force_exhaust_quota_creates_row_when_none_exists(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    sl._force_exhaust_quota(conn, "grok", "hourly")
    row = conn.execute(
        "SELECT limit_tokens, used_tokens FROM agent_quotas WHERE agent='grok' AND quota_type='hourly'"
    ).fetchone()
    assert row == (0, 0)
    status = sl._quota_status_for_agent(conn, "grok", estimated_tokens=0)
    assert status["status"] == "exhausted"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agent_quota_tracking.py -k "force_exhaust" -v`
Expected: FAIL — `AttributeError: module 'synlynk' has no attribute '_force_exhaust_quota'`

- [ ] **Step 3: Implement `_force_exhaust_quota()` in `synlynk/quota.py`**

Insert after `_open_reservations_sum`:

```python
def _force_exhaust_quota(conn, harness: str, window: str) -> None:
    """Reactive correction: zeroes `harness`'s headroom for `window` immediately,
    from a real observed rejection signal (see sentinel.py QUOTA_EXHAUSTED).

    Never touches daemon_jobs -- running jobs keep running (wait/resume policy).
    If no agent_quotas row exists yet for this harness/window, creates a
    zero-headroom placeholder row so the next _quota_status_for_agent() call
    sees it as exhausted rather than "unknown" (degraded, non-blocking).
    """
    if window not in QUOTA_TYPES:
        window = "5h"
    rows = conn.execute(
        "SELECT model, unit, limit_tokens FROM agent_quotas WHERE agent=? AND quota_type=?",
        (harness, window),
    ).fetchall()
    if not rows:
        _upsert_agent_quota(
            harness, window, limit_tokens=0, used_tokens=0, unit="tokens", conn=conn
        )
        return
    for model, unit, limit_tokens in rows:
        conn.execute(
            "UPDATE agent_quotas SET used_tokens=?, updated_at=CURRENT_TIMESTAMP "
            "WHERE agent=? AND model=? AND quota_type=? AND unit=?",
            (int(limit_tokens), harness, model, window, unit),
        )
    conn.commit()
```

- [ ] **Step 4: Re-export from `synlynk/__init__.py`**

Add `_force_exhaust_quota` to the `from synlynk.quota import (...)` block (alphabetically, before `_open_reservation`):

```python
from synlynk.quota import (
    _estimate_story_cost_usd,
    _force_exhaust_quota,
    _open_reservation,
    _open_reservations_sum,
    _project_request_quota_from_config,
    _quota_headroom,
    _quota_status_for_agent,
    _read_agent_quota_rows,
    _refresh_agent_quotas_from_telemetry,
    _release_reservation,
    _upsert_agent_quota,
    cmd_quota,
    refresh_agent_quotas_from_telemetry,
)
```

- [ ] **Step 5: Run quota tests to verify they pass**

Run: `pytest tests/test_agent_quota_tracking.py -k "force_exhaust" -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Write failing test for the sentinel wiring**

Create `tests/test_sentinel_quota_exhaustion.py`:

```python
"""Tests that sentinel's QUOTA_EXHAUSTED detection actually corrects agent_quotas."""


def test_quota_exhausted_detection_calls_force_exhaust(project_dir):
    import synlynk as sl
    from synlynk.sentinel import check_sentinel_patterns

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "claude", "5h", limit_tokens=200_000, used_tokens=1_000, unit="tokens", conn=conn
    )

    check_sentinel_patterns(
        output_text="Error: rate limit exceeded for this billing period",
        exit_code=1,
        cmd="claude --print",
    )

    row = conn.execute(
        "SELECT limit_tokens, used_tokens FROM agent_quotas WHERE agent='claude' AND quota_type='5h'"
    ).fetchone()
    assert row[1] == row[0]


def test_quota_exhausted_detection_noop_when_no_match(project_dir):
    import synlynk as sl
    from synlynk.sentinel import check_sentinel_patterns

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "claude", "5h", limit_tokens=200_000, used_tokens=1_000, unit="tokens", conn=conn
    )

    check_sentinel_patterns(
        output_text="All good, task complete.", exit_code=0, cmd="claude --print"
    )

    row = conn.execute(
        "SELECT used_tokens FROM agent_quotas WHERE agent='claude' AND quota_type='5h'"
    ).fetchone()
    assert row[0] == 1_000
```

- [ ] **Step 7: Run test to verify it fails**

Run: `pytest tests/test_sentinel_quota_exhaustion.py::test_quota_exhausted_detection_calls_force_exhaust -v`
Expected: FAIL — `used_tokens` still `1_000` (sentinel doesn't call `_force_exhaust_quota` yet).

- [ ] **Step 8: Wire the call into `synlynk/sentinel.py`**

In `check_sentinel_patterns()`, the `QUOTA_PATTERNS` match block is at `synlynk/sentinel.py:475-486`:

```python
    if output_text:
        lower = output_text.lower()
        for phrase in QUOTA_PATTERNS:
            if phrase.lower() in lower:
                cli = cmd.split()[0] if cmd else "agent"
                _write_sentinel_alert(
                    "CRITICAL", "QUOTA_EXHAUSTED",
                    f"`{cli}` — matched \"{phrase}\". "
                    "Check plan limits or switch agent CLI."
                )
                print(f"\n  \U0001f6a8 [QUOTA_EXHAUSTED] Matched \"{phrase}\" in output.")
                break
```

Change it to (add the `_force_exhaust_quota` call right after the existing print, still inside the `if phrase.lower() in lower:` block, before `break`):

```python
    if output_text:
        lower = output_text.lower()
        for phrase in QUOTA_PATTERNS:
            if phrase.lower() in lower:
                cli = cmd.split()[0] if cmd else "agent"
                _write_sentinel_alert(
                    "CRITICAL", "QUOTA_EXHAUSTED",
                    f"`{cli}` — matched \"{phrase}\". "
                    "Check plan limits or switch agent CLI."
                )
                print(f"\n  \U0001f6a8 [QUOTA_EXHAUSTED] Matched \"{phrase}\" in output.")
                try:
                    from synlynk import _get_db, _force_exhaust_quota
                    _quota_conn = _get_db()
                    try:
                        _force_exhaust_quota(_quota_conn, cli, "5h")
                    finally:
                        _quota_conn.close()
                except Exception:
                    pass
                break
```

`cli` (the first token of `cmd`, e.g. `"claude"`) is already the harness identifier — this reuses the existing variable rather than introducing a new one. `"5h"` is used as the window because it's the shortest/most common quota window and the exhaustion phrase itself doesn't identify which window was hit; this is a deliberate conservative default, not a full disambiguation (the spec's "Reactive Correction" section documents that vendor-side rejection detail isn't observable). Wrapped in `try/except Exception: pass` matching this module's existing defensive style (e.g. `check_model_rates_freshness`'s callers) so a DB error never prevents the alert itself from being written.

- [ ] **Step 9: Run tests to verify they pass**

Run: `pytest tests/test_sentinel_quota_exhaustion.py -v`
Expected: PASS (2 tests)

- [ ] **Step 10: Commit**

```bash
git add synlynk/quota.py synlynk/__init__.py synlynk/sentinel.py tests/test_agent_quota_tracking.py tests/test_sentinel_quota_exhaustion.py
git commit -m "feat: wire QUOTA_EXHAUSTED sentinel detection to _force_exhaust_quota"
```

---

### Task 5: `dispatch_agent()` — unconditional quota gate + reservation open + defer-not-raise

**Files:**
- Modify: `synlynk/dispatch.py:1635-1714`
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write failing tests**

```python
def test_dispatch_agent_defers_when_quota_exhausted(project_dir, monkeypatch):
    """Even with --force-agent, dispatch_agent must not bypass the quota gate."""
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=1_000, used_tokens=1_000, unit="tokens", conn=conn
    )

    result = sl.dispatch_agent(
        "codex", "do a small task", force_agent=True, skip_preflight=True
    )

    assert result.get("deferred") is True
    assert result["reason"]
    assert "retry_after" in result

    # A daemon_jobs row must exist, queued, with blocked_reason set
    row = conn.execute(
        "SELECT status, blocked_reason FROM daemon_jobs WHERE agent='codex' "
        "ORDER BY enqueued_at DESC LIMIT 1"
    ).fetchone()
    assert row == ("queued", "quota_exhausted")


def test_dispatch_agent_opens_reservation_when_headroom_exists(project_dir, monkeypatch):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=100_000, used_tokens=0, unit="tokens", conn=conn
    )

    calls = {}

    def fake_popen(*args, **kwargs):
        class _P:
            pid = 12345
        return _P()

    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)

    sl.dispatch_agent("codex", "do a small task", force_agent=True, skip_preflight=True)

    reservations = conn.execute(
        "SELECT harness, status FROM agent_reservations WHERE harness='codex'"
    ).fetchall()
    assert len(reservations) == 1
    assert reservations[0] == ("codex", "open")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py -k "quota_exhausted or opens_reservation" -v`
Expected: FAIL — `result.get("deferred")` is `None` (quota gate currently bypassed under `force_agent=True`); no `agent_reservations` row exists.

- [ ] **Step 3: Locate the exact insertion point**

In `synlynk/dispatch.py`, the existing bypass is at line 1656:

```python
    if story_id and not force_agent:
        best_agent = _pkg("_best_agent_for_story")
        if best_agent:
            best = best_agent(story_id)
            if best and best in baselines_map:
                agent = best
```

This block stays as-is (it's the *routing* decision — which harness to pick — and `force_agent=True` correctly still means "don't let routing override my chosen harness"). The new unconditional *budget* check goes after `agent` is fully finalized: after the `requires_gh_write` rerouting block and the unknown-agent validation, i.e. right after line 1689 (`raise ValueError(f"Unknown agent: '{agent}'. Known: {list(baselines_map)}")`), and before the `resolve_or_create_story_id` call at line 1691. Job id must exist before opening a reservation tied to it, so generate `job_id` here (reusing the same md5 scheme already used later at line 1846, deduplicated in Step 5 below) rather than waiting until line 1844.

- [ ] **Step 4: Implement the gate**

Replace the block from line 1688-1690 (`if agent not in baselines_map: ... resolve_or_create_story_id = ...`) with:

```python
    if agent not in baselines_map:
        raise ValueError(f"Unknown agent: '{agent}'. Known: {list(baselines_map)}")

    import hashlib as _hashlib_early
    if not job_id:
        _job_seed = dispatch_time if dispatch_time is not None else time.time()
        job_id = "job-" + _hashlib_early.md5(f"{agent}{task}{_job_seed}".encode()).hexdigest()[:8]

    get_db_fn = _pkg("_get_db")
    if get_db_fn:
        _quota_conn = get_db_fn()
        try:
            resolve_story_fn = _pkg("resolve_or_create_story_id")
            _est_tokens = None
            if story_id and resolve_story_fn:
                _row = _quota_conn.execute(
                    "SELECT estimated_tokens FROM stories WHERE story_id=?", (story_id,)
                ).fetchone()
                if _row and _row[0]:
                    _est_tokens = int(_row[0])
            if _est_tokens is None:
                # Ad-hoc call with no story estimate: rough heuristic, ~4 chars/token.
                _est_tokens = max(1000, len(task) // 4)

            quota_status_fn = _pkg("_quota_status_for_agent")
            qstatus = quota_status_fn(_quota_conn, agent, estimated_tokens=_est_tokens) \
                if quota_status_fn else {"status": "unknown", "degraded": True}

            if qstatus.get("status") == "exhausted":
                reset_at = None
                rows_fn = _pkg("_read_agent_quota_rows")
                if rows_fn:
                    for _r in (rows_fn(_quota_conn, agent) or []):
                        if _r.get("reset_at"):
                            reset_at = _r["reset_at"]
                            break
                now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
                _quota_conn.execute(
                    "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, "
                    "priority, depends_on, enqueued_at, blocked_reason) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (job_id, agent, task, story_id, "queued", 5, "[]", now_iso,
                     "quota_exhausted"),
                )
                _quota_conn.commit()
                return {
                    "deferred": True,
                    "reason": qstatus.get("reason", "quota_exhausted"),
                    "retry_after": reset_at,
                    "job_id": job_id,
                }

            open_reservation_fn = _pkg("_open_reservation")
            if open_reservation_fn:
                _scope = "plan" if os.environ.get("SYNLYNK_SCHEDULE_RUN_ID") else "session"
                open_reservation_fn(
                    _quota_conn, agent, _est_tokens, scope=_scope,
                    scope_id=os.environ.get("SYNLYNK_SCHEDULE_RUN_ID"), job_id=job_id,
                )
        finally:
            _quota_conn.close()

    resolve_or_create_story_id = _pkg("resolve_or_create_story_id")
```

Note: `force_agent=True` no longer means "skip the budget check" — it only means "don't let `_best_agent_for_story()` pick a different harness" (the existing block at line 1656, untouched). This is exactly the bug fix the spec calls for at Dispatch-Time Flow step 1.

- [ ] **Step 5: Remove the now-duplicate `job_id` generation later in the function**

At the original line 1844-1846 (`import hashlib as _hashlib` / `if not job_id: ...`), this logic is now redundant since `job_id` is guaranteed set by Step 4 above. Delete those three lines (the `import hashlib as _hashlib` line and the `if not job_id:` block that follows it), since `job_id` is already bound by the time execution reaches that point.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -k "quota_exhausted or opens_reservation" -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Run the full dispatch test file to check for regressions**

Run: `pytest tests/test_dispatch.py tests/test_dispatch_local_agent.py tests/test_dispatch_cycle.py tests/test_agy_dispatch_fix.py tests/test_dispatch_github_identity.py tests/test_dispatch_context_mode_hint.py -v`
Expected: all pass. If any existing test dispatches an agent with no `agent_quotas` row present, `_quota_status_for_agent` returns `{"status": "unknown", "degraded": True}` (not `"exhausted"`), so the new gate is a no-op for them — existing behavior is preserved for the common "no quota data yet" case.

- [ ] **Step 8: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "fix: consult quota unconditionally in dispatch_agent, deferring instead of bypassing"
```

---

### Task 6: Fix `_dispatch_ready_jobs()` all-exhausted fall-through

**Files:**
- Modify: `synlynk/jobs.py:2034-2126`
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write failing test**

```python
def test_dispatch_ready_jobs_stays_queued_when_all_exhausted(project_dir, monkeypatch):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=1_000, used_tokens=1_000, unit="tokens", conn=conn
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, "
        "phase, estimated_tokens) VALUES (?,?,?,?,?,?,?)",
        ("story-exh1", "Exhaustion test", "backend", "platform", "ott", "build", 5_000),
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, priority, "
        "depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?,?)",
        ("job-exh1", "codex", "task", "story-exh1", "queued", 5, "[]",
         "2026-08-08T00:00:00"),
    )
    conn.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("dispatch_agent must not be called when all candidates exhausted")

    monkeypatch.setattr(sl, "dispatch_agent", fail_if_called)

    launched = sl._dispatch_ready_jobs(max_parallel=4)

    assert launched == 0
    status = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id='job-exh1'"
    ).fetchone()[0]
    assert status == "queued"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs.py::test_dispatch_ready_jobs_stays_queued_when_all_exhausted -v`
Expected: FAIL — `AssertionError: dispatch_agent must not be called when all candidates exhausted` (current fall-through calls it anyway).

- [ ] **Step 3: Locate and fix the fall-through**

In `synlynk/jobs.py`, inside `_dispatch_ready_jobs()`, the loop body (starting at line 2060) currently does not consult quota at all before calling `dispatch_fn`. Read the segment from line 2082 onward (`dispatch_fn = _pkg("dispatch_agent")`) through the dispatch call — per the earlier read, this calls `dispatch_fn(agent, task, story_id=story_id, force_agent=True, job_id=job_id)` around line 2086-2092.

Since Task 5 already made `dispatch_agent()` itself consult quota unconditionally and return `{"deferred": True, ...}` instead of dispatching when exhausted, `_dispatch_ready_jobs()` needs to handle that return value instead of treating every non-exception return as a launch. Replace the section that calls `dispatch_fn` and handles its result with:

```python
            try:
                result = dispatch_fn(
                    agent, task, story_id=story_id, force_agent=True, job_id=job_id
                )
            except (RuntimeError, ValueError) as e:
                conn.execute(
                    "UPDATE daemon_jobs SET status='failed', completed_at=? WHERE job_id=?",
                    (now, job_id),
                )
                conn.commit()
                continue

            if isinstance(result, dict) and result.get("deferred"):
                # Stays 'queued' -- dispatch_agent() already wrote blocked_reason.
                # Do not advance launched count; try the next candidate instead.
                continue
```

This replaces whatever unconditional "mark running" logic previously followed the dispatch call unconditionally — the existing `UPDATE daemon_jobs SET status='running', pid=..., started_at=..., log_path=...` block (previously reached for every non-exception return) now only runs when `result` is not a deferred dict, i.e. keep that existing block as the `else` path implicitly (it already only runs code after this new early-`continue`, so no further restructuring is needed beyond inserting the `if isinstance(result, dict) and result.get("deferred"): continue` guard right after the try/except).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs.py::test_dispatch_ready_jobs_stays_queued_when_all_exhausted -v`
Expected: PASS

- [ ] **Step 5: Run the full jobs test file to check for regressions**

Run: `pytest tests/test_jobs.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "fix: _dispatch_ready_jobs keeps job queued instead of falling through to exhausted harness"
```

---

### Task 7: Release reservation on job settlement in `_reconcile_daemon_jobs()`

**Files:**
- Modify: `synlynk/jobs.py:1895-2030` (`_reconcile_daemon_jobs`)
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write failing test**

```python
def test_reconcile_releases_reservation_on_settlement(project_dir, monkeypatch):
    import synlynk as sl
    import os

    conn = sl._get_db()
    rid = sl._open_reservation(conn, "codex", 4_000, scope="adhoc", job_id="job-settle1")
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, started_at) "
        "VALUES ('job-settle1', 'codex', 'task', 'running', 999999, "
        "'2026-08-08T00:00:00', '2026-08-08T00:00:00')"
    )
    conn.commit()

    # pid 999999 should not exist -- reconcile will treat it as exited/dead
    monkeypatch.setattr(sl, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(sl, "extract_tokens", lambda log_text, agent=None: (0, 0))
    monkeypatch.setattr(sl, "extract_model_version", lambda log_text, agent=None: "unknown")
    monkeypatch.setattr(sl, "update_costs", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_write_job_summary", lambda *a, **k: None)

    sl._reconcile_daemon_jobs()

    status = conn.execute(
        "SELECT status FROM agent_reservations WHERE id=?", (rid,)
    ).fetchone()[0]
    assert status == "released"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs.py::test_reconcile_releases_reservation_on_settlement -v`
Expected: FAIL — reservation status still `"open"` (nothing releases it yet).

- [ ] **Step 3: Wire the release call**

In `synlynk/jobs.py`, `_reconcile_daemon_jobs()` has two `UPDATE daemon_jobs SET status=...` sites that transition a row out of `running`:

1. The "preferred" terminal-summary-truth path at lines 1949-1954 (`status, exit_code = preferred` then `UPDATE ... WHERE job_id=? AND status='running'`, followed by `continue`).
2. The main path at lines 1968-1973 (`UPDATE daemon_jobs SET status=?, exit_code=?, completed_at=? WHERE job_id=?`), which is reached for the `done`/`timed_out`/`failed` classification.

Add a reservation-release call right after each of these two `UPDATE`+`commit()` pairs, using the already-in-scope `job_id` loop variable. After line 1954 (`conn.commit()` following the "preferred" path's UPDATE), insert:

```python
                    release_fn = _pkg("_release_reservation")
                    if release_fn:
                        _res_row = conn.execute(
                            "SELECT id FROM agent_reservations WHERE job_id=? AND status='open'",
                            (job_id,),
                        ).fetchone()
                        if _res_row:
                            release_fn(conn, _res_row[0])
```

(insert this immediately before the existing `# Do not rewrite summary / re-bill costs — truth already on disk.` comment and its `continue`, i.e. right after the `conn.commit()` at line 1954).

After line 1973 (`conn.commit()` following the main path's UPDATE), insert the identical block:

```python
                release_fn = _pkg("_release_reservation")
                if release_fn:
                    _res_row = conn.execute(
                        "SELECT id FROM agent_reservations WHERE job_id=? AND status='open'",
                        (job_id,),
                    ).fetchone()
                    if _res_row:
                        release_fn(conn, _res_row[0])
```

(note the different indentation level between the two insertion points — the "preferred" path is nested one level deeper inside the `if preferred is not None:` block than the main path).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs.py::test_reconcile_releases_reservation_on_settlement -v`
Expected: PASS

- [ ] **Step 5: Run the full jobs test file to check for regressions**

Run: `pytest tests/test_jobs.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat: release agent_reservations on daemon job settlement"
```

---

### Task 8: `scheduler.py`'s `_enqueue_plan()` opens real reservations at batch-commit time

**Files:**
- Modify: `synlynk/scheduler.py:156-192` (`_enqueue_plan`)
- Test: `tests/test_fleet_scheduler.py`

- [ ] **Step 1: Write failing test**

```python
def test_enqueue_plan_opens_reservations(project_dir):
    from synlynk.scheduler import _enqueue_plan
    import synlynk as sl

    plan = [
        {
            "story_id": "story-sched1",
            "title": "Sched test",
            "agent": "codex",
            "score": 1.0,
            "model": "unknown",
            "priority": 5,
            "estimated_tokens": 7_000,
            "headroom_before": 100_000,
            "headroom_after": 93_000,
        },
    ]

    job_ids = _enqueue_plan(plan)
    assert len(job_ids) == 1

    conn = sl._get_db()
    rows = conn.execute(
        "SELECT harness, tokens, scope, job_id, status FROM agent_reservations "
        "WHERE job_id=?",
        (job_ids[0],),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][:3] == ("codex", 7_000, "plan")
    assert rows[0][4] == "open"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fleet_scheduler.py::test_enqueue_plan_opens_reservations -v`
Expected: FAIL — no `agent_reservations` rows exist for the job (nothing opens them yet).

- [ ] **Step 3: Implement in `_enqueue_plan()`**

In `synlynk/scheduler.py`, `_enqueue_plan()` (lines 156-192) currently does:

```python
    from synlynk import _get_db

    conn = _get_db()
    job_ids = []
    try:
        for item in plan:
            story_id = item["story_id"]
            agent = item["agent"]
            task = f"Implement {story_id}: {item.get('title') or story_id}"
            job_id = "djob-" + hashlib.md5(
                f"{agent}{task}{time.time()}".encode()
            ).hexdigest()[:8]
            # Distinguish home vs headless dispatch context; detection logic itself is future work (issue #740).
            dispatch_context = "unknown"
            conn.execute(
                "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, "
                "priority, depends_on, enqueued_at, dispatch_context) VALUES (?,?,?,?,?,?,?,?,?)",
                (job_id, agent, task, story_id, "queued",
                 item.get("priority", 5), "[]",
                 time.strftime("%Y-%m-%dT%H:%M:%S"), dispatch_context),
            )
            job_ids.append(job_id)
        conn.commit()
    finally:
        conn.close()
    return job_ids
```

Change the import line and add a reservation-open call inside the loop:

```python
    from synlynk import _get_db, _open_reservation

    conn = _get_db()
    job_ids = []
    run_id = "sched-" + hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    try:
        for item in plan:
            story_id = item["story_id"]
            agent = item["agent"]
            task = f"Implement {story_id}: {item.get('title') or story_id}"
            job_id = "djob-" + hashlib.md5(
                f"{agent}{task}{time.time()}".encode()
            ).hexdigest()[:8]
            # Distinguish home vs headless dispatch context; detection logic itself is future work (issue #740).
            dispatch_context = "unknown"
            conn.execute(
                "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, "
                "priority, depends_on, enqueued_at, dispatch_context) VALUES (?,?,?,?,?,?,?,?,?)",
                (job_id, agent, task, story_id, "queued",
                 item.get("priority", 5), "[]",
                 time.strftime("%Y-%m-%dT%H:%M:%S"), dispatch_context),
            )
            _open_reservation(
                conn, agent, int(item.get("estimated_tokens") or 0),
                scope="plan", scope_id=run_id, job_id=job_id,
            )
            job_ids.append(job_id)
        conn.commit()
    finally:
        conn.close()
    return job_ids
```

`run_id` is generated once per `_enqueue_plan()` call so every reservation opened by the same batch shares one `scope_id` — this is the "schedule-run-id" the spec's `scheduler.py` Changes section refers to.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fleet_scheduler.py::test_enqueue_plan_opens_reservations -v`
Expected: PASS

- [ ] **Step 5: Run the full scheduler test file to check for regressions**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: all pass. `_compute_schedule_plan()` itself is untouched (per the spec, it becomes reservation-aware "for free" through `_quota_status_for_agent()`'s Task 3 change) — its existing tests should be unaffected since they don't pre-populate `agent_reservations`.

- [ ] **Step 6: Commit**

```bash
git add synlynk/scheduler.py tests/test_fleet_scheduler.py
git commit -m "feat: open real reservations when committing a batch schedule plan"
```

---

### Task 9: TPM hook stubs — `synlynk/tpm_hooks.py`

**Files:**
- Create: `synlynk/tpm_hooks.py`
- Test: `tests/test_tpm_hooks.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tpm_hooks.py`:

```python
"""Tests for the TPM hook stub surface (synlynk/tpm_hooks.py).

These are narrow, independently-testable pure functions -- not a TPM agent
implementation, but the stable surface a future role='tpm' dispatch calls
instead of touching agent_reservations / daemon_jobs directly. See the
Naming Collision section of the design spec: `harness` here always means the
core CLI binary (claude/agy/codex/grok/local), never the functional role.
"""
import pytest


def test_tpm_observe_reservations_returns_open_reservations(project_dir):
    import synlynk as sl
    from synlynk.tpm_hooks import tpm_observe_reservations

    conn = sl._get_db()
    sl._open_reservation(conn, "claude", 2_000, scope="session")
    sl._open_reservation(conn, "codex", 3_000, scope="plan", scope_id="run-1")

    result = tpm_observe_reservations(conn)
    harnesses = {r["harness"] for r in result}
    assert harnesses == {"claude", "codex"}

    scoped = tpm_observe_reservations(conn, scope="plan", scope_id="run-1")
    assert len(scoped) == 1
    assert scoped[0]["harness"] == "codex"


def test_tpm_reorder_queue_updates_priorities(project_dir):
    import synlynk as sl
    from synlynk.tpm_hooks import tpm_reorder_queue

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, enqueued_at) "
        "VALUES ('job-r1', 'codex', 't', 'queued', 5, '2026-08-08T00:00:00')"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, enqueued_at) "
        "VALUES ('job-r2', 'agy', 't', 'queued', 5, '2026-08-08T00:00:00')"
    )
    conn.commit()

    changed = tpm_reorder_queue(conn, {"job-r1": 1, "job-r2": 9})
    assert changed == 2

    rows = dict(conn.execute(
        "SELECT job_id, priority FROM daemon_jobs WHERE job_id IN ('job-r1','job-r2')"
    ).fetchall())
    assert rows == {"job-r1": 1, "job-r2": 9}


def test_tpm_reallocate_moves_reservation_and_agent(project_dir):
    import synlynk as sl
    from synlynk.tpm_hooks import tpm_reallocate

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, enqueued_at) "
        "VALUES ('job-realloc1', 'codex', 't', 'queued', 5, '2026-08-08T00:00:00')"
    )
    rid = sl._open_reservation(conn, "codex", 5_000, scope="adhoc", job_id="job-realloc1")
    conn.commit()

    result = tpm_reallocate(conn, "job-realloc1", "agy")

    assert result["job_id"] == "job-realloc1"
    assert result["new_harness"] == "agy"

    new_agent = conn.execute(
        "SELECT agent FROM daemon_jobs WHERE job_id='job-realloc1'"
    ).fetchone()[0]
    assert new_agent == "agy"

    old_status = conn.execute(
        "SELECT status FROM agent_reservations WHERE id=?", (rid,)
    ).fetchone()[0]
    assert old_status == "released"

    new_res = conn.execute(
        "SELECT harness, tokens, status FROM agent_reservations "
        "WHERE job_id='job-realloc1' AND status='open'"
    ).fetchone()
    assert new_res == ("agy", 5_000, "open")


def test_tpm_reallocate_raises_when_not_queued(project_dir):
    import synlynk as sl
    from synlynk.tpm_hooks import tpm_reallocate

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, enqueued_at) "
        "VALUES ('job-running2', 'codex', 't', 'running', 5, '2026-08-08T00:00:00')"
    )
    conn.commit()

    with pytest.raises(ValueError):
        tpm_reallocate(conn, "job-running2", "agy")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tpm_hooks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.tpm_hooks'`

- [ ] **Step 3: Implement `synlynk/tpm_hooks.py`**

```python
"""TPM workspace-agent hook stubs.

Not a TPM agent implementation -- the stable, independently-testable surface
a future role='tpm' dispatch calls to observe/reorder/reallocate the
dispatch reservation ledger, instead of touching agent_reservations /
daemon_jobs directly. See the Naming Collision section of
docs/superpowers/specs/2026-08-08-quota-aware-dispatch-reservation-design.md:
`harness` here always means the core CLI binary identity
(claude/agy/codex/grok/local), `role` (not used by these functions directly,
but by their future caller) means the functional-taxonomy dimension
(stories.role: architect/dev/pm/tpm/qa/designer). Never conflate the two.
"""


def tpm_observe_reservations(conn, scope: str = None, scope_id: str = None) -> list:
    """Read-only: open reservations + live headroom per harness, optionally
    filtered to one plan/session scope. Backs `synlynk quota tpm-view`."""
    from synlynk import _open_reservations_sum, _quota_status_for_agent

    query = "SELECT id, harness, tokens, scope, scope_id, job_id, created_at FROM agent_reservations WHERE status='open'"
    params = []
    if scope:
        query += " AND scope=?"
        params.append(scope)
    if scope_id:
        query += " AND scope_id=?"
        params.append(scope_id)
    query += " ORDER BY created_at ASC"

    rows = conn.execute(query, params).fetchall()
    result = []
    seen_headroom = {}
    for rid, harness, tokens, res_scope, res_scope_id, job_id, created_at in rows:
        if harness not in seen_headroom:
            status = _quota_status_for_agent(conn, harness)
            seen_headroom[harness] = status.get("headroom")
        result.append({
            "id": rid,
            "harness": harness,
            "tokens": tokens,
            "scope": res_scope,
            "scope_id": res_scope_id,
            "job_id": job_id,
            "created_at": created_at,
            "current_headroom": seen_headroom[harness],
        })
    return result


def tpm_reorder_queue(conn, priorities: dict) -> int:
    """Bulk-update daemon_jobs.priority for {job_id: new_priority}. Returns rows
    changed. Pure reprioritization -- does not touch reservations or harnesses."""
    changed = 0
    for job_id, new_priority in priorities.items():
        cur = conn.execute(
            "UPDATE daemon_jobs SET priority=? WHERE job_id=? AND status='queued'",
            (int(new_priority), job_id),
        )
        changed += cur.rowcount
    conn.commit()
    return changed


def tpm_reallocate(conn, job_id: str, new_harness: str) -> dict:
    """Move a queued (not yet running) job's reservation from its current harness
    to new_harness: release old reservation, open new one, update daemon_jobs.agent.
    Raises if job_id is not status='queued' (can't reallocate a running/done job)."""
    from synlynk import _open_reservation, _release_reservation

    row = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No such job_id: {job_id!r}")
    if row[0] != "queued":
        raise ValueError(
            f"Cannot reallocate job_id={job_id!r}: status is {row[0]!r}, not 'queued'"
        )

    res_row = conn.execute(
        "SELECT id, tokens, scope, scope_id FROM agent_reservations "
        "WHERE job_id=? AND status='open'",
        (job_id,),
    ).fetchone()

    conn.execute("UPDATE daemon_jobs SET agent=? WHERE job_id=?", (new_harness, job_id))

    new_reservation_id = None
    if res_row:
        old_id, tokens, scope, scope_id = res_row
        _release_reservation(conn, old_id)
        new_reservation_id = _open_reservation(
            conn, new_harness, tokens, scope=scope, scope_id=scope_id, job_id=job_id
        )
    conn.commit()

    return {
        "job_id": job_id,
        "new_harness": new_harness,
        "new_reservation_id": new_reservation_id,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tpm_hooks.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/tpm_hooks.py tests/test_tpm_hooks.py
git commit -m "feat: add TPM hook stub functions (observe/reorder/reallocate)"
```

---

### Task 10: `synlynk quota tpm-view` CLI subcommand

**Files:**
- Modify: `synlynk/cli.py:740-754` (quota_parser args), `synlynk/cli.py:1174-1178` (quota command dispatch)
- Test: `tests/test_tpm_hooks.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_tpm_hooks.py`:

```python
def test_cli_quota_tpm_view_prints_reservations(project_dir, capsys):
    import synlynk as sl
    from synlynk.cli import main

    conn = sl._get_db()
    sl._open_reservation(conn, "claude", 4_500, scope="session")

    main(["quota", "--tpm-view"])

    out = capsys.readouterr().out
    assert "claude" in out
    assert "4,500" in out or "4500" in out
```

(If `synlynk/cli.py`'s entry point is not literally named `main` taking an argv list, adjust the call to match the actual CLI entry point signature used by other CLI tests in this file — check an existing CLI-invocation test in `tests/test_dispatch.py` or `tests/test_jobs.py` for the exact pattern used in this codebase before writing this step, since the entry point name was not directly confirmed during planning.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tpm_hooks.py::test_cli_quota_tpm_view_prints_reservations -v`
Expected: FAIL — `--tpm-view` is an unrecognized argument.

- [ ] **Step 3: Add the `--tpm-view` flag to the `quota` subparser**

In `synlynk/cli.py`, the `quota` subparser is defined at lines 740-754:

```python
    quota_parser = subparsers.add_parser(
        "quota",
        help="Show per-agent quota headroom / reset windows (5h, hourly, daily, weekly, monthly)",
    )
    quota_parser.add_argument(
        "--agent",
        default=None,
        help="Filter to a single agent (claude, agy, codex, grok, local)",
    )
    quota_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON",
    )
```

Add a fourth argument after `--json`:

```python
    quota_parser.add_argument(
        "--tpm-view",
        action="store_true",
        dest="tpm_view",
        help="Show open reservations across all harnesses (read-only TPM hook view)",
    )
```

- [ ] **Step 4: Add the dispatch branch**

At `synlynk/cli.py:1174-1178`, the current dispatch is:

```python
    elif args.command == "quota":
        cmd_quota(
            agent=getattr(args, "agent", None),
            json_output=getattr(args, "json_output", False),
        )
```

Change to:

```python
    elif args.command == "quota":
        if getattr(args, "tpm_view", False):
            cmd_quota_tpm_view()
        else:
            cmd_quota(
                agent=getattr(args, "agent", None),
                json_output=getattr(args, "json_output", False),
            )
```

- [ ] **Step 5: Add `cmd_quota_tpm_view()` to `synlynk/quota.py`**

Insert after `cmd_quota()` (after line 402):

```python
def cmd_quota_tpm_view() -> None:
    """Read-only CLI wrapper around tpm_observe_reservations() -- the one real
    caller that keeps that hook function from shipping as dead code."""
    from synlynk.tpm_hooks import tpm_observe_reservations

    conn = _pkg("_get_db")()
    try:
        reservations = tpm_observe_reservations(conn)
    finally:
        conn.close()

    if not reservations:
        print("  No open reservations.")
        return

    print(f"\n  {'Harness':<10} {'Tokens':>10} {'Scope':<10} {'Scope ID':<14} {'Job ID':<14} {'Headroom':>10}")
    print("  " + "-" * 72)
    for r in reservations:
        headroom = "unknown" if r["current_headroom"] is None else f"{r['current_headroom']:,}"
        print(
            f"  {r['harness']:<10} {r['tokens']:>10,} {r['scope']:<10} "
            f"{(r['scope_id'] or '-'):<14} {(r['job_id'] or '-'):<14} {headroom:>10}"
        )
```

- [ ] **Step 6: Wire `cmd_quota_tpm_view` into `synlynk/cli.py`'s imports**

Find how `cmd_quota` itself is imported into `cli.py` (grep `from synlynk` / `from synlynk.quota` near the top of `synlynk/cli.py`) and add `cmd_quota_tpm_view` to the same import statement, following the exact existing pattern for `cmd_quota`.

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_tpm_hooks.py::test_cli_quota_tpm_view_prints_reservations -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add synlynk/cli.py synlynk/quota.py tests/test_tpm_hooks.py
git commit -m "feat: add synlynk quota --tpm-view CLI command"
```

---

### Task 11: Integration tests — full reserve → dispatch → settle → release cycle, and exhaustion/resume

**Files:**
- Create: `tests/test_quota_reservation_integration.py`

- [ ] **Step 1: Write the integration tests**

```python
"""Integration coverage for the quota-aware dispatch reservation design.

Exercises the full lifecycle across the pieces built in Tasks 1-8: a batch
plan reserved via _enqueue_plan(), dispatched via _dispatch_ready_jobs(),
settled via _reconcile_daemon_jobs(), with reservations released at the end
-- and a second scenario proving a deferred (exhausted) job survives a
reset_at boundary and resumes automatically on a later poll, without
re-dispatching jobs already done. No live harness calls -- dispatch_agent
is monkeypatched to simulate success/failure without spawning a subprocess.
"""
import time


def _fake_dispatch_success(monkeypatch, sl):
    """Monkeypatches dispatch_agent to simulate a successful spawn without a
    real subprocess -- marks the job 'running' with a fake pid, matching what
    the real dispatch_agent would have done just before spawning."""
    def _fake(agent, task, story_id=None, force_agent=False, job_id=None, **kwargs):
        conn = sl._get_db()
        conn.execute(
            "UPDATE daemon_jobs SET status='running', pid=999999, started_at=? "
            "WHERE job_id=?",
            (time.strftime("%Y-%m-%dT%H:%M:%S"), job_id),
        )
        conn.commit()
        conn.close()
        return {"job_id": job_id, "pid": 999999}
    monkeypatch.setattr(sl, "dispatch_agent", _fake)


def test_full_reserve_dispatch_settle_release_cycle(project_dir, monkeypatch):
    import synlynk as sl
    from synlynk.scheduler import _enqueue_plan

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=100_000, used_tokens=0, unit="tokens", conn=conn
    )
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=100_000, used_tokens=0, unit="tokens", conn=conn
    )

    plan = [
        {"story_id": "story-int1", "title": "A", "agent": "codex", "score": 1.0,
         "model": "unknown", "priority": 5, "estimated_tokens": 10_000,
         "headroom_before": 100_000, "headroom_after": 90_000},
        {"story_id": "story-int2", "title": "B", "agent": "agy", "score": 1.0,
         "model": "unknown", "priority": 5, "estimated_tokens": 20_000,
         "headroom_before": 100_000, "headroom_after": 80_000},
    ]
    job_ids = _enqueue_plan(plan)
    assert len(job_ids) == 2

    open_count = conn.execute(
        "SELECT COUNT(*) FROM agent_reservations WHERE status='open'"
    ).fetchone()[0]
    assert open_count == 2

    _fake_dispatch_success(monkeypatch, sl)
    monkeypatch.setattr(sl, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(sl, "extract_tokens", lambda log_text, agent=None: (0, 0))
    monkeypatch.setattr(sl, "extract_model_version", lambda log_text, agent=None: "unknown")
    monkeypatch.setattr(sl, "update_costs", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_write_job_summary", lambda *a, **k: None)

    launched = sl._dispatch_ready_jobs(max_parallel=4)
    assert launched == 2

    running_count = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE status='running'"
    ).fetchone()[0]
    assert running_count == 2

    sl._reconcile_daemon_jobs()

    for job_id in job_ids:
        status = conn.execute(
            "SELECT status FROM daemon_jobs WHERE job_id=?", (job_id,)
        ).fetchone()[0]
        assert status in ("done", "timed_out", "failed")

    open_count_after = conn.execute(
        "SELECT COUNT(*) FROM agent_reservations WHERE status='open'"
    ).fetchone()[0]
    assert open_count_after == 0
    released_count = conn.execute(
        "SELECT COUNT(*) FROM agent_reservations WHERE status='released'"
    ).fetchone()[0]
    assert released_count == 2


def test_deferred_job_survives_reset_and_resumes_without_redispatch(project_dir, monkeypatch):
    import synlynk as sl

    conn = sl._get_db()
    # codex is fully exhausted with a reset_at in the near past (already reopened)
    past_reset = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 60))
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=10_000, used_tokens=10_000, unit="tokens",
        reset_at=past_reset, conn=conn,
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, enqueued_at, blocked_reason) VALUES (?,?,?,?,?,?,?,?)",
        ("job-deferred1", "codex", "task", "queued", 5, "[]",
         "2026-08-08T00:00:00", "quota_exhausted"),
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?)",
        ("job-already-done1", "codex", "task", "done", 5, "[]", "2026-08-08T00:00:00"),
    )
    conn.commit()

    # First poll: codex still shows exhausted in agent_quotas (used==limit) even
    # though reset_at has passed -- refresh_agent_quotas_from_telemetry is what
    # normally clears this in production; here we simulate the post-reset state
    # directly by refreshing the row, matching what the daemon poll loop
    # effectively achieves once telemetry reflects the new window.
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=10_000, used_tokens=0, unit="tokens",
        reset_at=None, conn=conn,
    )

    _fake_dispatch_success(monkeypatch, sl)

    launched = sl._dispatch_ready_jobs(max_parallel=4)
    assert launched == 1

    status = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id='job-deferred1'"
    ).fetchone()[0]
    assert status == "running"

    already_done_status = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id='job-already-done1'"
    ).fetchone()[0]
    assert already_done_status == "done"  # untouched, not re-dispatched
```

- [ ] **Step 2: Run tests to verify they fail (before Tasks 1-8 land) or pass (after)**

Run: `pytest tests/test_quota_reservation_integration.py -v`

If run after Tasks 1-8 are complete (the expected order in this plan): PASS (2 tests). If any test fails, use the failure to identify which earlier task's wiring is incomplete — this file is a cross-cutting check, not a new-feature TDD step, so a failure here means go back to the relevant task, not that this test is wrong.

- [ ] **Step 3: Commit**

```bash
git add tests/test_quota_reservation_integration.py
git commit -m "test: add integration coverage for full reservation lifecycle and defer/resume"
```

---

### Task 12: Full regression suite + README documentation

**Files:**
- Modify: `README.md` (or wherever `synlynk quota` / `synlynk schedule` are currently documented — grep for `synlynk quota` in `README.md` first)
- Test: entire suite

- [ ] **Step 1: Grep for existing `synlynk quota` / `synlynk schedule` documentation**

Run: `grep -n "synlynk quota\|synlynk schedule" README.md`

- [ ] **Step 2: Add documentation for the new behavior**

Near the existing `synlynk quota` documentation in `README.md`, add a short paragraph (adapt exact wording/formatting to match the surrounding doc style found in Step 1):

```markdown
`synlynk quota` headroom now accounts for open reservations, not just
telemetry-recorded usage — every dispatch path (ad-hoc, `--force-agent`,
daemon-queued, batch-scheduled via `synlynk schedule --execute`) reserves
estimated tokens against a harness before it fires and releases the
reservation once real usage lands. When headroom is insufficient, dispatch
defers (stays `queued` with `blocked_reason=quota_exhausted`) rather than
failing — it resumes automatically once the harness's quota window resets,
picked up by the next `synlynk watch` daemon poll. Use `synlynk quota
--tpm-view` to see all open reservations across harnesses.
```

- [ ] **Step 3: Run the entire test suite**

Run: `pytest tests/`
Expected: `1730 + N passed, 2 skipped` where `N` is the total new test count added across Tasks 1-11 (roughly 20-24 new tests). Zero failures, zero new skips.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document quota-aware dispatch reservation behavior"
```

---

## Self-Review

**Spec coverage:**
- Naming Collision rule (harness vs role, never conflated) → enforced throughout: every new function signature uses `harness`, `tpm_hooks.py` docstring states the rule explicitly. ✅
- Goal 1 (one shared ledger, every dispatch path) → Task 5 (`dispatch_agent`), Task 6 (`_dispatch_ready_jobs`), Task 8 (`_enqueue_plan`) all route through the same `agent_reservations` table and `_quota_status_for_agent()`. ✅
- Goal 2 (fix bypass + fall-through as part of wiring, not separate patches) → Task 5 Step 3 explicitly removes the `force_agent` bypass semantics; Task 6 fixes the fall-through in the same change that makes `_dispatch_ready_jobs` respect `dispatch_agent`'s new deferred-return contract. ✅
- Goal 3 (auto-defer, never hard-fail) → Task 5 Step 4 returns `{"deferred": True, ...}` instead of raising; Task 6 keeps deferred jobs `queued`. ✅
- Goal 4 (TPM hooks, narrow surface) → Task 9 (three pure functions), Task 10 (one real caller via CLI). ✅
- Goal 5 (document limitation + reactive correction) → Task 4 (`_force_exhaust_quota` + sentinel wiring); the spec's prose limitation itself is already committed in the design doc, no code task needed for that half. ✅
- Data Model (`agent_reservations` schema) → Task 1, exact column-for-column match to spec SQL. ✅
- Dispatch-Time Flow steps 1-5 → Task 5 (steps 1-3), Task 6 (step 4), Task 7 (step 5). ✅
- Wait/resume policy → Task 5's defer-not-raise + Task 6's stays-queued + Task 11's resume-without-redispatch integration test directly verifies "no explicit resume command needed." ✅
- `scheduler.py` Changes → Task 8; `_compute_schedule_plan()` explicitly left unchanged per spec (noted in Task 8 Step 5). ✅
- Reactive Correction → Task 4. ✅
- TPM Hook Stubs (exact 3 signatures) → Task 9, signatures copied verbatim from spec. ✅
- Deferred Follow-Ups → not implementation tasks by design (issues #786/#787 already filed; plan-limit calibration explicitly deferred per spec, no task needed). ✅
- Testing Approach (unit/integration/regression, no live harness calls) → Tasks 1-9 are unit-level against tmp sqlite; Task 11 is the integration scenario; Task 12 is the regression gate. All dispatch-triggering tests monkeypatch `subprocess.Popen`/`dispatch_agent` rather than spawning real CLIs. ✅

**Placeholder scan:** no TBD/TODO/"add appropriate handling" language found in any task — re-checked while writing this section.

**Type consistency:** `_open_reservation(conn, harness, tokens, scope, scope_id=None, job_id=None) -> int` used identically in Tasks 2, 5, 7, 8, 9. `_release_reservation(conn, reservation_id) -> None` used identically in Tasks 2, 7, 9. `_quota_status_for_agent(conn, agent, estimated_tokens=None, estimated_requests=1) -> dict` — parameter name stays `agent` (existing signature, unchanged) even though callers increasingly think of it as a harness; not renamed per the spec's explicit non-goal. `tpm_observe_reservations(conn, scope=None, scope_id=None) -> list`, `tpm_reorder_queue(conn, priorities: dict) -> int`, `tpm_reallocate(conn, job_id, new_harness) -> dict` match the spec's stub signatures exactly across Tasks 9 and 10.
