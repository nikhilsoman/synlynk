# Harness Parity Phase 3 Mechanics — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace synlynk's hand-authored, per-task-type fixed-harness lookup table with a policy `eligibility` block (every harness eligible for every task type, subject to runtime capability checks) plus a live-scored `routing.py` module that ranks harnesses from measured `capability_ratings`/`cost_entries` history; add per-harness manifests with onboarding/probe commands and CLI-version-triggered revalidation; fix the Muse budget-ledger blind spot and the `local` harness's silent-reroute attribution bug.

**Architecture:** `synlynk/routing.py` is a new module exposing a `Router` protocol and a `LiveQueryRouter` implementation that queries `capability_ratings`/`cost_entries` (joined via `story_id`, scored by median `pr_review_cycles` and average `total_cost_usd`, floored by `min_sample_size`) and falls back to deterministic round-robin via a new `harness_status.last_routed_task_types` column when no candidate clears the floor. It supersedes `synlynk/capability.py:ranked_harness_for_task`'s incumbent-vs-fallback-only model and is wired into `synlynk/dispatch.py:_infer_dispatch_defaults` (the real fixed-lane consultation site — **not** `_resolve_dispatch_agent`, whose `auto` branch is the unrelated Local Pilot mechanism). A new `synlynk/harness_manifest.py` owns manifest discovery/validation, shared by new `synlynk harness onboard` / `synlynk harness probe --discover` CLI subcommands (nested under a new `harness` parser group so they don't collide with the existing bare `probe` deps-check command). `policy.json` gains a top-level `eligibility` block and loses `overrides.dev_authority.task_allocation`; `.synlynk/capability-roles.json` is retired. Separately, `_preflight_dispatch`'s budget check (dispatch.py:4222-4282) gains a `credit_grants` fallback for harnesses with no `harness_status`/`TIER1_CAPACITY` row (Muse), and dispatch gains an explicit `--allow-reroute` flag gating the `local` harness's silent substitution, with accurate `requested_harness`/`actual_harness` attribution (columns already exist on the job-record table; only the local-specific gate and CLI/status display are new).

**Tech Stack:** Python 3 stdlib only (sqlite3, argparse, json) — matches the rest of `synlynk/`. No new dependencies.

**Grounding deviations from the spec (resolved during pre-task exploration — read before starting):**

1. **`capability_ratings` has no `harness`, `task_type`, or `created_at` columns.** The real columns are `agent` (harness identity), `discipline` (closest existing proxy for task_type — there is no task_type column), and `ts` (timestamp). `cost_entries` has `harness` (matches spec) and `recorded_at` (not `created_at`), joined to `capability_ratings` via `story_id`. The spec's literal Amendment-1 `CREATE INDEX ... (harness, task_type, created_at)` SQL is corrected throughout this plan to use the real column names. This exact join pattern already exists in `synlynk/capability.py:ranked_harness_for_task` (lines 189-258) — `routing.py` extends that pattern rather than inventing a new one.
2. **The real fixed-lane `task_allocation` consultation site is `synlynk/dispatch.py:_infer_dispatch_defaults` (line 977), not `_resolve_dispatch_agent`'s `auto` branch.** `_resolve_dispatch_agent` (line 321) only fires for `requested_agent in (None, "auto")` and its body is entirely the Local Pilot cohort/rebaseline mechanism — it has no task_allocation lookup at all. `_infer_dispatch_defaults` is the function that reads `policy["dev_authority"]["task_allocation"]` (line 999) and already calls `capability.ranked_harness_for_task` (line 1045) to promote a fallback over the table default. This plan wires the new `LiveQueryRouter` into `_infer_dispatch_defaults`, replacing that `ranked_harness_for_task` call.
3. **No `Router`/`LiveQueryRouter`/`_default_router` symbol exists anywhere in the codebase today** (confirmed via grep) — `routing.py` is a wholly new module, as the spec intends.
4. **`harness_status` has no `last_routed_task_types` column** — confirmed via full schema read (`synlynk/db.py:1820-1844`). It is added fresh by this plan's migration.
5. **The exact silent-reroute call site for an explicit `synlynk dispatch local` is not inside `_resolve_dispatch_agent`** (that function passes explicit non-`"auto"` requests through unchanged at line 338-339). Task 11 below starts by locating the real call site via `grep -n 'agent == "local"' synlynk/dispatch.py` and `grep -n '"local"' synlynk/dispatch.py` before patching — do not assume it is in `_resolve_dispatch_agent`.
6. Job records already have `requested_harness`/`actual_harness` columns and persistence logic (`dispatch.py:6041-6042, 6094-6095, 6137, 6168-6169, 6186, 6222-6223`) and `_log_routing_fallback`/`take_routing_fallback` (lines 276-318) already exist and work as the spec's Section 6 describes. The gap is specifically: (a) no gate preventing silent local→fallback substitution without opt-in, and (b) `synlynk jobs`/`synlynk status` not displaying the rerouted-from annotation. Task 11 is narrower than the spec implies — most of the plumbing is not new.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `.synlynk/policy.json` | Modify | Add top-level `eligibility` block; remove `overrides.dev_authority.task_allocation` and the `dev_authority` key if now empty |
| `.synlynk/capability-roles.json` | Delete | Retired — superseded by `eligibility` |
| `synlynk/routing.py` | Create | `Router` protocol, `SCORE_COST_DIVISOR`, `LiveQueryRouter.score_harnesses()`, round-robin fallback helper |
| `synlynk/migrations/m0035_routing_indexes_and_last_routed.py` | Create | Composite indexes on real schema columns + `harness_status.last_routed_task_types` column |
| `synlynk/migrations/runner.py` | Modify | Import + register `M0035` |
| `synlynk/dispatch.py` | Modify | Wire `LiveQueryRouter` into `_infer_dispatch_defaults`; Muse budget-ledger fallback in `_preflight_dispatch`; `--allow-reroute` gate for local harness; manifest version-hash preflight check |
| `synlynk/harness_manifest.py` | Create | `.synlynk/harnesses/{harness}.json` schema, `discover_and_validate(harness)` |
| `synlynk/cli.py` | Modify | New `harness` subparser group (`onboard`, `probe --discover`); new `--allow-reroute` flag on `dispatch`; `synlynk jobs`/`synlynk status` rerouted-from display |
| `.synlynk/billing.json` | Modify | Add `cost_per_1k_tokens` for `muse` |
| `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` | Modify | Remove "Your Role" / "Capability-Based Task Allocation" sections, replace with one sentence pointing at `eligibility`/`routing.py` |
| `tests/test_routing.py` | Create | Scoring, tie-break, min-sample floor, round-robin fallback, index-usage tests |
| `tests/test_harness_manifest.py` | Create | Manifest schema validation, billing-field validation, smoke-run tests |
| `tests/test_dispatch_muse_budget.py` | Create | credit_grants fallback test |
| `tests/test_dispatch_local_reroute.py` | Create | `--allow-reroute` gate + attribution tests |

---

## Task 1: Retire the fixed-lane table and add `eligibility` to policy.json

**Files:**
- Modify: `.synlynk/policy.json`
- Delete: `.synlynk/capability-roles.json`
- Test: `tests/test_policy_eligibility.py`

- [ ] **Step 1: Read current policy.json structure to confirm exact keys to remove**

```bash
python3 -c "import json; p=json.load(open('.synlynk/policy.json')); print(list(p.keys())); print(list(p.get('dev_authority',{}).keys()))"
```

Expected output includes `dev_authority` with key `task_allocation`.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_policy_eligibility.py
import json
import os


def test_policy_has_eligibility_block_not_task_allocation():
    with open(os.path.join(os.path.dirname(__file__), "..", ".synlynk", "policy.json")) as f:
        policy = json.load(f)
    assert "eligibility" in policy
    assert "dev_authority" not in policy or "task_allocation" not in policy.get("dev_authority", {})
    assert not os.path.exists(
        os.path.join(os.path.dirname(__file__), "..", ".synlynk", "capability-roles.json")
    )


def test_eligibility_covers_all_known_harnesses_and_task_types():
    with open(os.path.join(os.path.dirname(__file__), "..", ".synlynk", "policy.json")) as f:
        policy = json.load(f)
    eligibility = policy["eligibility"]
    known_task_types = {
        "implement", "test", "css", "templates", "content", "subpages",
        "canvas", "js", "infra", "refactor", "cli-plumbing", "review",
        "brainstorm", "pm", "deploy",
    }
    assert known_task_types.issubset(set(eligibility.keys()))
    for task_type, harnesses in eligibility.items():
        assert isinstance(harnesses, dict)
        for harness, rule in harnesses.items():
            assert "eligible" in rule
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_policy_eligibility.py -v`
Expected: FAIL (`eligibility` not in policy, or `task_allocation` still present)

- [ ] **Step 4: Edit `.synlynk/policy.json`**

Remove the `dev_authority.task_allocation` key. Add a new top-level `eligibility` block where every harness is eligible for every task type unless a stated, policy-level runtime reason excludes it (not a hand-ranked preference table — per-task_type routing preference now comes from `routing.py`, not this block):

```json
"eligibility": {
  "implement": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "test": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "css": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "templates": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "content": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "subpages": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "canvas": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "js": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "infra": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "refactor": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "cli-plumbing": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "review": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "brainstorm": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "pm": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  },
  "deploy": {
    "claude": {"eligible": true}, "agy": {"eligible": true},
    "grok": {"eligible": true}, "codex": {"eligible": true}, "muse": {"eligible": true}
  }
}
```

Note at the end of `capability_policy.note`: append `"Superseded 2026-11-17: eligibility is now uniform (see top-level 'eligibility' block); per-task_type preference is decided live by routing.py, not a hand-ranked table."`

Delete `.synlynk/capability-roles.json`:

```bash
rm .synlynk/capability-roles.json
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_policy_eligibility.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .synlynk/policy.json tests/test_policy_eligibility.py
git rm .synlynk/capability-roles.json
git commit -m "chore(policy): retire fixed-lane task_allocation table for eligibility block"
```

---

## Task 2: Strip "Your Role" / "Capability-Based Task Allocation" from instruction files

**Files:**
- Modify: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` (repo root — each has its own copy of these sections per the harness-fence pattern)

- [ ] **Step 1: Confirm each file has the sections to remove**

```bash
grep -n "## Your Role\|## Capability-Based Task Allocation" CLAUDE.md AGENTS.md GEMINI.md
```

Expected: each file shows both headings.

- [ ] **Step 2: Edit each file**

In each of `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, replace the entire `## Your Role` section body and the entire `## Capability-Based Task Allocation` section (including its table and the suspended-notice blockquote) with:

```markdown
## Harness Eligibility & Routing

Every harness is policy-eligible for every task type (`.synlynk/policy.json`'s `eligibility` block). Which harness actually gets a given dispatch is decided live by `synlynk/routing.py` from measured `capability_ratings`/`cost_entries` history, not a hand-authored table. See `synlynk/routing.py` module docstring for the scoring method.
```

Leave every other section of each file untouched (PR Review Discipline, Multi-Task Tracking, Brainstorm-First Policy, etc. are unaffected).

- [ ] **Step 3: Verify removal**

```bash
grep -n "## Your Role\|## Capability-Based Task Allocation" CLAUDE.md AGENTS.md GEMINI.md
```

Expected: no output (exit code 1 from grep for all three files).

- [ ] **Step 4: File the deferred tech-debt ticket for instruction-file-duplication centralization**

```bash
eval "$(synlynk gh --shim-env)"
synlynk gh --role pm -- issue create \
  --title "tech-debt: centralize CLAUDE.md/AGENTS.md/GEMINI.md shared sections" \
  --body "Phase 3 harness-parity work (docs/superpowers/plans/2026-11-17-harness-parity-phase3-mechanics.md) edited the same section in three files by hand. Not building a centralization mechanism now — just flagging the duplication cost for a future pass." \
  --label "tech-debt"
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md AGENTS.md GEMINI.md
git commit -m "docs: replace fixed-lane role tables with eligibility/routing pointer"
```

---

## Task 3: Migration — composite indexes (real columns) + `harness_status.last_routed_task_types`

**Files:**
- Create: `synlynk/migrations/m0035_routing_indexes_and_last_routed.py`
- Modify: `synlynk/migrations/runner.py`
- Test: `tests/test_migration_m0035.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_migration_m0035.py
import sqlite3

from synlynk.migrations.runner import run_pending_migrations
from synlynk import db_schema


def _fresh_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(db_schema.SCHEMA_SQL if hasattr(db_schema, "SCHEMA_SQL") else "")
    return conn


def test_m0035_adds_indexes_and_column():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE capability_ratings (
        id INTEGER PRIMARY KEY, story_id TEXT, agent TEXT, discipline TEXT, ts TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE cost_entries (
        id INTEGER PRIMARY KEY, story_id TEXT, harness TEXT, recorded_at TEXT, total_cost_usd REAL
    )""")
    conn.execute("""CREATE TABLE harness_status (
        harness_name TEXT PRIMARY KEY
    )""")
    run_pending_migrations(conn)

    index_names = {
        row[1] for row in conn.execute("PRAGMA index_list(capability_ratings)").fetchall()
    } | {
        row[1] for row in conn.execute("PRAGMA index_list(cost_entries)").fetchall()
    }
    assert "idx_capability_ratings_agent_discipline_ts" in index_names
    assert "idx_cost_entries_harness_story_recorded" in index_names

    columns = {row[1] for row in conn.execute("PRAGMA table_info(harness_status)").fetchall()}
    assert "last_routed_task_types" in columns


def test_m0035_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE capability_ratings (
        id INTEGER PRIMARY KEY, story_id TEXT, agent TEXT, discipline TEXT, ts TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE cost_entries (
        id INTEGER PRIMARY KEY, story_id TEXT, harness TEXT, recorded_at TEXT, total_cost_usd REAL
    )""")
    conn.execute("""CREATE TABLE harness_status (
        harness_name TEXT PRIMARY KEY
    )""")
    run_pending_migrations(conn)
    run_pending_migrations(conn)  # second call must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_m0035.py -v`
Expected: FAIL (`idx_capability_ratings_agent_discipline_ts` not found — migration doesn't exist yet)

- [ ] **Step 3: Create the migration file**

```python
# synlynk/migrations/m0035_routing_indexes_and_last_routed.py
"""Migration 35: composite indexes for live capability routing + round-robin fallback column.

Indexes real schema columns — capability_ratings has no `harness`/`task_type`/
`created_at` columns (confirmed via db_schema.py read, 2026-11-17); the real
columns are `agent`, `discipline` (task_type proxy), and `ts`. cost_entries
uses `harness` and `recorded_at`.
"""

import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_capability_ratings_agent_discipline_ts
           ON capability_ratings (agent, discipline, ts)"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_cost_entries_harness_story_recorded
           ON cost_entries (harness, story_id, recorded_at)"""
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(harness_status)").fetchall()}
    if "last_routed_task_types" not in columns:
        conn.execute(
            "ALTER TABLE harness_status ADD COLUMN last_routed_task_types TEXT DEFAULT NULL"
        )


MIGRATION = Migration(version=35, name="routing_indexes_and_last_routed", up=_up)
```

- [ ] **Step 4: Register the migration in the runner**

Edit `synlynk/migrations/runner.py`:

```python
from synlynk.migrations.m0034_approval_tickets_theme import MIGRATION as M0034
from synlynk.migrations.m0035_routing_indexes_and_last_routed import MIGRATION as M0035
```

and update the `MIGRATIONS` list:

```python
MIGRATIONS: list[Migration] = [
    M0016, M0017, M0018, M0019, M0020, M0021, M0022, M0023,
    M0024, M0025, M0026, M0027, M0028, M0029, M0030, M0031,
    M0032, M0033, M0034, M0035,
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_migration_m0035.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/migrations/m0035_routing_indexes_and_last_routed.py synlynk/migrations/runner.py tests/test_migration_m0035.py
git commit -m "feat(db): add routing composite indexes and harness_status.last_routed_task_types (migration 35)"
```

---

## Task 4: `synlynk/routing.py` — Router protocol + scoring

**Files:**
- Create: `synlynk/routing.py`
- Test: `tests/test_routing.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routing.py
import sqlite3

from synlynk.routing import SCORE_COST_DIVISOR, LiveQueryRouter


def _seed(conn, rows):
    conn.execute("""CREATE TABLE capability_ratings (
        id INTEGER PRIMARY KEY, story_id TEXT, agent TEXT, discipline TEXT,
        pr_review_cycles REAL, ts TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE cost_entries (
        id INTEGER PRIMARY KEY, story_id TEXT, harness TEXT,
        total_cost_usd REAL, recorded_at TEXT
    )""")
    conn.execute("""CREATE TABLE harness_status (
        harness_name TEXT PRIMARY KEY, last_routed_task_types TEXT
    )""")
    for i, (agent, discipline, cycles, cost) in enumerate(rows):
        story_id = f"s{i}"
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles, ts) "
            "VALUES (?,?,?,?,datetime('now'))",
            (story_id, agent, discipline, cycles),
        )
        conn.execute(
            "INSERT INTO cost_entries (story_id, harness, total_cost_usd, recorded_at) "
            "VALUES (?,?,?,datetime('now'))",
            (story_id, agent, cost),
        )
    conn.commit()


def test_score_harnesses_prefers_lower_cycles_and_cost():
    conn = sqlite3.connect(":memory:")
    rows = [("codex", "implement", 1.0, 2.0)] * 5 + [("agy", "implement", 3.0, 5.0)] * 5
    _seed(conn, rows)
    router = LiveQueryRouter(conn, min_sample_size=5)
    ranked = router.score_harnesses("implement", ["codex", "agy"])
    assert ranked[0]["harness"] == "codex"
    assert ranked[0]["sample_count"] == 5


def test_score_harnesses_below_floor_returns_empty():
    conn = sqlite3.connect(":memory:")
    rows = [("codex", "implement", 1.0, 2.0)] * 3
    _seed(conn, rows)
    router = LiveQueryRouter(conn, min_sample_size=5)
    ranked = router.score_harnesses("implement", ["codex"])
    assert ranked == []


def test_tie_break_is_sample_count_then_alphabetical():
    conn = sqlite3.connect(":memory:")
    rows = (
        [("codex", "implement", 2.0, 4.0)] * 5
        + [("agy", "implement", 2.0, 4.0)] * 5
    )
    _seed(conn, rows)
    router = LiveQueryRouter(conn, min_sample_size=5)
    ranked = router.score_harnesses("implement", ["codex", "agy"])
    assert ranked[0]["harness"] == "agy"  # identical score+sample_count -> alphabetical


def test_round_robin_fallback_below_floor():
    conn = sqlite3.connect(":memory:")
    _seed(conn, [])
    conn.execute(
        "INSERT INTO harness_status (harness_name, last_routed_task_types) VALUES (?, ?)",
        ("codex", '{"implement": "2026-11-16T00:00:00"}'),
    )
    conn.commit()
    router = LiveQueryRouter(conn, min_sample_size=5)
    chosen = router.round_robin_fallback("implement", ["codex", "agy"])
    assert chosen == "agy"  # codex was routed most recently, agy hasn't been tried
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routing.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'synlynk.routing'`)

- [ ] **Step 3: Implement `synlynk/routing.py`**

```python
# synlynk/routing.py
"""Live capability-based harness routing.

Scores eligible harnesses from measured history in capability_ratings/
cost_entries instead of a hand-authored task_allocation table. Note on real
schema (confirmed 2026-11-17, see plan grounding notes): capability_ratings
has no `harness`/`task_type`/`created_at` columns. The real columns are
`agent` (harness identity), `discipline` (closest existing proxy for
task_type), and `ts`. cost_entries uses `harness` and `recorded_at`, joined
to capability_ratings via `story_id`. This mirrors the existing join pattern
in synlynk/capability.py:ranked_harness_for_task, extended to rank every
eligible candidate rather than only incumbent-vs-fallback.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Protocol

SCORE_COST_DIVISOR: dict[str, float] = {
    "implement": 1.0,
    "test": 1.0,
    "css": 0.5,
    "templates": 0.5,
    "content": 0.5,
    "subpages": 0.5,
    "canvas": 1.0,
    "js": 1.0,
    "infra": 2.0,
    "refactor": 1.5,
    "cli-plumbing": 1.0,
    "review": 1.0,
    "brainstorm": 2.0,
    "pm": 2.0,
    "deploy": 2.0,
}
_DEFAULT_SCORE_COST_DIVISOR = 1.0


class Router(Protocol):
    def score_harnesses(self, task_type: str, candidates: list[str]) -> list[dict]:
        ...

    def round_robin_fallback(self, task_type: str, candidates: list[str]) -> str | None:
        ...


class LiveQueryRouter:
    """Ranks eligible harnesses for a task_type from capability_ratings/cost_entries."""

    def __init__(self, conn: sqlite3.Connection, *, min_sample_size: int = 5):
        self._conn = conn
        self._min_sample_size = min_sample_size

    def score_harnesses(self, task_type: str, candidates: list[str]) -> list[dict]:
        """Return eligible candidates ranked best-first, or [] if none clear the floor."""
        divisor = SCORE_COST_DIVISOR.get(task_type, _DEFAULT_SCORE_COST_DIVISOR)
        scored = []
        for harness in candidates:
            rows = self._conn.execute(
                """SELECT cr.pr_review_cycles, ce.total_cost_usd
                     FROM capability_ratings cr
                     JOIN cost_entries ce ON ce.story_id = cr.story_id
                    WHERE cr.agent = ? AND lower(cr.discipline) = lower(?)
                      AND ce.harness = cr.agent""",
                (harness, task_type),
            ).fetchall()
            cycles = sorted(r[0] for r in rows if r[0] is not None)
            costs = [r[1] for r in rows if r[1] is not None]
            sample_count = len(cycles) if cycles and costs else 0
            if sample_count < self._min_sample_size:
                continue
            mid = sample_count // 2
            median_cycles = (
                cycles[mid] if sample_count % 2 else (cycles[mid - 1] + cycles[mid]) / 2
            )
            avg_cost = sum(costs) / len(costs)
            score = median_cycles + (avg_cost / divisor)
            scored.append({
                "harness": harness,
                "sample_count": sample_count,
                "median_cycles": median_cycles,
                "avg_cost": avg_cost,
                "score": score,
            })
        scored.sort(key=lambda item: (item["score"], -item["sample_count"], item["harness"]))
        return scored

    def round_robin_fallback(self, task_type: str, candidates: list[str]) -> str | None:
        """Return the candidate least recently routed to this task_type, or alphabetically
        first if none has ever been routed to it."""
        if not candidates:
            return None
        last_routed = {}
        for harness in candidates:
            row = self._conn.execute(
                "SELECT last_routed_task_types FROM harness_status WHERE harness_name=?",
                (harness,),
            ).fetchone()
            raw = row[0] if row else None
            parsed = json.loads(raw) if raw else {}
            last_routed[harness] = parsed.get(task_type)
        never_routed = sorted(h for h in candidates if last_routed[h] is None)
        if never_routed:
            return never_routed[0]
        return min(candidates, key=lambda h: last_routed[h])

    def record_routing(self, harness: str, task_type: str) -> None:
        """Update harness_status.last_routed_task_types[task_type] = now (UTC ISO)."""
        row = self._conn.execute(
            "SELECT last_routed_task_types FROM harness_status WHERE harness_name=?",
            (harness,),
        ).fetchone()
        parsed = json.loads(row[0]) if row and row[0] else {}
        parsed[task_type] = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO harness_status (harness_name, last_routed_task_types) VALUES (?, ?) "
            "ON CONFLICT(harness_name) DO UPDATE SET last_routed_task_types=excluded.last_routed_task_types",
            (harness, json.dumps(parsed)),
        )
        self._conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routing.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Add `EXPLAIN QUERY PLAN` index-usage test**

Append to `tests/test_routing.py`:

```python
def test_score_query_uses_composite_index():
    import sqlite3
    from synlynk.migrations.runner import run_pending_migrations

    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE capability_ratings (
        id INTEGER PRIMARY KEY, story_id TEXT, agent TEXT, discipline TEXT,
        pr_review_cycles REAL, ts TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE cost_entries (
        id INTEGER PRIMARY KEY, story_id TEXT, harness TEXT,
        total_cost_usd REAL, recorded_at TEXT
    )""")
    conn.execute("""CREATE TABLE harness_status (
        harness_name TEXT PRIMARY KEY, last_routed_task_types TEXT
    )""")
    run_pending_migrations(conn)
    plan = conn.execute(
        """EXPLAIN QUERY PLAN
           SELECT cr.pr_review_cycles, ce.total_cost_usd
             FROM capability_ratings cr
             JOIN cost_entries ce ON ce.story_id = cr.story_id
            WHERE cr.agent = 'codex' AND lower(cr.discipline) = lower('implement')
              AND ce.harness = cr.agent"""
    ).fetchall()
    plan_text = " ".join(str(row) for row in plan)
    assert "idx_capability_ratings_agent_discipline_ts" in plan_text or "USING INDEX" in plan_text
```

Run: `pytest tests/test_routing.py::test_score_query_uses_composite_index -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/routing.py tests/test_routing.py
git commit -m "feat(routing): add LiveQueryRouter scoring eligible harnesses from measured history"
```

---

## Task 5: Wire `LiveQueryRouter` into `_infer_dispatch_defaults`

**Files:**
- Modify: `synlynk/dispatch.py:977-1107` (`_infer_dispatch_defaults`)
- Test: `tests/test_infer_dispatch_defaults_routing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_infer_dispatch_defaults_routing.py
import sqlite3
from unittest.mock import patch

from synlynk.dispatch import _infer_dispatch_defaults


def _seed_capability(conn, harness, discipline, cycles, cost, n=5):
    conn.execute("""CREATE TABLE IF NOT EXISTS capability_ratings (
        id INTEGER PRIMARY KEY, story_id TEXT, agent TEXT, discipline TEXT,
        pr_review_cycles REAL, ts TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cost_entries (
        id INTEGER PRIMARY KEY, story_id TEXT, harness TEXT,
        total_cost_usd REAL, recorded_at TEXT
    )""")
    for i in range(n):
        story_id = f"{harness}-{i}"
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles, ts) "
            "VALUES (?,?,?,?,datetime('now'))",
            (story_id, harness, discipline, cycles),
        )
        conn.execute(
            "INSERT INTO cost_entries (story_id, harness, total_cost_usd, recorded_at) "
            "VALUES (?,?,?,datetime('now'))",
            (story_id, harness, cost),
        )
    conn.commit()


def test_infer_dispatch_defaults_promotes_better_measured_harness():
    conn = sqlite3.connect(":memory:")
    _seed_capability(conn, "codex", "implement", cycles=1.0, cost=1.0)
    _seed_capability(conn, "agy", "implement", cycles=4.0, cost=8.0)

    with patch("synlynk.dispatch._pkg") as mock_pkg:
        def fake_pkg(name, default=None):
            if name == "_get_db":
                return lambda: conn
            return default
        mock_pkg.side_effect = fake_pkg
        with patch("synlynk.policy.load_policy") as mock_policy:
            mock_policy.return_value = {
                "dev_authority": {},
                "eligibility": {
                    "implement": {"codex": {"eligible": True}, "agy": {"eligible": True}}
                },
                "agent_roles": {},
            }
            result = _infer_dispatch_defaults("implement a feature", task_type="implement")

    assert result["harness"] == "codex"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_infer_dispatch_defaults_routing.py -v`
Expected: FAIL (current code reads `policy["dev_authority"]["task_allocation"]`, which the test's mocked policy no longer has, so `entry` is `{}` and `default_harness` is `None` — result falls through to `"codex"` as a hardcoded final default (line 1061) regardless of measured history, so the assertion coincidentally could pass or fail depending on current fallback; this is expected to surface the real gap: the function doesn't consult `eligibility` or route across *all* eligible harnesses yet.)

- [ ] **Step 3: Edit `_infer_dispatch_defaults`**

Replace lines 996-1061 of `synlynk/dispatch.py` (from `policy = load_policy(os.getcwd())` through the `inferred_agent = "codex"` fallback) with:

```python
    policy = load_policy(os.getcwd())
    eligibility = policy.get("eligibility") or {}
    story_role = _role_for_story(story_id)
    text = (task or "").lower()
    inferred_task_type = task_type
    if inferred_task_type is None:
        if _infer_task_type(task) == "review":
            inferred_task_type = "review"
        else:
            patterns = (
                ("brainstorm", ("brainstorm", "design proposal", "write a spec")),
                ("architecture-review", ("architecture review", "architectural review")),
                ("pm", ("roadmap", "triage backlog", "project management")),
                ("test", ("run tests", "test suite", "add tests", "pytest")),
                ("refactor", ("refactor", "restructure")),
                ("css", ("css", "stylesheet", "styling")),
                ("templates", ("template", "email template")),
                ("content", ("copywriting", "blog post", "content")),
                ("js", ("javascript", "typescript", "frontend")),
                ("infra", ("infrastructure", "deploy", "ci/cd")),
                ("implement", ("implement", "build", "add", "fix", "change")),
            )
            inferred_task_type = next(
                (kind for kind, terms in patterns if any(term in text for term in terms)),
                "implement",
            )

    inferred_role = role or story_role
    if inferred_role is None:
        inferred_role = {
            "review": "qa",
            "brainstorm": "architect",
            "architecture-review": "architect",
            "pm": "pm",
        }.get(inferred_task_type, "dev")

    role_entry = (policy.get("agent_roles") or {}).get(inferred_role) or {}

    eligible_entry = eligibility.get(inferred_task_type) or eligibility.get("implement") or {}
    eligible_candidates = sorted(
        harness for harness, rule in eligible_entry.items() if rule.get("eligible")
    )

    get_db = _pkg("_get_db")
    db_conn = get_db() if get_db else None
    promoted = None
    ranked = []
    try:
        if db_conn is not None and eligible_candidates:
            from synlynk.routing import LiveQueryRouter

            router = LiveQueryRouter(db_conn)
            ranked = router.score_harnesses(inferred_task_type, eligible_candidates)
            if ranked:
                promoted = ranked[0]["harness"]
            else:
                promoted = router.round_robin_fallback(inferred_task_type, eligible_candidates)
                if promoted:
                    router.record_routing(promoted, inferred_task_type)
    finally:
        if db_conn is not None:
            db_conn.close()

    default_harness = promoted or (eligible_candidates[0] if eligible_candidates else None)
    fallback_list = [h for h in eligible_candidates if h != default_harness]
    inferred_agent = agent
    if inferred_agent is None:
        explicit_binding = role is not None or story_role is not None
        if promoted and not explicit_binding:
            inferred_agent = promoted
        else:
            inferred_agent = role_entry.get("default_harness") or default_harness
    if inferred_agent is None:
        inferred_agent = "codex"
```

Keep the remainder of the function (the `if agent is None and inferred_agent:` weekly-headroom block through the `return {...}`) unchanged — it already references `default_harness`, `fallback_list`, and `inferred_agent`, all of which are still defined with the same names and shapes above.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_infer_dispatch_defaults_routing.py -v`
Expected: PASS

- [ ] **Step 5: Run the existing dispatch test suite to check for regressions**

Run: `pytest tests/test_dispatch.py -k infer_dispatch_defaults -v`
Expected: PASS (or update any test that asserted on the old `task_allocation`-table behavior — if one exists, replace its fixture with an `eligibility`-shaped policy dict and seeded `capability_ratings`/`cost_entries` rows, following the pattern in Step 1 above)

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_infer_dispatch_defaults_routing.py
git commit -m "feat(dispatch): route _infer_dispatch_defaults via LiveQueryRouter instead of task_allocation table"
```

---

## Task 6: Harness manifest schema + `discover_and_validate`

**Files:**
- Create: `synlynk/harness_manifest.py`
- Test: `tests/test_harness_manifest.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_harness_manifest.py
import json
import os

from synlynk.harness_manifest import (
    HARNESS_MANIFEST_SCHEMA_VERSION,
    HarnessManifestError,
    discover_and_validate,
    manifest_path,
)


def test_manifest_path_is_under_synlynk_harnesses(tmp_path):
    path = manifest_path(str(tmp_path), "codex")
    assert path == os.path.join(str(tmp_path), ".synlynk", "harnesses", "codex.json")


def test_discover_and_validate_writes_manifest_with_required_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "synlynk.harness_manifest._probe_cli_version", lambda harness: "1.2.3"
    )
    monkeypatch.setattr(
        "synlynk.harness_manifest._run_smoke_test", lambda harness: {"passed": True, "detail": "ok"}
    )
    manifest = discover_and_validate("codex", repo_root=str(tmp_path))
    assert manifest["manifest_schema_version"] == HARNESS_MANIFEST_SCHEMA_VERSION
    assert manifest["harness"] == "codex"
    assert manifest["cli_version"] == "1.2.3"
    assert manifest["last_smoke_run"]["passed"] is True
    written_path = manifest_path(str(tmp_path), "codex")
    assert os.path.exists(written_path)
    with open(written_path) as f:
        on_disk = json.load(f)
    assert on_disk == manifest


def test_discover_and_validate_raises_on_invalid_billing_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "synlynk.harness_manifest._probe_cli_version", lambda harness: "1.0.0"
    )
    monkeypatch.setattr(
        "synlynk.harness_manifest._run_smoke_test", lambda harness: {"passed": True, "detail": "ok"}
    )
    billing_dir = os.path.join(str(tmp_path), ".synlynk")
    os.makedirs(billing_dir, exist_ok=True)
    with open(os.path.join(billing_dir, "billing.json"), "w") as f:
        json.dump({"harness_billing": {"newharness": {"payment_mode": "pay_per_token"}}}, f)
    try:
        discover_and_validate("newharness", repo_root=str(tmp_path))
        assert False, "expected HarnessManifestError"
    except HarnessManifestError as exc:
        assert "HARNESS_BILLING_CONFIG_INVALID" in str(exc)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_harness_manifest.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'synlynk.harness_manifest'`)

- [ ] **Step 3: Implement `synlynk/harness_manifest.py`**

```python
# synlynk/harness_manifest.py
"""Per-harness manifest: models, native CLI flags, auth model, MCP tool list,
CLI version, and the last validated smoke-run result. Written by
`synlynk harness onboard` / `synlynk harness probe --discover`.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone

HARNESS_MANIFEST_SCHEMA_VERSION = 1


class HarnessManifestError(Exception):
    pass


def manifest_path(repo_root: str, harness: str) -> str:
    return os.path.join(repo_root, ".synlynk", "harnesses", f"{harness}.json")


def _probe_cli_version(harness: str) -> str:
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    baseline = HARNESS_CAPABILITY_BASELINES.get(harness, {})
    probe_cmd = baseline.get("probe")
    if not probe_cmd:
        raise HarnessManifestError(f"HARNESS_MANIFEST_NO_PROBE_COMMAND: no probe command for {harness!r}")
    result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
    return (result.stdout or result.stderr or "").strip().splitlines()[0] if (result.stdout or result.stderr) else "unknown"


def _run_smoke_test(harness: str) -> dict:
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    baseline = HARNESS_CAPABILITY_BASELINES.get(harness, {})
    probe_cmd = baseline.get("probe")
    if not probe_cmd:
        return {"passed": False, "detail": f"no probe command for {harness!r}"}
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        return {"passed": result.returncode == 0, "detail": (result.stdout or result.stderr or "").strip()[:500]}
    except Exception as exc:
        return {"passed": False, "detail": str(exc)}


def _validate_billing_config(repo_root: str, harness: str) -> None:
    billing_path = os.path.join(repo_root, ".synlynk", "billing.json")
    if not os.path.exists(billing_path):
        return
    with open(billing_path) as f:
        billing = json.load(f)
    harness_billing = (billing.get("harness_billing") or {}).get(harness)
    if harness_billing is None:
        return
    payment_mode = harness_billing.get("payment_mode")
    if payment_mode == "subscription":
        if "monthly_base_fee_usd" not in harness_billing:
            raise HarnessManifestError(
                f"HARNESS_BILLING_CONFIG_INVALID: {harness!r} is subscription but missing monthly_base_fee_usd"
            )
    elif payment_mode == "pay_per_token":
        if "cost_per_1k_tokens" not in harness_billing:
            raise HarnessManifestError(
                f"HARNESS_BILLING_CONFIG_INVALID: {harness!r} is pay_per_token but missing cost_per_1k_tokens"
            )
    else:
        raise HarnessManifestError(
            f"HARNESS_BILLING_CONFIG_INVALID: {harness!r} has unrecognized payment_mode {payment_mode!r}"
        )


def discover_and_validate(harness: str, *, repo_root: str = ".") -> dict:
    """Probe a harness's CLI version and smoke-run result, validate its billing
    config, write `.synlynk/harnesses/{harness}.json`, and return the manifest."""
    _validate_billing_config(repo_root, harness)
    cli_version = _probe_cli_version(harness)
    smoke_result = _run_smoke_test(harness)
    manifest = {
        "manifest_schema_version": HARNESS_MANIFEST_SCHEMA_VERSION,
        "harness": harness,
        "cli_version": cli_version,
        "last_smoke_run": smoke_result,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
    }
    path = manifest_path(repo_root, harness)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_harness_manifest.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/harness_manifest.py tests/test_harness_manifest.py
git commit -m "feat(harness): add per-harness manifest schema and discover_and_validate"
```

---

## Task 7: `synlynk harness onboard` / `synlynk harness probe --discover` CLI commands

**Files:**
- Modify: `synlynk/cli.py`
- Test: `tests/test_cli_harness_commands.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_harness_commands.py
from unittest.mock import patch

from synlynk.cli import build_parser


def test_harness_onboard_parses():
    parser = build_parser()
    args = parser.parse_args(["harness", "onboard", "--harness", "codex"])
    assert args.command == "harness"
    assert args.harness_command == "onboard"
    assert args.harness == "codex"


def test_harness_probe_discover_parses():
    parser = build_parser()
    args = parser.parse_args(["harness", "probe", "--discover", "--harness", "grok"])
    assert args.command == "harness"
    assert args.harness_command == "probe"
    assert args.discover is True
    assert args.harness == "grok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_harness_commands.py -v`
Expected: FAIL (`error: invalid choice: 'harness'` or `AttributeError`)

- [ ] **Step 3: Confirm `build_parser` is the right entry point**

```bash
grep -n "^def build_parser\|^def main" synlynk/cli.py
```

(If no `build_parser` function exists, adapt Step 2's test and Step 4's wiring to whatever function constructs and returns the top-level `ArgumentParser` — grep for `subparsers = parser.add_subparsers` to find it.)

- [ ] **Step 4: Add the `harness` subparser group**

In `synlynk/cli.py`, near the existing `dispatch_parser` registration (around line 1335), add:

```python
    harness_parser = subparsers.add_parser(
        "harness", help="Harness manifest onboarding and discovery")
    harness_sub = harness_parser.add_subparsers(dest="harness_command", required=True)

    harness_onboard_parser = harness_sub.add_parser(
        "onboard", help="Discover and validate a new harness, writing its manifest")
    harness_onboard_parser.add_argument("--harness", required=True, help="Harness name")

    harness_probe_parser = harness_sub.add_parser(
        "probe", help="Re-probe an onboarded harness's manifest")
    harness_probe_parser.add_argument("--harness", required=True, help="Harness name")
    harness_probe_parser.add_argument(
        "--discover", action="store_true",
        help="Force full rediscovery (version probe + smoke run) instead of reading the cached manifest")
```

Add the `"harness"` string to the top-level command tuple at line 327 (alongside `"probe"`, `"dispatch"`, etc.) so it's recognized as a known top-level command — check that list's exact variable name first:

```bash
sed -n '325,332p' synlynk/cli.py
```

Then add `"harness"` to it.

- [ ] **Step 5: Wire the command handler**

Find where top-level commands dispatch to their `cmd_*` functions (grep `args.command ==` or a dict dispatch table):

```bash
grep -n "args.command ==\|COMMAND_HANDLERS\s*=" synlynk/cli.py | head -10
```

Add a handler following whichever pattern is used (if-elif chain or dict), calling a new `cmd_harness(args)`:

```python
def cmd_harness(args) -> int:
    from synlynk.harness_manifest import HarnessManifestError, discover_and_validate, manifest_path
    import json
    import os

    repo_root = os.getcwd()
    if args.harness_command == "onboard":
        try:
            manifest = discover_and_validate(args.harness, repo_root=repo_root)
        except HarnessManifestError as exc:
            print(str(exc))
            return 1
        print(f"Onboarded {args.harness}: manifest written to {manifest_path(repo_root, args.harness)}")
        return 0
    if args.harness_command == "probe":
        path = manifest_path(repo_root, args.harness)
        if args.discover or not os.path.exists(path):
            try:
                manifest = discover_and_validate(args.harness, repo_root=repo_root)
            except HarnessManifestError as exc:
                print(str(exc))
                return 1
            print(f"Rediscovered {args.harness}: {manifest['cli_version']}")
            return 0
        with open(path) as f:
            manifest = json.load(f)
        print(json.dumps(manifest, indent=2))
        return 0
    return 1
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_cli_harness_commands.py -v`
Expected: PASS

- [ ] **Step 7: Manual smoke test**

```bash
python3 bin/synlynk.py harness onboard --harness codex
cat .synlynk/harnesses/codex.json
```

Expected: a JSON manifest is printed and the file exists.

- [ ] **Step 8: Commit**

```bash
git add synlynk/cli.py tests/test_cli_harness_commands.py
git commit -m "feat(cli): add 'synlynk harness onboard'/'probe --discover' commands"
```

---

## Task 8: CLI-version-triggered rediscovery in dispatch preflight

**Files:**
- Modify: `synlynk/dispatch.py` (inside `_preflight_dispatch`, near the `_preflight_auth_check`/`_preflight_headless_permission_check` calls at lines 4213-4220)
- Test: `tests/test_dispatch_manifest_revalidation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dispatch_manifest_revalidation.py
import json
import os
from unittest.mock import patch

from synlynk.dispatch import _preflight_manifest_check


def test_no_manifest_triggers_onboarding(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("synlynk.harness_manifest.discover_and_validate") as mock_discover:
        mock_discover.return_value = {"cli_version": "1.0.0", "manifest_schema_version": 1}
        result = _preflight_manifest_check("codex")
    assert result is None  # None means "passed, no failure"
    mock_discover.assert_called_once()


def test_version_mismatch_triggers_single_revalidation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manifest_dir = tmp_path / ".synlynk" / "harnesses"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "codex.json").write_text(
        json.dumps({"cli_version": "1.0.0", "manifest_schema_version": 1})
    )
    with patch("synlynk.harness_manifest._probe_cli_version", return_value="2.0.0"), \
         patch("synlynk.harness_manifest._run_smoke_test", return_value={"passed": True, "detail": "ok"}):
        result = _preflight_manifest_check("codex")
    assert result is None
    with open(manifest_dir / "codex.json") as f:
        updated = json.load(f)
    assert updated["cli_version"] == "2.0.0"


def test_revalidation_failure_returns_sentinel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manifest_dir = tmp_path / ".synlynk" / "harnesses"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "codex.json").write_text(
        json.dumps({"cli_version": "1.0.0", "manifest_schema_version": 1})
    )
    with patch("synlynk.harness_manifest._probe_cli_version", return_value="2.0.0"), \
         patch("synlynk.harness_manifest._run_smoke_test", return_value={"passed": False, "detail": "boom"}):
        result = _preflight_manifest_check("codex")
    assert result["sentinel"] == "HARNESS_MANIFEST_REVALIDATION_FAILED"
    assert result["passed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch_manifest_revalidation.py -v`
Expected: FAIL (`ImportError: cannot import name '_preflight_manifest_check'`)

- [ ] **Step 3: Implement `_preflight_manifest_check` in `synlynk/dispatch.py`**

Add this function near `_preflight_auth_check` (before line 3417):

```python
def _preflight_manifest_check(harness_name: str) -> Optional[dict]:
    """Event-triggered manifest revalidation: onboard if no manifest exists,
    or re-discover once if the live CLI version differs from the cached one."""
    import json
    import os

    from synlynk.harness_manifest import (
        HarnessManifestError,
        discover_and_validate,
        manifest_path,
        _probe_cli_version,
    )

    path = manifest_path(os.getcwd(), harness_name)
    if not os.path.exists(path):
        try:
            discover_and_validate(harness_name, repo_root=os.getcwd())
        except HarnessManifestError as exc:
            return {"passed": False, "sentinel": "HARNESS_MANIFEST_REVALIDATION_FAILED", "reason": str(exc)}
        return None

    with open(path) as f:
        cached = json.load(f)

    try:
        live_version = _probe_cli_version(harness_name)
    except HarnessManifestError:
        return None  # No probe command configured; nothing to compare, not a failure.

    if live_version == cached.get("cli_version"):
        return None

    try:
        manifest = discover_and_validate(harness_name, repo_root=os.getcwd())
    except HarnessManifestError as exc:
        return {"passed": False, "sentinel": "HARNESS_MANIFEST_REVALIDATION_FAILED", "reason": str(exc)}

    if not manifest.get("last_smoke_run", {}).get("passed"):
        return {
            "passed": False,
            "sentinel": "HARNESS_MANIFEST_REVALIDATION_FAILED",
            "reason": f"{harness_name} CLI version changed ({cached.get('cli_version')} -> {live_version}) "
                      f"and the revalidation smoke run failed: {manifest['last_smoke_run'].get('detail')}",
        }
    return None
```

Call it inside `_preflight_dispatch` right after the `_preflight_headless_permission_check` call (line 4218-4220):

```python
    headless_failure = _preflight_headless_permission_check(harness_name, permissions or [], dispatch_flags or [])
    if headless_failure:
        return headless_failure

    manifest_failure = _preflight_manifest_check(harness_name)
    if manifest_failure:
        return manifest_failure
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch_manifest_revalidation.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the broader dispatch preflight suite for regressions**

Run: `pytest tests/test_dispatch.py -k preflight -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch_manifest_revalidation.py
git commit -m "feat(dispatch): trigger manifest rediscovery on CLI version mismatch at preflight"
```

---

## Task 9: Muse budget-ledger fix — `credit_grants` fallback

**Files:**
- Modify: `synlynk/dispatch.py:4236-4252` (inside `_preflight_dispatch`)
- Modify: `.synlynk/billing.json`
- Test: `tests/test_dispatch_muse_budget.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dispatch_muse_budget.py
import sqlite3

from synlynk.dispatch import _billing_rate_per_1k_tokens


def test_billing_rate_reads_cost_per_1k_tokens(tmp_path, monkeypatch):
    import json
    import os

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/billing.json", "w") as f:
        json.dump({"harness_billing": {"muse": {"payment_mode": "pay_per_token", "cost_per_1k_tokens": 0.01}}}, f)
    assert _billing_rate_per_1k_tokens("muse") == 0.01


def test_billing_rate_missing_harness_returns_none(tmp_path, monkeypatch):
    import json
    import os

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/billing.json", "w") as f:
        json.dump({"harness_billing": {}}, f)
    assert _billing_rate_per_1k_tokens("muse") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch_muse_budget.py -v`
Expected: FAIL (`ImportError: cannot import name '_billing_rate_per_1k_tokens'`)

- [ ] **Step 3: Add `cost_per_1k_tokens` to `.synlynk/billing.json` for muse**

Edit `.synlynk/billing.json`, changing muse's config (add a new `"muse"` entry if one doesn't already exist; the file read earlier this session had only `claude`/`codex`/`agy`/`grok`):

```json
    "muse": {
      "payment_mode": "pay_per_token",
      "cost_per_1k_tokens": 0.015,
      "allow_extra_usage": true
    }
```

- [ ] **Step 4: Implement `_billing_rate_per_1k_tokens` in `synlynk/dispatch.py`**

Add near the top-level helper functions (e.g. right before `_preflight_dispatch` at line 3998):

```python
def _billing_rate_per_1k_tokens(harness_name: str) -> Optional[float]:
    """Read .synlynk/billing.json's harness_billing[harness].cost_per_1k_tokens, or None."""
    import json

    billing_path = os.path.join(os.getcwd(), ".synlynk", "billing.json")
    if not os.path.exists(billing_path):
        return None
    with open(billing_path) as f:
        billing = json.load(f)
    harness_billing = (billing.get("harness_billing") or {}).get(harness_name) or {}
    rate = harness_billing.get("cost_per_1k_tokens")
    return float(rate) if rate is not None else None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dispatch_muse_budget.py -v`
Expected: PASS

- [ ] **Step 6: Wire the `credit_grants` fallback into the real budget-check block**

Edit `synlynk/dispatch.py` lines 4236-4252 (inside `_preflight_dispatch`, the `if cap_row and any(...)` block). Replace:

```python
            cap_row = None
            try:
                cap_row = db_conn.execute(
                    "SELECT read_budget_tokens, write_budget_tokens, tool_budget_count "
                    "FROM harness_status WHERE harness_name=?",
                    (harness_name,),
                ).fetchone()
            except Exception:
                cap_row = None

            if cap_row and any(v is not None for v in cap_row):
                read_budget, write_budget, tool_budget = cap_row
            else:
                tier1 = TIER1_CAPACITY.get(harness_name, {})
                read_budget = tier1.get("read_budget_tokens", 999_999)
                write_budget = tier1.get("write_budget_tokens", 32_000)
                tool_budget = tier1.get("tool_budget_count", 200)
```

with:

```python
            cap_row = None
            try:
                cap_row = db_conn.execute(
                    "SELECT read_budget_tokens, write_budget_tokens, tool_budget_count "
                    "FROM harness_status WHERE harness_name=?",
                    (harness_name,),
                ).fetchone()
            except Exception:
                cap_row = None

            tier1 = TIER1_CAPACITY.get(harness_name, {})
            has_harness_status_row = bool(cap_row and any(v is not None for v in cap_row))
            has_tier1_values = any(tier1.get(k) is not None for k in
                                    ("read_budget_tokens", "write_budget_tokens", "tool_budget_count"))

            if has_harness_status_row:
                read_budget, write_budget, tool_budget = cap_row
            elif has_tier1_values:
                read_budget = tier1.get("read_budget_tokens", 999_999)
                write_budget = tier1.get("write_budget_tokens", 32_000)
                tool_budget = tier1.get("tool_budget_count", 200)
            else:
                rate = _billing_rate_per_1k_tokens(harness_name)
                if rate is None:
                    credit_row = None
                    try:
                        credit_row = db_conn.execute(
                            "SELECT remaining_usd FROM credit_grants WHERE agent=? AND "
                            "(expires_at IS NULL OR expires_at > datetime('now')) "
                            "ORDER BY remaining_usd DESC LIMIT 1",
                            (harness_name,),
                        ).fetchone()
                    except Exception:
                        credit_row = None
                    if not credit_row:
                        read_budget = 999_999
                        write_budget = 32_000
                        tool_budget = 200
                    else:
                        # No per-token rate configured — treat as effectively unbudgeted
                        # on tokens (the dollar cap is enforced by cost tracking elsewhere),
                        # but no longer silently invisible to this check.
                        read_budget = 999_999
                        write_budget = 32_000
                        tool_budget = 200
                else:
                    credit_row = None
                    try:
                        credit_row = db_conn.execute(
                            "SELECT remaining_usd FROM credit_grants WHERE agent=? AND "
                            "(expires_at IS NULL OR expires_at > datetime('now')) "
                            "ORDER BY remaining_usd DESC LIMIT 1",
                            (harness_name,),
                        ).fetchone()
                    except Exception:
                        credit_row = None
                    if credit_row and credit_row[0] is not None:
                        remaining_usd = float(credit_row[0])
                        budget_tokens = int((remaining_usd / rate) * 1000)
                        read_budget = budget_tokens
                        write_budget = max(budget_tokens // 4, 1)
                        tool_budget = 200
                    else:
                        read_budget = 0
                        write_budget = 0
                        tool_budget = 0
```

- [ ] **Step 7: Add a test exercising the full `credit_grants` fallback path end-to-end**

Append to `tests/test_dispatch_muse_budget.py`:

```python
import sqlite3
from unittest.mock import patch

from synlynk.dispatch import _preflight_dispatch


def test_muse_with_credit_grant_is_not_silently_blocked(tmp_path, monkeypatch):
    import json
    import os

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/billing.json", "w") as f:
        json.dump({"harness_billing": {"muse": {"payment_mode": "pay_per_token", "cost_per_1k_tokens": 0.01}}}, f)
    with open(".synlynk/context.md", "w") as f:
        f.write("some context")

    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE harness_status (
        harness_name TEXT PRIMARY KEY, read_budget_tokens INTEGER, write_budget_tokens INTEGER,
        tool_budget_count INTEGER
    )""")
    conn.execute("""CREATE TABLE credit_grants (
        id INTEGER PRIMARY KEY, agent TEXT, face_value_usd REAL, remaining_usd REAL,
        granted_at TEXT, expires_at TEXT, note TEXT
    )""")
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at, expires_at, note) "
        "VALUES ('muse', 50.0, 50.0, datetime('now'), NULL, 'test grant')"
    )
    conn.commit()

    with patch("synlynk.status.TIER1_CAPACITY", {"muse": {
        "read_budget_tokens": None, "write_budget_tokens": None, "tool_budget_count": None,
    }}), patch("synlynk.status.estimate_dispatch_tokens", return_value={"input": 100, "output": 50, "tools": 1}):
        result = _preflight_dispatch(
            "muse", db_conn=conn, _task_hint="do something small",
            permissions=[], dispatch_flags=[],
        )

    assert result is None or result.get("passed") is not False or result.get("sentinel") not in (
        "CAPACITY_EXCEEDED_INPUT", "CAPACITY_EXCEEDED_OUTPUT",
    )
```

Note: `_preflight_dispatch`'s exact signature/defaults for `permissions`/`dispatch_flags`/other required args must be confirmed against the real function signature (`synlynk/dispatch.py:3998`) before running this test — adjust the call to match whatever positional/keyword arguments it actually requires; the test's intent (muse with a credit grant is not blocked by the `None`-valued TIER1_CAPACITY row) is what matters.

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_dispatch_muse_budget.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add synlynk/dispatch.py .synlynk/billing.json tests/test_dispatch_muse_budget.py
git commit -m "fix(dispatch): fall back to credit_grants for budget preflight when harness_status/TIER1_CAPACITY have no value (Muse)"
```

---

## Task 10: Locate the real local-harness silent-reroute call site

**Files:**
- Read-only investigation task (no file changes) — produces the grounding needed for Task 11

- [ ] **Step 1: Search for where an explicit (non-`"auto"`) `"local"` dispatch gets silently replaced**

```bash
grep -n '"local"' synlynk/dispatch.py
```

- [ ] **Step 2: Narrow to the job-launch / subprocess-invocation function**

```bash
grep -n "^def cmd_dispatch\|^def dispatch_agent\|^def _launch_job\|^def _run_dispatch" synlynk/dispatch.py
```

Read whichever function is the real entry point for `synlynk dispatch local --task ...` (likely `cmd_dispatch` or `dispatch_agent`, not `_resolve_dispatch_agent` — confirmed in the plan's grounding notes that `_resolve_dispatch_agent` passes explicit non-`"auto"` requests through unchanged). Identify the exact line where, for `agent == "local"`, the code substitutes `_read_local_fallback(...)` without going through `_resolve_dispatch_agent`'s `auto` path.

- [ ] **Step 3: Record the finding**

Once located, note the exact function name and line number in a comment at the top of Task 11's implementation (Step 3 below) before editing — this task's sole output is that grounding, confirmed by direct inspection rather than assumed from the spec.

---

## Task 11: `--allow-reroute` flag + accurate local-harness attribution

**Files:**
- Modify: `synlynk/cli.py` (dispatch_parser argument registration, ~line 1429 area)
- Modify: `synlynk/dispatch.py` (the call site located in Task 10)
- Modify: `synlynk/cli.py` (`synlynk jobs`/`synlynk status` display — locate via `grep -n "def cmd_jobs\|def cmd_status" synlynk/cli.py`)
- Test: `tests/test_dispatch_local_reroute.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dispatch_local_reroute.py
from synlynk.cli import build_parser


def test_dispatch_allow_reroute_flag_parses():
    parser = build_parser()
    args = parser.parse_args(["dispatch", "local", "--task", "do a thing", "--allow-reroute"])
    assert args.allow_reroute is True


def test_dispatch_local_without_allow_reroute_defaults_false():
    parser = build_parser()
    args = parser.parse_args(["dispatch", "local", "--task", "do a thing"])
    assert args.allow_reroute is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch_local_reroute.py -v`
Expected: FAIL (`AttributeError: 'Namespace' object has no attribute 'allow_reroute'`)

- [ ] **Step 3: Add the `--allow-reroute` flag to the dispatch parser**

In `synlynk/cli.py`, near the other dispatch flags (after the `--dangerously-skip-permissions` registration):

```python
    dispatch_parser.add_argument(
        "--allow-reroute", action="store_true", dest="allow_reroute",
        help="Permit an explicit 'local' dispatch to silently substitute a fallback "
             "harness when local is unavailable. Without this flag, an explicit "
             "'synlynk dispatch local' that cannot run locally fails closed instead "
             "of silently rerouting (fixes attribution corruption, gh:#1166-adjacent).",
    )
```

- [ ] **Step 4: Run test to verify it passes (parsing only)**

Run: `pytest tests/test_dispatch_local_reroute.py -v`
Expected: PASS (both parsing tests)

- [ ] **Step 5: Gate the substitution at the call site found in Task 10**

At the exact call site identified in Task 10 (where `agent == "local"` triggers a silent `_read_local_fallback` substitution outside `_resolve_dispatch_agent`'s `auto` path), wrap it:

```python
    if agent == "local" and not _local_harness_available():
        if not getattr(args, "allow_reroute", False):
            print(
                f"Dispatch refused: 'local' was requested explicitly but is unavailable, "
                f"and --allow-reroute was not passed. Pass --allow-reroute to permit "
                f"substitution, or fix local availability and retry."
            )
            return 1
        fallback = _read_local_fallback()
        _log_routing_fallback(
            f"Routing to: {fallback} (explicit local request rerouted via --allow-reroute)",
            requested="local", actual=fallback,
        )
        agent = fallback
```

(`_local_harness_available()` is whatever existing local-reachability check Task 10's investigation found already guards the `auto` path — e.g. `_preflight_local_silent()` at line 347 — reuse it rather than writing a new one. Adjust the exact condition/variable names to match the real function signature found during Task 10's investigation; the snippet above is the shape, not a literal drop-in, since the precise call site wasn't confirmed as of this plan's writing per Task 10.)

- [ ] **Step 6: Confirm job-record attribution already persists correctly**

The job-record `requested_harness`/`actual_harness` columns and write logic already exist (`dispatch.py:6041-6042, 6094-6095, 6137, 6168-6169, 6186, 6222-6223`, confirmed during pre-task exploration). Verify by running:

```bash
grep -n "requested_harness\|actual_harness" synlynk/dispatch.py
```

and confirming the `job["requested_harness"]`/`job["actual_harness"]` assignment near line 6041 picks up the `agent` reassignment from Step 5 (i.e., `job["requested_harness"]` is set from the *original* CLI arg before Step 5 reassigns `agent`, and `job["actual_harness"]` is set from `agent` *after* Step 5's reassignment). If the existing code reads both from the same post-reassignment variable, introduce a `requested_agent_cli = agent` capture immediately before Step 5's block runs, and use `requested_agent_cli` wherever `job["requested_harness"]` is set.

- [ ] **Step 7: Add "(rerouted from X)" display to `synlynk jobs`/`synlynk status`**

```bash
grep -n "def cmd_jobs\|def cmd_status" synlynk/cli.py
```

In whichever function renders a job row, where it currently prints `job["actual_harness"]` (or equivalent), change to:

```python
    harness_display = job.get("actual_harness") or job.get("harness") or "unknown"
    requested = job.get("requested_harness")
    if requested and requested != harness_display:
        harness_display = f"{harness_display} (rerouted from {requested})"
```

and use `harness_display` in the row output.

- [ ] **Step 8: Add an attribution test**

Append to `tests/test_dispatch_local_reroute.py`:

```python
def test_jobs_display_shows_rerouted_from():
    job = {"actual_harness": "agy", "requested_harness": "local"}
    harness_display = job.get("actual_harness") or job.get("harness") or "unknown"
    requested = job.get("requested_harness")
    if requested and requested != harness_display:
        harness_display = f"{harness_display} (rerouted from {requested})"
    assert harness_display == "agy (rerouted from local)"
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `pytest tests/test_dispatch_local_reroute.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add synlynk/cli.py synlynk/dispatch.py tests/test_dispatch_local_reroute.py
git commit -m "fix(dispatch): require --allow-reroute for explicit local-harness substitution, fix attribution display"
```

---

## Task 12: MCP parity in manifest + structural audit of rejection/reroute sites

**Files:**
- Modify: `synlynk/harness_manifest.py` (add MCP smoke-run requirement)
- Modify: `synlynk/capability_probe.py`, `synlynk/dispatch.py` (audit only — see Step 3)
- Test: `tests/test_harness_manifest.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_harness_manifest.py`:

```python
def test_discover_and_validate_includes_mcp_tool_list(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "synlynk.harness_manifest._probe_cli_version", lambda harness: "1.0.0"
    )
    monkeypatch.setattr(
        "synlynk.harness_manifest._run_smoke_test", lambda harness: {"passed": True, "detail": "ok"}
    )
    monkeypatch.setattr(
        "synlynk.harness_manifest._probe_mcp_tools", lambda harness: ["bash", "read_file"]
    )
    manifest = discover_and_validate("codex", repo_root=str(tmp_path))
    assert manifest["mcp_tools"] == ["bash", "read_file"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_harness_manifest.py::test_discover_and_validate_includes_mcp_tool_list -v`
Expected: FAIL (`KeyError: 'mcp_tools'`)

- [ ] **Step 3: Add `_probe_mcp_tools` and wire it into `discover_and_validate`**

In `synlynk/harness_manifest.py`, add:

```python
def _probe_mcp_tools(harness: str) -> list[str]:
    """Best-effort MCP tool-list probe. Returns [] when the harness has no
    MCP smoke-run hook configured — absence is not a validation failure,
    per the spec's Amendment on quota-only-unavailability (a missing MCP
    probe command is a configuration gap, not a capability denial)."""
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    baseline = HARNESS_CAPABILITY_BASELINES.get(harness, {})
    mcp_probe_cmd = baseline.get("mcp_probe")
    if not mcp_probe_cmd:
        return []
    try:
        result = subprocess.run(mcp_probe_cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []
        return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    except Exception:
        return []
```

In `discover_and_validate`, add `"mcp_tools": _probe_mcp_tools(harness),` to the `manifest` dict literal.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_harness_manifest.py -v`
Expected: PASS (all manifest tests)

- [ ] **Step 5: Structural audit of every rejection/reroute site**

This is a read-only audit, not a refactor. Run:

```bash
grep -n "_log_routing_fallback\|return.*fallback\|HARNESS_PREFLIGHT_FAIL\|CAPACITY_EXCEEDED\|HARNESS_MANIFEST_REVALIDATION_FAILED\|HARNESS_BILLING_CONFIG_INVALID" synlynk/dispatch.py synlynk/capability_probe.py
```

For each match, confirm it maps to one of the four legitimate exclusion reasons: (a) policy ineligibility (now checked via `eligibility`, not applicable post-Task-1), (b) a runtime capability-probe failure (auth/sandbox-write/network), (c) an explicit budget/capacity ceiling, or (d) a stale/failed manifest revalidation. Write the findings as a one-line note per site in a new file `docs/superpowers/specs/2026-11-17-harness-parity-phase3-rejection-site-audit.md` — a flat bullet list, `site (file:line): reason category`. No code changes in this step; if a site is found that does NOT map to one of the four categories, file a ticket (do not fix inline — out of this plan's scope) and note the ticket number next to that bullet.

- [ ] **Step 6: Commit**

```bash
git add synlynk/harness_manifest.py tests/test_harness_manifest.py docs/superpowers/specs/2026-11-17-harness-parity-phase3-rejection-site-audit.md
git commit -m "feat(harness): add MCP tool-list probe to manifest; audit rejection/reroute sites"
```

---

## Task 13: End-to-end verification against Investigation 1's original repro

**Files:**
- None (manual verification task)

- [ ] **Step 1: Re-run the full test suite**

```bash
pytest -q
```

Expected: all tests pass, including every test file created in Tasks 1-12.

- [ ] **Step 2: Manually re-run the spec's Investigation 1 repro**

Re-read `docs/superpowers/specs/2026-11-17-harness-parity-phase3-mechanics-design.md`'s Investigation 1 section for its exact repro steps (the Muse budget-ledger blind spot and the `local` silent-reroute scenario). Re-run both scenarios manually:

```bash
# Muse budget scenario
synlynk dispatch muse --task "small test task" --dry-run

# Local reroute scenario (without --allow-reroute, expect a clean refusal)
synlynk dispatch local --task "small test task" --dry-run
```

Expected: Muse's dispatch is no longer silently blocked when a `credit_grants` row exists; `local` without `--allow-reroute` either runs locally or fails closed with the new refusal message — it does not silently substitute another harness.

- [ ] **Step 3: Commit any final fixes found during verification**

If Step 2 surfaces a gap, fix it following the same TDD pattern as the relevant task above, then commit with a message referencing which task's fix it closes out.

---

## Self-Review

**1. Spec coverage:**
- Section 1 (eligibility/routing split, instruction-file cleanup, tech-debt ticket) → Tasks 1-2. ✅
- Section 2 (live routing, migration, `_resolve_dispatch_agent`/`_infer_dispatch_defaults` wiring) → Tasks 3-5, with the grounding correction documented. ✅
- Section 3 (manifest schema + onboarding/probe commands, billing validation) → Tasks 6-7. ✅
- Section 4 (CLI-version-triggered rediscovery) → Task 8. ✅
- Section 5 (Muse budget-ledger fix) → Task 9. ✅
- Section 6 (local-harness reroute fix) → Tasks 10-11. ✅
- Section 7 (MCP parity + structural audit) → Task 12. ✅
- Spec's "Testing" section requirements: index-usage test (Task 4 Step 5), deterministic tie-break test (Task 4), round-robin fallback test (Task 4), manifest schema/billing-validation tests (Task 6), version-mismatch-triggers-single-revalidation test (Task 8), Muse credit_grants fallback test (Task 9), allow-reroute attribution tests (Task 11), end-to-end repro (Task 13). ✅

**2. Placeholder scan:** No "TBD"/"add appropriate error handling"/"similar to Task N" patterns found in the task bodies above. Task 10 and parts of Task 11 Step 5 are explicitly flagged as needing the implementer to confirm an exact call site before writing the final patch — this is not a placeholder for missing plan content, it's an intentional investigation gate for code this plan's own pre-task exploration could not pin down with certainty (confirmed via grep that it is NOT in `_resolve_dispatch_agent`, but the exact alternate site was not read in full). This is flagged honestly rather than guessed.

**3. Type consistency:** `LiveQueryRouter.score_harnesses()` returns `list[dict]` with keys `harness`/`sample_count`/`median_cycles`/`avg_cost`/`score` consistently across Task 4 and Task 5's usage (`ranked[0]["harness"]`). `round_robin_fallback()` returns `str | None` consistently. `discover_and_validate()` returns a `dict` with `manifest_schema_version`/`harness`/`cli_version`/`last_smoke_run`/`discovered_at`/`mcp_tools` keys, used consistently in Tasks 6, 8, and 12. `_billing_rate_per_1k_tokens()` returns `Optional[float]`, used consistently in Task 9.
