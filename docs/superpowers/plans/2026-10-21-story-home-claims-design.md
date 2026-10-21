# Story Home Claims Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing `task_leases` story-claim mechanism (gh:#1507) actually enforce the "same story, two interactive sessions" conflict described in gh:#2511 — add harness/PID identity so dead/foreign sessions don't block, and wire acquire/heartbeat/release into real CLI entry points, since nothing in the codebase currently calls `acquire_task_lease`/`renew_task_lease`/`release_task_lease` at all.

**Architecture:** Extend the dead-but-already-shaped `task_leases` table (in `synlynk/db_schema.py`, logic in `synlynk/jobs.py`) rather than creating a parallel `story_home_claims` table as the design spec originally proposed — the spec's proposed schema and the existing `task_leases` table are the same concept (TTL + heartbeat + story_id-scoped lease), and running two lease tables against the same `stories.status` field would itself create the duplicated-effort problem gh:#2511 exists to prevent. Add `pid` and `harness` columns via the existing `ALTER TABLE ... ADD COLUMN` + `PRAGMA table_info` guard pattern already used for `stories`/`backlog_items` in `synlynk/db.py`. Add dead-PID detection (mirroring `worktree_lease.py`'s `_is_pid_alive`). Wire `synlynk story claim`, `synlynk exec`'s heartbeat, `synlynk story done`, and `execute_home_handover` to the existing functions. Extend `reclaim_stranded_stories` to also sweep dead-PID claims, not just missing-daemon-job claims.

**Tech Stack:** Python 3 stdlib only (sqlite3, os.kill for PID liveness), existing `synlynk.wal_ledger.write_transaction` for write safety, pytest for tests.

**Note on the design spec:** `docs/superpowers/specs/2026-10-21-story-home-claims-design.md` proposed a new `story_home_claims` table and a new `synlynk/story_claims.py` module. Planning discovered `synlynk/jobs.py` already has `acquire_task_lease`/`renew_task_lease`/`release_task_lease`/`get_active_lease` against a `task_leases` table with the identical shape (story_id, leased_by, acquired_at, heartbeat_at, expires_at, status) and an identical conflict rule, built for gh:#1507, but with zero callers anywhere in the CLI or dispatch path, and no PID/harness-aware staleness check (only TTL + "no running daemon job", via `reclaim_stranded_stories`). This plan extends that existing, tested machinery instead of duplicating it. This is a deliberate, in-session architecture correction to the approved spec's "new table" framing — the behavior and CLI/testing contract described in the spec (block-at-claim, override flag, heartbeat+TTL, same-story-only scope, interactive-only) are all preserved; only the storage layer changes from "new table" to "extend existing table."

---

### Task 1: Add `pid` and `harness` columns to `task_leases`

**Files:**
- Modify: `synlynk/db_schema.py:554-563` (document new columns in the `CREATE TABLE` for fresh databases)
- Modify: `synlynk/db.py` — add a migration block near the existing `story_cols`/`backlog_cols` ALTER guards inside `_run_legacy_migration_and_repairs` (`synlynk/db.py:1130`, guards live around `synlynk/db.py:1225-1270`)
- Test: `tests/test_task_leases.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_task_leases.py`:

```python
def test_task_leases_table_has_pid_and_harness_columns(db_conn):
    cols = {row[1] for row in db_conn.execute("PRAGMA table_info(task_leases)")}
    assert "pid" in cols
    assert "harness" in cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_leases.py::test_task_leases_table_has_pid_and_harness_columns -v`
Expected: FAIL — `AssertionError` (columns don't exist yet)

- [ ] **Step 3: Update the CREATE TABLE in db_schema.py**

In `synlynk/db_schema.py`, change the `task_leases` block (lines 554-563) to:

```sql
CREATE TABLE IF NOT EXISTS task_leases (
    lease_id           TEXT PRIMARY KEY,
    story_id           TEXT NOT NULL,
    leased_by          TEXT NOT NULL,
    pid                INTEGER,
    harness            TEXT,
    acquired_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    heartbeat_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at         TIMESTAMP NOT NULL,
    status             TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_task_leases_story ON task_leases(story_id, status);
```

This covers fresh databases. Existing databases need the ALTER TABLE migration added next.

- [ ] **Step 4: Add the migration guard in db.py**

In `synlynk/db.py`, inside `_run_legacy_migration_and_repairs`, immediately after the existing `stories` column guards (after the `stack_tags` guard block, before the function returns — same style as lines 1237-1270), add:

```python
        task_lease_cols = {row[1] for row in conn.execute("PRAGMA table_info(task_leases)")}
        if task_lease_cols and "pid" not in task_lease_cols:
            try:
                conn.execute("ALTER TABLE task_leases ADD COLUMN pid INTEGER")
            except sqlite3.OperationalError:
                pass
        if task_lease_cols and "harness" not in task_lease_cols:
            try:
                conn.execute("ALTER TABLE task_leases ADD COLUMN harness TEXT")
            except sqlite3.OperationalError:
                pass
```

`task_lease_cols` is only non-empty if the table already exists (a fresh DB created from the updated `db_schema.py` already has both columns, so the guard is a no-op there — this only matters for DBs created before this change).

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_task_leases.py -v`
Expected: all existing tests in this file still PASS, plus the new column test PASSES

- [ ] **Step 6: Commit**

```bash
git add synlynk/db_schema.py synlynk/db.py tests/test_task_leases.py
git commit -m "feat(leases): add pid and harness columns to task_leases (gh:#2511)"
```

---

### Task 2: Dead-PID-aware conflict detection in `acquire_task_lease`

**Files:**
- Modify: `synlynk/jobs.py:3919-3978` (`acquire_task_lease`)
- Test: `tests/test_task_leases.py`

Currently `acquire_task_lease` only checks TTL expiry (`curr_exp < now_str`) or same-holder reuse — a claim held by a dead process on an unexpired TTL blocks everyone else until the TTL lapses. gh:#2511 explicitly wants dead-session claims to not block.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_task_leases.py`:

```python
import os

def test_dead_pid_claim_does_not_block_new_claim(db_conn):
    # Simulate a crashed session: a PID that is guaranteed not to exist.
    dead_pid = 999999
    acquire_task_lease(
        "story-lease-1", "claude:session-a", duration_seconds=600,
        pid=dead_pid, harness="claude", conn=db_conn,
    )

    result = acquire_task_lease(
        "story-lease-1", "codex:session-b", duration_seconds=600,
        pid=os.getpid(), harness="codex", conn=db_conn,
    )
    assert result["acquired"] is True


def test_live_pid_claim_blocks_new_claim_without_override(db_conn):
    acquire_task_lease(
        "story-lease-1", "claude:session-a", duration_seconds=600,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )

    conflict = acquire_task_lease(
        "story-lease-1", "codex:session-b", duration_seconds=600,
        pid=os.getpid(), harness="codex", conn=db_conn,
    )
    assert conflict["acquired"] is False
    assert conflict["reason"] == "already_leased"
    assert conflict["harness"] == "claude"


def test_override_bypasses_live_claim(db_conn):
    acquire_task_lease(
        "story-lease-1", "claude:session-a", duration_seconds=600,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )

    result = acquire_task_lease(
        "story-lease-1", "codex:session-b", duration_seconds=600,
        pid=os.getpid(), harness="codex", override=True, conn=db_conn,
    )
    assert result["acquired"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_leases.py::test_dead_pid_claim_does_not_block_new_claim -v`
Expected: FAIL — `TypeError: acquire_task_lease() got an unexpected keyword argument 'pid'`

- [ ] **Step 3: Implement dead-PID check and override**

Replace `synlynk/jobs.py:3919-3978` (`acquire_task_lease`) with:

```python
def _lease_pid_is_alive(pid) -> bool:
    """Check if a process with given PID is currently alive on the host system."""
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def acquire_task_lease(
    story_id: str,
    leased_by: str,
    duration_seconds: int = 1800,
    pid: int = None,
    harness: str = None,
    override: bool = False,
    conn=None,
) -> dict:
    """Acquire or extend a rolling lease on a story in state.db.

    A live conflicting claim (unexpired TTL AND holder PID still alive) blocks
    acquisition unless ``override=True``. A claim whose TTL expired OR whose
    holder PID is dead is stale and does not block (gh:#2511).
    """
    owns_conn = False
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
        owns_conn = True

    now = time.time()
    expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + duration_seconds))
    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    lease_id = f"lease-{hashlib.md5(f'{story_id}:{leased_by}:{now}'.encode()).hexdigest()[:8]}"
    effective_pid = pid if pid is not None else os.getpid()

    try:
        row = conn.execute(
            "SELECT lease_id, leased_by, pid, harness, expires_at FROM task_leases "
            "WHERE story_id=? AND status='active' ORDER BY rowid DESC LIMIT 1",
            (story_id,),
        ).fetchone()

        if row:
            curr_id, curr_holder, curr_pid, curr_harness, curr_exp = row
            is_expired = curr_exp < now_str
            is_dead = not _lease_pid_is_alive(curr_pid)
            is_same_holder = curr_holder == leased_by
            is_stale = is_expired or is_dead or is_same_holder

            if is_stale or override:
                conn.execute(
                    "UPDATE task_leases SET status='expired' WHERE lease_id=?",
                    (curr_id,),
                )
            else:
                return {
                    "acquired": False,
                    "reason": "already_leased",
                    "leased_by": curr_holder,
                    "harness": curr_harness,
                    "expires_at": curr_exp,
                }

        conn.execute(
            """INSERT INTO task_leases
               (lease_id, story_id, leased_by, pid, harness, acquired_at, heartbeat_at, expires_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
            (lease_id, story_id, leased_by, effective_pid, harness, now_str, now_str, expires_at),
        )
        conn.execute(
            "UPDATE stories SET status='in_progress', readiness='in_progress' WHERE story_id=?",
            (story_id,),
        )
        conn.commit()
        return {
            "acquired": True,
            "lease_id": lease_id,
            "story_id": story_id,
            "leased_by": leased_by,
            "harness": harness,
            "expires_at": expires_at,
        }
    finally:
        if owns_conn:
            conn.close()
```

Note: `is_same_holder` is kept as stale-equivalent (same behavior as before this change) so a session can freely renew its own claim by re-calling acquire.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_leases.py -v`
Expected: all PASS, including the 3 new tests and the 4 pre-existing ones (`test_acquire_and_get_task_lease`, `test_concurrent_lease_conflict`, `test_renew_task_lease`, `test_release_task_lease`, `test_reclaim_stranded_story_with_lease`)

- [ ] **Step 5: Commit**

```bash
git add synlynk/jobs.py tests/test_task_leases.py
git commit -m "feat(leases): dead-PID-aware conflict detection + override on acquire_task_lease (gh:#2511)"
```

---

### Task 3: Surface harness in `get_active_lease`

**Files:**
- Modify: `synlynk/jobs.py` (`get_active_lease`, currently at line ~4041)
- Test: `tests/test_task_leases.py`

The CLI claim command (Task 4) needs to print which harness/session holds a conflicting claim. `get_active_lease` currently doesn't select the `harness`/`pid` columns.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_task_leases.py`:

```python
def test_get_active_lease_includes_harness_and_pid(db_conn):
    acquire_task_lease(
        "story-lease-1", "claude:session-a", duration_seconds=600,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )
    lease = get_active_lease("story-lease-1", conn=db_conn)
    assert lease["harness"] == "claude"
    assert lease["pid"] == os.getpid()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_leases.py::test_get_active_lease_includes_harness_and_pid -v`
Expected: FAIL — `KeyError: 'harness'`

- [ ] **Step 3: Update get_active_lease**

Replace the body of `get_active_lease` in `synlynk/jobs.py` with:

```python
def get_active_lease(story_id: str, conn=None) -> Optional[dict]:
    """Retrieve the currently active lease for a story."""
    owns_conn = False
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
        owns_conn = True

    try:
        row = conn.execute(
            "SELECT lease_id, story_id, leased_by, pid, harness, acquired_at, heartbeat_at, expires_at, status "
            "FROM task_leases WHERE story_id=? AND status='active' ORDER BY rowid DESC LIMIT 1",
            (story_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "lease_id": row[0],
            "story_id": row[1],
            "leased_by": row[2],
            "pid": row[3],
            "harness": row[4],
            "acquired_at": row[5],
            "heartbeat_at": row[6],
            "expires_at": row[7],
            "status": row[8],
        }
    finally:
        if owns_conn:
            conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_leases.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/jobs.py tests/test_task_leases.py
git commit -m "feat(leases): surface harness/pid in get_active_lease (gh:#2511)"
```

---

### Task 4: `synlynk story claim` CLI command

**Files:**
- Modify: `synlynk/cli.py` — add subparser near `story_reclaim_parser` (after line 1544, before the blank line at 1546)
- Modify: `synlynk/cli.py` — add dispatch branch near line 3000 (after the `reclaim` branch)
- Test: `tests/test_cli_story_claim.py` (new)

This is the actual interactive entry point gh:#2511 is about — currently `acquire_task_lease` has no caller anywhere, so no interactive session can take or be blocked by a claim at all. This command fills that gap. It generates a `session_id` as `f"{harness}:{socket.gethostname()}:{os.getpid()}"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_story_claim.py`:

```python
import os
import subprocess
import sys


def test_story_claim_blocks_second_session(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_claim.db")
    monkeypatch.setenv("SYNLYNK_DB_PATH", db_path)

    from synlynk import _get_db
    conn = _get_db(db_path=db_path)
    conn.execute("""
        INSERT INTO stories (story_id, title, role, stage, status, readiness)
        VALUES ('story-claim-1', 'Claim test story', 'dev', 'open', 'ready', 'ready')
    """)
    conn.commit()
    conn.close()

    from synlynk.jobs import acquire_task_lease, get_active_lease
    # Simulate a live holder (this test process's own PID is alive).
    first = acquire_task_lease(
        "story-claim-1", "claude:host:111", pid=os.getpid(), harness="claude",
    )
    assert first["acquired"] is True

    second = acquire_task_lease(
        "story-claim-1", "codex:host:222", pid=os.getpid(), harness="codex",
    )
    assert second["acquired"] is False
    assert second["harness"] == "claude"
```

(This test exercises the underlying function directly rather than shelling out to the CLI, since the CLI's db path is resolved via `synlynk._get_db()`'s own config lookup rather than an env var in all code paths — direct function calls are deterministic and match the existing style of `tests/test_task_leases.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_story_claim.py -v`
Expected: PASS already (this test only exercises Task 2's function, already implemented) — this step confirms Task 2's work generalizes outside the `db_conn` fixture before building the CLI layer on top of it. If it fails, stop and fix Task 2 first.

- [ ] **Step 3: Add the `claim` subparser in cli.py**

In `synlynk/cli.py`, immediately after the `story_reclaim_parser` block (after line 1545: `story_reclaim_parser.add_argument("--dry-run", ...)`), add:

```python
    story_claim_parser = story_sub.add_parser("claim", help="Take an interactive home claim on a story (gh:#2511)")
    story_claim_parser.add_argument("story_id")
    story_claim_parser.add_argument("--harness", default=None, help="Harness identity; auto-detected if omitted")
    story_claim_parser.add_argument("--duration", type=int, default=2700, help="Claim TTL in seconds (default: 45min)")
    story_claim_parser.add_argument("--override", action="store_true", help="Force-take the claim even if another live session holds it")
```

- [ ] **Step 4: Add the dispatch branch and handler**

In `synlynk/cli.py`, immediately after the `elif args.story_action == "reclaim":` block (after line 3002), add:

```python
        elif args.story_action == "claim":
            from synlynk.jobs import cmd_story_claim
            sys.exit(cmd_story_claim(
                args.story_id,
                harness=getattr(args, "harness", None),
                duration_seconds=getattr(args, "duration", 2700),
                override=getattr(args, "override", False),
            ))
```

Add `cmd_story_claim` to `synlynk/jobs.py`, directly after `cmd_story_reclaim` (after line 4079):

```python
def cmd_story_claim(
    story_id: str,
    harness: str = None,
    duration_seconds: int = 2700,
    override: bool = False,
) -> int:
    """CLI handler for `synlynk story claim` (gh:#2511)."""
    import socket
    from synlynk.context import detect_active_home_harness

    effective_harness = harness or detect_active_home_harness()
    session_id = f"{effective_harness}:{socket.gethostname()}:{os.getpid()}"

    result = acquire_task_lease(
        story_id,
        session_id,
        duration_seconds=duration_seconds,
        pid=os.getpid(),
        harness=effective_harness,
        override=override,
    )

    if result["acquired"]:
        print(f"\n  {_BOLD}synlynk story claim{_RESET}  story={story_id}  harness={effective_harness}  session={session_id}")
        print(f"  Claim active until {result['expires_at']}\n")
        return 0

    print(f"\n  {_BOLD}synlynk story claim{_RESET}  REFUSED — story={story_id} already claimed")
    print(f"  Held by harness={result.get('harness')}  leased_by={result.get('leased_by')}  expires_at={result.get('expires_at')}")
    print("  Pass --override to force-take this claim.\n")
    return 1
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cli_story_claim.py tests/test_task_leases.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py synlynk/jobs.py tests/test_cli_story_claim.py
git commit -m "feat(leases): add synlynk story claim CLI command (gh:#2511)"
```

---

### Task 5: Heartbeat on every `synlynk exec`

**Files:**
- Modify: `synlynk/dispatch.py:5687-5707` (`exec_command`)
- Modify: `synlynk/jobs.py` (`renew_task_lease` — extend signature, no behavior change needed since it already renews by `leased_by`; add a session-wide heartbeat helper)
- Test: `tests/test_task_leases.py`

`exec_command` runs once per `synlynk exec` invocation and already calls `generate_context()` unconditionally. Per the design spec, reuse this existing per-command hook rather than adding a new polling loop. A session heartbeats *all* claims it currently holds (there's no story_id available in `exec_command` to target one specifically), identified by its own PID.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_task_leases.py`:

```python
def test_heartbeat_all_claims_for_pid(db_conn):
    acquire_task_lease(
        "story-lease-1", "claude:host:999", duration_seconds=10,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )
    before = get_active_lease("story-lease-1", conn=db_conn)

    time.sleep(1)
    from synlynk.jobs import heartbeat_claims_for_pid
    count = heartbeat_claims_for_pid(os.getpid(), extend_seconds=120, conn=db_conn)
    assert count == 1

    after = get_active_lease("story-lease-1", conn=db_conn)
    assert after["heartbeat_at"] > before["heartbeat_at"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_leases.py::test_heartbeat_all_claims_for_pid -v`
Expected: FAIL — `ImportError: cannot import name 'heartbeat_claims_for_pid'`

- [ ] **Step 3: Implement `heartbeat_claims_for_pid`**

Add to `synlynk/jobs.py`, directly after `renew_task_lease` (after line ~4010):

```python
def heartbeat_claims_for_pid(pid: int, extend_seconds: int = 2700, conn=None) -> int:
    """Renew every active task_lease held by the given PID. Returns count renewed."""
    owns_conn = False
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
        owns_conn = True

    try:
        now = time.time()
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + extend_seconds))
        cur = conn.execute(
            "UPDATE task_leases SET heartbeat_at=?, expires_at=? WHERE pid=? AND status='active'",
            (now_str, expires_at, pid),
        )
        conn.commit()
        return cur.rowcount
    except sqlite3.OperationalError:
        return 0
    finally:
        if owns_conn:
            conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_leases.py -v`
Expected: all PASS

- [ ] **Step 5: Wire into exec_command (fail-open)**

In `synlynk/dispatch.py`, in `exec_command` right after the `if generate_context: generate_context()` block (after line 5707), add:

```python
    try:
        from synlynk.jobs import heartbeat_claims_for_pid
        heartbeat_claims_for_pid(os.getpid())
    except Exception:
        pass
```

This is deliberately fail-open per the design spec's error-handling section: a broken/missing `state.db` must never block `synlynk exec` from running the underlying command.

- [ ] **Step 6: Run full test suite for regressions**

Run: `pytest tests/test_task_leases.py tests/ -k "exec_command" -v`
Expected: all PASS, no new failures

- [ ] **Step 7: Commit**

```bash
git add synlynk/jobs.py synlynk/dispatch.py tests/test_task_leases.py
git commit -m "feat(leases): heartbeat held claims on every synlynk exec (gh:#2511)"
```

---

### Task 6: Release claim on `synlynk story done` and home handover

**Files:**
- Modify: `synlynk/db.py:4138-4158` (`cmd_story_done`)
- Modify: `synlynk/handover.py` (`execute_home_handover`, around line 149-190)
- Test: `tests/test_task_leases.py`, `tests/test_handover.py` (check if exists; if not, add inline test in `tests/test_task_leases.py`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_task_leases.py`:

```python
def test_story_done_releases_active_claim(db_conn):
    from synlynk.jobs import get_active_lease
    acquire_task_lease(
        "story-lease-1", "claude:host:1", duration_seconds=600,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )

    from synlynk.db import cmd_story_done
    cmd_story_done("story-lease-1")  # uses its own _get_db(), shares the same on-disk DB in CI config

    # Re-fetch via the test's own connection since cmd_story_done opens its own.
    row = db_conn.execute(
        "SELECT status FROM task_leases WHERE story_id='story-lease-1' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert row[0] == "released"
```

Note: this test requires `cmd_story_done` and the `db_conn` fixture to resolve to the *same* underlying database file. Since `_get_db()` resolves a single shared per-workspace path (not configurable per-call in the current fixture), if this isolation assumption doesn't hold in practice, convert this specific test to call `release_task_lease` directly (already proven in `test_release_task_lease`) and instead verify only that `cmd_story_done`'s source contains the call via a `grep`-style source-string assertion, OR refactor `cmd_story_done` to accept an optional `conn` the way every other function in this plan does, and pass `db_conn` through. Prefer the `conn` parameter refactor — it matches this file's existing pattern everywhere else and keeps the test deterministic.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_leases.py::test_story_done_releases_active_claim -v`
Expected: FAIL (claim still `active`, since `cmd_story_done` doesn't release it yet)

- [ ] **Step 3: Give `cmd_story_done` an optional `conn` param and release the claim**

Replace `synlynk/db.py:4138-4158` with:

```python
def cmd_story_done(story_id: str, conn=None) -> None:
    """Marks a story done, releases any active task_lease, and emits a story_done event."""
    from synlynk import _GREEN, _RESET, _get_db
    from synlynk.events import emit_event
    owns_conn = False
    if conn is None:
        conn = _get_db()
        owns_conn = True
    story = conn.execute(
        "SELECT story_id, goal_id FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    if not story:
        if owns_conn:
            conn.close()
        print(f"  Story '{story_id}' not found.")
        return
    conn.execute(
        "UPDATE stories SET status='done', readiness='done' WHERE story_id=?",
        (story_id,),
    )
    conn.execute(
        "UPDATE task_leases SET status='released' WHERE story_id=? AND status='active'",
        (story_id,),
    )
    phase_result = conn.execute(
        "UPDATE roadmap_phases SET status='done' WHERE story_id=? AND status != 'done'",
        (story_id,),
    )
    conn.commit()
```

(Keep the rest of the original function body — the `emit_event` call and anything following line 4158 — unchanged; only the signature, the `conn` handling, and the new `UPDATE task_leases` line are new. Close `conn` at the end if `owns_conn`, matching the pattern used elsewhere in this plan.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_leases.py -v`
Expected: all PASS

- [ ] **Step 5: Release claims on home handover**

In `synlynk/handover.py`, inside `execute_home_handover` (starting line 149), after the `drain_info`/`active_story_id` computation (after line 179: `active_story_id = drain_info["active_story_id"] if not force else None`), add:

```python
    if active_story_id:
        try:
            from synlynk.jobs import release_task_lease
            release_task_lease(active_story_id, current_home, new_status=None)
        except Exception:
            pass
```

`new_status=None` is passed because `release_task_lease`'s existing signature only writes a new `stories.status` when `new_status` is truthy (see `synlynk/jobs.py:4011-4030`) — handover should release the claim without forcing the story back to `done`, since the story is mid-flight, not finished.

- [ ] **Step 6: Run full regression pass**

Run: `pytest tests/test_task_leases.py tests/test_handover.py -v` (if `tests/test_handover.py` doesn't exist, run `pytest tests/ -k handover -v` instead)
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add synlynk/db.py synlynk/handover.py tests/test_task_leases.py
git commit -m "feat(leases): release task_lease on story done and home handover (gh:#2511)"
```

---

### Task 7: Dead-PID sweep in `reclaim_stranded_stories`

**Files:**
- Modify: `synlynk/jobs.py:3836-3913` (`reclaim_stranded_stories`)
- Test: `tests/test_task_leases.py`

`reclaim_stranded_stories` already expires a story's `task_leases` row when it reclaims a stranded `in_progress` story with no running daemon job (line ~3896-3900). But it never checks `task_leases.pid` directly — a story claimed interactively (no daemon job at all, by design, since claims are interactive-only) whose session has died is invisible to the existing "no running daemon job" check only by accident (no daemon job ever existed for an interactive claim, so it already looks stranded). This task makes the dead-PID check explicit and correct rather than incidental, consistent with the design spec's reclamation requirement.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_task_leases.py`:

```python
def test_reclaim_leaves_live_interactive_claim_alone(db_conn):
    # A live interactive claim (no daemon job at all) must NOT be reclaimed.
    acquire_task_lease(
        "story-lease-1", "claude:host:live", duration_seconds=600,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )

    reclaimed = reclaim_stranded_stories(max_age_minutes=30, dry_run=False, conn=db_conn)
    assert reclaimed == []

    row = db_conn.execute("SELECT status FROM stories WHERE story_id='story-lease-1'").fetchone()
    assert row[0] == "in_progress"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_leases.py::test_reclaim_leaves_live_interactive_claim_alone -v`
Expected: FAIL — currently `reclaim_stranded_stories` reclaims this story because it has no daemon job rows at all (the existing `has_active_worker` check only looks at `daemon_jobs`, never at `task_leases.pid`), so it wrongly treats every interactive claim as stranded.

- [ ] **Step 3: Make the stranded check also honor a live claim PID**

In `synlynk/jobs.py`, inside `reclaim_stranded_stories`, replace the loop body (lines 3861-3900) with:

```python
        for story_id, title in rows:
            job_rows = conn.execute(
                "SELECT job_id, agent, status, pid, started_at FROM daemon_jobs "
                "WHERE story_id=? AND status IN ('running', 'queued') ORDER BY rowid DESC",
                (story_id,),
            ).fetchall()

            has_active_worker = False
            for job_id, agent, j_status, pid, started_at in job_rows:
                if j_status == "running" and pid is not None:
                    if _pid_is_alive(pid):
                        has_active_worker = True
                        break

            if not has_active_worker:
                lease_row = conn.execute(
                    "SELECT pid FROM task_leases WHERE story_id=? AND status='active' "
                    "ORDER BY rowid DESC LIMIT 1",
                    (story_id,),
                ).fetchone()
                if lease_row and lease_row[0] is not None and _pid_is_alive(lease_row[0]):
                    has_active_worker = True

            if not has_active_worker:
                reclaimed.append({
                    "story_id": story_id,
                    "title": title,
                    "reclaimed": not dry_run,
                })
                if not dry_run:
                    terminal_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    for job_id, agent, j_status, pid, started_at in job_rows:
                        if j_status == "running":
                            _settle_daemon_job_terminal(
                                conn,
                                job_id,
                                "failed",
                                137,
                                terminal_at,
                                only_running=True,
                            )
                    conn.execute(
                        "UPDATE stories SET status='ready', readiness='ready' WHERE story_id=?",
                        (story_id,),
                    )
                    try:
                        conn.execute(
                            "UPDATE task_leases SET status='expired' WHERE story_id=? AND status='active'",
                            (story_id,),
                        )
                    except Exception:
                        pass
```

`_pid_is_alive` is the existing helper already used earlier in this same function (confirm it's defined/imported above line 3836 in `synlynk/jobs.py`; it is the same liveness check as `_lease_pid_is_alive` from Task 2 — reuse `_pid_is_alive` here rather than duplicating, they are functionally identical).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_leases.py -v`
Expected: all PASS, including `test_reclaim_stranded_story_with_lease` (the pre-existing test, which uses a `"dead-worker"` leased_by string with no `pid` argument — confirm it still passes: with `pid=None` passed implicitly via the default in `acquire_task_lease`, Task 2's change sets `effective_pid = os.getpid()` when `pid` is omitted, so this pre-existing test's lease now carries *this test process's own* live PID. Since that test asserts the story **is** reclaimed, verify it still passes — if the test's dead-worker scenario now looks "live" because of the new default-to-`os.getpid()` behavior, update that pre-existing test to pass `pid=999999` explicitly so it still represents a genuinely dead worker.)

- [ ] **Step 5: Fix the pre-existing test if needed**

If Step 4 reveals `test_reclaim_stranded_story_with_lease` now fails (because the default `pid=os.getpid()` makes the "dead worker" lease look alive), update it in `tests/test_task_leases.py`:

```python
def test_reclaim_stranded_story_with_lease(db_conn):
    # Acquire lease with an explicitly dead PID (dead worker scenario)
    acquire_task_lease("story-lease-1", "dead-worker", duration_seconds=60, pid=999999, conn=db_conn)

    # Run reclaim (dead worker has no running daemon job, and its claim PID is dead)
    reclaimed = reclaim_stranded_stories(max_age_minutes=30, dry_run=False, conn=db_conn)
    assert len(reclaimed) == 1
    assert reclaimed[0]["story_id"] == "story-lease-1"

    row = db_conn.execute("SELECT status FROM stories WHERE story_id='story-lease-1'").fetchone()
    assert row[0] == "ready"

    active_lease = get_active_lease("story-lease-1", conn=db_conn)
    assert active_lease is None
```

- [ ] **Step 6: Run the full test_task_leases.py file one more time**

Run: `pytest tests/test_task_leases.py -v`
Expected: all PASS, no regressions

- [ ] **Step 7: Commit**

```bash
git add synlynk/jobs.py tests/test_task_leases.py
git commit -m "fix(leases): reclaim_stranded_stories checks claim PID liveness, not just daemon_jobs (gh:#2511)"
```

---

### Task 8: Update the design spec to match the implemented architecture

**Files:**
- Modify: `docs/superpowers/specs/2026-10-21-story-home-claims-design.md`

The approved spec describes a new `story_home_claims` table and `synlynk/story_claims.py` module. Tasks 1-7 implemented the same behavior by extending the existing `task_leases` table/`synlynk/jobs.py` functions instead, per the "Note on the design spec" at the top of this plan. Update the spec so it accurately documents what was actually built — the spec should never describe a module or table that doesn't exist in the finished code.

- [ ] **Step 1: Rewrite the spec's Architecture/Schema/Module sections**

In `docs/superpowers/specs/2026-10-21-story-home-claims-design.md`, replace the `### Schema`, `### New module: synlynk/story_claims.py`, and `### Integration points` subsections (everything between `## Architecture` and `### session_id generation`) with a short section pointing at the real implementation:

```markdown
### Implementation note (added after planning)

This design is implemented by extending the pre-existing `task_leases` table
and `synlynk/jobs.py` functions (`acquire_task_lease`, `renew_task_lease`,
`release_task_lease`, `get_active_lease`, originally built for gh:#1507 but
previously uncalled from anywhere) rather than by adding a new table/module.
See `docs/superpowers/plans/2026-10-21-story-home-claims-design.md` for the
full rationale and implementation detail. The schema gained `pid` and
`harness` columns; `acquire_task_lease` gained dead-PID detection and an
`override` flag; a new `synlynk story claim` CLI command, an `exec_command()`
heartbeat hook, and release hooks on `story done`/home handover are the new
integration points. `reclaim_stranded_stories` now also checks claim-PID
liveness.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-10-21-story-home-claims-design.md
git commit -m "docs: reconcile story-home-claims spec with as-built task_leases extension (gh:#2511)"
```

---

### Task 9: Full regression pass and PR

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -q`
Expected: 0 failures. If any pre-existing failures are unrelated to this change (confirm by checking they also fail on `origin/main`), note them in the PR description rather than trying to fix them here.

- [ ] **Step 2: Push branch and open PR**

```bash
git push -u origin docs/claude/story-home-claims-design
gh pr create --title "feat: story home claims via task_leases extension (gh:#2511)" --body "$(cat <<'EOF'
## Summary
- Closes gh:#2511 by making the long-dead `task_leases` mechanism (built for gh:#1507, never called) actually enforce same-story interactive-session conflicts.
- Adds `pid`/`harness` columns, dead-PID-aware conflict detection, and `--override`.
- New `synlynk story claim` CLI command; heartbeat wired into `exec_command()`; release wired into `story done` and home handover; `reclaim_stranded_stories` now checks claim-PID liveness directly.
- Design spec updated to reflect the as-built architecture (extending `task_leases`, not a new `story_home_claims` table — see the plan's "Note on the design spec" for why).

## Test plan
- [ ] `pytest tests/test_task_leases.py -v` — all pass
- [ ] `pytest tests/test_cli_story_claim.py -v` — all pass
- [ ] `pytest tests/ -q` — full suite green

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Per the Hardened PR Review Policy, this PR needs a reviewer on a different harness+model who runs `synlynk pr check` from the PR's own worktree and performs the merge as the final step of their own dispatch.
