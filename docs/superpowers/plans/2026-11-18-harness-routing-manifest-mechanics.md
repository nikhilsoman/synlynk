# Harness Routing & Manifest Mechanics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 7 sections of `docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md` — eligibility/routing split, live capability-based "auto" routing, per-harness manifests with onboard/probe commands, CLI-version-triggered manifest rediscovery, the Muse budget-rate bug, the local-harness reroute attribution gap, and MCP parity in manifest validation.

**Architecture:** A new `synlynk/routing.py` module ranks eligible harnesses from the existing `policy.json` `overrides.dev_authority.task_allocation` table using `capability_ratings`/`cost_entries`, and is wired into the one real narrow point where `dispatch.py` currently hardcodes a single fallback harness (`_resolve_dispatch_agent`'s non-local branch). A new `synlynk/harness_manifest.py` module owns per-harness `.synlynk/harnesses/{harness}.json` discovery/validation, exposed via two new `synlynk harness onboard|probe` CLI subcommands following the existing `tool`/`spec`/`connector` nested-subparser pattern. Two small, targeted bugs get fixed in place: a wrong hardcoded Muse billing rate in `costs.py`, and a missing fail-closed gate + missing `requested_harness` persistence for `cost_entries`/`capability_ratings` on local-harness reroutes (the equivalent column/mechanism already exists and works for `daemon_jobs` — this plan extends the *same* pattern, it does not invent a new one).

**Tech Stack:** Python 3 stdlib, sqlite3 (`state.db`, WAL mode), argparse (nested subparsers), pytest.

**Grounding corrections vs. the spec (read this before starting — these change how several tasks are scoped):**

1. **Section 2's "auto" resolution branch** is `_resolve_dispatch_agent()` (`synlynk/dispatch.py:321`). It is a **local-vs-single-fallback-string** decision, not a multi-harness ranking function. It early-returns any non-`None`/non-`"auto"` `requested_agent` unchanged. When it doesn't route to `"local"`, it calls `_read_local_fallback()`, which reads one hardcoded string (`local_fallback`, default `"agy"`) from `.synlynk/workspace.json` — **it does not consult `policy.json`'s `task_allocation` table at all**. This plan's Task 4 replaces that single-string lookup with `LiveQueryRouter.select(...)` over the harnesses already listed as eligible for the task's `task_type` in `policy.json`'s existing `task_allocation[task_type]` (primary + `fallback` list) — i.e., it wires live ranking into the one place `auto` currently ignores the capability table completely, rather than replacing or duplicating `task_allocation` itself (which the Phase 2 decision requires stays the binding authority).
2. **The `requested_harness`/`actual_harness` attribution mechanism already exists and works — for `daemon_jobs` only.** `synlynk/dispatch.py:276-318` (`_log_routing_fallback`/`take_routing_fallback`/`_pending_routing_fallback`) populates it, `synlynk/db_schema.py:258-260` + `synlynk/db.py:1579-1584` define/migrate the column, and `synlynk/jobs.py:6537-6655` (inside its `_render()` closure, **not** `synlynk/status.py` as the spec assumed) already prints `requested->actual` whenever they differ. `synlynk/status.py` has zero job-level routing-attribution code (it renders fleet-aggregate state only) — **Task 6 below does not touch `status.py` at all**, because the display the spec wanted already ships in `jobs.py`. The real, narrower gap: `cost_entries` and `capability_ratings` have no equivalent column at all (confirmed via `grep -rn requested_harness synlynk/` — zero hits outside `daemon_jobs`-related code), and nothing threads `initial_agent` into the two canonical write paths for those tables (`_insert_cost_row` in `synlynk/db.py:2693` and `_write_capability_rating` in `synlynk/jobs.py:2037`). Tasks 9-11 below fix exactly that, reusing the daemon_jobs row's already-populated `requested_harness` value as the source — no new capture mechanism needed, only new persistence at two call sites.
3. **The local-harness reroute is already announced, not silent.** `dispatch_agent()` (`synlynk/dispatch.py:4771-4780`) always `print()`s `_capability_reroute_message(initial_agent, agent, probed_agent)` whenever `agent != initial_agent and not force_agent`. The real gap the spec is chasing is *durable attribution* (fixed by Tasks 9-11) plus the *missing fail-closed gate* specifically for `initial_agent == "local"` (fixed by Task 9's `--allow-reroute` flag) — not a missing announcement.
4. **Section 5's credit-pool fallback already exists.** `synlynk/quota.py:984-1063` (`_unexpired_credit_remaining` + `provider_pool_preflight`, wired in at `synlynk/dispatch.py:5060`) already falls back to summing `credit_grants` when a harness has no subscription-track quota row, and is already the live quota-exhaustion gate. The actual, narrow, still-real bug is that `synlynk/costs.py:695` maps `"muse-spark-1.3"` to `_DEFAULT_MODEL_RATE` (the Claude-Sonnet-shaped generic default) instead of a real Meta Standard-tier rate — this corrupts `_estimate_story_cost_usd`/`api_equivalent_usd` cost *accounting* for Muse dispatches, a separate concern from the quota-exhaustion gate. Task 8 fixes only this constant; no new `_billing_rate_per_1k_tokens` helper is needed since the credit-pool fallback this would have duplicated is already built and already wired.

---

### Task 1: `eligibility` block in policy.json + CLAUDE.md routing note

**Files:**
- Modify: `.synlynk/policy.json`
- Modify: `CLAUDE.md` (and the generated `AGENTS.md`/`GEMINI.md` mirrors, if this repo keeps them in sync manually — check with `grep -l "Capability-Based Task Allocation" CLAUDE.md AGENTS.md GEMINI.md .cursorrules` first and edit every file that matches)
- Test: `tests/test_policy_eligibility.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import pytest


def test_policy_json_has_eligibility_block():
    with open(".synlynk/policy.json") as f:
        policy = json.load(f)
    eligibility = policy["capability_policy"]["eligibility"]
    # Every harness already in HARNESS_CAPABILITY_BASELINES must have an entry.
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES
    for harness in HARNESS_CAPABILITY_BASELINES:
        assert harness in eligibility, f"missing eligibility entry for {harness}"
        assert "can_gh_write" in eligibility[harness]
        assert eligibility[harness]["can_gh_write"] == HARNESS_CAPABILITY_BASELINES[harness]["can_gh_write"]


def test_policy_json_task_allocation_untouched():
    """The Phase 2 decision requires task_allocation stays the binding authority — this
    task is additive only and must not remove or restructure it."""
    with open(".synlynk/policy.json") as f:
        policy = json.load(f)
    task_allocation = policy["overrides"]["dev_authority"]["task_allocation"]
    assert "implement" in task_allocation
    assert task_allocation["implement"]["harness"] == "codex"
```

Run: `pytest tests/test_policy_eligibility.py -v`
Expected: FAIL with `KeyError: 'eligibility'`

- [ ] **Step 2: Add the eligibility block**

Edit `.synlynk/policy.json`'s `capability_policy` object (currently ends with the `"note"` key) to add a sibling `"eligibility"` key built from `HARNESS_CAPABILITY_BASELINES`' existing `can_gh_write` field (`synlynk/_constants.py:70-`):

```json
    "note": "task_allocation below is the current interim default, ...",
    "eligibility": {
      "claude": {"can_gh_write": true},
      "codex": {"can_gh_write": true},
      "agy": {"can_gh_write": true},
      "grok": {"can_gh_write": true},
      "muse": {"can_gh_write": false},
      "local": {"can_gh_write": false}
    }
```

Run `python3 -c "from synlynk._constants import HARNESS_CAPABILITY_BASELINES as H; print({k: v['can_gh_write'] for k, v in H.items()})"` first and copy the real values rather than guessing — the plan's sample above must match whatever that prints.

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_policy_eligibility.py -v`
Expected: PASS

- [ ] **Step 4: Add the CLAUDE.md routing-note paragraph**

Find the `Capability-Based Task Allocation` section (the table of Role/Harness/Tasks) in `CLAUDE.md`. Immediately below the table and above the `Do not start a task outside your role column...` line, add:

```markdown
**Live routing note:** the table above is the binding eligibility/default authority for every task type. When a dispatch resolves `agent="auto"` and the task does not route to `local`, `synlynk/routing.py`'s `LiveQueryRouter` picks among the table's primary harness + its `fallback` list for that task type, ranked by live `capability_ratings`/`cost_entries` data once a harness×task_type pair reaches 5 samples; below that floor it round-robins across the same eligible set instead of defaulting to one hardcoded harness. This changes *which eligible harness* auto-dispatch picks — it never adds or removes a harness from a task type's eligibility, which stays governed by this table.
```

Repeat the same paragraph insertion in `AGENTS.md`/`GEMINI.md`/`.cursorrules` if `grep -l "Capability-Based Task Allocation"` found the table duplicated there.

- [ ] **Step 5: File the instruction-file-duplication tech-debt ticket**

```bash
gh issue create --title "Centralize instruction-file routing-table content (CLAUDE.md/AGENTS.md/GEMINI.md duplication)" \
  --body "Editing the Capability-Based Task Allocation table and its routing note currently requires hand-syncing across CLAUDE.md, AGENTS.md, GEMINI.md, and .cursorrules. Follow-up to docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md Section 1 — tech-debt only, not blocking this plan." \
  --label "tech-debt"
```

- [ ] **Step 6: Commit**

```bash
git add .synlynk/policy.json CLAUDE.md AGENTS.md GEMINI.md .cursorrules tests/test_policy_eligibility.py
git commit -m "chore: add additive eligibility block to policy.json + routing note"
```

---

### Task 2: `routing_rotation_state` migration (m0035)

**Files:**
- Create: `synlynk/migrations/m0035_routing_rotation_state.py`
- Test: `tests/migrations/test_m0035_routing_rotation_state.py`

- [ ] **Step 1: Write the failing test**

```python
import sqlite3

from synlynk.migrations.m0035_routing_rotation_state import MIGRATION


def test_m0035_creates_table_and_indexes():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE capability_ratings (
            story_id TEXT, agent TEXT, task_type TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE cost_entries (
            agent TEXT, type_id TEXT
        )
    """)
    MIGRATION.up(conn)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "routing_rotation_state" in tables
    indexes = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )}
    assert "idx_capability_ratings_harness_task" in indexes
    assert "idx_cost_entries_harness_task" in indexes


def test_m0035_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE capability_ratings (story_id TEXT, agent TEXT, task_type TEXT)")
    conn.execute("CREATE TABLE cost_entries (agent TEXT, type_id TEXT)")
    MIGRATION.up(conn)
    MIGRATION.up(conn)  # must not raise
```

Run: `pytest tests/migrations/test_m0035_routing_rotation_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.migrations.m0035_routing_rotation_state'`

- [ ] **Step 2: Write the migration**

Follow the exact template already used by `synlynk/migrations/m0034_approval_tickets_theme.py`:

```python
"""Migration 35: routing rotation state + capability/cost lookup indexes.

Backs synlynk/routing.py's LiveQueryRouter: a sub-floor (<5 samples)
harness×task_type pair round-robins via the pointer in this table instead
of defaulting to one hardcoded fallback harness.

See docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS routing_rotation_state (
            task_type   TEXT NOT NULL,
            cursor      INTEGER NOT NULL DEFAULT 0,
            updated_at  TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (task_type)
        )
    """)
    cap_cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_ratings)")}
    if {"agent", "task_type"} <= cap_cols:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_capability_ratings_harness_task "
            "ON capability_ratings(agent, task_type)"
        )
    cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    if {"agent", "type_id"} <= cost_cols:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cost_entries_harness_task "
            "ON cost_entries(agent, type_id)"
        )


MIGRATION = Migration(version=35, name="routing_rotation_state", up=_up)
```

Note: `capability_ratings` does not have a `task_type` column yet in this schema (confirmed via `PRAGMA table_info` during grounding — its domain-matching columns are `engg_domain`/`discipline`/`org_domain`/`role`/`stage`/`phase`, not `task_type`). Before writing this step for real, run:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('.synlynk/workspace.json' if False else __import__('synlynk')._get_db().execute('PRAGMA database_list').fetchone()[2])
" 2>/dev/null || true
sqlite3 "$(find ~/.synlynk/workspaces -name state.db | head -1)" "PRAGMA table_info(capability_ratings)" | grep -i task_type
```

If that prints nothing (no `task_type` column exists), change the index to the nearest real equivalent column instead of a column that doesn't exist — use `discipline` in place of `task_type` for `idx_capability_ratings_harness_task` (i.e. `ON capability_ratings(agent, discipline)`), and update `LiveQueryRouter` in Task 3 to query by `discipline` for the `capability_ratings` side and `type_id` for the `cost_entries` side. Do not invent a `task_type` column on `capability_ratings` as part of this migration — that is a larger schema change outside this plan's scope if it turns out to be needed; confirm the real column name first and use it.

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/migrations/test_m0035_routing_rotation_state.py -v`
Expected: PASS

- [ ] **Step 4: Register the migration**

Check how migrations are discovered — run `grep -n "m0034\|migrations.*glob\|import_module" synlynk/migrations/runner.py` and confirm the runner auto-discovers by filename (no manual registry list to update) before assuming this step is a no-op. If a manual list exists, add `m0035_routing_rotation_state` to it.

- [ ] **Step 5: Commit**

```bash
git add synlynk/migrations/m0035_routing_rotation_state.py tests/migrations/test_m0035_routing_rotation_state.py
git commit -m "feat: add routing_rotation_state migration (m0035)"
```

---

### Task 3: `synlynk/routing.py` — `LiveQueryRouter`

**Files:**
- Create: `synlynk/routing.py`
- Test: `tests/test_routing.py`

- [ ] **Step 1: Write the failing tests**

```python
import sqlite3

import pytest

from synlynk.routing import SAMPLE_SIZE_FLOOR, LiveQueryRouter


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE capability_ratings (
            story_id TEXT, agent TEXT, discipline TEXT, pr_review_cycles REAL
        )
    """)
    conn.execute("""
        CREATE TABLE cost_entries (
            agent TEXT, type_id TEXT, total_cost_usd REAL
        )
    """)
    conn.execute("""
        CREATE TABLE routing_rotation_state (
            task_type TEXT PRIMARY KEY, cursor INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT
        )
    """)
    return conn


def test_round_robins_below_sample_floor():
    conn = _make_db()
    router = LiveQueryRouter()
    picks = [router.select(["codex", "grok", "agy"], "implement", conn) for _ in range(6)]
    assert picks == ["codex", "grok", "agy", "codex", "grok", "agy"]


def test_ranks_by_score_at_or_above_floor():
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', ?)", (f"s{i}", 1.0)
        )
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', ?)", (f"g{i}", 3.0)
        )
    conn.commit()
    router = LiveQueryRouter()
    # codex has the lower (better) median pr_review_cycles, should win.
    assert router.select(["codex", "grok"], "implement", conn) == "codex"


def test_deterministic_tie_break_prefers_higher_sample_count_then_alphabetical():
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'agy', 'implement', ?)", (f"a{i}", 2.0)
        )
    for i in range(SAMPLE_SIZE_FLOOR + 2):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', ?)", (f"c{i}", 2.0)
        )
    conn.commit()
    router = LiveQueryRouter()
    # Tied score (2.0 both); codex has more samples (7 vs 5) so it wins the tie.
    assert router.select(["agy", "codex"], "implement", conn) == "codex"


def test_single_eligible_harness_short_circuits():
    conn = _make_db()
    router = LiveQueryRouter()
    assert router.select(["codex"], "implement", conn) == "codex"


def test_empty_eligible_list_raises():
    conn = _make_db()
    router = LiveQueryRouter()
    with pytest.raises(ValueError):
        router.select([], "implement", conn)
```

Run: `pytest tests/test_routing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.routing'`

- [ ] **Step 2: Implement `synlynk/routing.py`**

```python
"""Live capability-based routing for agent="auto" dispatches.

Ranks eligible harnesses (the primary + fallback list already configured in
policy.json's overrides.dev_authority.task_allocation[task_type]) using
capability_ratings/cost_entries once a harness has >=SAMPLE_SIZE_FLOOR
samples for the task type; round-robins across the eligible set below that
floor instead of defaulting to one hardcoded harness.

See docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md
Section 2.
"""
import sqlite3
from statistics import median
from typing import Optional

SAMPLE_SIZE_FLOOR = 5
SCORE_COST_DIVISOR = {
    "implement": 50.0,
    "test": 50.0,
    "review": 30.0,
    "refactor": 50.0,
    "cli-plumbing": 50.0,
}
_DEFAULT_SCORE_COST_DIVISOR = 50.0


class LiveQueryRouter:
    """Selects one harness from an eligible set for a task type."""

    def select(self, eligible_harnesses: list[str], task_type: str, db_conn: sqlite3.Connection) -> str:
        if not eligible_harnesses:
            raise ValueError("eligible_harnesses must be non-empty")
        if len(eligible_harnesses) == 1:
            return eligible_harnesses[0]

        samples = {h: self._sample_count(db_conn, h, task_type) for h in eligible_harnesses}
        below_floor = [h for h in eligible_harnesses if samples[h] < SAMPLE_SIZE_FLOOR]
        if below_floor:
            return self._round_robin(db_conn, task_type, eligible_harnesses)

        scored = [
            (self._score(db_conn, h, task_type), -samples[h], h)
            for h in eligible_harnesses
        ]
        scored.sort()  # lowest score first, then higher sample_count (more negative), then alphabetical
        return scored[0][2]

    def _sample_count(self, conn: sqlite3.Connection, harness: str, task_type: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) FROM capability_ratings WHERE agent=? AND discipline=?",
            (harness, task_type),
        ).fetchone()
        return row[0] if row else 0

    def _score(self, conn: sqlite3.Connection, harness: str, task_type: str) -> float:
        cycles = [
            row[0] for row in conn.execute(
                "SELECT pr_review_cycles FROM capability_ratings "
                "WHERE agent=? AND discipline=? AND pr_review_cycles IS NOT NULL",
                (harness, task_type),
            ).fetchall()
        ]
        costs = [
            row[0] for row in conn.execute(
                "SELECT total_cost_usd FROM cost_entries "
                "WHERE agent=? AND type_id=? AND total_cost_usd IS NOT NULL",
                (harness, task_type),
            ).fetchall()
        ]
        divisor = SCORE_COST_DIVISOR.get(task_type, _DEFAULT_SCORE_COST_DIVISOR)
        median_cycles = median(cycles) if cycles else 0.0
        median_cost = median(costs) if costs else 0.0
        return median_cycles + (median_cost / divisor)

    def _round_robin(self, conn: sqlite3.Connection, task_type: str, eligible_harnesses: list[str]) -> str:
        row = conn.execute(
            "SELECT cursor FROM routing_rotation_state WHERE task_type=?", (task_type,)
        ).fetchone()
        cursor = row[0] if row else 0
        picked = eligible_harnesses[cursor % len(eligible_harnesses)]
        conn.execute(
            "INSERT INTO routing_rotation_state (task_type, cursor, updated_at) "
            "VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(task_type) DO UPDATE SET cursor=excluded.cursor, updated_at=excluded.updated_at",
            (task_type, cursor + 1),
        )
        conn.commit()
        return picked
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_routing.py -v`
Expected: PASS (5 tests)

- [ ] **Step 4: Commit**

```bash
git add synlynk/routing.py tests/test_routing.py
git commit -m "feat: add LiveQueryRouter for capability-based auto-dispatch routing"
```

---

### Task 4: Wire `LiveQueryRouter` into `_resolve_dispatch_agent`'s fallback branch

**Files:**
- Modify: `synlynk/dispatch.py:321-362` (`_resolve_dispatch_agent`)
- Test: `tests/test_dispatch_auto_routing.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import sqlite3
from unittest.mock import patch

from synlynk.dispatch import _resolve_dispatch_agent


def _make_db_with_floor(agent: str, task_type: str, cycles: float, n: int):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE capability_ratings (story_id TEXT, agent TEXT, discipline TEXT, pr_review_cycles REAL)")
    conn.execute("CREATE TABLE cost_entries (agent TEXT, type_id TEXT, total_cost_usd REAL)")
    conn.execute("CREATE TABLE routing_rotation_state (task_type TEXT PRIMARY KEY, cursor INTEGER NOT NULL DEFAULT 0, updated_at TEXT)")
    for i in range(n):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) VALUES (?, ?, ?, ?)",
            (f"s{i}", agent, task_type, cycles),
        )
    conn.commit()
    return conn


def test_auto_consults_live_router_instead_of_static_fallback(tmp_path):
    config_path = tmp_path / "workspace.json"
    config_path.write_text(json.dumps({"local_fallback": "agy", "local_auto_threshold": 0.5}))
    conn = _make_db_with_floor("codex", "implement", 1.0, 5)
    for i in range(5):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) VALUES (?, ?, ?, ?)",
            (f"g{i}", "grok", "implement", 3.0),
        )
    conn.commit()
    with patch("synlynk.dispatch._preflight_local_silent", return_value=False), \
         patch("synlynk.dispatch._eligible_harnesses_for_task_type", return_value=["codex", "grok"]):
        result = _resolve_dispatch_agent("auto", "implement", conn, config_path=str(config_path))
    # codex has the better (lower) score, must win over the hardcoded "agy" default.
    assert result == "codex"
```

Run: `pytest tests/test_dispatch_auto_routing.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.dispatch' has no attribute '_eligible_harnesses_for_task_type'` (or the test asserts `result == "agy"` today — confirm it fails for the right reason before proceeding)

- [ ] **Step 2: Add `_eligible_harnesses_for_task_type` helper and wire the router**

In `synlynk/dispatch.py`, add a new helper near `_read_local_fallback` (after line 259):

```python
def _eligible_harnesses_for_task_type(task_type: str, config_path: str = ".synlynk/policy.json") -> list[str]:
    """Read the primary + fallback harness list for a task_type from policy.json.

    Returns [] if policy.json is missing, malformed, or the task_type has no
    entry — callers must fall back to _read_local_fallback() in that case.
    """
    try:
        with open(config_path) as handle:
            policy = json.load(handle)
        allocation = policy["overrides"]["dev_authority"]["task_allocation"].get(task_type)
        if not allocation:
            return []
        harnesses = [allocation["harness"]] + list(allocation.get("fallback", []))
        return [h for h in harnesses if h != "local"]
    except Exception:
        return []
```

Then change the two non-local-fallback sites inside `_resolve_dispatch_agent` (lines 341-362) from:

```python
    fallback = _read_local_fallback(config_path)
```

to:

```python
    eligible = _eligible_harnesses_for_task_type(task_type)
    if len(eligible) > 1:
        from synlynk.routing import LiveQueryRouter
        fallback = LiveQueryRouter().select(eligible, task_type, db)
    elif eligible:
        fallback = eligible[0]
    else:
        fallback = _read_local_fallback(config_path)
```

Note `fallback` is computed once, before the `if not _preflight_local_silent():`/`score >= threshold` branches that both reference it — so this replacement happens exactly once, at line 341, not duplicated at both use sites.

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_dispatch_auto_routing.py -v`
Expected: PASS

- [ ] **Step 4: Run the existing dispatch test suite to check for regressions**

Run: `pytest tests/test_dispatch.py tests/test_parity.py -v`
Expected: PASS (no regressions — `_read_local_fallback` is still used as the final fallback when `policy.json` has no entry for the task type, so existing single-fallback behavior is preserved for any task_type not in `task_allocation`)

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch_auto_routing.py
git commit -m "feat: wire LiveQueryRouter into auto-dispatch's non-local fallback path"
```

---

### Task 5: Harness manifest schema + `discover_and_validate`

**Files:**
- Create: `synlynk/harness_manifest.py`
- Test: `tests/test_harness_manifest.py`

- [ ] **Step 1: Write the failing tests**

```python
import json
import os

import pytest

from synlynk.harness_manifest import HARNESS_BILLING_CONFIG_INVALID, discover_and_validate


def test_discover_and_validate_writes_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    manifest = discover_and_validate("claude")
    assert manifest["harness"] == "claude"
    assert manifest["manifest_schema_version"] == 1
    assert "cli_version_hash" in manifest
    path = os.path.join(".synlynk", "harnesses", "claude.json")
    assert os.path.exists(path)
    with open(path) as f:
        on_disk = json.load(f)
    assert on_disk == manifest


def test_per_token_billing_without_rate_fails_closed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    # muse is per_token billing (not subscription) per HARNESS_CAPABILITY_BASELINES/_payment_model_config_for_agent,
    # and no .synlynk/billing.json exists in this tmp_path — must fail closed.
    with pytest.raises(ValueError) as exc:
        discover_and_validate("muse")
    assert HARNESS_BILLING_CONFIG_INVALID in str(exc.value)


def test_per_token_billing_with_rate_succeeds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/billing.json", "w") as f:
        json.dump({"muse": {"cost_per_1k_tokens": {"input": 0.00125, "output": 0.00425}}}, f)
    manifest = discover_and_validate("muse")
    assert manifest["harness"] == "muse"
```

Run: `pytest tests/test_harness_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.harness_manifest'`

- [ ] **Step 2: Implement `synlynk/harness_manifest.py`**

First check how `_payment_model_config_for_agent` reports billing mode by running:
```bash
python3 -c "from synlynk.costs import _payment_model_config_for_agent; print(_payment_model_config_for_agent('muse'))"
```
Use whatever key that prints (confirmed during grounding: `.get('mode')`, default `'pay_as_you_go'` — treat `'pay_as_you_go'`/`'credit_grant'` as per-token modes requiring a billing rate, and `'subscription'` as exempt) to decide which harnesses the billing check applies to.

```python
"""Per-harness manifest discovery and validation.

Writes .synlynk/harnesses/{harness}.json recording models, native CLI flags,
auth model, MCP tool list, CLI version hash, and last validated smoke-run
result. See docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md
Section 3.
"""
import hashlib
import json
import os
import subprocess

from synlynk._constants import HARNESS_CAPABILITY_BASELINES

MANIFEST_SCHEMA_VERSION = 1
HARNESS_BILLING_CONFIG_INVALID = "HARNESS_BILLING_CONFIG_INVALID"
_MANIFEST_DIR = os.path.join(".synlynk", "harnesses")


def _cli_version_hash(cli_name: str) -> str:
    try:
        result = subprocess.run([cli_name, "--version"], capture_output=True, text=True, timeout=10)
        version_text = (result.stdout or result.stderr or "").strip()
    except Exception:
        version_text = "unknown"
    return hashlib.sha256(version_text.encode()).hexdigest()[:16]


def _billing_rate_configured(harness: str) -> bool:
    from synlynk.costs import _payment_model_config_for_agent

    mode = (_payment_model_config_for_agent(harness) or {}).get("mode", "pay_as_you_go")
    if mode == "subscription":
        return True
    billing_path = os.path.join(".synlynk", "billing.json")
    if not os.path.exists(billing_path):
        return False
    try:
        with open(billing_path) as f:
            billing = json.load(f)
        rate = billing.get(harness, {}).get("cost_per_1k_tokens")
        return isinstance(rate, dict) and "input" in rate and "output" in rate
    except Exception:
        return False


def discover_and_validate(harness: str) -> dict:
    """Discover a harness's real CLI shape and write its manifest.

    Raises ValueError(HARNESS_BILLING_CONFIG_INVALID) if the harness is
    billed per-token and no non-placeholder rate is configured.
    """
    baseline = HARNESS_CAPABILITY_BASELINES.get(harness, {})
    if not _billing_rate_configured(harness):
        raise ValueError(
            f"{HARNESS_BILLING_CONFIG_INVALID}: {harness} is billed per-token "
            f"but has no cost_per_1k_tokens configured in .synlynk/billing.json"
        )

    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "harness": harness,
        "models": baseline.get("models", []),
        "native_cli_flags": baseline.get("dispatch_flags", {}),
        "auth_model": baseline.get("panel_auth_check", {}),
        "mcp_tools": baseline.get("mcp_tools", []),
        "cli_version_hash": _cli_version_hash(baseline.get("cli", harness)),
        "last_validated_smoke_run": None,
    }
    os.makedirs(_MANIFEST_DIR, exist_ok=True)
    with open(os.path.join(_MANIFEST_DIR, f"{harness}.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_harness_manifest.py -v`
Expected: PASS. If `test_per_token_billing_without_rate_fails_closed` fails because `claude`'s own mode is not `"subscription"` in this repo's actual `_payment_model_config_for_agent` output, swap that test to use whichever harness the real printed output showed as non-subscription (don't force `muse` if the real config disagrees — use the actual data).

- [ ] **Step 4: Commit**

```bash
git add synlynk/harness_manifest.py tests/test_harness_manifest.py
git commit -m "feat: add harness manifest discovery/validation with billing fail-closed check"
```

---

### Task 6: `synlynk harness onboard`/`probe` CLI subcommands

**Files:**
- Modify: `synlynk/cli.py` (parser section near line 504-540, dispatch section near line 3925-3963)
- Test: `tests/test_cli_harness_subcommand.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import subprocess
import sys


def test_harness_onboard_writes_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "synlynk.cli", "harness", "onboard", "--harness", "claude"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".synlynk" / "harnesses" / "claude.json").exists()


def test_harness_probe_without_discover_reads_existing_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manifest_dir = tmp_path / ".synlynk" / "harnesses"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "claude.json").write_text(json.dumps({"harness": "claude", "cli_version_hash": "abc123"}))
    result = subprocess.run(
        [sys.executable, "-m", "synlynk.cli", "harness", "probe", "--harness", "claude"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "abc123" in result.stdout
```

Run: `pytest tests/test_cli_harness_subcommand.py -v`
Expected: FAIL with argparse error `invalid choice: 'harness'`

- [ ] **Step 2: Add the `harness` subparser**

Mirror the exact pattern already used for `tool_parser`/`tool_sub` at `synlynk/cli.py:504-507` and `connector_parser`/`connector_sub` at `synlynk/cli.py:524-527`. Add immediately after the `connector_add_parser` block (after line ~539):

```python
    harness_parser = subparsers.add_parser(
        "harness", help="Discover, validate, and probe per-harness manifests"
    )
    harness_sub = harness_parser.add_subparsers(dest="harness_action")
    harness_onboard_parser = harness_sub.add_parser("onboard", help="Discover a harness's CLI shape and write its manifest")
    harness_onboard_parser.add_argument("--harness", required=True)
    harness_probe_parser = harness_sub.add_parser("probe", help="Read or re-discover a harness manifest")
    harness_probe_parser.add_argument("--harness", required=True)
    harness_probe_parser.add_argument("--discover", action="store_true",
        help="Re-run discovery instead of reading the existing manifest")
```

Also add `"harness"` to the top-level command list near line 324 (`"help", "init", ..., "tool",` → add `, "harness"`).

- [ ] **Step 3: Add the dispatch handler**

Mirror the `elif args.command == "tool":` block at `synlynk/cli.py:3925-3943`. Add a sibling `elif` branch immediately after the `connector` branch (after line ~3963):

```python
    elif args.command == "harness":
        from synlynk.harness_manifest import discover_and_validate
        action = getattr(args, "harness_action", None)
        if action == "onboard":
            try:
                manifest = discover_and_validate(args.harness)
                print(json.dumps(manifest, indent=2))
            except ValueError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)
        elif action == "probe":
            manifest_path = os.path.join(".synlynk", "harnesses", f"{args.harness}.json")
            if args.discover or not os.path.exists(manifest_path):
                try:
                    manifest = discover_and_validate(args.harness)
                except ValueError as exc:
                    print(f"Error: {exc}", file=sys.stderr)
                    sys.exit(1)
            else:
                with open(manifest_path) as f:
                    manifest = json.load(f)
            print(json.dumps(manifest, indent=2))
        else:
            help_parsers.get("harness", parser).print_help()
```

Also add `"harness": harness_parser,` to the `help_parsers` dict near line 2222.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_harness_subcommand.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py tests/test_cli_harness_subcommand.py
git commit -m "feat: add synlynk harness onboard/probe CLI subcommands"
```

---

### Task 7: CLI-version-hash-triggered manifest rediscovery in `_preflight_dispatch`

**Files:**
- Modify: `synlynk/dispatch.py` (`_preflight_dispatch`, starting at line 3998)
- Test: `tests/test_dispatch_manifest_revalidation.py`

- [ ] **Step 1: Read `_preflight_dispatch`'s current body in full**

Run: `sed -n '3998,4120p' synlynk/dispatch.py` to see exactly where in its existing sequence of checks (auth, headless-permission, capacity) a manifest check should be inserted. Insert it right after the `headless_failure` check at line 4218-4220 (before the capacity-budget block) since manifest validity is a preflight gate like the others, not a budget concern.

- [ ] **Step 2: Write the failing tests**

```python
import json
import os

from synlynk.dispatch import _preflight_dispatch


def test_missing_manifest_triggers_inline_discovery(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _preflight_dispatch(
        "claude", task="test task", permissions=[], dispatch_flags=[],
        db_conn=None, force_agent=False,
    )
    assert os.path.exists(os.path.join(".synlynk", "harnesses", "claude.json"))


def test_version_hash_mismatch_fails_closed_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    with open(".synlynk/harnesses/claude.json", "w") as f:
        json.dump({"harness": "claude", "cli_version_hash": "stale-hash-0000"}, f)
    result = _preflight_dispatch(
        "claude", task="test task", permissions=[], dispatch_flags=[],
        db_conn=None, force_agent=False,
    )
    assert result is not None
    assert result.get("passed") is False
    assert result.get("sentinel") == "HARNESS_MANIFEST_REVALIDATION_FAILED"


def test_version_hash_mismatch_passes_with_force_harness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    with open(".synlynk/harnesses/claude.json", "w") as f:
        json.dump({"harness": "claude", "cli_version_hash": "stale-hash-0000"}, f)
    result = _preflight_dispatch(
        "claude", task="test task", permissions=[], dispatch_flags=[],
        db_conn=None, force_agent=True,
    )
    assert not (isinstance(result, dict) and result.get("sentinel") == "HARNESS_MANIFEST_REVALIDATION_FAILED")
```

Run: `pytest tests/test_dispatch_manifest_revalidation.py -v`
Expected: FAIL — `test_missing_manifest_triggers_inline_discovery` fails because no manifest is written yet; adjust exact assertions after confirming `_preflight_dispatch`'s real parameter names via `grep -n "^def _preflight_dispatch" -A 20 synlynk/dispatch.py` before finalizing this test (the plan's draft signature here must match — if the real signature differs, use the real parameter names instead of guessing).

- [ ] **Step 3: Add the manifest-revalidation check**

Insert after the `headless_failure` check (after line 4220):

```python
    try:
        from synlynk.harness_manifest import _cli_version_hash, discover_and_validate
        from synlynk._constants import HARNESS_CAPABILITY_BASELINES

        manifest_path = os.path.join(".synlynk", "harnesses", f"{harness_name}.json")
        baseline = HARNESS_CAPABILITY_BASELINES.get(harness_name, {})
        if not os.path.exists(manifest_path):
            discover_and_validate(harness_name)
        else:
            with open(manifest_path) as f:
                manifest = json.load(f)
            current_hash = _cli_version_hash(baseline.get("cli", harness_name))
            if manifest.get("cli_version_hash") != current_hash and not force_agent:
                return {
                    "passed": False,
                    "sentinel": "HARNESS_MANIFEST_REVALIDATION_FAILED",
                    "reason": (
                        f"{harness_name}'s CLI version changed since its manifest was "
                        f"written (manifest={manifest.get('cli_version_hash')}, "
                        f"current={current_hash}); re-run `synlynk harness probe "
                        f"--harness {harness_name} --discover` or pass --force-harness."
                    ),
                }
            if manifest.get("cli_version_hash") != current_hash and force_agent:
                discover_and_validate(harness_name)
    except ValueError:
        # Billing-config failures from discover_and_validate surface through
        # the same manifest-check sentinel rather than crashing preflight.
        return {
            "passed": False,
            "sentinel": "HARNESS_MANIFEST_REVALIDATION_FAILED",
            "reason": f"{harness_name}'s manifest could not be (re)validated; see HARNESS_BILLING_CONFIG_INVALID.",
        }
    except Exception:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch_manifest_revalidation.py -v`
Expected: PASS

- [ ] **Step 5: Run full dispatch preflight suite for regressions**

Run: `pytest tests/test_dispatch.py -k preflight -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch_manifest_revalidation.py
git commit -m "feat: fail closed on stale harness manifest at dispatch preflight"
```

---

### Task 8: Fix the Muse billing-rate bug

**Files:**
- Modify: `synlynk/costs.py:695`
- Test: `tests/test_costs_muse_rate.py`

- [ ] **Step 1: Write the failing test**

```python
from synlynk.costs import _HARDCODED_FALLBACK_RATES, _model_rate_for_version


def test_muse_rate_is_not_the_generic_default():
    muse_rate = _HARDCODED_FALLBACK_RATES["models"]["muse-spark-1.3"]
    claude_sonnet_rate = _HARDCODED_FALLBACK_RATES["models"]["claude-sonnet-4-6"]
    assert muse_rate != claude_sonnet_rate, (
        "muse-spark-1.3 must not silently reuse the Claude Sonnet rate shape"
    )


def test_model_rate_for_version_returns_real_muse_rate():
    rate = _model_rate_for_version("muse-spark-1.3", agent="muse")
    assert rate == {"input": 0.00125, "output": 0.00425, "cache_read": 0.00015}
```

Run: `pytest tests/test_costs_muse_rate.py -v`
Expected: FAIL (`muse_rate == claude_sonnet_rate` since both are currently `_DEFAULT_MODEL_RATE`)

- [ ] **Step 2: Fix the constant**

In `synlynk/costs.py`, change line 695 from:

```python
        "muse-spark-1.3": _DEFAULT_MODEL_RATE,
```

to:

```python
        "muse-spark-1.3": {"input": 0.00125, "output": 0.00425, "cache_read": 0.00015},
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_costs_muse_rate.py -v`
Expected: PASS

- [ ] **Step 4: Run the existing costs suite for regressions**

Run: `pytest tests/test_costs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_costs_muse_rate.py
git commit -m "fix: use real Meta Standard-tier rate for muse-spark-1.3 instead of the generic default"
```

---

### Task 9: `--allow-reroute` flag + fail-closed gate for local-harness reroute

**Files:**
- Modify: `synlynk/cli.py` (dispatch parser near line 1348-1362, dispatch_agent call near line 3123-3157)
- Modify: `synlynk/dispatch.py` (`dispatch_agent` signature at line 4579, reroute block at line 4771-4780)
- Test: `tests/test_dispatch_local_reroute_gate.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from synlynk.dispatch import dispatch_agent


def test_local_reroute_without_allow_reroute_fails_closed(monkeypatch):
    """When agent="local" resolves through the pipeline to something else,
    and --allow-reroute was not passed, dispatch must refuse rather than
    silently substitute a different harness."""
    class _FakeRequest:
        agent = "agy"  # pipeline rerouted away from "local"

    class _FakePipeline:
        def resolve(self, request):
            return _FakeRequest()
        def authorize(self, request):
            return request

    monkeypatch.setattr("synlynk.dispatch_pipeline.build_pipeline", lambda: _FakePipeline())
    with pytest.raises(RuntimeError) as exc:
        dispatch_agent("local", "test task", allow_reroute=False, skip_preflight=True)
    assert "allow-reroute" in str(exc.value).lower() or "allow_reroute" in str(exc.value).lower()


def test_local_reroute_with_allow_reroute_proceeds(monkeypatch):
    class _FakeRequest:
        agent = "agy"

    class _FakePipeline:
        def resolve(self, request):
            return _FakeRequest()
        def authorize(self, request):
            return request

    monkeypatch.setattr("synlynk.dispatch_pipeline.build_pipeline", lambda: _FakePipeline())
    # Should not raise for the reroute-gate reason (may still fail later for
    # unrelated environment reasons in a unit-test sandbox — only assert the
    # specific RuntimeError from the gate is absent).
    try:
        dispatch_agent("local", "test task", allow_reroute=True, skip_preflight=True)
    except RuntimeError as exc:
        assert "allow-reroute" not in str(exc).lower()
```

Run: `pytest tests/test_dispatch_local_reroute_gate.py -v`
Expected: FAIL — first confirm the exact mock points by reading `synlynk/dispatch.py:4753-4780` again at implementation time (the plan's `_FakePipeline`/`build_pipeline` names are illustrative; use the real `synlynk.dispatch_pipeline` symbol names found via `grep -n "^def \|^class " synlynk/dispatch_pipeline.py` before finalizing this test) — `TypeError: dispatch_agent() got an unexpected keyword argument 'allow_reroute'`

- [ ] **Step 2: Add the `allow_reroute` parameter and gate**

In `synlynk/dispatch.py`, add to `dispatch_agent`'s signature (after `force_agent: bool = False,` at line 4581):

```python
                   allow_reroute: bool = False,
```

At the reroute block (lines 4771-4780), change:

```python
    probed_agent = take_probed_dispatch_harness()
    initial_agent = agent
    agent = request.agent
```

to:

```python
    probed_agent = take_probed_dispatch_harness()
    initial_agent = agent
    agent = request.agent
    if agent != initial_agent and initial_agent == "local" and not allow_reroute and not force_agent:
        raise RuntimeError(
            f"Refusing silent reroute from local to {agent}: pass --allow-reroute "
            f"to opt in, or --force-harness local to pin it."
        )
```

Keep this immediately before the existing `if agent != initial_agent and not force_agent: print(...)` announcement line — the gate only blocks the `initial_agent == "local"` case; every other reroute (gh-write routing, Grok-sandbox denial, etc.) keeps today's print-only behavior unchanged.

- [ ] **Step 3: Add the `--allow-reroute` CLI flag**

In `synlynk/cli.py`, add after the `--force-harness`/`--force-agent` argument (after line 1351):

```python
    dispatch_parser.add_argument(
        "--allow-reroute", action="store_true", dest="allow_reroute",
        help="Opt in to a silent local-harness reroute (e.g. to a capability fallback) "
             "instead of failing closed. Only affects agent=local dispatches.",
    )
```

And thread it into the `dispatch_agent(...)` call (after line 3128's `force_agent=(...)` block):

```python
                                 allow_reroute=getattr(args, "allow_reroute", False),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch_local_reroute_gate.py -v`
Expected: PASS

- [ ] **Step 5: Run the dispatch suite for regressions**

Run: `pytest tests/test_dispatch.py -v`
Expected: PASS (the gate only fires for `initial_agent == "local"` with a real agent mismatch, which no existing test should be relying on silently passing through)

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py synlynk/dispatch.py tests/test_dispatch_local_reroute_gate.py
git commit -m "feat: fail closed on silent local-harness reroute unless --allow-reroute is passed"
```

---

### Task 10: `requested_harness` migration for `cost_entries` and `capability_ratings` (m0036)

**Files:**
- Create: `synlynk/migrations/m0036_requested_harness_attribution.py`
- Test: `tests/migrations/test_m0036_requested_harness_attribution.py`

- [ ] **Step 1: Write the failing test**

```python
import sqlite3

from synlynk.migrations.m0036_requested_harness_attribution import MIGRATION


def test_m0036_adds_requested_harness_to_both_tables():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE cost_entries (agent TEXT, type_id TEXT)")
    conn.execute("CREATE TABLE capability_ratings (story_id TEXT, agent TEXT)")
    MIGRATION.up(conn)
    cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    cap_cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_ratings)")}
    assert "requested_harness" in cost_cols
    assert "requested_harness" in cap_cols


def test_m0036_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE cost_entries (agent TEXT, type_id TEXT)")
    conn.execute("CREATE TABLE capability_ratings (story_id TEXT, agent TEXT)")
    MIGRATION.up(conn)
    MIGRATION.up(conn)  # must not raise
```

Run: `pytest tests/migrations/test_m0036_requested_harness_attribution.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 2: Write the migration**

```python
"""Migration 36: requested_harness attribution on cost_entries/capability_ratings.

daemon_jobs already records requested_harness/actual_harness (see db_schema.py
and db.py's defensive ALTER TABLE loop) via dispatch.py's
_log_routing_fallback/take_routing_fallback mechanism. cost_entries and
capability_ratings had no equivalent column, so a reroute (e.g. local ->
fallback) was never attributable in cost or quality-rating reporting, only
in the job record itself. This migration extends the same, already-proven
pattern to both tables; synlynk/db.py:_insert_cost_row and
synlynk/jobs.py:_write_capability_rating are updated in a follow-up task to
actually populate it from the job row's own requested_harness value.

See docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md
Section 6.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    for table in ("cost_entries", "capability_ratings"):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "requested_harness" not in cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN requested_harness TEXT")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise


MIGRATION = Migration(version=36, name="requested_harness_attribution", up=_up)
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/migrations/test_m0036_requested_harness_attribution.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add synlynk/migrations/m0036_requested_harness_attribution.py tests/migrations/test_m0036_requested_harness_attribution.py
git commit -m "feat: add requested_harness column to cost_entries/capability_ratings (m0036)"
```

---

### Task 11: Thread `requested_harness` into `_insert_cost_row` and `_write_capability_rating`

**Files:**
- Modify: `synlynk/db.py:2693` (`_insert_cost_row`)
- Modify: `synlynk/jobs.py:2037` (`_write_capability_rating`), `synlynk/jobs.py:2169-2186` (its INSERT statement)
- Test: `tests/test_requested_harness_attribution.py`

- [ ] **Step 1: Write the failing tests**

```python
import sqlite3

from synlynk.db import _insert_cost_row


def test_insert_cost_row_persists_requested_harness(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT, agent TEXT, model TEXT,
            input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER,
            story_id TEXT, type_id TEXT, epic_id INTEGER, phase_id INTEGER,
            total_cost_usd REAL, api_equivalent_usd REAL, actual_usd REAL, payment_mode TEXT,
            notes TEXT, cost_source TEXT NOT NULL, estimate_basis TEXT, job_id TEXT,
            recorded_at TEXT, dispatch_context TEXT, context_mode TEXT, session_id TEXT,
            pr_number INTEGER, harness TEXT, agent_role TEXT, decision_revision INTEGER,
            requested_harness TEXT
        )
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr("synlynk._get_db", lambda *a, **k: sqlite3.connect(db_path))
    _insert_cost_row(
        session_date="2026-11-18", agent="agy", harness="agy",
        cost_source="actual", total_cost_usd=1.0, requested_harness="local",
        db_path=db_path,
    )
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT requested_harness FROM cost_entries").fetchone()
    assert row[0] == "local"
```

Run: `pytest tests/test_requested_harness_attribution.py -v`
Expected: FAIL with `TypeError: _insert_cost_row() got an unexpected keyword argument 'requested_harness'`

- [ ] **Step 2: Add the parameter and column to `_insert_cost_row`**

In `synlynk/db.py`, add to the signature (after `agent_role: str = None,` near line 2716):

```python
    requested_harness: str = None,
```

Find the function's actual `INSERT INTO cost_entries` statement (confirmed during grounding this is further down in the same function body, not shown in the excerpt read so far — run `sed -n '2693,2913p' synlynk/db.py` at implementation time to find the real column/value list) and add `requested_harness` to both the column list and the values tuple, defaulting to `harness_val` (the already-computed `harness or agent` value at line 2736) when the caller didn't pass one explicitly:

```python
    if requested_harness is None:
        requested_harness = harness_val
```//
Place this line right after `harness_val = harness or agent` (existing line 2736), then add `requested_harness` as a bound parameter in the real INSERT (match whatever placeholder style — `?` positional — the existing statement already uses).

- [ ] **Step 3: Thread it through from `_write_capability_rating`'s call site in `jobs.py`**

In `synlynk/jobs.py`'s `_write_capability_rating` (starting line 2037), the `job` dict passed in already carries `requested_harness` when the daemon_jobs row populated it (confirmed during grounding: `job["requested_harness"] = routing_fallback.get("requested_harness")` at `dispatch.py:6041`, and `jobs.py:3472`'s SELECT already reads `requested_harness` from `daemon_jobs` for other call sites). Add:

```python
    requested_harness = job.get("requested_harness") or agent
```

immediately after the existing `agent = job.get("agent", "unknown")` line (line 2056), and add `requested_harness` to both the column list and values tuple of the `INSERT INTO capability_ratings` statement (lines 2170-2186):

```python
    conn.execute(
        """INSERT INTO capability_ratings
           (story_id, agent, model_version, model_at_dispatch, model_at_completion, split_model,
            engg_domain, discipline, org_domain, role, stage, stack_tags, industry, phase,
            signal_source, quality, quality_auto,
            verifier_agent, verifier_model,
            test_pass_rate, build_success,
            dispatch_rework, micro_rework, pr_review_cycles,
            duration_vs_estimate, verified_by_ci, correct, ed25519_sig, requested_harness)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (story_id, agent, model_version, model_at_dispatch, model_at_completion, split_model,
         engg_domain, story_discipline, org_domain, role, stage, stack_tags, industry, phase,
         signal_source, quality, quality_auto,
         verifier_agent_val, verifier_model,
         signals["test_pass_rate"], signals["build_success"],
         dispatch_rework, micro_rework, signals.get("pr_review_cycles"),
         None, signals.get("verified_by_ci"), correct, ed25519_sig, requested_harness)
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_requested_harness_attribution.py -v`
Expected: PASS

- [ ] **Step 5: Run the cost/capability-rating suites for regressions**

Run: `pytest tests/test_costs.py tests/test_jobs.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py synlynk/jobs.py tests/test_requested_harness_attribution.py
git commit -m "feat: persist requested_harness on cost_entries/capability_ratings writes"
```

---

### Task 12: MCP smoke-run in `discover_and_validate`

**Files:**
- Modify: `synlynk/harness_manifest.py` (`discover_and_validate`, from Task 5)
- Test: `tests/test_harness_manifest.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch

from synlynk.harness_manifest import discover_and_validate


def test_discover_and_validate_runs_mcp_smoke_check_when_harness_declares_mcp_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    with patch("synlynk.doctor._run_tc8", return_value={"passed": True, "servers_checked": 1}) as mock_tc8:
        manifest = discover_and_validate("claude")
    if manifest.get("mcp_tools"):
        mock_tc8.assert_called_once()
        assert manifest["last_validated_smoke_run"] is not None
```

Run: `pytest tests/test_harness_manifest.py::test_discover_and_validate_runs_mcp_smoke_check_when_harness_declares_mcp_tools -v`
Expected: FAIL (mock not called — no MCP smoke-run wired yet). If `claude`'s baseline has no `mcp_tools` entry, check `HARNESS_CAPABILITY_BASELINES` for a harness that does (`grep -n "mcp_tools" synlynk/_constants.py`) and use that harness in the test instead.

- [ ] **Step 2: Wire the smoke-run into `discover_and_validate`**

In `synlynk/harness_manifest.py`, after building the `manifest` dict and before writing it to disk, add:

```python
    if manifest["mcp_tools"]:
        from synlynk.doctor import _run_tc8
        tc8_result = _run_tc8()
        manifest["last_validated_smoke_run"] = {
            "passed": tc8_result.get("passed", False),
            "servers_checked": tc8_result.get("servers_checked"),
        }
```

Place this before the existing `os.makedirs(_MANIFEST_DIR, exist_ok=True)` line so the smoke-run result is included in what gets written.

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_harness_manifest.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add synlynk/harness_manifest.py tests/test_harness_manifest.py
git commit -m "feat: run MCP smoke-check during harness manifest discovery"
```

---

### Task 13: Preflight sentinel-site audit

**Files:**
- Modify: `synlynk/dispatch.py` (`_dispatch_capability_preflight` lines 3840-3997, `_preflight_dispatch` lines 3998-4341+Task 7's addition) — fixes only if gaps are found, no speculative changes
- Test: `tests/test_preflight_sentinel_audit.py`

- [ ] **Step 1: Read both functions in full**

Run: `sed -n '3840,4341p' synlynk/dispatch.py` and read every `return {"passed": False, "sentinel": ...}` site.

- [ ] **Step 2: Write a test enumerating the 7 expected sentinels**

```python
import re

_EXPECTED_SENTINELS = {
    "HARNESS_PREFLIGHT_FAIL",
    "LOCAL_CAPABILITY_UNAVAILABLE",
    "LOCAL_ORBSTACK_UNAVAILABLE",
    "INSTRUCTION_FILE_MISSING",
    "MCP_SERVER_MISSING",
    "CAPACITY_EXCEEDED_INPUT",
    "CAPACITY_EXCEEDED_OUTPUT",
    "GOVERNS_LINKAGE_MISSING",
    "HARNESS_MANIFEST_REVALIDATION_FAILED",  # added by Task 7
}


def test_every_preflight_sentinel_is_cataloged():
    with open("synlynk/dispatch.py") as f:
        text = f.read()
    start = text.index("def _dispatch_capability_preflight")
    end = text.index("\ndef dispatch_agent")  # covers both preflight functions
    body = text[start:end]
    found = set(re.findall(r'"sentinel":\s*"([A-Z_]+)"', body))
    uncataloged = found - _EXPECTED_SENTINELS
    assert not uncataloged, f"Uncataloged sentinel(s) found: {uncataloged} — add to _EXPECTED_SENTINELS if intentional, or fix the site"
```

Run: `pytest tests/test_preflight_sentinel_audit.py -v`
Expected: Run it first to see what it actually reports — this is a discovery test, not a guaranteed-to-fail one. If it finds an uncataloged sentinel, that is this task's real finding.

- [ ] **Step 3: Resolve any finding**

If the test fails with an uncataloged sentinel: read that specific call site, determine whether it's a legitimate 9th sentinel this plan's catalog missed (add it to `_EXPECTED_SENTINELS` and note it in this plan's own task list via a follow-up commit message explaining why) or a genuine typo/divergent duplicate of one of the 7 (fix the site to use the canonical sentinel name). Do not guess which case applies without reading the surrounding code for that specific site.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_preflight_sentinel_audit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_preflight_sentinel_audit.py synlynk/dispatch.py
git commit -m "test: audit preflight sentinel sites against the cataloged set"
```

---

### Task 14: Full regression pass + plan-level self-review commit

**Files:** None new — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: All tests pass, including every test added in Tasks 1-13.

- [ ] **Step 2: Run `synlynk doctor` (or project-equivalent smoke check) if available**

Run: `python3 bin/synlynk.py doctor` (or `synlynk doctor` if installed)
Expected: No new failures attributable to this branch's changes (pre-existing unrelated failures, if any, are out of scope — note them but don't block on them).

- [ ] **Step 3: Confirm GOVERNS linkage for this work**

Per CLAUDE.md's "100% GOVERNS adherence" requirement, confirm this branch's dispatched work (if executed via `synlynk dispatch` rather than inline) links to the goal/story tracking this redesign (the one the committed spec and this plan both belong to). Run `synlynk story status <story-id>` or equivalent to confirm.

- [ ] **Step 4: Final commit if any cleanup was needed**

```bash
git status --short
# If clean, nothing to do. If not, stage and commit any leftover changes with a descriptive message.
```

---

## Explicitly Out of Scope (per the spec)

- Spec B / issue #5353 (cross-harness instruction-adherence verification) — no tasks here.
- Instruction-file-duplication templating system — ticketed in Task 1, not built.
- Re-litigating the `n>=5` sample-size floor or the PM-approved canaried fold-back gate — unchanged, reused as-is in Task 3.
