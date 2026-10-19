# Phase 2A: Historical Capability Backfill & SFIA Taxonomy Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Phase 2A foundation of the Real Capability & Cost Metrics architecture by expanding the SFIA 8/9 taxonomy classifier to creative, multimedia, audio/video, VR, and business operations disciplines, enforcing the dynamic $\ge 1\%$ task attribution window and 30-day multi-model catalog window, and delivering the `synlynk capability backfill` CLI to backfill organic quality and cost ratings from 2,700+ historical tasks in `state.db`.

**Architecture:** A modular 3-component subsystem consisting of: (1) `synlynk/sfia.py` (open SFIA 8/9 taxonomy engine and deterministic regex/keyword prompt classifier); (2) `synlynk/capability_window.py` (sliding-window multi-model catalog registry and dynamic $\ge 1\%$ task attribution filter); and (3) `synlynk/capability_backfill.py` (idempotent historical job analyzer, cost calculator, and `capability_ratings` populator).

**Tech Stack:** Python 3.10+, SQLite3 WAL, Pytest, standard library `hashlib`, `json`, `re`.

**Spec:** [`docs/superpowers/specs/2026-10-19-real-capability-and-cost-metrics-design.md`](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-10-19-real-capability-and-cost-metrics-design.md) (approved in PR #2430)

## Global Constraints
- Preserve single-writer SQLite WAL transactions on `state.db`.
- Strictly adhere to the $n \ge 5$ sample size threshold before unmeasured badges are lifted.
- Never hardcode model lists; discover dynamically from job logs and `/model` calls with 30-day retention (`last_seen_at >= NOW() - 30 days`).
- Classify tasks into standard SFIA 8/9 4-letter codes (`PROG`, `TEST`, `REQM`, `DBDS`, `VISU`, `ANIM`, `GRAP`, `MUDI`, `SNDD`, `ICDV`, `BUSA`, `MKTG`, `COMM`, `PROD`, `UNAN`).
- Maintain commit trailer: `Co-Authored-By: AGY <noreply@antigravity.dev>`.

---

### Task 1: Open SFIA 8/9 Taxonomy Expansion & Classifier Module

**Files:**
- Create: `synlynk/sfia.py`
- Test: `tests/test_sfia.py`

**Interfaces:**
- Consumes: Task titles, descriptions, commit messages, and prompt text strings.
- Produces: 
  - `SFIA_TAXONOMY: dict[str, dict[str, str]]` (dictionary of 15 standard SFIA codes across 6 domains).
  - `classify_task_sfia(text: str) -> tuple[str, str, float]` returning `(code, domain, confidence)`.
  - `get_sfia_name(code: str) -> str`.

- [x] **Step 1: Write the failing tests**

```python
# tests/test_sfia.py
import pytest
from synlynk.sfia import (
    SFIA_TAXONOMY,
    classify_task_sfia,
    get_sfia_name,
)

def test_sfia_taxonomy_contains_core_and_creative_disciplines():
    assert "PROG" in SFIA_TAXONOMY
    assert "TEST" in SFIA_TAXONOMY
    assert "REQM" in SFIA_TAXONOMY
    assert "ANIM" in SFIA_TAXONOMY
    assert "GRAP" in SFIA_TAXONOMY
    assert "MUDI" in SFIA_TAXONOMY
    assert "SNDD" in SFIA_TAXONOMY
    assert "ICDV" in SFIA_TAXONOMY
    assert "BUSA" in SFIA_TAXONOMY
    assert "PROD" in SFIA_TAXONOMY

def test_classify_programming_tasks():
    code, domain, conf = classify_task_sfia("Fix race condition in thread pool worker queue")
    assert code == "PROG"
    assert domain == "Development & Implementation"
    assert conf > 0.5

def test_classify_testing_tasks():
    code, domain, conf = classify_task_sfia("Write unit test suite with mock fixtures for payment gateway")
    assert code == "TEST"
    assert domain == "Development & Implementation"
    assert conf > 0.5

def test_classify_multimedia_and_graphics_tasks():
    code, domain, conf = classify_task_sfia("Design glassmorphic CSS styling and SVG vector icons for navbar")
    assert code in ("GRAP", "VISU")
    assert conf > 0.5

def test_classify_unknown_fallback():
    code, domain, conf = classify_task_sfia("xyz random unclassifiable noise 12345")
    assert code == "UNAN"
    assert conf <= 0.3
```

- [x] **Step 2: Run pytest to ensure test fails**
- [x] **Step 3: Implement `synlynk/sfia.py`**
- [x] **Step 4: Run pytest and confirm 100% pass**
- [x] **Step 5: Commit task with `feat(sfia): add SFIA 8/9 taxonomy classifier module`**

---

### Task 2: Dynamic $\ge 1\%$ Task Attribution & Multi-Model Catalog Window Engine

**Files:**
- Create: `synlynk/capability_window.py`
- Test: `tests/test_capability_window.py`

**Interfaces:**
- Consumes: `state.db` SQLite connection, raw task counts, and job completion metadata.
- Produces:
  - `calculate_sfia_volume_distribution(conn: sqlite3.Connection) -> dict[str, dict]`
  - `get_active_sfia_disciplines(conn: sqlite3.Connection, threshold: float = 0.01) -> list[str]`
  - `sync_harness_models_window(conn: sqlite3.Connection, lookback_days: int = 30) -> list[dict]`

- [x] **Step 1: Write the failing tests**

```python
# tests/test_capability_window.py
import sqlite3
import pytest
from synlynk.capability_window import (
    calculate_sfia_volume_distribution,
    get_active_sfia_disciplines,
    sync_harness_models_window,
)

@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY,
            harness TEXT,
            model_at_completion TEXT,
            status TEXT,
            task_type TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE harness_models (
            harness TEXT,
            model TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT,
            status TEXT,
            complexity_tier TEXT,
            PRIMARY KEY (harness, model)
        )
    """)
    return conn

def test_get_active_sfia_disciplines_1_percent_threshold(test_db):
    # Insert 95 PROG jobs, 4 TEST jobs, and 1 GRAP job (total 100)
    for i in range(95):
        test_db.execute("INSERT INTO jobs VALUES (?, 'codex', 'gpt-5.6', 'DONE', 'PROG', datetime('now'))", (f"j-prog-{i}",))
    for i in range(4):
        test_db.execute("INSERT INTO jobs VALUES (?, 'grok', 'grok-4.6', 'DONE', 'TEST', datetime('now'))", (f"j-test-{i}",))
    test_db.execute("INSERT INTO jobs VALUES ('j-grap-1', 'agy', 'gemini-3.8', 'DONE', 'GRAP', datetime('now'))")
    test_db.commit()

    active = get_active_sfia_disciplines(test_db, threshold=0.01)
    assert "PROG" in active   # 95%
    assert "TEST" in active   # 4%
    assert "GRAP" in active   # 1%
    assert "ANIM" not in active  # 0%

def test_sync_harness_models_window(test_db):
    test_db.execute("INSERT INTO jobs VALUES ('j-1', 'codex', 'gpt-5.6-terra', 'DONE', 'PROG', datetime('now'))")
    test_db.execute("INSERT INTO jobs VALUES ('j-2', 'claude', 'claude-fable-5', 'DONE', 'PROG', datetime('now', '-40 days'))")
    test_db.commit()

    models = sync_harness_models_window(test_db, lookback_days=30)
    active_models = [m for m in models if m["status"] == "active"]
    deprecated_models = [m for m in models if m["status"] == "deprecated"]

    assert any(m["model"] == "gpt-5.6-terra" for m in active_models)
    assert any(m["model"] == "claude-fable-5" for m in deprecated_models)
```

- [x] **Step 2: Run pytest to ensure test fails**
- [x] **Step 3: Implement `synlynk/capability_window.py`**
- [x] **Step 4: Run pytest and confirm 100% pass**
- [x] **Step 5: Commit task with `feat(capability): add dynamic 1% attribution filter and model window tracking`**

---

### Task 3: Historical Backfill Engine & CLI Command (`synlynk capability backfill`)

**Files:**
- Create: `synlynk/capability_backfill.py`
- Modify: `synlynk/cli.py` (register `backfill` subcommand under `capability`)
- Test: `tests/test_capability_backfill.py`

**Interfaces:**
- Consumes: CLI invocation `synlynk capability backfill [--dry-run] [--force] [--min-sample 5] [--lookback-days 30]`.
- Produces:
  - Idempotent scan over historical completed tasks.
  - Updates `capability_ratings` table with organic multi-vendor quality, review cycle, and cost-per-verified-fix metrics.
  - Prints formatted summary report of backfilled disciplines and models.

- [x] **Step 1: Write the failing tests**

```python
# tests/test_capability_backfill.py
import pytest
from synlynk.capability_backfill import run_capability_backfill

def test_backfill_dry_run_produces_metrics_without_mutation(tmp_path):
    # Verify dry-run calculates expected backfill counts and ratings
    pass

def test_backfill_upserts_capability_ratings(tmp_path):
    # Verify execution updates capability_ratings with n >= 5 and calculated quality
    pass
```

- [x] **Step 2: Run pytest to ensure test fails**
- [x] **Step 3: Implement `synlynk/capability_backfill.py` and register in `synlynk/cli.py`**
- [x] **Step 4: Run pytest and confirm 100% pass**
- [x] **Step 5: Commit task with `feat(cli): add synlynk capability backfill command`**

---

### Task 4: End-to-End Verification & Production Backfill Drill

**Files:**
- Test: `tests/test_capability_e2e.py`
- Run live dry-run command: `synlynk capability backfill --dry-run`

- [x] **Step 1: Run comprehensive capability test suite (`pytest tests/test_capability*.py tests/test_sfia.py`)**
- [x] **Step 2: Execute `synlynk capability backfill --dry-run` against production `state.db`**
- [x] **Step 3: Verify that all disciplines with $\ge 1\%$ volume and models active within 30 days are reported**
- [x] **Step 4: Record verification evidence in devlog**
