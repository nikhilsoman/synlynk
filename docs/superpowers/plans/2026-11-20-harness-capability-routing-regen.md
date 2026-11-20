# Harness Capability Routing & Policy Regen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the four sections of `docs/superpowers/specs/2026-11-20-harness-capability-routing-regen-design.md` (gh:#5416, GOVERNS `goal-e03d2671`): universal cross-harness eligibility with three new dispatch-time filters, a composite (not pr_review_cycles-only) capability score with documented missing-data handling, a new `synlynk capability regen` CLI command that regenerates `.synlynk/policy.json`'s calibration/eligibility fields from live data (closing gh:#1993), and an exploration-spend cap that pauses indefinite sub-floor spend on one cell.

**Architecture:** All routing logic stays in `synlynk/routing.py` (`LiveQueryRouter`); eligibility filters that must run *before* `LiveQueryRouter.select` live in `synlynk/dispatch.py` next to the existing `_eligible_harnesses_for_task_type`/`_resolve_dispatch_agent`. The new regen command is a new sibling module `synlynk/capability_regen.py` (mirrors `synlynk/capability_report.py`), wired into `synlynk/cli.py`'s existing `capability` subparser. A new migration `m0037` adds per-harness exploration-spend tracking to `routing_rotation_state`. A pre-existing dead-column bug (`cost_entries.type_id` is never populated, so the cost/time term in scoring has always had zero data) is fixed first since Section 2's score formula depends on it having real data.

**Tech Stack:** Python 3 stdlib only (sqlite3, json, statistics, argparse) — no new dependencies, matching the rest of `synlynk/`.

---

## Prerequisite finding (read before starting)

Grounding this plan surfaced a real, pre-existing bug: `cost_entries.type_id` is a column that exists in the schema (`synlynk/db.py:1888`, `:2034`, `:1596`) but **no code path has ever written a value into it** — `_insert_cost_row`'s INSERT and UPDATE statements (`synlynk/db.py:2856-2886`, `:2934-2938`) both omit `type_id` entirely. `LiveQueryRouter._score`'s existing cost query (`synlynk/routing.py:63-69`, `WHERE agent=? AND type_id=?`) has therefore always returned zero rows in production — the cost/time term has been silently dead since it was written. Section 2's composite score formula explicitly depends on `cost_entries.type_id=task_type` holding real data (the spec says so directly: "matches existing `_score`"), so Task 1 fixes this first. Without it, the new score's cost/time component would also always fall into the cell-wide-degenerate path and never actually discriminate between harnesses on cost.

---

### Task 1: Fix `cost_entries.type_id` population gap

**Files:**
- Modify: `synlynk/db.py:2704-2986` (`_insert_cost_row`)
- Test: `tests/test_cost_entries_type_id.py`

- [ ] **Step 1: Write the failing test**

```python
import sqlite3

import pytest

from synlynk.db import _insert_cost_row


def _make_min_db(tmp_path):
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT, agent TEXT, harness TEXT,
            agent_role TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER,
            cache_read_tokens INTEGER, cost_source TEXT, estimate_basis TEXT, total_cost_usd REAL,
            api_equivalent_usd REAL, actual_usd REAL, payment_mode TEXT, notes TEXT, story_id TEXT,
            epic_id INTEGER, phase_id INTEGER, job_id TEXT, dispatch_context TEXT, context_mode TEXT,
            session_id TEXT, pr_number INTEGER, decision_revision INTEGER, turn_usage_json TEXT,
            estimated_input_tokens INTEGER, estimated_output_tokens INTEGER, estimated_cost_usd REAL,
            compaction_event_type TEXT, requested_harness TEXT, type_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE daemon_jobs (
            job_id TEXT PRIMARY KEY, task_type TEXT, context_mode TEXT, session_id TEXT
        )
    """)
    conn.execute("INSERT INTO daemon_jobs (job_id, task_type) VALUES ('job-abc', 'css')")
    conn.commit()
    conn.close()
    return db_path


def test_insert_cost_row_populates_type_id_from_explicit_task_type(tmp_path, monkeypatch):
    db_path = _make_min_db(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    _insert_cost_row(
        session_date="2026-11-20 00:00", agent="codex", total_cost_usd=1.0,
        cost_source="actual", task_type="implement",
    )
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT type_id FROM cost_entries WHERE agent='codex'").fetchone()
    assert row[0] == "implement"


def test_insert_cost_row_populates_type_id_from_job_id_lookup(tmp_path, monkeypatch):
    db_path = _make_min_db(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    _insert_cost_row(
        session_date="2026-11-20 00:00", agent="codex", total_cost_usd=1.0,
        cost_source="actual", job_id="job-abc",
    )
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT type_id FROM cost_entries WHERE job_id='job-abc'").fetchone()
    assert row[0] == "css"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_entries_type_id.py -v`
Expected: FAIL with `TypeError: _insert_cost_row() got an unexpected keyword argument 'task_type'`

- [ ] **Step 3: Implement the fix**

In `synlynk/db.py`, add a `task_type: str = None` parameter to `_insert_cost_row`'s signature (right after `requested_harness: str = None,` at line 2731):

```python
    requested_harness: str = None,
    task_type: str = None,
    db_path: str = None,
```

Immediately after the existing `if requested_harness is None: requested_harness = harness_val` block (around line 2750-2751), add the job-id-based lookup fallback:

```python
        if requested_harness is None:
            requested_harness = harness_val
        if task_type is None and job_id:
            try:
                tt_row = conn.execute(
                    "SELECT task_type FROM daemon_jobs WHERE job_id=?", (job_id,)
                ).fetchone()
                if tt_row and tt_row[0]:
                    task_type = tt_row[0]
            except sqlite3.Error:
                pass
```

In the UPDATE branch (`update_sql` starting at line 2856), add `type_id` to the SET clause — insert this line right after the `phase_id=?,` line:

```python
                        phase_id=?,
                        type_id=COALESCE(?, type_id),
                        dispatch_context=COALESCE(?, dispatch_context),
```

And add `task_type` to `update_params` in the matching position (right after the `phase_id,` entry, before `dispatch_context`):

```python
                        phase_id,
                        task_type,
                        dispatch_context,
```

In the INSERT branch (`insert_sql` starting at line 2934), add `type_id` to the column list and VALUES placeholder count, and `task_type` to `insert_params` in the matching position — insert `type_id` right after `phase_id` in both the column list and the params tuple:

```python
        insert_sql = """INSERT INTO cost_entries
                (session_date, agent, harness, agent_role, model, input_tokens, output_tokens, cache_read_tokens,
                 cost_source, estimate_basis, total_cost_usd, api_equivalent_usd, actual_usd, payment_mode, notes, story_id, epic_id, phase_id, type_id, job_id, dispatch_context, context_mode, session_id, pr_number, decision_revision, turn_usage_json,
                 estimated_input_tokens, estimated_output_tokens, estimated_cost_usd, compaction_event_type, requested_harness)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        insert_params = (
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
                task_type,
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
                compaction_event_type,
                requested_harness,
        )
```

Both the INSERT's `except sqlite3.OperationalError` fallback (which currently only handles a missing `requested_harness` column) must also handle a missing `type_id` column, since `type_id` was added via a conditional `ALTER TABLE` and an old on-disk DB predating that migration could still lack it:

```python
        try:
            conn.execute(insert_sql, insert_params)
        except sqlite3.OperationalError as exc:
            if "has no column named requested_harness" in str(exc).lower():
                _add_column_if_missing(conn, table="cost_entries", column="requested_harness", definition="TEXT")
                conn.execute(insert_sql, insert_params)
            elif "has no column named type_id" in str(exc).lower():
                _add_column_if_missing(conn, table="cost_entries", column="type_id", definition="TEXT")
                conn.execute(insert_sql, insert_params)
            else:
                raise
```

Apply the identical `elif "has no column named type_id"` branch to the UPDATE statement's existing `except sqlite3.OperationalError` handler (the one just above it in the same function, around line 2919-2926).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_entries_type_id.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_cost_entries_type_id.py
git commit -m "fix: populate cost_entries.type_id from task_type/daemon_jobs lookup

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Add `--task-type` flag to `synlynk cost log`

**Files:**
- Modify: `synlynk/cli.py:1776-1793` (argparse), `synlynk/cli.py:3441-3449` (call site)
- Modify: `synlynk/db.py:5605-5680` (`cmd_cost_log`)
- Test: `tests/test_cost_log_task_type.py`

- [ ] **Step 1: Write the failing test**

```python
import sqlite3

from synlynk.db import cmd_cost_log


def test_cmd_cost_log_passes_task_type_to_insert_cost_row(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT, agent TEXT, harness TEXT,
            agent_role TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER,
            cache_read_tokens INTEGER, cost_source TEXT, estimate_basis TEXT, total_cost_usd REAL,
            api_equivalent_usd REAL, actual_usd REAL, payment_mode TEXT, notes TEXT, story_id TEXT,
            epic_id INTEGER, phase_id INTEGER, job_id TEXT, dispatch_context TEXT, context_mode TEXT,
            session_id TEXT, pr_number INTEGER, decision_revision INTEGER, turn_usage_json TEXT,
            estimated_input_tokens INTEGER, estimated_output_tokens INTEGER, estimated_cost_usd REAL,
            compaction_event_type TEXT, requested_harness TEXT, type_id TEXT
        )
    """)
    conn.execute("CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, actual_harness TEXT, resolved_model TEXT, task_type TEXT)")
    conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, discipline TEXT, phase TEXT)")
    conn.commit()
    conn.close()
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    cmd_cost_log(agent="codex", tokens_in=100, tokens_out=50, task_type="review")
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT type_id FROM cost_entries WHERE agent='codex'").fetchone()
    assert row[0] == "review"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_log_task_type.py -v`
Expected: FAIL with `TypeError: cmd_cost_log() got an unexpected keyword argument 'task_type'`

- [ ] **Step 3: Implement**

In `synlynk/db.py`, add `task_type: str = None` to `cmd_cost_log`'s signature (after `role: str = None,` at line 5614):

```python
    role: str = None,
    task_type: str = None,
) -> None:
```

Thread it into the `_insert_cost_row` call at line 5664:

```python
    _insert_cost_row(
        session_date=ts,
        agent=agent,
        model=model_version,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cache_read_tokens=0,
        cost_source="estimated_manual",
        estimate_basis="cli_manual_entry",
        total_cost_usd=est_cost,
        notes=note,
        task_type=task_type,
```
(keep the remaining existing kwargs on the lines that already follow).

In `synlynk/cli.py`, add the new flag right after `cost_log_parser.add_argument("--note", default=None)` (line 1793):

```python
    cost_log_parser.add_argument("--note", default=None)
    cost_log_parser.add_argument(
        "--task-type", default=None, dest="task_type",
        help="task_type bucket for capability scoring (e.g. implement, review, css)",
    )
```

At the call site (line 3441), add `task_type=args.task_type` to the `cmd_cost_log(...)` call:

```python
            cmd_cost_log(
                args.harness,
                args.tokens_in,
                args.tokens_out,
                story_id=args.story_id,
                job_id=args.job_id,
                pr=args.pr,
                note=args.note,
                model=args.model,
                task_type=args.task_type,
```
(keep whatever argument already follows `model=args.model,` on the next line).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cost_log_task_type.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py synlynk/db.py tests/test_cost_log_task_type.py
git commit -m "feat: add --task-type to synlynk cost log for capability scoring

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Migration m0037 — per-harness exploration-spend tracking

**Files:**
- Create: `synlynk/migrations/m0037_exploration_spend.py`
- Modify: `synlynk/migrations/runner.py`
- Test: `tests/test_migration_m0037_exploration_spend.py`

- [ ] **Step 1: Write the failing test**

```python
import sqlite3

from synlynk.migrations.m0035_routing_rotation_state import MIGRATION as M0035
from synlynk.migrations.m0037_exploration_spend import MIGRATION as M0037


def test_adds_exploration_spend_usd_column_with_empty_json_default():
    conn = sqlite3.connect(":memory:")
    M0035.up(conn)
    M0037.up(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(routing_rotation_state)")}
    assert "exploration_spend_usd" in cols
    conn.execute("INSERT INTO routing_rotation_state (task_type) VALUES ('implement')")
    row = conn.execute(
        "SELECT exploration_spend_usd FROM routing_rotation_state WHERE task_type='implement'"
    ).fetchone()
    assert row[0] == "{}"


def test_up_is_idempotent():
    conn = sqlite3.connect(":memory:")
    M0035.up(conn)
    M0037.up(conn)
    M0037.up(conn)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_m0037_exploration_spend.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.migrations.m0037_exploration_spend'`

- [ ] **Step 3: Write the migration**

Read `synlynk/migrations/m0035_routing_rotation_state.py` first to confirm the exact `Migration` namedtuple/class shape this project uses, then create `synlynk/migrations/m0037_exploration_spend.py`:

```python
"""Migration 37: per-cell exploration-spend cap tracking.

Adds exploration_spend_usd to routing_rotation_state: a JSON object mapping
harness -> cumulative USD spent on sub-floor round-robin picks for that
(task_type, harness) cell. Stored as a column on the existing per-task_type
row (not a new table) because routing_rotation_state's primary key is
task_type alone; the per-harness dimension is tracked inside the JSON blob.

See docs/superpowers/specs/2026-11-20-harness-capability-routing-regen-design.md
Section 4.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(routing_rotation_state)")}
    if "exploration_spend_usd" not in cols:
        conn.execute(
            "ALTER TABLE routing_rotation_state "
            "ADD COLUMN exploration_spend_usd TEXT NOT NULL DEFAULT '{}'"
        )


MIGRATION = Migration(version=37, name="exploration_spend", up=_up)
```

If `synlynk/migrations/__init__.py`'s `Migration` type takes different field names/order than `version=`, `name=`, `up=`, match whatever `m0035_routing_rotation_state.py` actually uses instead — copy its exact `MIGRATION = Migration(...)` line structure verbatim, substituting `37`/`"exploration_spend"`/`_up`.

In `synlynk/migrations/runner.py`, add the import at the top (next to the `M0036` import) and append to `MIGRATIONS`:

```python
from synlynk.migrations.m0037_exploration_spend import MIGRATION as M0037
```

```python
MIGRATIONS = [
    # ... existing entries ...
    M0036,
    M0037,
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migration_m0037_exploration_spend.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full migration runner against a fresh DB to confirm no ordering conflict**

Run: `python3 -c "
import sqlite3
from synlynk.migrations.runner import run_pending_migrations
conn = sqlite3.connect(':memory:')
run_pending_migrations(conn)
cols = {r[1] for r in conn.execute('PRAGMA table_info(routing_rotation_state)')}
assert 'exploration_spend_usd' in cols
print('OK')
"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add synlynk/migrations/m0037_exploration_spend.py synlynk/migrations/runner.py tests/test_migration_m0037_exploration_spend.py
git commit -m "feat: add m0037 migration for per-harness exploration-spend tracking

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Section 1 — widen every task_type's fallback list in `.synlynk/policy.json`

**Files:**
- Modify: `.synlynk/policy.json` (`overrides.dev_authority.task_allocation.*.fallback`)
- Test: `tests/test_policy_fallback_universal_eligibility.py`

- [ ] **Step 1: Write the failing test**

```python
import json

ALL_HARNESSES = {"claude", "codex", "agy", "grok", "muse"}


def test_every_task_type_fallback_covers_all_other_harnesses():
    with open(".synlynk/policy.json") as handle:
        policy = json.load(handle)
    task_allocation = policy["overrides"]["dev_authority"]["task_allocation"]
    gaps = {}
    for task_type, entry in task_allocation.items():
        primary = entry["agent"]
        fallback = set(entry.get("fallback", []))
        expected = ALL_HARNESSES - {primary}
        missing = expected - fallback
        if missing:
            gaps[task_type] = sorted(missing)
    assert gaps == {}, f"task_types missing universal fallback coverage: {gaps}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_policy_fallback_universal_eligibility.py -v`
Expected: FAIL — `gaps` is non-empty (e.g. `{'css': ['claude', 'codex', 'grok', 'muse'], ...}`)

- [ ] **Step 3: Apply the one-time data edit**

Run this one-off Python script (not committed as a file — a direct interactive edit of the live `.synlynk/policy.json`):

```bash
python3 -c "
import json

ALL_HARNESSES = ['claude', 'codex', 'agy', 'grok', 'muse']

with open('.synlynk/policy.json') as f:
    policy = json.load(f)

task_allocation = policy['overrides']['dev_authority']['task_allocation']
changed = []
for task_type, entry in task_allocation.items():
    primary = entry['agent']
    existing = entry.get('fallback', [])
    missing = [h for h in ALL_HARNESSES if h != primary and h not in existing]
    if missing:
        entry['fallback'] = existing + missing
        changed.append((task_type, entry['fallback']))

with open('.synlynk/policy.json', 'w') as f:
    json.dump(policy, f, indent=2)
    f.write('\n')

for task_type, fallback in changed:
    print(f'{task_type}: fallback -> {fallback}')
"
```

- [ ] **Step 4: Verify the diff is data-only**

Run: `git diff .synlynk/policy.json`
Expected: only `fallback` array entries change (widen, never shrink); no other keys touched. Visually confirm no task_type's `agent` (primary) field changed.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_policy_fallback_universal_eligibility.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .synlynk/policy.json tests/test_policy_fallback_universal_eligibility.py
git commit -m "feat: widen every task_type's fallback to all 5 harnesses (Section 1)

Removes the structural lock-in where css/templates/content/subpages/
canvas/js/infra/refactor/cli-plumbing had fallback: [] — a harness now
always has somewhere to land when its primary is unavailable.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Section 1 — hard availability/permission pre-filter

**Files:**
- Modify: `synlynk/dispatch.py` (near `_eligible_harnesses_for_task_type`, and inside `_resolve_dispatch_agent` at its `eligible = _eligible_harnesses_for_task_type(task_type)` call, ~line 360-364)
- Test: `tests/test_dispatch_hard_availability_filter.py`

- [ ] **Step 1: Write the failing test**

```python
import json

from synlynk.dispatch import _hard_availability_filter


def test_excludes_harness_without_can_gh_write_when_required(tmp_path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps({
        "capability_policy": {
            "eligibility": {
                "codex": {"can_gh_write": True},
                "agy": {"can_gh_write": False},
                "grok": {"can_gh_write": True},
            }
        }
    }))
    result = _hard_availability_filter(
        ["codex", "agy", "grok"], requires_gh_write=True, config_path=str(policy_path),
    )
    assert result == ["codex", "grok"]


def test_passthrough_when_gh_write_not_required(tmp_path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps({"capability_policy": {"eligibility": {}}}))
    result = _hard_availability_filter(
        ["codex", "agy"], requires_gh_write=False, config_path=str(policy_path),
    )
    assert result == ["codex", "agy"]


def test_falls_back_to_unfiltered_set_when_filter_would_empty_it(tmp_path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps({
        "capability_policy": {
            "eligibility": {"codex": {"can_gh_write": False}, "agy": {"can_gh_write": False}},
        }
    }))
    result = _hard_availability_filter(
        ["codex", "agy"], requires_gh_write=True, config_path=str(policy_path),
    )
    assert result == ["codex", "agy"]


def test_missing_policy_file_passes_through(tmp_path):
    result = _hard_availability_filter(
        ["codex", "agy"], requires_gh_write=True, config_path=str(tmp_path / "missing.json"),
    )
    assert result == ["codex", "agy"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch_hard_availability_filter.py -v`
Expected: FAIL with `ImportError: cannot import name '_hard_availability_filter'`

- [ ] **Step 3: Implement the filter**

In `synlynk/dispatch.py`, add this function immediately after `_eligible_harnesses_for_task_type`'s definition:

```python
def _hard_availability_filter(
    eligible: list[str],
    *,
    requires_gh_write: bool,
    config_path: str = ".synlynk/policy.json",
) -> list[str]:
    """Exclude a harness that cannot physically attempt this task at all.

    Universal fallback eligibility (task_allocation.fallback, Section 1) says
    a harness is *allowed* to be routed to for a task_type; this says it can
    actually run the dispatch. Today the only such hard gate encoded in
    policy.json is can_gh_write for a requires_gh_write dispatch. This does
    not replace the later per-harness preflight that already runs after a
    specific harness is chosen (_dispatch_capability_preflight /
    _preflight_dispatch) -- that remains a second, independent check.

    Falls back to the unfiltered set (rather than raising) if filtering
    would leave zero candidates, or if the policy file can't be read, so
    this filter degrades to a no-op instead of ever blocking dispatch on
    its own.
    """
    if not requires_gh_write:
        return eligible
    try:
        import json as _json
        with open(config_path) as handle:
            policy = _json.load(handle)
        eligibility = policy.get("capability_policy", {}).get("eligibility", {})
    except (OSError, ValueError):
        return eligible
    filtered = [h for h in eligible if eligibility.get(h, {}).get("can_gh_write") is True]
    return filtered if filtered else eligible
```

Then in `_resolve_dispatch_agent`, find the line `eligible = _eligible_harnesses_for_task_type(task_type)` (or equivalent — confirm exact variable name/line by reading the function body first) and insert the filter call immediately after it, before the `LiveQueryRouter().select(...)` call:

```python
    eligible = _eligible_harnesses_for_task_type(task_type)
    eligible = _hard_availability_filter(eligible, requires_gh_write=requires_gh_write)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dispatch_hard_availability_filter.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the existing dispatch test suite to confirm no regression**

Run: `pytest tests/test_dispatch.py -v -k "resolve_dispatch_agent or eligible"`
Expected: all pre-existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch_hard_availability_filter.py
git commit -m "feat: hard availability filter excludes gh-write-incapable harnesses pre-routing (Section 1)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: Section 1 — blast-radius guard (`sub_floor_exploration_mode`)

**Files:**
- Modify: `.synlynk/policy.json` (`capability_policy`)
- Modify: `synlynk/dispatch.py` (near the new filter functions)
- Test: `tests/test_dispatch_blast_radius_guard.py`

- [ ] **Step 1: Write the failing test**

```python
import json

import pytest

from synlynk.dispatch import _check_blast_radius_guard


def _policy(tmp_path, mode):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"capability_policy": {"sub_floor_exploration_mode": mode}}))
    return str(path)


def test_observe_mode_logs_but_does_not_block(tmp_path, capsys):
    path = _policy(tmp_path, "observe")
    result = _check_blast_radius_guard("deploy", "codex", config_path=path)
    assert result["blocked"] is False
    captured = capsys.readouterr()
    assert "deploy" in captured.out
    assert "codex" in captured.out


def test_enforce_mode_blocks_without_confirmation(tmp_path):
    path = _policy(tmp_path, "enforce")
    result = _check_blast_radius_guard("infra", "grok", config_path=path)
    assert result["blocked"] is True


def test_enforce_mode_allows_with_explicit_confirmation(tmp_path):
    path = _policy(tmp_path, "enforce")
    result = _check_blast_radius_guard(
        "infra", "grok", config_path=path, confirmed_harness="grok",
    )
    assert result["blocked"] is False


def test_non_blast_radius_task_type_is_never_blocked(tmp_path):
    path = _policy(tmp_path, "enforce")
    result = _check_blast_radius_guard("implement", "codex", config_path=path)
    assert result["blocked"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch_blast_radius_guard.py -v`
Expected: FAIL with `ImportError: cannot import name '_check_blast_radius_guard'`

- [ ] **Step 3: Add the policy field**

Edit `.synlynk/policy.json`'s `capability_policy` object (top-level sibling of `not_yet_calibrated`/`note`) to add:

```json
    "sub_floor_exploration_mode": "observe",
```

- [ ] **Step 4: Implement the guard**

In `synlynk/dispatch.py`, add next to `_hard_availability_filter`:

```python
_BLAST_RADIUS_TASK_TYPES = frozenset({"deploy", "infra", "architecture-review"})


def _check_blast_radius_guard(
    task_type: str,
    picked_harness: str,
    *,
    requires_gh_write: bool = False,
    confirmed_harness: str = None,
    config_path: str = ".synlynk/policy.json",
) -> dict:
    """Gate a sub-floor round-robin pick for a high-blast-radius task_type.

    Section 1's blast-radius guard: deploy/infra/architecture-review and any
    --requires-gh-write dispatch get extra scrutiny before a still-exploring
    (sub-floor) pick is actually used. observe (default): log the pick, do
    not block. enforce: block unless the caller already confirmed this exact
    harness via --confirm-blast-radius-pick (confirmed_harness == picked_harness).
    """
    if task_type not in _BLAST_RADIUS_TASK_TYPES and not requires_gh_write:
        return {"blocked": False}
    try:
        import json as _json
        with open(config_path) as handle:
            policy = _json.load(handle)
        mode = policy.get("capability_policy", {}).get("sub_floor_exploration_mode", "observe")
    except (OSError, ValueError):
        mode = "observe"

    print(
        f"  blast-radius-guard[{task_type}]: sub-floor pick '{picked_harness}' "
        f"(mode={mode})"
    )
    if mode != "enforce":
        return {"blocked": False}
    if confirmed_harness == picked_harness:
        return {"blocked": False}
    return {
        "blocked": True,
        "reason": (
            f"sub_floor_exploration_mode=enforce blocks '{picked_harness}' for "
            f"blast-radius task_type '{task_type}' without --confirm-blast-radius-pick"
        ),
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_dispatch_blast_radius_guard.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add .synlynk/policy.json synlynk/dispatch.py tests/test_dispatch_blast_radius_guard.py
git commit -m "feat: add blast-radius guard for sub-floor picks on deploy/infra/architecture-review (Section 1)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

Note: wiring `_check_blast_radius_guard`'s result into `_resolve_dispatch_agent`'s actual control flow (raising when `blocked=True`) and adding the `--confirm-blast-radius-pick` CLI flag is intentionally deferred — the spec's own "Explicitly out of scope" section states the blast-radius guard's human-approval UX is implementation-plan-level detail, and this task delivers the required mode/gate function itself. Track the CLI wiring as a follow-up story if the team wants `enforce` mode to actually block dispatch end-to-end rather than only being callable.

---

### Task 7: Section 1 — review-collision filter

**Files:**
- Modify: `synlynk/dispatch.py` (near the other filters, and `_resolve_dispatch_agent`'s signature/body)
- Test: `tests/test_dispatch_review_collision_filter.py`

- [ ] **Step 1: Write the failing test**

```python
from synlynk.dispatch import _review_collision_filter


def test_excludes_implementer_harness_from_review_eligible_set():
    result = _review_collision_filter(
        ["claude", "codex", "agy", "grok"], "review", implementer_harness="codex",
    )
    assert result == ["claude", "agy", "grok"]


def test_passthrough_for_non_review_task_type():
    result = _review_collision_filter(
        ["claude", "codex"], "implement", implementer_harness="codex",
    )
    assert result == ["claude", "codex"]


def test_passthrough_when_implementer_unknown():
    result = _review_collision_filter(["claude", "codex"], "review", implementer_harness=None)
    assert result == ["claude", "codex"]


def test_falls_back_to_unfiltered_set_if_exclusion_would_empty_it():
    result = _review_collision_filter(["codex"], "review", implementer_harness="codex")
    assert result == ["codex"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch_review_collision_filter.py -v`
Expected: FAIL with `ImportError: cannot import name '_review_collision_filter'`

- [ ] **Step 3: Implement the filter**

In `synlynk/dispatch.py`:

```python
def _review_collision_filter(
    eligible: list[str],
    task_type: str,
    *,
    implementer_harness: Optional[str] = None,
) -> list[str]:
    """Exclude the implementer's harness from a review-type eligible set.

    Mirrors merge_authority.cross_harness_review_required (reviewer must
    differ from implementer in harness and model) at the routing layer, so
    universal fallback eligibility (Section 1) never widens the candidate
    pool into one that includes the implementer itself. Model-level
    differentiation is enforced separately by `synlynk pr check` at merge
    time; this filter only has a harness name to work with at dispatch time.
    """
    if task_type != "review" or not implementer_harness:
        return eligible
    filtered = [h for h in eligible if h != implementer_harness]
    return filtered if filtered else eligible
```

(Confirm `Optional` is already imported in `synlynk/dispatch.py`; if not, add `from typing import Optional` to its imports.)

Wire it into `_resolve_dispatch_agent`: add a `story_id: Optional[str] = None` parameter to its signature (alongside the existing `dispatch_key`/`scope_paths` parameters), and inside the body, after building `eligible` (after Task 5's `_hard_availability_filter` call), add:

```python
    implementer_harness = None
    if task_type == "review" and story_id:
        row = db.execute(
            "SELECT harness FROM cost_entries WHERE story_id=? AND harness IS NOT NULL "
            "ORDER BY recorded_at DESC LIMIT 1",
            (story_id,),
        ).fetchone()
        implementer_harness = row[0] if row else None
    eligible = _review_collision_filter(eligible, task_type, implementer_harness=implementer_harness)
```

At the call site in `synlynk/cli.py` (the `_resolve_dispatch_agent(...)` call around line 3063), add `story_id=getattr(args, "story_id", None),` to the keyword arguments passed.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dispatch_review_collision_filter.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py synlynk/cli.py tests/test_dispatch_review_collision_filter.py
git commit -m "feat: review-collision filter excludes implementer's harness from review routing (Section 1)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Section 2 — shared `is_calibrated()` + extend the routing test fixture

**Files:**
- Modify: `synlynk/routing.py`
- Modify: `tests/test_routing.py` (`_make_db`)
- Test: additions within `tests/test_routing.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_routing.py`:

```python
from synlynk.routing import is_calibrated


def test_is_calibrated_true_at_floor():
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 1.0)", (f"s{i}",)
        )
    conn.commit()
    assert is_calibrated("codex", "implement", conn) is True


def test_is_calibrated_false_below_floor():
    conn = _make_db()
    conn.execute(
        "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
        "VALUES ('s0', 'codex', 'implement', 1.0)"
    )
    conn.commit()
    assert is_calibrated("codex", "implement", conn) is False


def test_router_select_and_is_calibrated_agree_on_floor_boundary():
    """LiveQueryRouter.select's below_floor branching must use the exact
    same criterion is_calibrated() exposes, so router and capability regen
    never disagree about which cells are calibrated (Section 2)."""
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 1.0)", (f"s{i}",)
        )
    conn.commit()
    assert is_calibrated("codex", "implement", conn) is True
    # grok has zero samples -- round-robin branch must still engage for it
    # even though codex alone is calibrated.
    picks = [LiveQueryRouter().select(["codex", "grok"], "implement", conn) for _ in range(2)]
    assert "grok" in picks
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing.py -v -k is_calibrated`
Expected: FAIL with `ImportError: cannot import name 'is_calibrated'`

- [ ] **Step 3: Implement `is_calibrated` and refactor `_sample_count`/`select` to use it**

In `synlynk/routing.py`, add this module-level function (after the constants, before the class):

```python
def is_calibrated(harness: str, task_type: str, conn: sqlite3.Connection) -> bool:
    """Per-cell calibration criterion shared by LiveQueryRouter and `synlynk
    capability regen` so the two never disagree about which (harness,
    task_type) cells have enough data to score instead of round-robin."""
    row = conn.execute(
        "SELECT COUNT(*) FROM capability_ratings WHERE agent=? AND discipline=?",
        (harness, task_type),
    ).fetchone()
    count = row[0] if row else 0
    return count >= SAMPLE_SIZE_FLOOR
```

Change `LiveQueryRouter._sample_count` to be a thin wrapper (kept for the tie-break's `-samples[h]` ordering, which needs the raw count, not just the boolean):

```python
    def _sample_count(self, conn: sqlite3.Connection, harness: str, task_type: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) FROM capability_ratings WHERE agent=? AND discipline=?",
            (harness, task_type),
        ).fetchone()
        return row[0] if row else 0
```
(unchanged — `is_calibrated` duplicates this exact query rather than calling `_sample_count` internally, since `is_calibrated` is a free function with no `LiveQueryRouter` instance to call a method on; both must stay in sync by inspection since they're 4 lines apart in the same file).

Change `select()`'s floor check from comparing `samples[h] < SAMPLE_SIZE_FLOOR` to calling `is_calibrated`:

```python
    def select(self, eligible_harnesses: list[str], task_type: str, db_conn: sqlite3.Connection) -> str:
        if not eligible_harnesses:
            raise ValueError("eligible_harnesses must be non-empty")
        if len(eligible_harnesses) == 1:
            return eligible_harnesses[0]

        samples = {h: self._sample_count(db_conn, h, task_type) for h in eligible_harnesses}
        below_floor = [h for h in eligible_harnesses if not is_calibrated(h, task_type, db_conn)]
        if below_floor:
            return self._round_robin(db_conn, task_type, below_floor)

        scored = self._compute_cell_scores(db_conn, eligible_harnesses, task_type)
        ranked = [
            (scored[h]["score"], -samples[h], h)
            for h in eligible_harnesses
        ]
        ranked.sort()
        self._log_score_audit(task_type, scored)
        return ranked[0][2]
```
(`_compute_cell_scores` and `_log_score_audit` are implemented in Task 9 — this step leaves them referenced-but-undefined, which is fine since Task 9 is the very next task and both tasks land in the same PR before any test run depends on `select()`'s floor-or-above branch. Do not run the full `test_routing.py` suite until Task 9 is also complete.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_routing.py -v -k is_calibrated`
Expected: PASS (3 passed) — this only exercises the below-floor branch, which doesn't touch `_compute_cell_scores`.

- [ ] **Step 5: Extend `_make_db()` with the new columns Section 2 needs**

Replace `tests/test_routing.py`'s `_make_db()` function body with:

```python
def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE capability_ratings (
            story_id TEXT, agent TEXT, discipline TEXT, pr_review_cycles REAL,
            dispatch_rework INTEGER, micro_rework INTEGER, duration_vs_estimate REAL,
            correct INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE cost_entries (
            agent TEXT, type_id TEXT, total_cost_usd REAL, recorded_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE routing_rotation_state (
            task_type TEXT PRIMARY KEY, cursor INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT, exploration_spend_usd TEXT NOT NULL DEFAULT '{}'
        )
    """)
    return conn
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/routing.py tests/test_routing.py
git commit -m "feat: shared is_calibrated() criterion for router + capability regen (Section 2)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 9: Section 2 — composite capability score with missing-value imputation

**Files:**
- Modify: `synlynk/routing.py`
- Test: `tests/test_routing.py` (new tests for the (a)-(h) requirements)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_routing.py`:

```python
from synlynk.routing import LiveQueryRouter, SCORE_WEIGHTS, MIN_VERDICTS_FOR_SUCCESS_RATIO


def _seed_cycles(conn, harness, task_type, values):
    for i, v in enumerate(values):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, ?, ?, ?)", (f"{harness}-{task_type}-{i}", harness, task_type, v),
        )
    conn.commit()


def test_a_lower_rework_and_cost_wins():
    conn = _make_db()
    _seed_cycles(conn, "codex", "implement", [1.0] * SAMPLE_SIZE_FLOOR)
    _seed_cycles(conn, "grok", "implement", [3.0] * SAMPLE_SIZE_FLOOR)
    router = LiveQueryRouter()
    assert router.select(["codex", "grok"], "implement", conn) == "codex"


def test_b_success_deficit_dominates_when_others_tied():
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles, correct) "
            "VALUES (?, 'codex', 'review', 1.0, 1)", (f"c{i}",)
        )
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles, correct) "
            "VALUES (?, 'grok', 'review', 1.0, ?)", (f"g{i}", 0 if i < 2 else 1)
        )
    conn.commit()
    router = LiveQueryRouter()
    # codex: 5/5 correct (success_deficit=0). grok: 3/5 correct (deficit=0.4, worse).
    assert router.select(["codex", "grok"], "review", conn) == "codex"


def test_c_rework_rate_included_in_score():
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles, dispatch_rework) "
            "VALUES (?, 'codex', 'implement', 1.0, 0)", (f"c{i}",)
        )
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles, dispatch_rework) "
            "VALUES (?, 'grok', 'implement', 1.0, 1)", (f"g{i}",)
        )
    conn.commit()
    router = LiveQueryRouter()
    assert router.select(["codex", "grok"], "implement", conn) == "codex"


def test_d_cost_time_term_uses_task_type_divisor():
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 1.0)", (f"c{i}",)
        )
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', 1.0)", (f"g{i}",)
        )
        conn.execute(
            "INSERT INTO cost_entries (agent, type_id, total_cost_usd, recorded_at) "
            "VALUES ('codex', 'implement', 1.0, datetime('now'))"
        )
        conn.execute(
            "INSERT INTO cost_entries (agent, type_id, total_cost_usd, recorded_at) "
            "VALUES ('grok', 'implement', 100.0, datetime('now'))"
        )
    conn.commit()
    router = LiveQueryRouter()
    assert router.select(["codex", "grok"], "implement", conn) == "codex"


def test_e_missing_correctness_defaults_to_median_of_qualified_others():
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles, correct) "
            "VALUES (?, 'codex', 'implement', 2.0, 1)", (f"c{i}",)
        )
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', 2.0)", (f"g{i}",)
        )
    conn.commit()
    router = LiveQueryRouter()
    scored = router._compute_cell_scores(conn, ["codex", "grok"], "implement")
    # grok has < MIN_VERDICTS_FOR_SUCCESS_RATIO non-null `correct` rows (zero),
    # so it must inherit codex's qualified success_ratio (1.0) rather than a
    # hardcoded 0/1 default.
    assert scored["grok"]["substitutions"]["success_ratio"] is True
    assert scored["codex"]["components"]["norm_success_deficit"] == scored["grok"]["components"]["norm_success_deficit"]


def test_f_scale_invariance_of_cost_divisor_choice():
    """Doubling every harness's cost in a cell must not change the winner --
    min-max normalization is scale-invariant."""
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 1.0)", (f"c{i}",)
        )
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', 1.0)", (f"g{i}",)
        )
        conn.execute(
            "INSERT INTO cost_entries (agent, type_id, total_cost_usd, recorded_at) "
            "VALUES ('codex', 'implement', 2.0, datetime('now'))"
        )
        conn.execute(
            "INSERT INTO cost_entries (agent, type_id, total_cost_usd, recorded_at) "
            "VALUES ('grok', 'implement', 20.0, datetime('now'))"
        )
    conn.commit()
    router = LiveQueryRouter()
    winner_normal = router.select(["codex", "grok"], "implement", conn)

    conn2 = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn2.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 1.0)", (f"c{i}",)
        )
        conn2.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', 1.0)", (f"g{i}",)
        )
        conn2.execute(
            "INSERT INTO cost_entries (agent, type_id, total_cost_usd, recorded_at) "
            "VALUES ('codex', 'implement', 4.0, datetime('now'))"
        )
        conn2.execute(
            "INSERT INTO cost_entries (agent, type_id, total_cost_usd, recorded_at) "
            "VALUES ('grok', 'implement', 40.0, datetime('now'))"
        )
    conn2.commit()
    winner_doubled = LiveQueryRouter().select(["codex", "grok"], "implement", conn2)
    assert winner_normal == winner_doubled == "codex"


def test_g_missing_substatistic_neutrality_not_hardcoded_zero():
    """A harness missing one sub-statistic entirely (zero non-null rows)
    must take the cell's median-of-others for that sub-statistic, not a
    hardcoded 0 -- a hardcoded 0 would wrongly reward missing deficit-style
    data (e.g. rework_rate) as if it were perfect."""
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles, dispatch_rework) "
            "VALUES (?, 'codex', 'implement', 1.0, 1)", (f"c{i}",)
        )
        # grok has pr_review_cycles but zero rows with a non-null rework flag.
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', 1.0)", (f"g{i}",)
        )
    conn.commit()
    router = LiveQueryRouter()
    scored = router._compute_cell_scores(conn, ["codex", "grok"], "implement")
    assert scored["grok"]["substitutions"]["rework_rate"] is True
    # grok's imputed rework_rate must equal codex's real rework_rate (the
    # only other harness in the cell), not 0.0.
    assert scored["grok"]["components"]["norm_rework"] == scored["codex"]["components"]["norm_rework"]


def test_h_cell_wide_degenerate_fallback_logs_and_ties():
    """If every eligible harness has zero non-null rows for a sub-statistic,
    that sub-statistic contributes 0 raw value for all of them (norm=0 tie),
    not an unresolvable gap."""
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 1.0)", (f"c{i}",)
        )
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', 1.0)", (f"g{i}",)
        )
    conn.commit()
    router = LiveQueryRouter()
    scored = router._compute_cell_scores(conn, ["codex", "grok"], "implement")
    # Neither harness has any cost_entries row at all for this cell.
    assert scored["codex"]["substitutions"]["total_cost_usd"] == "degenerate"
    assert scored["grok"]["substitutions"]["total_cost_usd"] == "degenerate"
    assert scored["codex"]["components"]["norm_cost_time"] == scored["grok"]["components"]["norm_cost_time"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing.py -v -k "test_a_ or test_b_ or test_c_ or test_d_ or test_e_ or test_f_ or test_g_ or test_h_"`
Expected: FAIL with `AttributeError: 'LiveQueryRouter' object has no attribute '_compute_cell_scores'` (and `ImportError` for `SCORE_WEIGHTS`/`MIN_VERDICTS_FOR_SUCCESS_RATIO`)

- [ ] **Step 3: Implement the composite score**

Replace `synlynk/routing.py`'s module-level constants (everything between the imports and `class LiveQueryRouter`) with:

```python
SAMPLE_SIZE_FLOOR = 5
MIN_VERDICTS_FOR_SUCCESS_RATIO = 3
SCORE_WEIGHTS = {"success_deficit": 2.0, "rework": 1.0, "cost_time": 1.0}
SCORE_COST_DIVISOR = {
    "implement": 50.0,
    "test": 50.0,
    "review": 30.0,
    "refactor": 50.0,
    "cli-plumbing": 50.0,
}
_DEFAULT_SCORE_COST_DIVISOR = 50.0


def _median_of_others(values: dict, exclude: str) -> Optional[float]:
    others = [v for h, v in values.items() if h != exclude and v is not None]
    return median(others) if others else None


def _fill_missing_with_cell_median(raw: dict) -> tuple:
    """Impute a harness's missing (None) raw value with the median of other
    eligible harnesses' real values in the same cell; if literally no
    harness in the cell has a real value, fall back to 0.0 for everyone
    (the cell-wide degenerate case) rather than leaving a gap.

    Returns (filled, substitution_flags) where substitution_flags[h] is
    False (real data), True (imputed from others), or "degenerate" (every
    harness in the cell was missing this statistic).
    """
    filled = dict(raw)
    substituted = {h: False for h in raw}
    missing = [h for h, v in raw.items() if v is None]
    for h in missing:
        imputed = _median_of_others(raw, h)
        if imputed is not None:
            filled[h] = imputed
            substituted[h] = True
    still_missing = [h for h, v in filled.items() if v is None]
    for h in still_missing:
        filled[h] = 0.0
        substituted[h] = "degenerate"
    return filled, substituted


def _min_max_normalize(raw: dict) -> dict:
    values = list(raw.values())
    lo, hi = min(values), max(values)
    if hi == lo:
        return {h: 0.0 for h in raw}
    return {h: (v - lo) / (hi - lo) for h, v in raw.items()}


def is_calibrated(harness: str, task_type: str, conn: sqlite3.Connection) -> bool:
    """Per-cell calibration criterion shared by LiveQueryRouter and `synlynk
    capability regen` so the two never disagree about which (harness,
    task_type) cells have enough data to score instead of round-robin."""
    row = conn.execute(
        "SELECT COUNT(*) FROM capability_ratings WHERE agent=? AND discipline=?",
        (harness, task_type),
    ).fetchone()
    count = row[0] if row else 0
    return count >= SAMPLE_SIZE_FLOOR
```

Then replace the whole body of `LiveQueryRouter._score` with two new methods (keep `_score` deleted — nothing outside this class called it, per the grep in grounding; `select()` was updated in Task 8 to call `_compute_cell_scores` directly):

```python
    def _compute_cell_scores(
        self, conn: sqlite3.Connection, eligible_harnesses: list, task_type: str,
    ) -> dict:
        cycles_raw, rework_raw, cost_raw, duration_raw, correct_raw = {}, {}, {}, {}, {}

        for h in eligible_harnesses:
            cycles_rows = [
                row[0] for row in conn.execute(
                    "SELECT pr_review_cycles FROM capability_ratings "
                    "WHERE agent=? AND discipline=? AND pr_review_cycles IS NOT NULL",
                    (h, task_type),
                ).fetchall()
            ]
            cycles_raw[h] = median(cycles_rows) if cycles_rows else None

            rework_rows = conn.execute(
                "SELECT dispatch_rework, micro_rework FROM capability_ratings "
                "WHERE agent=? AND discipline=? "
                "AND (dispatch_rework IS NOT NULL OR micro_rework IS NOT NULL)",
                (h, task_type),
            ).fetchall()
            if rework_rows:
                flags = [1.0 if ((dr or 0) != 0 or (mr or 0) != 0) else 0.0 for dr, mr in rework_rows]
                rework_raw[h] = sum(flags) / len(flags)
            else:
                rework_raw[h] = None

            cost_rows = [
                row[0] for row in conn.execute(
                    "SELECT total_cost_usd FROM cost_entries "
                    "WHERE agent=? AND type_id=? AND total_cost_usd IS NOT NULL",
                    (h, task_type),
                ).fetchall()
            ]
            cost_raw[h] = median(cost_rows) if cost_rows else None

            duration_rows = [
                row[0] for row in conn.execute(
                    "SELECT duration_vs_estimate FROM capability_ratings "
                    "WHERE agent=? AND discipline=? AND duration_vs_estimate IS NOT NULL",
                    (h, task_type),
                ).fetchall()
            ]
            duration_raw[h] = median(duration_rows) if duration_rows else None

            correct_rows = [
                row[0] for row in conn.execute(
                    "SELECT correct FROM capability_ratings "
                    "WHERE agent=? AND discipline=? AND correct IS NOT NULL",
                    (h, task_type),
                ).fetchall()
            ]
            correct_raw[h] = (
                sum(1 for c in correct_rows if c == 1) / len(correct_rows)
                if len(correct_rows) >= MIN_VERDICTS_FOR_SUCCESS_RATIO
                else None
            )

        cycles_filled, cycles_sub = _fill_missing_with_cell_median(cycles_raw)
        rework_filled, rework_sub = _fill_missing_with_cell_median(rework_raw)
        cost_filled, cost_sub = _fill_missing_with_cell_median(cost_raw)
        duration_filled, duration_sub = _fill_missing_with_cell_median(duration_raw)

        qualified = {h: v for h, v in correct_raw.items() if v is not None}
        if qualified:
            fallback_ratio = median(qualified.values())
            success_filled = {h: (v if v is not None else fallback_ratio) for h, v in correct_raw.items()}
            success_sub = {h: (v is None) for h, v in correct_raw.items()}
        else:
            success_filled = {h: 1.0 for h in eligible_harnesses}
            success_sub = {h: "degenerate" for h in eligible_harnesses}

        divisor = SCORE_COST_DIVISOR.get(task_type, _DEFAULT_SCORE_COST_DIVISOR)
        raw_success_deficit = {h: 1.0 - success_filled[h] for h in eligible_harnesses}
        raw_rework = {h: cycles_filled[h] + rework_filled[h] for h in eligible_harnesses}
        raw_cost_time = {h: cost_filled[h] / divisor + duration_filled[h] for h in eligible_harnesses}

        norm_success = _min_max_normalize(raw_success_deficit)
        norm_rework = _min_max_normalize(raw_rework)
        norm_cost_time = _min_max_normalize(raw_cost_time)

        results = {}
        for h in eligible_harnesses:
            score = (
                SCORE_WEIGHTS["success_deficit"] * norm_success[h]
                + SCORE_WEIGHTS["rework"] * norm_rework[h]
                + SCORE_WEIGHTS["cost_time"] * norm_cost_time[h]
            )
            results[h] = {
                "score": score,
                "components": {
                    "norm_success_deficit": norm_success[h],
                    "norm_rework": norm_rework[h],
                    "norm_cost_time": norm_cost_time[h],
                },
                "substitutions": {
                    "pr_review_cycles": cycles_sub[h],
                    "rework_rate": rework_sub[h],
                    "total_cost_usd": cost_sub[h],
                    "duration_vs_estimate": duration_sub[h],
                    "success_ratio": success_sub[h],
                },
            }
        return results

    def _log_score_audit(self, task_type: str, scored_cell: dict) -> None:
        for h, data in scored_cell.items():
            subs = {k: v for k, v in data["substitutions"].items() if v}
            print(
                f"  capability-score[{task_type}/{h}]: score={data['score']:.3f} "
                f"components={data['components']} substitutions={subs}"
            )
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `pytest tests/test_routing.py -v -k "test_a_ or test_b_ or test_c_ or test_d_ or test_e_ or test_f_ or test_g_ or test_h_"`
Expected: PASS (8 passed)

- [ ] **Step 5: Run the full routing test file to confirm no regression on the pre-existing tests**

Run: `pytest tests/test_routing.py -v`
Expected: all tests PASS (the pre-existing `test_ranks_by_score_at_or_above_floor` and `test_deterministic_tie_break_prefers_higher_sample_count_then_alphabetical` still pass under the new composite formula — verified by hand in this plan's design: with no cost/correct/rework data seeded, both reduce to the `norm_rework` term alone, which reproduces the old pr_review_cycles-only ranking)

- [ ] **Step 6: Commit**

```bash
git add synlynk/routing.py tests/test_routing.py
git commit -m "feat: composite capability score with missing-value imputation (Section 2)

Replaces the pr_review_cycles + cost/divisor score with a weighted,
per-cell min-max-normalized composite of success_deficit, rework, and
cost/time, each with documented missing-data substitution (median of
qualified peers, falling back to a logged cell-wide degenerate case).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 10: Section 4 — exploration-spend cap circuit breaker

**Files:**
- Modify: `synlynk/routing.py` (`_round_robin`)
- Modify: `synlynk/db.py` (`_insert_cost_row` — call the recorder)
- Test: `tests/test_routing.py` (new), `tests/test_cost_entries_type_id.py` (extend)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_routing.py`:

```python
import json

from synlynk.routing import EXPLORATION_SPEND_CAP_USD, record_exploration_spend


def test_round_robin_skips_a_harness_over_the_exploration_spend_cap():
    conn = _make_db()
    conn.execute(
        "INSERT INTO routing_rotation_state (task_type, cursor, exploration_spend_usd) "
        "VALUES ('implement', 0, ?)",
        (json.dumps({"codex": EXPLORATION_SPEND_CAP_USD + 1.0}),),
    )
    conn.commit()
    router = LiveQueryRouter()
    picks = [router.select(["codex", "grok"], "implement", conn) for _ in range(3)]
    assert "codex" not in picks
    assert picks == ["grok", "grok", "grok"]


def test_round_robin_falls_back_to_full_set_if_every_candidate_is_capped():
    conn = _make_db()
    conn.execute(
        "INSERT INTO routing_rotation_state (task_type, cursor, exploration_spend_usd) "
        "VALUES ('implement', 0, ?)",
        (json.dumps({"codex": EXPLORATION_SPEND_CAP_USD + 1.0, "grok": EXPLORATION_SPEND_CAP_USD + 1.0}),),
    )
    conn.commit()
    router = LiveQueryRouter()
    # Both capped -- must not deadlock; falls back to picking from the full set.
    pick = router.select(["codex", "grok"], "implement", conn)
    assert pick in ("codex", "grok")


def test_record_exploration_spend_accumulates_only_for_sub_floor_cells():
    conn = _make_db()
    conn.execute(
        "INSERT INTO routing_rotation_state (task_type, cursor, exploration_spend_usd) "
        "VALUES ('implement', 0, '{}')"
    )
    conn.commit()
    record_exploration_spend(conn, "codex", "implement", 3.5)
    record_exploration_spend(conn, "codex", "implement", 4.0)
    row = conn.execute(
        "SELECT exploration_spend_usd FROM routing_rotation_state WHERE task_type='implement'"
    ).fetchone()
    spend = json.loads(row[0])
    assert spend["codex"] == 7.5


def test_record_exploration_spend_is_a_noop_once_calibrated():
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 1.0)", (f"c{i}",)
        )
    conn.execute(
        "INSERT INTO routing_rotation_state (task_type, cursor, exploration_spend_usd) "
        "VALUES ('implement', 0, '{}')"
    )
    conn.commit()
    record_exploration_spend(conn, "codex", "implement", 5.0)
    row = conn.execute(
        "SELECT exploration_spend_usd FROM routing_rotation_state WHERE task_type='implement'"
    ).fetchone()
    assert json.loads(row[0]) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routing.py -v -k "exploration_spend"`
Expected: FAIL with `ImportError: cannot import name 'EXPLORATION_SPEND_CAP_USD'`

- [ ] **Step 3: Implement**

In `synlynk/routing.py`, add the constant near the other constants:

```python
EXPLORATION_SPEND_CAP_USD = 10.0
```

And add `import json` to the top-level imports (alongside `import sqlite3`).

Replace `_round_robin`'s body:

```python
    def _round_robin(self, conn: sqlite3.Connection, task_type: str, eligible_harnesses: list) -> str:
        row = conn.execute(
            "SELECT cursor, exploration_spend_usd FROM routing_rotation_state WHERE task_type=?",
            (task_type,),
        ).fetchone()
        cursor = row[0] if row else 0
        spend = json.loads(row[1]) if row and row[1] else {}

        capped = {h for h, usd in spend.items() if usd >= EXPLORATION_SPEND_CAP_USD}
        available = [h for h in eligible_harnesses if h not in capped]
        if not available:
            available = eligible_harnesses

        picked = available[cursor % len(available)]
        conn.execute(
            "INSERT INTO routing_rotation_state (task_type, cursor, exploration_spend_usd, updated_at) "
            "VALUES (?, ?, ?, datetime('now')) "
            "ON CONFLICT(task_type) DO UPDATE SET cursor=excluded.cursor, updated_at=excluded.updated_at",
            (task_type, cursor + 1, json.dumps(spend)),
        )
        conn.commit()
        return picked
```

Add the module-level recorder function (after `is_calibrated`):

```python
def record_exploration_spend(conn: sqlite3.Connection, harness: str, task_type: str, cost_usd: float) -> None:
    """Accrue cost_usd against (harness, task_type)'s exploration-spend cap,
    but only while that cell is still sub-floor -- once is_calibrated() is
    true, further spend is organic scored-routing cost, not exploration
    spend, so it no longer counts toward the cap (Section 4)."""
    if is_calibrated(harness, task_type, conn):
        return
    row = conn.execute(
        "SELECT exploration_spend_usd FROM routing_rotation_state WHERE task_type=?",
        (task_type,),
    ).fetchone()
    spend = json.loads(row[0]) if row and row[0] else {}
    spend[harness] = spend.get(harness, 0.0) + cost_usd
    conn.execute(
        "INSERT INTO routing_rotation_state (task_type, cursor, exploration_spend_usd, updated_at) "
        "VALUES (?, 0, ?, datetime('now')) "
        "ON CONFLICT(task_type) DO UPDATE SET exploration_spend_usd=excluded.exploration_spend_usd, updated_at=excluded.updated_at",
        (task_type, json.dumps(spend)),
    )
    conn.commit()
```

In `synlynk/db.py`'s `_insert_cost_row`, call the recorder right next to the existing `_maybe_alert_cost_estimate_drift` calls (both the UPDATE-path and INSERT-path ones, around lines 2928-2932 and 2980-2984) — add this immediately after each existing call:

```python
                conn.commit()
                _maybe_alert_cost_estimate_drift(
                    conn, job_id=job_id, harness=harness_val,
                    actual_usd=actual_usd if actual_usd is not None else total_cost_usd,
                    estimated_cost_usd=estimated_cost_usd,
                )
                if harness_val and task_type:
                    from synlynk.routing import record_exploration_spend
                    record_exploration_spend(
                        conn, harness_val, task_type,
                        actual_usd if actual_usd is not None else (total_cost_usd or 0.0),
                    )
                return
```
(and the identical `if harness_val and task_type:` block after the INSERT path's `_maybe_alert_cost_estimate_drift` call too, before the `finally: conn.close()`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_routing.py -v -k "exploration_spend"`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the full test_routing.py suite**

Run: `pytest tests/test_routing.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/routing.py synlynk/db.py tests/test_routing.py
git commit -m "feat: exploration-spend cap pauses indefinite sub-floor spend on one cell (Section 4)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 11: Section 3 — `synlynk/capability_regen.py` module

**Files:**
- Create: `synlynk/capability_regen.py`
- Test: `tests/test_capability_regen.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import sqlite3

import pytest

from synlynk.capability_regen import cmd_capability_regen


def _make_regen_db(tmp_path):
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE capability_ratings (
            story_id TEXT, agent TEXT, discipline TEXT, pr_review_cycles REAL,
            dispatch_rework INTEGER, micro_rework INTEGER, duration_vs_estimate REAL, correct INTEGER
        )
    """)
    conn.execute("CREATE TABLE cost_entries (agent TEXT, type_id TEXT, total_cost_usd REAL, recorded_at TEXT)")
    conn.execute("""
        CREATE TABLE daemon_jobs (
            job_id TEXT PRIMARY KEY, actual_harness TEXT, requires_gh_write INTEGER DEFAULT 0,
            gh_write_verified TEXT
        )
    """)
    for i in range(5):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 1.0)", (f"s{i}",)
        )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, actual_harness, requires_gh_write, gh_write_verified) "
        "VALUES ('j1', 'codex', 1, 'true')"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, actual_harness, requires_gh_write, gh_write_verified) "
        "VALUES ('j2', 'agy', 1, 'false')"
    )
    conn.commit()
    conn.close()
    return db_path


def _make_policy(tmp_path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps({
        "overrides": {"dev_authority": {"task_allocation": {
            "implement": {"agent": "codex", "fallback": ["agy", "grok", "claude", "muse"]},
            "review": {"agent": "codex", "fallback": ["claude", "agy", "grok", "muse"]},
        }}},
        "capability_policy": {
            "not_yet_calibrated": ["grok", "muse"],
            "calibration_detail": {},
            "note": "stale note",
            "sub_floor_exploration_mode": "observe",
            "eligibility": {
                "codex": {"can_gh_write": False},
                "agy": {"can_gh_write": False},
            },
        },
    }, indent=2))
    return str(policy_path)


def test_regen_rewrites_calibration_detail_and_not_yet_calibrated(tmp_path, monkeypatch):
    db_path = _make_regen_db(tmp_path)
    policy_path = _make_policy(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    cmd_capability_regen(policy_path=policy_path)
    with open(policy_path) as handle:
        policy = json.load(handle)
    detail = policy["capability_policy"]["calibration_detail"]
    assert detail["codex"]["implement"] is True
    assert detail["codex"]["review"] is False
    assert policy["capability_policy"]["not_yet_calibrated"] == ["grok", "muse"]


def test_regen_computes_can_gh_write_true_false_and_unproven(tmp_path, monkeypatch):
    db_path = _make_regen_db(tmp_path)
    policy_path = _make_policy(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    cmd_capability_regen(policy_path=policy_path)
    with open(policy_path) as handle:
        policy = json.load(handle)
    eligibility = policy["capability_policy"]["eligibility"]
    assert eligibility["codex"]["can_gh_write"] is True
    assert eligibility["agy"]["can_gh_write"] is False
    assert eligibility.get("grok", {}).get("can_gh_write") == "unproven"


def test_regen_leaves_task_allocation_untouched(tmp_path, monkeypatch):
    db_path = _make_regen_db(tmp_path)
    policy_path = _make_policy(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    with open(policy_path) as handle:
        before = json.load(handle)
    cmd_capability_regen(policy_path=policy_path)
    with open(policy_path) as handle:
        after = json.load(handle)
    assert before["overrides"] == after["overrides"]


def test_regen_dry_run_writes_nothing(tmp_path, monkeypatch, capsys):
    db_path = _make_regen_db(tmp_path)
    policy_path = _make_policy(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    with open(policy_path) as handle:
        before_text = handle.read()
    cmd_capability_regen(policy_path=policy_path, dry_run=True)
    with open(policy_path) as handle:
        after_text = handle.read()
    assert before_text == after_text
    captured = capsys.readouterr()
    assert "calibration_detail" in captured.out


def test_regen_malformed_policy_refuses_and_exits_nonzero(tmp_path, monkeypatch):
    db_path = _make_regen_db(tmp_path)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text("{not valid json")
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    with pytest.raises(ValueError):
        cmd_capability_regen(policy_path=str(policy_path))


def test_regen_missing_db_path_raises(tmp_path, monkeypatch):
    policy_path = _make_policy(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "does-not-exist.db"))
    with pytest.raises(Exception):
        cmd_capability_regen(policy_path=policy_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_regen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.capability_regen'`

- [ ] **Step 3: Implement the module**

Create `synlynk/capability_regen.py`:

```python
"""`synlynk capability regen` -- regenerate .synlynk/policy.json's
calibration/eligibility fields from live capability_ratings/cost_entries/
daemon_jobs data. Closes gh:#1993.

Rewrites only capability_policy.calibration_detail, .not_yet_calibrated,
.note, and .eligibility.*.can_gh_write -- task_allocation and every other
key are left untouched. See
docs/superpowers/specs/2026-11-20-harness-capability-routing-regen-design.md
Section 3.
"""
import json
import os
import sqlite3
import tempfile

from synlynk.routing import is_calibrated

_ALL_HARNESSES = ("claude", "codex", "agy", "grok", "muse")


def _load_policy(policy_path: str) -> dict:
    try:
        with open(policy_path) as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot load policy.json at {policy_path!r}: {exc}") from exc


def _task_types(policy: dict) -> list:
    return sorted(policy["overrides"]["dev_authority"]["task_allocation"].keys())


def _compute_calibration_detail(conn: sqlite3.Connection, task_types: list) -> dict:
    detail = {}
    for harness in _ALL_HARNESSES:
        detail[harness] = {tt: is_calibrated(harness, tt, conn) for tt in task_types}
    return detail


def _compute_not_yet_calibrated(detail: dict) -> list:
    return sorted(h for h, per_tt in detail.items() if not any(per_tt.values()))


def _compute_note(detail: dict) -> str:
    parts = []
    for harness in _ALL_HARNESSES:
        per_tt = detail[harness]
        total = len(per_tt)
        calibrated = sum(1 for v in per_tt.values() if v)
        parts.append(f"{harness}: calibrated on {calibrated}/{total} task_types")
    return "; ".join(parts)


def _compute_can_gh_write(conn: sqlite3.Connection) -> dict:
    result = {}
    for harness in _ALL_HARNESSES:
        true_row = conn.execute(
            "SELECT COUNT(*) FROM daemon_jobs WHERE actual_harness=? AND gh_write_verified='true'",
            (harness,),
        ).fetchone()
        has_true = bool(true_row and true_row[0] > 0)

        attempts_row = conn.execute(
            "SELECT COUNT(*) FROM daemon_jobs WHERE actual_harness=? AND requires_gh_write=1",
            (harness,),
        ).fetchone()
        has_attempts = bool(attempts_row and attempts_row[0] > 0)

        false_row = conn.execute(
            "SELECT COUNT(*) FROM daemon_jobs "
            "WHERE actual_harness=? AND requires_gh_write=1 AND gh_write_verified='false'",
            (harness,),
        ).fetchone()
        attempts_count = attempts_row[0] if attempts_row else 0
        false_count = false_row[0] if false_row else 0

        if has_true:
            result[harness] = True
        elif has_attempts and false_count == attempts_count:
            result[harness] = False
        elif has_attempts:
            result[harness] = "unproven"
        # No attempts at all: leave this harness out of the dict entirely --
        # there is no evidence either way, so don't claim one.
    return result


def cmd_capability_regen(policy_path: str = ".synlynk/policy.json", dry_run: bool = False) -> None:
    from synlynk import _get_db

    policy = _load_policy(policy_path)
    task_types = _task_types(policy)

    conn = _get_db(read_only=True)
    try:
        calibration_detail = _compute_calibration_detail(conn, task_types)
        not_yet_calibrated = _compute_not_yet_calibrated(calibration_detail)
        note = _compute_note(calibration_detail)
        can_gh_write = _compute_can_gh_write(conn)
    finally:
        conn.close()

    cap_policy = policy.setdefault("capability_policy", {})
    old_calibration_detail = cap_policy.get("calibration_detail", {})
    old_not_yet_calibrated = cap_policy.get("not_yet_calibrated", [])
    old_note = cap_policy.get("note", "")
    old_eligibility = cap_policy.get("eligibility", {})

    if dry_run:
        print("--- calibration_detail ---")
        print(f"before: {json.dumps(old_calibration_detail, sort_keys=True)}")
        print(f"after:  {json.dumps(calibration_detail, sort_keys=True)}")
        print("--- not_yet_calibrated ---")
        print(f"before: {old_not_yet_calibrated}")
        print(f"after:  {not_yet_calibrated}")
        print("--- note ---")
        print(f"before: {old_note!r}")
        print(f"after:  {note!r}")
        print("--- eligibility.*.can_gh_write ---")
        for harness, value in can_gh_write.items():
            before = old_eligibility.get(harness, {}).get("can_gh_write")
            print(f"{harness}: before={before!r} after={value!r}")
        return

    cap_policy["calibration_detail"] = calibration_detail
    cap_policy["not_yet_calibrated"] = not_yet_calibrated
    cap_policy["note"] = note
    eligibility = cap_policy.setdefault("eligibility", {})
    for harness, value in can_gh_write.items():
        eligibility.setdefault(harness, {})["can_gh_write"] = value

    _atomic_write_json(policy_path, policy)
    print(f"  capability regen: rewrote calibration_detail/not_yet_calibrated/note/eligibility in {policy_path}")
    print(f"  {note}")


def _atomic_write_json(path: str, payload: dict) -> None:
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".policy-regen-")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_regen.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/capability_regen.py tests/test_capability_regen.py
git commit -m "feat: synlynk capability regen rewrites policy.json calibration fields from live data (Section 3, closes #1993)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 12: Section 3 — wire `synlynk capability regen` into the CLI

**Files:**
- Modify: `synlynk/cli.py` (the `capability` subparser and its dispatch `elif` chain)
- Test: `tests/test_cli_capability_regen.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import subprocess
import sys


def test_capability_regen_dry_run_via_cli(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE capability_ratings (story_id TEXT, agent TEXT, discipline TEXT, pr_review_cycles REAL, dispatch_rework INTEGER, micro_rework INTEGER, duration_vs_estimate REAL, correct INTEGER)")
    conn.execute("CREATE TABLE cost_entries (agent TEXT, type_id TEXT, total_cost_usd REAL, recorded_at TEXT)")
    conn.execute("CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, actual_harness TEXT, requires_gh_write INTEGER DEFAULT 0, gh_write_verified TEXT)")
    conn.commit()
    conn.close()

    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps({
        "overrides": {"dev_authority": {"task_allocation": {"implement": {"agent": "codex", "fallback": []}}}},
        "capability_policy": {"not_yet_calibrated": [], "calibration_detail": {}, "note": "", "eligibility": {}},
    }))

    env = {"SYNLYNK_STATE_DB_PATH": db_path}
    result = subprocess.run(
        [sys.executable, "bin/synlynk.py", "capability", "regen", "--policy-path", str(policy_path), "--dry-run"],
        capture_output=True, text=True, env={**__import__("os").environ, **env},
    )
    assert result.returncode == 0, result.stderr
    assert "calibration_detail" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_capability_regen.py -v`
Expected: FAIL — argparse error, `invalid choice: 'regen'`

- [ ] **Step 3: Wire the subcommand**

Read `synlynk/cli.py` around its existing `capability_sub.add_parser("sweep"/"report"/"backfill"/"export-pack", ...)` block first to confirm the exact variable name (`capability_sub`) and indentation, then add immediately after the `export-pack` parser definition:

```python
    regen_parser = capability_sub.add_parser(
        "regen", help="Regenerate policy.json's calibration_detail/not_yet_calibrated/can_gh_write from live data",
    )
    regen_parser.add_argument(
        "--policy-path", default=".synlynk/policy.json", dest="policy_path",
    )
    regen_parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Print the proposed diff without writing policy.json",
    )
```

Then in the `elif args.command == "capability":` dispatch chain, add a new branch alongside the existing `sweep`/`report`/`backfill`/`export-pack` branches:

```python
            elif args.capability_action == "regen":
                from synlynk.capability_regen import cmd_capability_regen
                cmd_capability_regen(policy_path=args.policy_path, dry_run=args.dry_run)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_capability_regen.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py tests/test_cli_capability_regen.py
git commit -m "feat: wire synlynk capability regen into the CLI (Section 3)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 13: Section 3 — semantic-equality and failure-mode tests for regen

**Files:**
- Test: `tests/test_capability_regen.py` (extend)

- [ ] **Step 1: Write the test**

Add to `tests/test_capability_regen.py`:

```python
def test_regen_semantic_equality_of_every_untouched_key(tmp_path, monkeypatch):
    """Every key other than calibration_detail/not_yet_calibrated/note/
    eligibility.*.can_gh_write must compare equal by value before and after,
    even if key order or whitespace differs in the rewritten file."""
    db_path = _make_regen_db(tmp_path)
    policy_path = _make_policy(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    with open(policy_path) as handle:
        before = json.load(handle)
    cmd_capability_regen(policy_path=policy_path)
    with open(policy_path) as handle:
        after = json.load(handle)

    def _strip_regen_fields(policy):
        stripped = json.loads(json.dumps(policy))
        cap = stripped.get("capability_policy", {})
        cap.pop("calibration_detail", None)
        cap.pop("not_yet_calibrated", None)
        cap.pop("note", None)
        for harness_entry in cap.get("eligibility", {}).values():
            harness_entry.pop("can_gh_write", None)
        return stripped

    assert _strip_regen_fields(before) == _strip_regen_fields(after)


def test_regen_locked_db_fails_loudly_not_silently(tmp_path, monkeypatch):
    db_path = _make_regen_db(tmp_path)
    policy_path = _make_policy(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    # Hold an exclusive write lock on the db to simulate contention.
    blocker = sqlite3.connect(db_path, timeout=0.1)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(sqlite3.OperationalError):
            cmd_capability_regen(policy_path=policy_path)
    finally:
        blocker.rollback()
        blocker.close()
```

- [ ] **Step 2: Run test to verify it fails or passes as expected**

Run: `pytest tests/test_capability_regen.py -v -k "semantic_equality or locked_db"`
Expected: `test_regen_semantic_equality_of_every_untouched_key` should already PASS given Task 11's implementation (it only touches the four documented fields). `test_regen_locked_db_fails_loudly_not_silently` should also PASS as-is since `_get_db(read_only=True)` opens the real sqlite file and a genuine `BEGIN EXCLUSIVE` lock from another connection causes a real `OperationalError` on read — if it does not raise, investigate whether `_get_db(read_only=True)`'s WAL-snapshot-to-memory behavior (seen in `synlynk/__init__.py`'s `_connect`) bypasses the lock, and adjust the test to instead corrupt the db file bytes directly (`open(db_path, "wb").write(b"not a db")`) to force a reliable `sqlite3.DatabaseError`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_capability_regen.py
git commit -m "test: semantic-equality and failure-mode coverage for capability regen (Section 3)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 14: Section 1 integration test — widened fallback actually reaches round-robin

**Files:**
- Test: `tests/test_dispatch_section1_integration.py`

- [ ] **Step 1: Write the test**

```python
import json
import sqlite3

from synlynk.dispatch import _hard_availability_filter, _review_collision_filter
from synlynk.routing import LiveQueryRouter


def test_widened_fallback_reaches_round_robin_with_no_router_code_change(tmp_path):
    """Section 1 is a data change (wider fallback) plus new pre-filters --
    LiveQueryRouter itself must need zero changes for a previously fallback:[]
    task_type (e.g. css) to now round-robin across every harness."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE capability_ratings (story_id TEXT, agent TEXT, discipline TEXT, pr_review_cycles REAL)")
    conn.execute("CREATE TABLE cost_entries (agent TEXT, type_id TEXT, total_cost_usd REAL, recorded_at TEXT)")
    conn.execute("CREATE TABLE routing_rotation_state (task_type TEXT PRIMARY KEY, cursor INTEGER NOT NULL DEFAULT 0, updated_at TEXT, exploration_spend_usd TEXT NOT NULL DEFAULT '{}')")
    conn.commit()

    eligible = ["agy", "claude", "codex", "grok", "muse"]  # what Task 4's widened css fallback now yields
    eligible = _hard_availability_filter(eligible, requires_gh_write=False)
    eligible = _review_collision_filter(eligible, "css", implementer_harness=None)

    picks = {LiveQueryRouter().select(eligible, "css", conn) for _ in range(len(eligible))}
    assert picks == set(eligible)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch_section1_integration.py -v`
Expected: FAIL if run before Tasks 4-9 land (import errors / assertion failure); should PASS once this plan's earlier tasks are all committed.

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_dispatch_section1_integration.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_dispatch_section1_integration.py
git commit -m "test: integration coverage for Section 1's widened fallback reaching round-robin

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 15: Full suite run and final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `pytest -q`
Expected: all tests pass, 0 failures (confirm no cross-task regression — in particular re-check `tests/test_dispatch.py` and `tests/test_capability_report.py` for any assumption about `_score`, `_eligible_harnesses_for_task_type`, or `.synlynk/policy.json`'s `task_allocation` fallback shape that this plan's changes might have invalidated)

- [ ] **Step 2: Confirm `.synlynk/policy.json` still validates against whatever schema/lint check the repo runs**

Run: `python3 -c "import json; json.load(open('.synlynk/policy.json'))" && echo "valid JSON"`
Expected: `valid JSON`

- [ ] **Step 3: Re-run `synlynk capability regen --dry-run` against the real live state.db to sanity-check real-world output**

Run: `python3 bin/synlynk.py capability regen --dry-run`
Expected: prints a before/after diff for `calibration_detail`/`not_yet_calibrated`/`note`/`eligibility.*.can_gh_write` without raising; inspect the printed `not_yet_calibrated` list and compare it by eye against the current live `.synlynk/policy.json`'s stale `["grok", "muse"]` value noted in this plan's grounding -- confirm the new computation is at least directionally sane (e.g. codex should show high calibration coverage) before trusting it enough to run for real (without `--dry-run`) in a follow-up PR.

- [ ] **Step 4: Final commit (if any cleanup was needed in Steps 1-3)**

```bash
git status --short
# only commit if Steps 1-3 required a fix; otherwise this task is verification-only
```
