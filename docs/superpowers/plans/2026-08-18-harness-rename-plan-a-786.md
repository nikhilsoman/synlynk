# Harness Rename (Plan A of #786) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename every `agent`-named symbol/table/column/CLI-flag that actually means "harness" (execution backend) to `harness`, while leaving genuine Agent-role symbols (`daemon_jobs.agent_id`, `stories.role`) untouched, per the classification rules in `docs/superpowers/specs/2026-08-18-harness-capability-registry-v2-786-design.md`.

**Architecture:** Rename in dependency order — DB schema first (via the existing `synlynk migrate` path), then the shared constant (`AGENT_CAPABILITY_BASELINES`), then per-file parameter/variable renames grouped by module, then CLI flags (with a one-release deprecation shim), finishing with a full-suite regression run and a grep-zero check for anything missed.

**Tech Stack:** Python 3 stdlib, sqlite3, existing `synlynk` test suite (`pytest`).

---

## Scope correction from the brainstorm estimate

Recon during plan-writing found the actual footprint differs from #786's original estimate in two ways worth flagging before execution starts:
- **CLI flags:** only 4 flags carry harness meaning (`probe --agent`, `cost log --agent`, `credit grant --agent`, `quota --agent`), not 18. The other ~14 are unrelated `--agent-*`-prefixed or incidental matches.
- **`agent_name` as a bare identifier** is far more pervasive than "5 DB columns" suggested — it's the de facto parameter name for "which harness" across `probe.py`, `status.py`, `dispatch.py`, `doctor.py`, `events.py`, `support_engineer.py`, `wizard.py`, `hud.py`, `db.py`, in addition to 3 DB table columns. This plan accounts for the real footprint.

## Revisions from PR #1053 review (Grok + Agy, 2026-08-18)

Two independent non-authoring reviews of this plan found two blocking issues in Task 1, both fixed below:
- **`_DB_SCHEMA` in `synlynk/__init__.py` is a second, independent source of `agent_quotas`/`agent_reservations` DDL**, separate from the re-assert block in `db.py:838-880`. `_migrate_db()` runs `conn.executescript(_DB_SCHEMA)` unconditionally on every call (`db.py:242`) before any other migration logic. Task 1 originally only listed the `db.py` DDL blocks — `synlynk/__init__.py:1005-1036` is now in scope too (Step 3a below).
- **The original `_run_harness_rename_migration()` draft had a data-loss bug**: `harness_records`' rebuild step selected `agent_name` into the new `harness_name` primary key, discarding the table's real, already-populated `harness_name` column (e.g. `'claude-cli'` would be overwritten by `'claude'`). Fixed in Step 3 below — the rebuild now selects the actual `harness_name` column.
- The test in Step 1 also called `db._get_db(str(db_path))`, but the real `_get_db()` (defined in `synlynk/__init__.py:1096`, not `db.py`) takes zero arguments and resolves its path via the `SYNLYNK_STATE_DB_PATH` env var. Fixed via `monkeypatch.setenv`.

## File Structure

| File | Change |
|---|---|
| `synlynk/db.py` | DDL renames (Task 1), constant renames (Task 2 call sites), quota/reservation table + query renames (Task 8) |
| `synlynk/__init__.py` | `_DB_SCHEMA`'s independent `agent_quotas`/`agent_reservations` DDL copy (Task 1, Step 3a) — separate from `db.py`'s re-assert block, also runs unconditionally on every `_migrate_db()` call |
| `synlynk/_constants.py` | `AGENT_CAPABILITY_BASELINES` → `HARNESS_CAPABILITY_BASELINES` (Task 2) |
| `synlynk/capability_sweep.py` | Internal `agent` → `harness` rename (Task 3) |
| `synlynk/probe.py` | `agent_name` → `harness_name` parameter rename (Task 4) |
| `synlynk/dispatch.py` | `agent_name` param rename in preflight functions + quota/reservation call sites (Task 5, Task 8) |
| `synlynk/status.py`, `synlynk/doctor.py`, `synlynk/events.py`, `synlynk/support_engineer.py`, `synlynk/hud.py`, `synlynk/wizard.py`, `synlynk/__init__.py` | `agent_name` query/variable rename at `harness_records`/`harness_verb_map`/`harness_version_history` call sites (Task 6) |
| `synlynk/cli.py` | 4 flag renames with deprecation shim (Task 7) |
| `synlynk/costs.py`, `synlynk/jobs.py`, `synlynk/quota.py`, `synlynk/scheduler.py`, `synlynk/tpm_hooks.py` | `agent_quotas`/`agent_reservations` call-site rename (Task 8) |
| `tests/*.py` | Updated in lockstep with each task, not as a separate pass |

---

### Task 1: DB schema rename

**Files:**
- Modify: `synlynk/db.py:376-419` (harness_records, harness_verb_map, harness_version_history DDL)
- Modify: `synlynk/db.py:838-880` (agent_quotas, agent_reservations re-assert DDL)
- Modify: `synlynk/__init__.py:1005-1036` (`_DB_SCHEMA`'s independent copy of the `agent_quotas`/`agent_reservations` DDL — this is a *separate* CREATE TABLE from the one in `db.py`, executed unconditionally by `conn.executescript(_DB_SCHEMA)` at `db.py:242` on every `_migrate_db()` call, so it must be renamed too or fresh installs will still see the old names)
- Test: `tests/test_db_migration.py` (create if it does not already cover schema migrations — check first with `grep -l "def test.*migrat" tests/*.py`)

- [ ] **Step 1: Write the failing migration test**

```python
def test_harness_rename_migration_preserves_data(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import db

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    # Simulate a pre-rename DB: old table/column names.
    # NOTE: harness_records already carries BOTH agent_name (PK) and a
    # separately-populated harness_name column in the real schema (they can
    # diverge, e.g. agent_name='claude' vs harness_name='claude-cli') — the
    # migration must preserve the real harness_name value, not derive it
    # from agent_name.
    conn.execute("""
        CREATE TABLE harness_records (
            agent_name TEXT PRIMARY KEY,
            harness_name TEXT NOT NULL,
            installed_version TEXT NOT NULL DEFAULT 'unknown',
            compliance_status TEXT NOT NULL DEFAULT 'unknown',
            active_contract TEXT NOT NULL DEFAULT '{}',
            active_flags TEXT NOT NULL DEFAULT '{}',
            last_probe_at TEXT,
            capability_hash TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "INSERT INTO harness_records VALUES ('claude', 'claude-cli', '1.2.0', 'ok', '{}', '{}', '2026-08-18', 'abc')"
    )
    conn.execute("""
        CREATE TABLE agent_quotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL, model TEXT NOT NULL DEFAULT 'unknown',
            quota_type TEXT NOT NULL, unit TEXT NOT NULL DEFAULT 'tokens',
            limit_tokens INTEGER NOT NULL, used_tokens INTEGER NOT NULL DEFAULT 0,
            reset_at TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent, model, quota_type, unit)
        )
    """)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, limit_tokens) VALUES ('codex', 'gpt-5', '5h', 100000)"
    )
    conn.commit()
    conn.close()

    # Run the migration. _get_db() takes no path argument — it resolves the
    # DB location from SYNLYNK_STATE_DB_PATH, so point that at our tmp DB.
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    conn = db._get_db()
    db._run_harness_rename_migration(conn)
    conn.commit()

    cols = {row[1] for row in conn.execute("PRAGMA table_info(harness_records)")}
    assert "harness_name" in cols
    assert "agent_name" not in cols
    row = conn.execute("SELECT harness_name, installed_version FROM harness_records WHERE harness_name='claude-cli'").fetchone()
    assert row == ("claude-cli", "1.2.0"), "must preserve the real harness_name value, not overwrite it with agent_name"

    quota_cols = {row[1] for row in conn.execute("PRAGMA table_info(harness_quotas)")}
    assert "harness" in quota_cols
    assert "agent" not in quota_cols
    qrow = conn.execute("SELECT harness, model, limit_tokens FROM harness_quotas WHERE harness='codex'").fetchone()
    assert qrow == ("codex", "gpt-5", 100000)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db_migration.py::test_harness_rename_migration_preserves_data -v`
Expected: `FAIL` — `AttributeError: module 'synlynk.db' has no attribute '_run_harness_rename_migration'`

- [ ] **Step 3: Implement `_run_harness_rename_migration()` in `synlynk/db.py`**

Add this function near the other migration helpers (alongside the existing `ALTER TABLE cost_entries RENAME TO cost_entries_pre_provenance` pattern at `db.py:679`):

```python
def _run_harness_rename_migration(conn) -> None:
    """One-time rename of agent-named harness symbols to harness-named (#786 Plan A)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(harness_records)")}
    if "agent_name" in cols and "harness_name" in cols:
        # harness_records already carries BOTH agent_name (the old PK) and a
        # separately-populated harness_name data column — they can diverge
        # (e.g. agent_name='claude' vs harness_name='claude-cli'). Promote
        # the REAL harness_name column to the new PK; do not derive it from
        # agent_name, or existing harness_name data is silently lost.
        conn.executescript("""
            CREATE TABLE harness_records_new (
                harness_name TEXT PRIMARY KEY,
                installed_version TEXT NOT NULL DEFAULT 'unknown',
                compliance_status TEXT NOT NULL DEFAULT 'unknown',
                active_contract TEXT NOT NULL DEFAULT '{}',
                active_flags TEXT NOT NULL DEFAULT '{}',
                last_probe_at TEXT,
                capability_hash TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO harness_records_new
                SELECT harness_name, installed_version, compliance_status, active_contract,
                       active_flags, last_probe_at, capability_hash FROM harness_records;
            DROP TABLE harness_records;
            ALTER TABLE harness_records_new RENAME TO harness_records;
        """)
    for tbl, old_col, new_col in [
        ("harness_verb_map", "agent_name", "harness_name"),
        ("harness_verb_map", "agent_command", "harness_command"),
        ("harness_version_history", "agent_name", "harness_name"),
    ]:
        tcols = {row[1] for row in conn.execute(f"PRAGMA table_info({tbl})")}
        if old_col in tcols and new_col not in tcols:
            conn.execute(f"ALTER TABLE {tbl} RENAME COLUMN {old_col} TO {new_col}")
    qcols = {row[1] for row in conn.execute("PRAGMA table_info(agent_quotas)")} if _table_exists(conn, "agent_quotas") else set()
    if qcols and "agent" in qcols:
        conn.execute("ALTER TABLE agent_quotas RENAME COLUMN agent TO harness")
        conn.execute("ALTER TABLE agent_quotas RENAME TO harness_quotas")
        conn.execute("DROP INDEX IF EXISTS idx_agent_quotas_agent")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_harness_quotas_harness ON harness_quotas(harness)")
    if _table_exists(conn, "agent_reservations"):
        conn.execute("ALTER TABLE agent_reservations RENAME TO harness_reservations")
        conn.execute("DROP INDEX IF EXISTS idx_agent_reservations_harness")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_harness_reservations_harness ON harness_reservations(harness, status)"
        )


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None
```

Then update every `CREATE TABLE IF NOT EXISTS` in `db.py:376-419` and `db.py:838-880` to use the new names directly (`harness_name`, `harness_command`, `harness_quotas`/`harness`, `harness_reservations`) so fresh installs never see the old names at all — the migration function above only fires for pre-existing DBs where `PRAGMA table_info` still shows the old column/table. Call `_run_harness_rename_migration(conn)` from wherever the existing `ALTER TABLE cost_entries RENAME TO ...` migration is invoked (same migration-runner call site, `db.py:679`'s caller — i.e. inside `_migrate_db()` in `db.py`, which runs on every connection open, so the rename stays idempotent).

- [ ] **Step 3a: Rename `_DB_SCHEMA`'s independent `agent_quotas`/`agent_reservations` DDL in `synlynk/__init__.py`**

`_migrate_db()` (`db.py:239-242`) runs `conn.executescript(_DB_SCHEMA)` *before* the rest of migration logic, on every single call. `_DB_SCHEMA` is defined in `synlynk/__init__.py:833` and contains its own `CREATE TABLE IF NOT EXISTS agent_quotas` (line 1005) and `CREATE TABLE IF NOT EXISTS agent_reservations` (line 1025) — a second, independent copy of the DDL from `db.py:838-880`, not a duplicate of the same statement. `agent_reservations` here already uses `harness` as its column name (only the table name is stale); `agent_quotas` uses `agent` for both the column and the table name and needs both renamed. In `synlynk/__init__.py`:

```python
CREATE TABLE IF NOT EXISTS harness_quotas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    harness      TEXT NOT NULL,
    model        TEXT NOT NULL DEFAULT 'unknown',
    quota_type   TEXT NOT NULL,
    unit         TEXT NOT NULL DEFAULT 'tokens',
    limit_tokens INTEGER NOT NULL,
    used_tokens  INTEGER NOT NULL DEFAULT 0,
    reset_at     TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(harness, model, quota_type, unit)
);
CREATE INDEX IF NOT EXISTS idx_harness_quotas_harness ON harness_quotas(harness);

CREATE TABLE IF NOT EXISTS harness_reservations (
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
CREATE INDEX IF NOT EXISTS idx_harness_reservations_harness ON harness_reservations(harness, status);
```

Because `_DB_SCHEMA` executes unconditionally before `_run_harness_rename_migration()` runs later in the same `_migrate_db()` call, a genuinely fresh install would otherwise create `agent_quotas` (old name) first and rely on the rename migration to immediately convert it — functionally correct but confusing and easy to regress later. Renaming the source DDL directly means fresh installs create the right table the first time, and `_run_harness_rename_migration()` remains solely responsible for converting *pre-existing* databases.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db_migration.py::test_harness_rename_migration_preserves_data -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py synlynk/__init__.py tests/test_db_migration.py
git commit -m "feat(db): rename agent-named harness schema to harness (#786 Plan A, 1/8)"
```

---

### Task 2: Rename `AGENT_CAPABILITY_BASELINES` → `HARNESS_CAPABILITY_BASELINES`

**Files:**
- Modify: `synlynk/_constants.py:44`
- Modify (import/usage sites): `synlynk/__init__.py`, `synlynk/doctor.py`, `synlynk/db.py`, `synlynk/cli.py`, `synlynk/capability_sweep.py`, `synlynk/probe.py`, `synlynk/dispatch.py`, `synlynk/instructions.py`, `synlynk/jobs.py`, `synlynk/fleet.py`, `synlynk/platform_ops.py`, `synlynk/quota.py`, `synlynk/support_engineer.py`, `synlynk/status.py`, `synlynk/team.py`
- Test: any test file importing `AGENT_CAPABILITY_BASELINES` directly (`grep -rl AGENT_CAPABILITY_BASELINES tests/`)

- [ ] **Step 1: Confirm the full call-site list**

Run: `grep -rln "AGENT_CAPABILITY_BASELINES" synlynk/*.py tests/*.py`
Expected: the 15 `synlynk/*.py` files listed above plus `_constants.py` itself, plus whatever `tests/*.py` files the grep surfaces.

- [ ] **Step 2: Rename the definition**

In `synlynk/_constants.py:44`, change:
```python
AGENT_CAPABILITY_BASELINES = {
```
to:
```python
HARNESS_CAPABILITY_BASELINES = {
```

- [ ] **Step 3: Rename every call site**

Run this from the repo root — a plain identifier substitution is safe here because `AGENT_CAPABILITY_BASELINES` is a unique, unambiguous name with no substring collisions in the codebase (verified by the grep in Step 1):

```bash
grep -rl "AGENT_CAPABILITY_BASELINES" synlynk/*.py tests/*.py | \
  xargs sed -i '' 's/AGENT_CAPABILITY_BASELINES/HARNESS_CAPABILITY_BASELINES/g'
```

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/ -x -q`
Expected: `PASS` (no `NameError`/`ImportError` for the old name anywhere)

- [ ] **Step 5: Verify zero remaining references**

Run: `grep -rn "AGENT_CAPABILITY_BASELINES" synlynk/ tests/`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: rename AGENT_CAPABILITY_BASELINES to HARNESS_CAPABILITY_BASELINES (#786 Plan A, 2/8)"
```

---

### Task 3: `capability_sweep.py` internal rename

**Files:**
- Modify: `synlynk/capability_sweep.py` (33 `agent`-token occurrences: variable names, parameter names, docstring references — this file has no DB/CLI surface, purely internal)
- Test: `tests/test_capability_sweep.py`

- [ ] **Step 1: List every occurrence for manual review (not blind sed — local variable names can collide with real Agent-role concepts inside a single file)**

Run: `grep -n "\bagent\b" synlynk/capability_sweep.py`

- [ ] **Step 2: Rename each occurrence to `harness`**

For every match from Step 1 where the term refers to "which CLI/model is being calibrated" (the entire file — `capability_sweep.py` never references charter roles), rename `agent` → `harness` in that line: `_discover_models()`'s internal loop variable (`for agent, baseline in AGENT_CAPABILITY_BASELINES.items()` → `for harness, baseline in HARNESS_CAPABILITY_BASELINES.items()`, plus the `discovered[agent] = models` assignment), `_fallback_models_for_agent(agent: str)` → `_fallback_models_for_harness(harness: str)` (its `agent_model_prefixes` local dict → `harness_model_prefixes`), `_estimate_sweep_cost()`'s `for agent, models in discovered.items()` loop and its `_model_rate_for_version(model, agent=agent)` kwarg (this kwarg name belongs to `synlynk/costs.py`'s `_model_rate_for_version` — check whether that function's `agent=` kwarg is in this task's scope or Task 6's cost.py scope via `grep -n "def _model_rate_for_version" synlynk/costs.py`; if the kwarg itself isn't renamed yet, keep passing `agent=harness` at this call site until costs.py is renamed), `cmd_capability_sweep()`'s log line (`"{len(discovered)} agents"` → `"{len(discovered)} harnesses"`), and `_pick_verifier_agent(executor_agent, available_agents)` → `_pick_verifier_harness(executor_harness, available_harnesses)` including its `candidates = [agent for agent in available_agents if agent != executor_agent]` body and its `ValueError` message text. Apply the same rename to `_run_sweep()`'s `agent`/`all_agents`/`verifier_agent` loop variables (confirmed at line ~183).

- [ ] **Step 3: Run this file's test suite**

Run: `pytest tests/test_capability_sweep.py -v`
Expected: `PASS` after updating any test-side references to renamed function names (`_pick_verifier_agent` → `_pick_verifier_harness`, etc. — `grep -n "_pick_verifier_agent\|_discover_models" tests/test_capability_sweep.py` to find them)

- [ ] **Step 4: Commit**

```bash
git add synlynk/capability_sweep.py tests/test_capability_sweep.py
git commit -m "feat: rename agent to harness throughout capability_sweep.py (#786 Plan A, 3/8)"
```

---

### Task 4: `probe.py` — `agent_name` → `harness_name`

**Files:**
- Modify: `synlynk/probe.py` (every `agent_name` parameter/variable: `_baseline_schema_issues`, `_run_tc0`, `_scan_command_palette`, `_build_fence_body_from_record`, `_probe_agent`, `_run_tc1`, `_run_tc2`, `_run_tc4`, `_run_tc6`, `_repair_sops_only`, `_probe_model_version`, plus all SQL query params against `harness_records`/`harness_version_history` renamed by Task 1)
- Test: `tests/test_probe.py`

- [ ] **Step 1: Rename every `agent_name` parameter and local variable to `harness_name`**

Run: `grep -c "agent_name" synlynk/probe.py` to get the exact count, then apply the rename. Since `agent_name` in this file is unambiguous (every occurrence means "which harness CLI," confirmed by Task 1's DDL rename already retiring the DB-side name), a scoped sed is safe:

```bash
sed -i '' 's/\bagent_name\b/harness_name/g' synlynk/probe.py
```

Leave `agent` (without `_name`) occurrences that refer to the CLI-facing docstring language ("Agent 'X' auth preflight failed") as-is for now — those are handled in Task 5 alongside `dispatch.py`'s matching preflight functions, since the same error-message convention is shared between the two files.

- [ ] **Step 2: Update the SQL queries in this file to match Task 1's renamed columns**

Every `WHERE agent_name=?` against `harness_records`/`harness_version_history` becomes `WHERE harness_name=?` (already covered by Step 1's sed, since the Python variable and the SQL placeholder text share the literal string `agent_name`). Confirm via: `grep -n "harness_name=?" synlynk/probe.py` — should show all the query sites from the earlier recon (lines ~512, 536, 551-563, 577-581, 757).

- [ ] **Step 3: Run this file's test suite**

Run: `pytest tests/test_probe.py -v`
Expected: `PASS` after updating any test-side `agent_name=` kwargs (`grep -n "agent_name" tests/test_probe.py`)

- [ ] **Step 4: Commit**

```bash
git add synlynk/probe.py tests/test_probe.py
git commit -m "feat: rename agent_name to harness_name in probe.py (#786 Plan A, 4/8)"
```

---

### Task 5: `dispatch.py` preflight functions

**Files:**
- Modify: `synlynk/dispatch.py` (`_preflight_auth_check`, `_known_headless_permission_denial`, `_preflight_headless_permission_check`, and the TC-2 flag-check block using `agent_name` — lines ~1336-1990, plus call sites at ~2306/2315/2321)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Rename `agent_name` parameters to `harness_name` in the four preflight functions**

```bash
sed -n '1336,1990p' synlynk/dispatch.py | grep -c "agent_name"
```

Then apply: `sed -i '' '1336,1990s/\bagent_name\b/harness_name/g' synlynk/dispatch.py`

Update the error-message strings in the same range from `f"Agent '{harness_name}' auth preflight failed..."` to `f"Harness '{harness_name}' auth preflight failed..."` (the printed text, not just the variable) — these are operator-facing diagnostic messages and should say what they mean now that the variable itself is renamed.

- [ ] **Step 2: Rename the call sites**

At `dispatch.py:2306`, `2315`, `2321` (`preflight_fn(agent_name=agent, ...)` etc.), rename the keyword argument to match: `preflight_fn(harness_name=agent, ...)`. Leave the local variable `agent` itself alone here — it's the harness identifier passed down from `_best_agent_for_story()`'s existing return value and is handled in Task 8/Plan A's later files, not this task.

- [ ] **Step 3: Run this file's test suite**

Run: `pytest tests/test_dispatch.py -v`
Expected: `PASS` after updating test-side kwargs referencing the renamed preflight functions

- [ ] **Step 4: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: rename agent_name to harness_name in dispatch.py preflight checks (#786 Plan A, 5/8)"
```

---

### Task 6: Remaining `agent_name` query/variable sites

**Files:**
- Modify: `synlynk/status.py`, `synlynk/doctor.py`, `synlynk/events.py`, `synlynk/support_engineer.py`, `synlynk/hud.py`, `synlynk/wizard.py`, `synlynk/__init__.py` (all `harness_records`/`harness_verb_map`/`harness_version_history`/`cycle_capability`/`harness_status` query sites using `agent_name`)
- Test: `tests/test_status.py`, `tests/test_doctor_identity_roles.py`, `tests/test_events.py`, `tests/test_hud_buffer.py`, `tests/test_hud_cycles.py`, `tests/test_hud_errors.py`, `tests/test_hud_integration.py`, `tests/test_hud_live.py`, `tests/test_hud_renderer.py`, `tests/test_hud_snapshot.py`, `tests/test_wizard.py`, `tests/test_synlynk.py` (real filenames per repo, corrected from `test_doctor.py`/`test_hud.py` in the original draft — `synlynk/support_engineer.py` has no dedicated test file; its `agent_name` sites are covered indirectly via `tests/test_cost_ledger.py`, run that too if touching `support_engineer.py`)

- [ ] **Step 1: Per file, confirm every `agent_name` occurrence is DB-column-facing (not a genuine Agent-role reference)**

Run per file: `grep -n "agent_name" synlynk/status.py synlynk/doctor.py synlynk/events.py synlynk/support_engineer.py synlynk/hud.py synlynk/wizard.py`

Every occurrence found in the earlier recon in these files is either a SQL column reference against the now-renamed `harness_records`/`harness_verb_map`/`harness_version_history`/`cycle_capability` tables, or a plain "which harness" function parameter (`_get_avg_tool_calls`, `estimate_dispatch_tokens`, `_compute_cycle_capability`, `pending_events`, `advance_checkpoint`, `scan_local_events`). None of these files reference charter roles — safe to rename all matches.

- [ ] **Step 2: Apply the rename per file**

```bash
for f in synlynk/status.py synlynk/doctor.py synlynk/events.py synlynk/support_engineer.py synlynk/hud.py synlynk/wizard.py; do
  sed -i '' 's/\bagent_name\b/harness_name/g' "$f"
done
```

For `synlynk/__init__.py`, the `agent_name` occurrences are mixed with genuine CLI-onboarding language (`cmd_agent_add`, `agent_slots`, `.agents/<name>.json` directory, `workgroup_agents`) that stays as `agent_*` naming (user-facing onboarding concepts, not this task's scope — `cmd_agent_add` literally means "add a harness to the roster," but renaming CLI command names and on-disk directory conventions is riskier/higher-blast-radius than internal variable renames and is deferred to the dispatched full-sweep audit from the spec's classification process, not hand-applied here). Apply the rename only to the specific `agent_name` SQL-query and harness-records-lookup sites identified in this session's recon: `__init__.py:2238-2239, 2241, 2243-2244, 3309-3452` (the `_probe_agent`/housekeeping loop and the `harness_records` display table) — leave `cmd_agent_add`/`cmd_agent_configure`/`agent_slots`/`.agents/` untouched in this task:

```bash
sed -i '' '2230,2270s/\bagent_name\b/harness_name/g; 3300,3460s/\bagent_name\b/harness_name/g' synlynk/__init__.py
```

- [ ] **Step 3: Run the affected test files**

Run: `pytest tests/test_status.py tests/test_doctor_identity_roles.py tests/test_events.py tests/test_hud_buffer.py tests/test_hud_cycles.py tests/test_hud_errors.py tests/test_hud_integration.py tests/test_hud_live.py tests/test_hud_renderer.py tests/test_hud_snapshot.py tests/test_wizard.py tests/test_synlynk.py -v`
Expected: `PASS` after updating any test-side `agent_name=` references in the same line ranges

- [ ] **Step 4: Commit**

```bash
git add synlynk/status.py synlynk/doctor.py synlynk/events.py synlynk/support_engineer.py synlynk/hud.py synlynk/wizard.py synlynk/__init__.py tests/
git commit -m "feat: rename remaining agent_name query sites to harness_name (#786 Plan A, 6/8)"
```

---

### Task 7: CLI flag rename with deprecation shim

**Files:**
- Modify: `synlynk/cli.py:338-339` (`probe --agent`), `:811` (`cost log --agent`), `:832` (`credit grant --agent`), `:842-846` (`quota --agent`)
- Test: `tests/test_cli_parser.py`

- [ ] **Step 1: Write the failing deprecation test**

```python
def test_probe_agent_flag_deprecated_alias(capsys, monkeypatch):
    import sys
    from synlynk import cli
    monkeypatch.setattr(sys, "argv", ["synlynk", "probe", "--agent", "codex"])
    args = cli.build_parser().parse_args(["probe", "--agent", "codex"])
    assert args.harness == "codex"  # new dest
    # old flag still resolves, with a warning
    captured = capsys.readouterr()


def test_probe_harness_flag_new(monkeypatch):
    from synlynk import cli
    args = cli.build_parser().parse_args(["probe", "--harness", "codex"])
    assert args.harness == "codex"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_cli_parser.py -k "agent_flag_deprecated or harness_flag_new" -v`
Expected: `FAIL` — `AttributeError: 'Namespace' object has no attribute 'harness'`

- [ ] **Step 3: Add the new flag + deprecated alias for each of the 4 sites**

`synlynk/cli.py:338-339`, change:
```python
    probe_parser.add_argument("--agent", default=None,
                              help="Probe a single agent instead of all known agents")
```
to:
```python
    probe_parser.add_argument("--harness", "--agent", default=None, dest="harness",
                              help="Probe a single harness instead of all known harnesses "
                                   "(--agent is deprecated, use --harness)")
```

`synlynk/cli.py:811`, change:
```python
    cost_log_parser.add_argument("--agent", required=True)
```
to:
```python
    cost_log_parser.add_argument("--harness", "--agent", required=True, dest="harness")
```

`synlynk/cli.py:832`, change:
```python
    grant_parser.add_argument("--agent", required=True, help="Agent name (e.g. agy, codex)")
```
to:
```python
    grant_parser.add_argument("--harness", "--agent", required=True, dest="harness",
                              help="Harness name (e.g. agy, codex) (--agent is deprecated, use --harness)")
```

`synlynk/cli.py:842-846`, change:
```python
    quota_parser.add_argument(
        "--agent",
        default=None,
        help="Filter to a single agent (claude, agy, codex, grok, local)",
    )
```
to:
```python
    quota_parser.add_argument(
        "--harness", "--agent",
        default=None,
        dest="harness",
        help="Filter to a single harness (claude, agy, codex, grok, local) (--agent is deprecated, use --harness)",
    )
```

argparse resolves either spelling to the same `dest="harness"` automatically — no separate deprecation-warning code path is needed at parse time. Add the runtime warning where each `args.harness` (formerly `args.agent`) is first consumed, e.g. in the `probe` command handler:
```python
    if "--agent" in sys.argv and "--harness" not in sys.argv:
        print("  warning: --agent is deprecated, use --harness instead", file=sys.stderr)
```
Apply the same 2-line check at the start of the `cost log`, `credit grant`, and `quota` handlers (find them via `grep -n "def cmd_probe\|def cmd_cost_log\|def cmd_credit_grant\|def cmd_quota" synlynk/*.py`).

- [ ] **Step 4: Update every downstream consumer of `args.agent` for these 4 subcommands to `args.harness`**

Run: `grep -rn "args\.agent\b" synlynk/*.py` and update only the call sites belonging to `cmd_probe`, `cmd_cost_log`/`cost_log`, `cmd_credit_grant`, `cmd_quota` handler bodies (identified by tracing each handler function found in Step 3's grep).

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cli_parser.py -k "agent_flag_deprecated or harness_flag_new" -v`
Expected: `PASS`

- [ ] **Step 6: Run the full CLI test suite**

Run: `pytest tests/test_cli_parser.py -v`
Expected: `PASS`

- [ ] **Step 7: Commit**

```bash
git add synlynk/cli.py synlynk/*.py tests/test_cli_parser.py
git commit -m "feat(cli): rename --agent to --harness on probe/cost log/credit grant/quota, deprecate old flag (#786 Plan A, 7/8)"
```

---

### Task 8: `agent_quotas`/`agent_reservations` Python call-site rename

**Files:**
- Modify: `synlynk/costs.py`, `synlynk/jobs.py`, `synlynk/quota.py`, `synlynk/scheduler.py`, `synlynk/tpm_hooks.py`, `synlynk/dispatch.py`, `synlynk/__init__.py`
- Test: `tests/test_agent_quota_tracking.py`, `tests/test_quota_reservation_integration.py`, `tests/test_sentinel_quota_exhaustion.py`, `tests/test_fleet_scheduler.py`, `tests/test_cost_ledger.py`, `tests/test_tpm_hooks.py` (real filenames per repo, corrected from `test_quota.py`/`test_scheduler.py`/`test_costs.py` in the original draft — no files with those exact names exist)

- [ ] **Step 1: Confirm every call site**

Run: `grep -n "agent_quotas\|agent_reservations" synlynk/costs.py synlynk/jobs.py synlynk/quota.py synlynk/scheduler.py synlynk/tpm_hooks.py synlynk/dispatch.py synlynk/__init__.py`

- [ ] **Step 2: Rename table references and the `agent` column reference to match Task 1's renamed schema**

```bash
for f in synlynk/costs.py synlynk/jobs.py synlynk/quota.py synlynk/scheduler.py synlynk/tpm_hooks.py synlynk/dispatch.py synlynk/__init__.py; do
  sed -i '' 's/\bagent_quotas\b/harness_quotas/g; s/\bagent_reservations\b/harness_reservations/g' "$f"
done
```

For each file, additionally check whether the SQL in that file references the `agent` column by name (e.g. `WHERE agent=?` against the old `agent_quotas` table) — those need the column reference renamed to `harness` too:

Run: `grep -n "WHERE agent=\|SET agent=\|(agent," synlynk/costs.py synlynk/jobs.py synlynk/quota.py synlynk/scheduler.py synlynk/tpm_hooks.py synlynk/dispatch.py`

For each match, rename `agent` → `harness` in that specific SQL fragment only (not a blind file-wide sed, since `agent` alone is a much more ambiguous token than `agent_quotas`/`agent_name` — some of these files may also reference genuine Agent-role concepts elsewhere).

- [ ] **Step 3: Run the affected test files**

Run: `pytest tests/test_agent_quota_tracking.py tests/test_quota_reservation_integration.py tests/test_sentinel_quota_exhaustion.py tests/test_fleet_scheduler.py tests/test_cost_ledger.py tests/test_tpm_hooks.py -v`
Expected: `PASS` after updating test-side table/column references

- [ ] **Step 4: Commit**

```bash
git add synlynk/costs.py synlynk/jobs.py synlynk/quota.py synlynk/scheduler.py synlynk/tpm_hooks.py synlynk/dispatch.py synlynk/__init__.py tests/
git commit -m "feat: rename agent_quotas/agent_reservations call sites to harness_quotas/harness_reservations (#786 Plan A, 8/8)"
```

---

### Task 9: KEEP-list regression guard

**Files:**
- Test: `tests/test_agent_role_columns_preserved.py` (new)

- [ ] **Step 1: Write the regression test that guards the two columns this rename must never touch**

```python
def test_daemon_jobs_agent_id_column_unchanged():
    """Guards against #786 Plan A accidentally renaming the genuine Agent-role
    identifier introduced by PR #1003/#1030 (Agent-roles-charters Phase 1)."""
    import subprocess
    result = subprocess.run(
        ["grep", "-n", "agent_id", "synlynk/db.py", "synlynk/cli.py", "synlynk/dispatch.py"],
        capture_output=True, text=True,
    )
    assert "agent_id" in result.stdout, "daemon_jobs.agent_id must remain named agent_id"


def test_stories_role_column_unchanged():
    import subprocess
    result = subprocess.run(
        ["grep", "-n", "stories.role\\|role TEXT", "synlynk/db.py"],
        capture_output=True, text=True,
    )
    assert result.stdout.strip() != "", "stories.role must remain named role, not agent"
```

- [ ] **Step 2: Run to verify it passes (it should already pass — this is a guard, not new functionality)**

Run: `pytest tests/test_agent_role_columns_preserved.py -v`
Expected: `PASS`

- [ ] **Step 3: Commit**

```bash
git add tests/test_agent_role_columns_preserved.py
git commit -m "test: add regression guard for daemon_jobs.agent_id and stories.role (#786 Plan A)"
```

---

### Task 10: Full-suite verification + grep-zero check

**Files:** none modified — verification only

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -q`
Expected: `PASS`, same or higher test count than before Task 1 started

- [ ] **Step 2: Grep-zero check for missed renames**

Run: `grep -rn "AGENT_CAPABILITY_BASELINES\|agent_quotas\|agent_reservations" synlynk/ tests/`
Expected: no output

Run: `grep -rn "\bagent_name\b" synlynk/*.py | grep -v "cmd_agent_add\|cmd_agent_configure\|agent_slots\|\.agents/"`
Expected: no output (any remaining `agent_name` hits belong to the deliberately-deferred CLI-onboarding surface from Task 6 Step 2, or are new false positives to investigate)

- [ ] **Step 3: Confirm the KEEP-list is intact**

Run: `grep -n "agent_id" synlynk/db.py | grep daemon_jobs`
Expected: `daemon_jobs.agent_id` still present, unchanged

- [ ] **Step 4: Commit the verification as a no-op checkpoint (only if any stragglers were fixed in Steps 1-3; otherwise skip commit)**

If Step 2's grep found stragglers, fix them, re-run Steps 1-2, then:
```bash
git add -A
git commit -m "fix: address remaining agent->harness rename stragglers (#786 Plan A verification)"
```

---

## Out of scope for this plan (per spec)

- The dispatched-audit sweep of the remaining ~2,000 occurrences across 331 doc files and the `cmd_agent_add`/`cmd_agent_configure`/`agent_slots`/`.agents/` CLI-onboarding surface in `__init__.py` — tracked as a follow-up dispatched task per the spec's audit process, not itemized here since it's a large, mechanically-repetitive doc/naming sweep rather than logic requiring TDD-style verification.
- Plan B (capability registry v2) — separate plan, depends on this plan landing first.
