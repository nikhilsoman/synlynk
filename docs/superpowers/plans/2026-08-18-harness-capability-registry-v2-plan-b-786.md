# Capability Registry v2 (Plan B of #786) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Prerequisite: Plan A (`docs/superpowers/plans/2026-08-18-harness-rename-plan-a-786.md`) must be merged first** — this plan builds new tables/functions on the renamed `harness_*` vocabulary and would create fresh conflation if run first.

**Goal:** Track the live model roster and evolving tools/skills/flags per harness, auto-calibrate newly-discovered models against a difficulty-graded per-charter-role task pool, and bias dispatch routing to explore new models instead of starving them via the existing cold-start `None` return.

**Architecture:** Four new `state.db` tables (`harness_models`, `harness_modes`, `capability_calibration_tasks`, `capability_calibration_results`); `synlynk probe` diffs discovered models against `harness_models` and auto-queues a sweep through the existing `capability_sweep.py` machinery; a new Stage 0 in `_best_agent_for_story()` (`synlynk/jobs.py:1056`) applies a bounded explore bonus for thin-data active models ahead of the existing Stage 1-3 pipeline.

**Tech Stack:** Python 3 stdlib, sqlite3, existing `synlynk` test suite (`pytest`).

## Revisions from PR #1053 review (Grok + Agy, 2026-08-18)

Two independent non-authoring reviews of this plan found three blocking issues, fixed below:
- **`db._get_db(str(path))` doesn't exist.** The real `_get_db()` (defined in `synlynk/__init__.py:1096`, not `db.py`) takes zero arguments and resolves its path via the `SYNLYNK_STATE_DB_PATH` env var. Every test snippet in Tasks 1-4 that called `db._get_db(str(tmp_path / "state.db"))` is fixed below to use `monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db")); conn = db._get_db()` instead.
- **Task 3's `dispatch_harness()` and `_execute_calibration_task()` were invented, not real.** `synlynk/capability_sweep.py` already has `_dispatch_calibration_task()` (lines 120-128) which calls the real `dispatch_agent()`, plus `_verify_calibration_result()` (lines 130-156) for scoring. Task 3 Step 7 is rewritten below to reuse this existing pair instead of introducing a parallel dispatch path.
- **Task 4's Stage 0 explore bonus had a cold-start bug that made it a no-op for its own target case.** `_apply_stage0_explore_bonus()` only re-scores models already present in `candidates`, but `candidates` comes from `_capability_candidates_for_story()`, which reads the `capability_scores` VIEW — a newly-discovered model with zero calibration rows has no `capability_scores` row and therefore never appears in `candidates` in the first place. The bonus could never fire for the exact cold-start models it exists to surface. Fixed below by having Stage 0 separately query `harness_models` for thin/zero-data active models matching the story's discipline and inject them as candidates (at a bounded baseline score) before applying the bonus, rather than only re-scoring what Stage 1-3 already found.

## File Structure

| File | Change |
|---|---|
| `synlynk/db.py` | 4 new `CREATE TABLE` blocks (Task 1) |
| `synlynk/probe.py` | model-diff detection + auto-queue call (Task 2) |
| `synlynk/capability_sweep.py` | extend `_run_sweep()` to accept a task pool instead of the fixed 3-skill template; add `cmd_capability_sweep_for_harness_model()` entry point for auto-triggered single-model sweeps (Task 3) |
| `synlynk/jobs.py` | Stage 0 explore-bonus in `_best_agent_for_story()` (Task 4) |
| `tests/*.py` | Updated alongside each task |

---

### Task 1: New registry tables

**Files:**
- Modify: `synlynk/db.py` (add alongside the `harness_*` DDL block from Plan A Task 1, i.e. immediately after the renamed `harness_version_history` table)
- Test: `tests/test_db_migration.py`

- [ ] **Step 1: Write the failing test**

```python
def test_registry_v2_tables_exist(tmp_path, monkeypatch):
    from synlynk import db
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    for tbl in (
        "harness_models", "harness_modes",
        "capability_calibration_tasks", "capability_calibration_results",
    ):
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        assert row is not None, f"{tbl} not created"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db_migration.py::test_registry_v2_tables_exist -v`
Expected: `FAIL` — `AssertionError: harness_models not created`

- [ ] **Step 3: Add the DDL**

In `synlynk/db.py`, in the same `conn.executescript("""...""")` block as the `harness_*` tables (immediately after `harness_version_history`'s closing `);`), add:

```sql
        CREATE TABLE IF NOT EXISTS harness_models (
            harness_name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            superseded_by TEXT,
            discovery_source TEXT NOT NULL DEFAULT 'curated',
            PRIMARY KEY (harness_name, model_id)
        );

        CREATE TABLE IF NOT EXISTS harness_modes (
            harness_name TEXT NOT NULL,
            cli_version_range TEXT NOT NULL,
            mode_type TEXT NOT NULL,
            mode_name TEXT NOT NULL,
            shape TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (harness_name, cli_version_range, mode_type, mode_name)
        );

        CREATE TABLE IF NOT EXISTS capability_calibration_tasks (
            task_id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            skill TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            prompt_template TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS capability_calibration_results (
            result_id TEXT PRIMARY KEY,
            harness_name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            score REAL NOT NULL,
            cost_usd REAL NOT NULL,
            verified_by TEXT NOT NULL,
            run_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES capability_calibration_tasks(task_id)
        );
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db_migration.py::test_registry_v2_tables_exist -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_db_migration.py
git commit -m "feat(db): add harness_models/harness_modes/capability_calibration_* tables (#786 Plan B, 1/4)"
```

---

### Task 2: Model-diff detection + auto-queue in `synlynk probe`

**Files:**
- Modify: `synlynk/probe.py` (`_probe_agent`/`_probe_harness` — renamed by Plan A Task 4; add a call after the existing `_scan_command_palette()` invocation, ~line 666)
- Test: `tests/test_probe.py`

- [ ] **Step 1: Write the failing test**

```python
def test_probe_queues_sweep_for_new_model(tmp_path, monkeypatch):
    from synlynk import db, probe
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    conn.execute(
        "INSERT INTO harness_models (harness_name, model_id, first_seen_at, last_seen_at, status, discovery_source) "
        "VALUES ('codex', 'gpt-5', '2026-08-01', '2026-08-01', 'active', 'curated')"
    )
    conn.commit()

    queued = []
    monkeypatch.setattr(
        probe, "_queue_calibration_sweep",
        lambda harness_name, model_id, conn: queued.append((harness_name, model_id)),
    )
    probe._diff_and_queue_new_models("codex", ["gpt-5", "gpt-5.5"], conn)
    assert queued == [("codex", "gpt-5.5")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_probe.py::test_probe_queues_sweep_for_new_model -v`
Expected: `FAIL` — `AttributeError: module 'synlynk.probe' has no attribute '_diff_and_queue_new_models'`

- [ ] **Step 3: Implement the diff-and-queue function**

Add to `synlynk/probe.py`:

```python
def _diff_and_queue_new_models(harness_name: str, discovered_model_ids: list, conn) -> None:
    """Diff a harness's discovered models against harness_models; queue a
    calibration sweep for any model_id not yet recorded (#786 Plan B)."""
    known = {
        row[0]
        for row in conn.execute(
            "SELECT model_id FROM harness_models WHERE harness_name=?", (harness_name,)
        ).fetchall()
    }
    now = _now_iso()  # reuse existing helper if present; else datetime.utcnow().isoformat()
    for model_id in discovered_model_ids:
        if model_id in known:
            conn.execute(
                "UPDATE harness_models SET last_seen_at=? WHERE harness_name=? AND model_id=?",
                (now, harness_name, model_id),
            )
            continue
        conn.execute(
            "INSERT INTO harness_models "
            "(harness_name, model_id, first_seen_at, last_seen_at, status, discovery_source) "
            "VALUES (?, ?, ?, ?, 'active', 'self_report')",
            (harness_name, model_id, now, now),
        )
        _queue_calibration_sweep(harness_name, model_id, conn)
    conn.commit()


def _queue_calibration_sweep(harness_name: str, model_id: str, conn) -> None:
    """Auto-trigger a cost-capped, verified calibration sweep for one newly
    discovered (harness, model) pair, reusing capability_sweep.py's machinery."""
    from synlynk.capability_sweep import cmd_capability_sweep_for_harness_model
    try:
        cmd_capability_sweep_for_harness_model(harness_name, model_id)
    except SystemExit:
        pass  # cost cap exceeded — model stays 'active' with zero calibration data,
              # picked up by the routing explore-bonus in Task 4 instead
```

Check for an existing `_now_iso()`-style helper first: `grep -n "def _now_iso\|datetime.utcnow" synlynk/probe.py` — reuse it if present rather than introducing a second timestamp convention in the same file.

Wire the call in: find the harness's discovered model list (probe already resolves this via `_probe_model_version()` at `probe.py:1247`, confirmed by earlier recon) and call `_diff_and_queue_new_models(harness_name, [discovered_version], conn)` immediately after the existing `_scan_command_palette(harness_name, ...)` call in `_probe_agent`/`_probe_harness` (~line 666, post Plan-A-rename).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_probe.py::test_probe_queues_sweep_for_new_model -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add synlynk/probe.py tests/test_probe.py
git commit -m "feat(probe): auto-queue calibration sweep on new model discovery (#786 Plan B, 2/4)"
```

---

### Task 3: Difficulty-graded task pool + single-model sweep entry point

**Files:**
- Modify: `synlynk/capability_sweep.py` (add `cmd_capability_sweep_for_harness_model()`, extend `_run_sweep()` to accept a task list; seed `capability_calibration_tasks`)
- Test: `tests/test_capability_sweep.py`

- [ ] **Step 1: Write the failing test for pool completeness**

```python
def test_calibration_pool_has_all_role_difficulty_combinations(tmp_path, monkeypatch):
    from synlynk import db
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    roles = ("pm", "architect", "tpm", "dev", "designer", "qa", "marketing", "synlynk-bot")
    difficulties = ("basic", "intermediate", "advanced")
    rows = conn.execute("SELECT role, difficulty FROM capability_calibration_tasks").fetchall()
    present = {(r, d) for r, d in rows}
    missing = [(r, d) for r in roles for d in difficulties if (r, d) not in present]
    assert not missing, f"missing calibration tasks for: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_sweep.py::test_calibration_pool_has_all_role_difficulty_combinations -v`
Expected: `FAIL` — `missing` lists all 24 combinations (empty table)

- [ ] **Step 3: Seed the task pool**

Add a seed function to `synlynk/capability_sweep.py`, called from the same migration/init path that creates the tables in Task 1 (find it via `grep -n "def _seed_\|def _init_db\|_get_db" synlynk/db.py | head -5` to place it alongside existing seed-data functions):

```python
_ROLE_TASK_TEMPLATES = {
    "pm": {
        "basic": "Write a 3-bullet status update summarizing a completed feature.",
        "intermediate": "Triage this bug report into a GitHub issue with severity and repro steps: {context}",
        "advanced": "Draft a roadmap section reconciling two conflicting stakeholder priorities: {context}",
    },
    "architect": {
        "basic": "List the trade-offs between two database indexing strategies for {context}.",
        "intermediate": "Design a data model for {context} with at least 2 tables and their relationships.",
        "advanced": "Review this system design for a race condition and propose a fix: {context}",
    },
    "tpm": {
        "basic": "Break a 3-step feature into a dependency-ordered task list.",
        "intermediate": "Identify the critical path across 4 parallel workstreams: {context}",
        "advanced": "Reconcile a slipping deadline against two blocked dependencies: {context}",
    },
    "dev": {
        "basic": "Write a minimal Python function demonstrating {context}.",
        "intermediate": "Fix a failing test given this stack trace: {context}",
        "advanced": "Refactor this function to remove duplication while preserving behavior: {context}",
    },
    "designer": {
        "basic": "Describe a simple 3-field form layout for {context}.",
        "intermediate": "Propose a navigation structure for a 5-page app: {context}",
        "advanced": "Resolve a usability conflict between mobile and desktop layouts: {context}",
    },
    "qa": {
        "basic": "Write 3 test cases for {context}.",
        "intermediate": "Identify an edge case this test suite misses: {context}",
        "advanced": "Design a regression test strategy for a flaky integration test: {context}",
    },
    "marketing": {
        "basic": "Write a 1-sentence pitch for {context}.",
        "intermediate": "Draft a changelog entry for a breaking change: {context}",
        "advanced": "Reconcile messaging across two conflicting positioning statements: {context}",
    },
    "synlynk-bot": {
        "basic": "Summarize a devlog entry in 2 sentences.",
        "intermediate": "Detect drift between two versions of a roadmap doc: {context}",
        "advanced": "Reconcile a merge conflict in a union-merged markdown file: {context}",
    },
}


def _seed_calibration_tasks(conn) -> None:
    """Idempotently seed capability_calibration_tasks with the 24 role x
    difficulty baseline templates (#786 Plan B)."""
    import uuid
    from datetime import datetime, timezone
    existing = {
        (row[0], row[1])
        for row in conn.execute("SELECT role, difficulty FROM capability_calibration_tasks").fetchall()
    }
    now = datetime.now(timezone.utc).isoformat()
    for role, by_difficulty in _ROLE_TASK_TEMPLATES.items():
        for difficulty, template in by_difficulty.items():
            if (role, difficulty) in existing:
                continue
            conn.execute(
                "INSERT INTO capability_calibration_tasks "
                "(task_id, role, skill, difficulty, prompt_template, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), role, "general", difficulty, template, now),
            )
    conn.commit()
```

Call `_seed_calibration_tasks(conn)` immediately after the Task 1 DDL block executes, in the same function in `synlynk/db.py` (the one containing the `harness_models`/`harness_modes`/etc. `CREATE TABLE` statements) — import it there: `from synlynk.capability_sweep import _seed_calibration_tasks`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_sweep.py::test_calibration_pool_has_all_role_difficulty_combinations -v`
Expected: `PASS`

- [ ] **Step 5: Write the failing test for the single-model sweep entry point**

This reuses the real dispatch/verify pair already in `capability_sweep.py` — `_dispatch_calibration_task(agent, task, **kwargs)` (line 120, calls `dispatch_agent()`) and `_verify_calibration_result(verifier_agent, executor_agent, model, skill, executor_output)` (line 130, calls `_dispatch_calibration_task()` again for the verifier and parses its verdict) — rather than the invented `dispatch_harness()`/`_execute_calibration_task()` from the original draft. Note the real verifier picker is `_pick_verifier_agent(executor_agent, available_agents)` (line 106), not `_pick_verifier_harness`.

```python
def test_sweep_for_harness_model_writes_calibration_result(tmp_path, monkeypatch):
    from synlynk import db, capability_sweep

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    monkeypatch.setattr(capability_sweep, "_get_db", lambda: conn)
    monkeypatch.setattr(
        capability_sweep, "_dispatch_calibration_task",
        lambda agent, task, **kwargs: {"output": "example output"},
    )
    monkeypatch.setattr(
        capability_sweep, "_verify_calibration_result",
        lambda verifier_agent, executor_agent, model, skill, executor_output: {"quality": 8.0, "correct": True},
    )
    monkeypatch.setattr(capability_sweep, "_pick_verifier_agent", lambda executor, available: "codex")

    capability_sweep.cmd_capability_sweep_for_harness_model("agy", "gemini-3-pro")

    rows = conn.execute(
        "SELECT harness_name, model_id, score FROM capability_calibration_results WHERE harness_name='agy'"
    ).fetchall()
    assert len(rows) >= 1
    assert all(r[2] == 0.8 for r in rows)  # quality 8.0 normalized to a 0-1 score
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_capability_sweep.py::test_sweep_for_harness_model_writes_calibration_result -v`
Expected: `FAIL` — `AttributeError: module 'synlynk.capability_sweep' has no attribute 'cmd_capability_sweep_for_harness_model'`

- [ ] **Step 7: Implement the entry point**

Add to `synlynk/capability_sweep.py`:

This reuses the real dispatch/verify pair (`_dispatch_calibration_task()` and `_verify_calibration_result()`, both already in this file — see the "Revisions" section above) instead of inventing `_execute_calibration_task()`/`dispatch_harness()`. `_pick_verifier_agent(executor_agent, available_agents)` (line 106) picks the independent verifier, matching `_run_sweep()`'s existing pattern exactly.

```python
def cmd_capability_sweep_for_harness_model(harness_name: str, model_id: str) -> None:
    """Auto-triggered single-(harness,model) sweep against the full
    difficulty-graded task pool for every charter role (#786 Plan B).
    Reuses the existing dispatch/verify pair and cost-cap guardrail that
    _run_sweep() already uses for its 3-skill baseline sweep."""
    import uuid
    from datetime import datetime, timezone
    from synlynk import load_config

    conn = _get_db()
    cfg = load_config()
    cost_cap = cfg.get("capability_sweep", {}).get("cost_cap_usd", _DEFAULT_SWEEP_COST_CAP_USD)

    tasks = conn.execute(
        "SELECT task_id, role, skill, difficulty, prompt_template FROM capability_calibration_tasks"
    ).fetchall()
    available_agents = [a for a in AGENT_CAPABILITY_BASELINES if a != "local" and a != harness_name]

    total_cost = 0.0
    now = datetime.now(timezone.utc).isoformat()
    for task_id, role, skill, difficulty, template in tasks:
        prompt = template.format(context=f"a {skill} scenario at {difficulty} difficulty")
        executor_result = _dispatch_calibration_task(harness_name, prompt)
        # NOTE: confirm the exact cost field on dispatch_agent()'s real return
        # dict at implementation time (grep `cost_usd=` in dispatch.py around
        # its telemetry write) — this plan assumes the same "cost_usd" key
        # _run_sweep() and the rest of the dispatch layer already use.
        total_cost += executor_result.get("cost_usd", 0.0)
        if total_cost > cost_cap:
            print(f"  Calibration sweep for {harness_name}/{model_id} stopped: cost cap ${cost_cap:.2f} reached",
                  file=sys.stderr)
            break
        verifier_agent = _pick_verifier_agent(harness_name, available_agents)
        verdict = _verify_calibration_result(verifier_agent, harness_name, model_id, skill, executor_result)
        conn.execute(
            "INSERT INTO capability_calibration_results "
            "(result_id, harness_name, model_id, task_id, score, cost_usd, verified_by, run_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), harness_name, model_id, task_id,
             verdict["quality"] / 10.0, executor_result.get("cost_usd", 0.0), verifier_agent, now),
        )
    conn.commit()
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_capability_sweep.py::test_sweep_for_harness_model_writes_calibration_result -v`
Expected: `PASS`

- [ ] **Step 9: Commit**

```bash
git add synlynk/capability_sweep.py synlynk/db.py tests/test_capability_sweep.py
git commit -m "feat: seed per-role calibration task pool + single-model sweep entry point (#786 Plan B, 3/4)"
```

---

### Task 4: Stage 0 explore bonus in `_best_agent_for_story()`

**Files:**
- Modify: `synlynk/jobs.py:1056-1130` (`_best_agent_for_story`)
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write the failing test**

`_apply_stage0_explore_bonus` takes `candidates` as a plain list argument (it does not query `capability_scores` itself — that VIEW lookup already happened in the caller, `_capability_candidates_for_story`), so this test only needs `harness_models`/`capability_calibration_results` fixture rows, no story/capability_scores fixture at all.

**Cold-start correction (Agy's review finding, 2026-08-18):** the original draft only re-scored models already present in `candidates`. But `candidates` comes from `_capability_candidates_for_story()`, which reads the `capability_scores` VIEW — and a genuinely new, uncalibrated model (zero rows in `capability_calibration_results`) also has zero `capability_scores` rows, so it would never appear in `candidates` to begin with. The bonus could never fire for the exact case it exists to fix. Two tests below: one for the original "already-a-candidate-but-thin" case (kept, still a real scenario — e.g. a model seeded once via the legacy baseline but never calibration-swept), and a new one for the true cold-start case where the model has to be *injected* as a candidate, not just re-scored.

```python
def test_stage0_explore_bonus_bumps_thin_existing_candidate(tmp_path, monkeypatch):
    from synlynk import db, jobs

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    # gpt-5 is calibrated (has a result row); gpt-5.5 is thin (zero results) but
    # already appears in candidates (e.g. seeded once via the legacy baseline).
    conn.execute(
        "INSERT INTO harness_models (harness_name, model_id, first_seen_at, last_seen_at, status, discovery_source) "
        "VALUES ('codex', 'gpt-5', '2026-08-01', '2026-08-01', 'active', 'curated'), "
        "('codex', 'gpt-5.5', '2026-08-18', '2026-08-18', 'active', 'self_report')"
    )
    conn.execute(
        "INSERT INTO capability_calibration_tasks (task_id, role, skill, difficulty, prompt_template, created_at) "
        "VALUES ('t1', 'dev', 'general', 'basic', 'x', '2026-08-01')"
    )
    conn.execute(
        "INSERT INTO capability_calibration_results "
        "(result_id, harness_name, model_id, task_id, score, cost_usd, verified_by, run_at) "
        "VALUES ('r1', 'codex', 'gpt-5', 't1', 0.9, 0.01, 'grok', '2026-08-01')"
    )
    conn.commit()

    candidates = [("codex", 0.7, "gpt-5"), ("codex", 0.68, "gpt-5.5")]
    result = jobs._apply_stage0_explore_bonus(conn, candidates, discipline="backend", phase="build")

    scores = {model: score for _agent, score, model in result}
    assert scores["gpt-5"] == 0.7  # calibrated — unchanged
    assert scores["gpt-5.5"] == 0.68 + jobs._STAGE0_EXPLORE_BONUS  # thin — bumped
    assert result[0][2] == "gpt-5.5"  # bumped score (0.73) now sorts first over gpt-5 (0.7)


def test_stage0_explore_bonus_injects_cold_start_model_absent_from_candidates(tmp_path, monkeypatch):
    from synlynk import db, jobs

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    # gpt-5.5 was just discovered by probe (harness_models row exists) but has
    # never been calibrated or organically scored — no capability_scores row,
    # so it is NOT in the `candidates` list the caller passes in. This is the
    # real cold-start case: Stage 0 must inject it, not just re-score it.
    conn.execute(
        "INSERT INTO harness_models (harness_name, model_id, first_seen_at, last_seen_at, status, discovery_source) "
        "VALUES ('codex', 'gpt-5', '2026-08-01', '2026-08-01', 'active', 'curated'), "
        "('codex', 'gpt-5.5', '2026-08-18', '2026-08-18', 'active', 'self_report')"
    )
    conn.commit()

    candidates = [("codex", 0.7, "gpt-5")]  # gpt-5.5 absent — the bug case
    result = jobs._apply_stage0_explore_bonus(conn, candidates, discipline="backend", phase="build")

    models = {model for _agent, _score, model in result}
    assert "gpt-5.5" in models, "cold-start model must be injected as a candidate, not silently dropped"
    scores = {model: score for _agent, score, model in result}
    assert scores["gpt-5.5"] == jobs._STAGE0_BASELINE_SCORE + jobs._STAGE0_EXPLORE_BONUS
    assert scores["gpt-5.5"] < scores["gpt-5"], "injected baseline+bonus must stay below an already-calibrated model's real score"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs.py -k stage0_explore_bonus -v`
Expected: `FAIL` — `AttributeError: module 'synlynk.jobs' has no attribute '_apply_stage0_explore_bonus'`

- [ ] **Step 3: Implement Stage 0**

Add to `synlynk/jobs.py`, immediately before `_best_agent_for_story` (~line 1056):

```python
_STAGE0_EXPLORE_BONUS = 0.05  # bounded: smaller than typical _CAPABILITY_COST_TIE_GAP
_STAGE0_BASELINE_SCORE = 0.5  # neutral starting point for an injected, never-scored model


def _apply_stage0_explore_bonus(conn, candidates: list, discipline: str, phase: str) -> list:
    """Stage 0 (#786 Plan B): surface thin/zero-calibration-data active models
    instead of letting cold-start scoring starve them.

    Two cases, both bounded by _STAGE0_EXPLORE_BONUS (smaller than
    _CAPABILITY_COST_TIE_GAP, so this nudges exploration without overriding a
    well-calibrated cheaper option at Stage 3):
    1. Model is already in `candidates` (has a capability_scores row, e.g. via
       the legacy baseline seed) but has zero capability_calibration_results
       rows — bump its existing score.
    2. Model has a harness_models row but is absent from `candidates` entirely
       (true cold start — no capability_scores row yet) — inject it at
       _STAGE0_BASELINE_SCORE + the bonus, so it can compete for Stage 1-3
       instead of never being considered.
    """
    known_models = {model for _agent, _score, model in candidates}

    thin_rows = conn.execute(
        "SELECT hm.harness_name, hm.model_id FROM harness_models hm "
        "LEFT JOIN capability_calibration_results ccr "
        "  ON ccr.model_id = hm.model_id AND ccr.harness_name = hm.harness_name "
        "WHERE hm.status='active' "
        "GROUP BY hm.harness_name, hm.model_id HAVING COUNT(ccr.result_id) = 0"
    ).fetchall()
    thin_model_ids = {model_id for _harness_name, model_id in thin_rows}

    boosted = list(candidates)
    for harness_name, model_id in thin_rows:
        if model_id not in known_models:
            boosted.append((harness_name, _STAGE0_BASELINE_SCORE, model_id))

    result = []
    for agent, score, model in boosted:
        bumped_score = score + _STAGE0_EXPLORE_BONUS if model in thin_model_ids else score
        result.append((agent, bumped_score, model))
    return sorted(result, key=lambda c: c[1], reverse=True)
```

Then wire it into `_best_agent_for_story()` — note the injection case means Stage 0 must run even when the raw `candidates` list from Stage 1 is empty (a discipline with zero calibrated history but a freshly-discovered model should still be explorable), so the `if not candidates: return None` early-return has to move to *after* Stage 0 runs, not before it (`jobs.py:1082-1086`):

```python
        candidates = _capability_candidates_for_story(
            conn, discipline, org, industry, phase
        )
        candidates = _apply_stage0_explore_bonus(conn, candidates, discipline, phase)
        if not candidates:
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jobs.py -k stage0_explore_bonus -v`
Expected: `PASS` (both tests)

- [ ] **Step 5: Run the full `_best_agent_for_story` regression suite**

Run: `pytest tests/test_jobs.py -k "best_agent_for_story or capability" -v`
Expected: `PASS` — confirms the bonus never flips routing for already-calibrated candidates outside the `_CAPABILITY_COST_TIE_GAP` window

- [ ] **Step 6: Commit**

```bash
git add synlynk/jobs.py tests/test_jobs.py
git commit -m "feat(jobs): add Stage 0 explore bonus for thin-calibration-data models (#786 Plan B, 4/4)"
```

---

## Out of scope for this plan (per spec)

- `harness_modes` population (tools/skills/flags tracking) — the table is created in Task 1 but no writer is implemented in this plan; populating it requires extending `_scan_command_palette()` in `probe.py`, deferred as a fast-follow once the model-registry half (this plan) is proven in production.
- Competitive landscape SWOT — separate track, no dependency on this plan.
