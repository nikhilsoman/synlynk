# SQLite WAL Soak Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove `state.db` (SQLite WAL) survives 20–50 concurrent writers without corruption or unrecoverable lock contention, per gh:#2102.

**Architecture:** One opt-in pytest module, isolated temp DB per run, threaded workers doing realistic mixed writes, integrity + lock-failure-rate assertions, JSON report artifact.

**Tech Stack:** Python stdlib `sqlite3`, `threading`, `pytest` with a custom `soak` marker.

---

### Task 1: Soak test module skeleton + isolated DB fixture

**Files:**
- Create: `tests/soak/__init__.py` (empty)
- Create: `tests/soak/test_state_db_concurrent_writers.py`

- [ ] **Step 1: Write the fixture**

```python
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import json
import pytest

pytestmark = pytest.mark.soak


@pytest.fixture
def isolated_db_path():
    tmpdir = tempfile.mkdtemp(prefix="synlynk-soak-")
    db_path = os.path.join(tmpdir, "state.db")
    yield db_path
    shutil.rmtree(tmpdir, ignore_errors=True)


def _init_schema(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE cost_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "job_id TEXT, harness TEXT, total_cost_usd REAL)"
    )
    conn.execute(
        "CREATE TABLE capability_ratings (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "agent TEXT, story_id TEXT, quality REAL)"
    )
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, status TEXT, updated_at REAL)"
    )
    conn.commit()
    conn.close()
```

- [ ] **Step 2: Run to verify fixture creates and tears down cleanly**

Run: `pytest tests/soak/test_state_db_concurrent_writers.py -m soak --collect-only -v`
Expected: module collects with no errors (no test functions yet, so 0 collected is fine at this step — this step only verifies the fixture file imports without error via `python3 -c "import tests.soak.test_state_db_concurrent_writers"`)

- [ ] **Step 3: Commit**

```bash
git add tests/soak/__init__.py tests/soak/test_state_db_concurrent_writers.py
git commit -m "test(soak): add isolated temp-db fixture for WAL soak test (gh:#2102)"
```

### Task 2: Concurrent writer workload + lock/latency tracking

**Files:**
- Modify: `tests/soak/test_state_db_concurrent_writers.py`

- [ ] **Step 1: Write the worker function and result collector**

```python
def _worker(db_path, worker_id, duration_s, results):
    attempts = 0
    successes = 0
    lock_failures = 0
    latencies = []
    conn = sqlite3.connect(db_path, timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    deadline = time.monotonic() + duration_s
    i = 0
    while time.monotonic() < deadline:
        attempts += 1
        start = time.monotonic()
        try:
            conn.execute(
                "INSERT INTO cost_entries (job_id, harness, total_cost_usd) VALUES (?, ?, ?)",
                (f"job-{worker_id}-{i}", "soak-harness", 0.01),
            )
            conn.execute(
                "INSERT INTO capability_ratings (agent, story_id, quality) VALUES (?, ?, ?)",
                (f"agent-{worker_id}", f"story-{worker_id}-{i}", 1.0),
            )
            conn.execute(
                "INSERT OR REPLACE INTO daemon_jobs (job_id, status, updated_at) VALUES (?, ?, ?)",
                (f"job-{worker_id}", "running", time.time()),
            )
            conn.commit()
            successes += 1
            latencies.append(time.monotonic() - start)
        except sqlite3.OperationalError:
            lock_failures += 1
            conn.rollback()
        i += 1
    conn.close()
    results[worker_id] = {
        "attempts": attempts,
        "successes": successes,
        "lock_failures": lock_failures,
        "latencies": latencies,
    }
```

- [ ] **Step 2: Write the parametrized test that spawns N workers**

```python
@pytest.mark.parametrize("num_workers", [20, 50])
def test_concurrent_writers_no_corruption(isolated_db_path, num_workers):
    _init_schema(isolated_db_path)
    results = {}
    threads = [
        threading.Thread(target=_worker, args=(isolated_db_path, i, 10.0, results))
        for i in range(num_workers)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    conn = sqlite3.connect(isolated_db_path)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    assert integrity == "ok"

    total_attempts = sum(r["attempts"] for r in results.values())
    total_lock_failures = sum(r["lock_failures"] for r in results.values())
    failure_rate = total_lock_failures / total_attempts if total_attempts else 0
    assert failure_rate < 0.01, f"lock failure rate {failure_rate:.4f} exceeds 1% threshold"

    report = {
        "num_workers": num_workers,
        "total_attempts": total_attempts,
        "total_lock_failures": total_lock_failures,
        "failure_rate": failure_rate,
    }
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"{int(time.time())}-soak-{num_workers}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    conn.close()
```

- [ ] **Step 3: Run test to verify it passes at both parametrizations**

Run: `pytest tests/soak/test_state_db_concurrent_writers.py -m soak -v`
Expected: `2 passed` (num_workers=20 and num_workers=50), report JSON files written under `tests/soak/reports/`

- [ ] **Step 4: Gitignore the reports directory**

Add `tests/soak/reports/` to `.gitignore`.

- [ ] **Step 5: Commit**

```bash
git add tests/soak/test_state_db_concurrent_writers.py .gitignore
git commit -m "test(soak): add concurrent-writer workload and pass thresholds (gh:#2102)"
```

### Task 3: Register the `soak` marker and exclude from default run

**Files:**
- Modify: whichever file already registers pytest markers for this project (search for an existing `markers =` section in `pytest.ini`/`pyproject.toml`/`setup.cfg`/`conftest.py` and follow that file's existing pattern — if the project already excludes another opt-in marker like `slow` or `integration` from the default run, mirror that exact mechanism rather than inventing a new one).

- [ ] **Step 1: Register the marker**

Add `soak: soak/load test, opt-in only` next to the existing marker registrations, in whichever config file currently holds them.

- [ ] **Step 2: Confirm default `pytest` run (no `-m`) skips soak tests**

Run: `pytest --collect-only -q | grep -i soak`
Expected: no soak tests collected by a bare default run if the project's default `addopts` already excludes non-default markers; if the project has no such global exclusion mechanism, add `-m "not soak"` to the project's documented default test command instead, following whatever convention the existing opt-in markers use.

- [ ] **Step 3: Commit**

```bash
git add <config file touched in Step 1>
git commit -m "test(soak): register soak marker, exclude from default suite (gh:#2102)"
```

## Execution Handoff

Per this project's Default Agent Role policy, dispatch implementation via `synlynk dispatch` to Grok (infra/data-structure fit, per the roadmap's Section 12 harness allocation), not implemented by Claude directly. Link to story-issue-2102 / goal-adb60ccc for GOVERNS adherence.
