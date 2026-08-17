# Agent-Roles-Charters Phase 1 Follow-Ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all five non-blocking review notes from PR #1003 (`daemon_jobs.agent_id` persistence, `capability_grants` clobber on `agent edit`, `--dry-run`/`--as-agent` preview bug, `_harness_for_org_role` sort-order, missing test coverage) in one small PR, per `docs/superpowers/specs/2026-08-16-agent-roles-phase1-followups-design.md`.

**Architecture:** Five independent, pattern-following fixes in the existing `synlynk/dispatch.py`, `synlynk/agent_store.py`, `synlynk/agent_cli.py`, `synlynk/cli.py`, `synlynk/db.py` neighborhood. No new files, no new subsystems. Ordered so schema/storage-layer changes land before their callers.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest.

**Deviation from the written spec (flagged here, not silent):** Spec §3 says to add `agent_id` to the quota-deferred `INSERT INTO daemon_jobs` branch at `dispatch.py:2112-2118`, "mirroring the `session_id` pattern exactly." A fresh read of that branch (Task 4 below) shows `session_id` is **not** included there today — only `job_id, agent, task, story_id, status, priority, depends_on, enqueued_at, blocked_reason`. Truly mirroring `session_id`'s current scope means *not* touching this branch. Task 4 leaves the quota-deferred branch alone and only threads `agent_id` through the two branches that actually carry `session_id` today (the `UPDATE` and `INSERT OR REPLACE` branches). If a job gets deferred for quota and its `agent_id` attribution matters later, that's a pre-existing gap shared with `session_id` and out of scope for this spec.

---

### Task 1: `daemon_jobs.agent_id` schema migration

**Files:**
- Modify: `synlynk/db.py:332-336`
- Test: `tests/test_dispatch.py` (new test near `test_daemon_jobs_migration_adds_requires_gh_write_and_gh_write_target` at line 1041)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dispatch.py`, immediately after `test_daemon_jobs_migration_adds_requires_gh_write_and_gh_write_target` (currently ends at line 1047):

```python
def test_daemon_jobs_migration_adds_agent_id_column(project_dir):
    from synlynk import _get_db
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    assert "agent_id" in cols
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dispatch.py::test_daemon_jobs_migration_adds_agent_id_column -v`
Expected: FAIL — `assert "agent_id" in cols` fails, column doesn't exist yet.

- [ ] **Step 3: Add the migration**

In `synlynk/db.py`, the `daemon_jobs` migration block currently reads (lines 301-351):

```python
    daemon_job_cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    ...
    if "session_id" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN session_id TEXT")
        except sqlite3.OperationalError:
            pass
    if "requires_gh_write" not in daemon_job_cols:
```

Insert a new block immediately after the `session_id` block (i.e. between lines 336 and 337):

```python
    if "agent_id" not in daemon_job_cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN agent_id TEXT")
        except sqlite3.OperationalError:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_dispatch.py::test_daemon_jobs_migration_adds_agent_id_column -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_dispatch.py
git commit -m "feat: add daemon_jobs.agent_id schema migration"
```

---

### Task 2: `regenerate_agent_projection()` merge-not-replace semantics

**Files:**
- Modify: `synlynk/agent_store.py:338-353`
- Test: `tests/test_agent_store.py` (new test after `test_regenerate_agent_projection_is_idempotent`, currently ending at line 282)

**Context:** `regenerate_agent_projection(agent_id, repo_overrides=None)` currently writes `repo_overrides or {}` straight into the projection's `overrides` field every call — a second call with a different `repo_overrides` silently drops whatever the first call wrote. None of the three existing tests in `tests/test_agent_store.py` (`writes_flat_yaml`, `is_idempotent`, `path_is_gitignored`) actually exercise a second call with *different* `repo_overrides`, so none of them need to change — only a new test is needed to cover the merge behavior.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agent_store.py`, immediately after `test_regenerate_agent_projection_is_idempotent` (currently ends at line 282):

```python
def test_regenerate_agent_projection_merges_overrides_across_calls(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])

    agent_store.regenerate_agent_projection(
        "dev-primary", repo_overrides={"capability_grants": {}}
    )
    agent_store.regenerate_agent_projection(
        "dev-primary", repo_overrides={"new_key": "value"}
    )

    projection_path = os.path.join(".synlynk", "agents", "dev-primary.yaml")
    with open(projection_path) as f:
        rendered = f.read()
    assert "capability_grants: {}" in rendered
    assert "new_key: value" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agent_store.py::test_regenerate_agent_projection_merges_overrides_across_calls -v`
Expected: FAIL — `"capability_grants: {}" in rendered` fails because the second call's `repo_overrides={"new_key": "value"}` replaced the first call's `overrides` entirely.

- [ ] **Step 3: Implement merge-not-replace**

`synlynk/agent_store.py:338-353` currently reads:

```python
def regenerate_agent_projection(agent_id: str, repo_overrides: dict = None) -> None:
    workspace_id = get_workspace_id()
    payload = {
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "role": _agent_role(agent_id),
        "overrides": repo_overrides or {},
    }
    rendered = _dump_flat_yaml(payload) + "\n"

    projection_dir = os.path.join(".synlynk", "agents")
    os.makedirs(projection_dir, exist_ok=True)
    projection_path = os.path.join(projection_dir, f"{agent_id}.yaml")
    with open(projection_path, "w") as f:
        f.write(rendered)
```

Replace with:

```python
def _read_existing_projection_overrides(projection_path: str) -> dict:
    if not os.path.exists(projection_path):
        return {}
    try:
        with open(projection_path) as f:
            lines = f.readlines()
    except OSError:
        return {}
    overrides = {}
    in_overrides = False
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped == "overrides:":
            in_overrides = True
            continue
        if in_overrides:
            if not stripped.startswith("  ") or stripped.strip() == "":
                break
            key, _, value = stripped.strip().partition(": ")
            if key:
                overrides[key] = value if value != "{}" else {}
    return overrides


def regenerate_agent_projection(agent_id: str, repo_overrides: dict = None) -> None:
    workspace_id = get_workspace_id()
    projection_dir = os.path.join(".synlynk", "agents")
    os.makedirs(projection_dir, exist_ok=True)
    projection_path = os.path.join(projection_dir, f"{agent_id}.yaml")

    merged_overrides = _read_existing_projection_overrides(projection_path)
    merged_overrides.update(repo_overrides or {})

    payload = {
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "role": _agent_role(agent_id),
        "overrides": merged_overrides,
    }
    rendered = _dump_flat_yaml(payload) + "\n"

    with open(projection_path, "w") as f:
        f.write(rendered)
```

`_dump_flat_yaml`'s existing rendering (confirmed by reading `synlynk/agent_store.py` around line 320) writes empty-dict override values as `key: {}` and scalar values as `key: value` at 2-space indent under `overrides:` — the parser above matches that exact shape and needs no changes to `_dump_flat_yaml` itself.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_agent_store.py::test_regenerate_agent_projection_merges_overrides_across_calls -v`
Expected: PASS

- [ ] **Step 5: Run the full existing agent_store test file to confirm no regressions**

Run: `python3 -m pytest tests/test_agent_store.py -v`
Expected: All PASS (including the three pre-existing projection tests, which are single-call or repeat-identical-call scenarios unaffected by the merge change).

- [ ] **Step 6: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "fix: regenerate_agent_projection merges overrides instead of replacing them"
```

---

### Task 3: `cmd_agent_edit` stops clobbering `capability_grants`

**Files:**
- Modify: `synlynk/agent_cli.py:115`
- Test: `tests/test_agent_cli.py` (new test after `test_cmd_agent_edit_stale_revision_exits_1`, currently ending at line 155)

**Depends on:** Task 2 (merge-not-replace semantics must be in place first, otherwise this test would fail for the same reason Task 2's test would).

**Context:** `cmd_agent_edit` (`synlynk/agent_cli.py:94-116`) currently calls:

```python
    agent_store.regenerate_agent_projection(agent_id, repo_overrides={"capability_grants": {}})
```

on line 115. This unconditionally wipes any `overrides` a future mechanism might have written since `cmd_agent_init` (e.g. a Phase 3 capability registry). `cmd_agent_init` (lines 37-57) is unaffected by this task — it still seeds `capability_grants: {}` via its own `repo_overrides={"capability_grants": {}}` call at lines 53-55, and Task 2's merge-not-replace change is a no-op on a brand-new agent's first projection write (nothing to merge against).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agent_cli.py`, immediately after `test_cmd_agent_edit_stale_revision_exits_1` (currently ends at line 155):

```python
def test_cmd_agent_edit_preserves_capability_grants_set_after_init(project_dir, tmp_path, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    # Simulate a future mechanism (e.g. Phase 3 capability registry) writing
    # a non-empty capability_grants after init but before this edit.
    agent_store.regenerate_agent_projection(
        agent_id, repo_overrides={"capability_grants": {"can_deploy": True}}
    )

    charter_file = tmp_path / "edited_charter.md"
    charter_file.write_text("Implementation — writes the code, now with more detail.")
    agent_cli.cmd_agent_edit(agent_id, str(charter_file))

    projection_path = os.path.join(".synlynk", "agents", f"{agent_id}.yaml")
    with open(projection_path) as f:
        rendered = f.read()
    assert "can_deploy: True" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agent_cli.py::test_cmd_agent_edit_preserves_capability_grants_set_after_init -v`
Expected: FAIL — `cmd_agent_edit` still hardcodes `repo_overrides={"capability_grants": {}}`, wiping `can_deploy: True`.

- [ ] **Step 3: Fix `cmd_agent_edit`**

In `synlynk/agent_cli.py`, line 115 currently reads:

```python
    agent_store.regenerate_agent_projection(agent_id, repo_overrides={"capability_grants": {}})
```

Change to:

```python
    agent_store.regenerate_agent_projection(agent_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_agent_cli.py::test_cmd_agent_edit_preserves_capability_grants_set_after_init -v`
Expected: PASS

- [ ] **Step 5: Run the full existing agent_cli test file to confirm no regressions**

Run: `python3 -m pytest tests/test_agent_cli.py -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add synlynk/agent_cli.py tests/test_agent_cli.py
git commit -m "fix: agent edit no longer clobbers capability_grants set after init"
```

---

### Task 4: Thread `agent_id` through `daemon_jobs` write paths

**Files:**
- Modify: `synlynk/dispatch.py:140-156` (new helper), `synlynk/dispatch.py:2533-2535` (call site), `synlynk/dispatch.py:2542-2589` (UPDATE + INSERT OR REPLACE branches)
- Test: `tests/test_dispatch.py` (new test after `test_dispatch_agent_persists_requires_gh_write_and_target_on_daemon_jobs`, near line 1075)

**Depends on:** Task 1 (the `agent_id` column must exist before this task writes to it).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dispatch.py`, after `test_dispatch_agent_persists_requires_gh_write_and_target_on_daemon_jobs`:

```python
def test_dispatch_agent_persists_agent_id_on_daemon_jobs(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk import agent_cli

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    agent_id = agent_cli.cmd_agent_init("dev")

    sl.dispatch_agent(
        "codex", "do work", agent_id=agent_id, force_agent=True, context_mode="none",
    )

    conn = sl._get_db()
    row = conn.execute(
        "SELECT agent_id FROM daemon_jobs ORDER BY enqueued_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row[0] == agent_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dispatch.py::test_dispatch_agent_persists_agent_id_on_daemon_jobs -v`
Expected: FAIL — `row[0]` is `None`, `agent_id` is never written to `daemon_jobs`.

- [ ] **Step 3: Add `_ensure_daemon_job_agent_id_column` helper**

In `synlynk/dispatch.py`, immediately after `_ensure_daemon_job_session_column` (which currently ends at line 156, right before `_ensure_daemon_job_gh_write_columns` starts at line 159), insert:

```python
def _ensure_daemon_job_agent_id_column(conn) -> None:
    """Add agent_id if missing (legacy schemas + unit fixtures). Mirrors
    _ensure_daemon_job_session_column above — same no-op-on-absence contract.
    """
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)").fetchall()}
    except Exception:
        return
    if not cols:
        return
    if "agent_id" not in cols:
        try:
            conn.execute("ALTER TABLE daemon_jobs ADD COLUMN agent_id TEXT")
        except Exception:
            pass
```

- [ ] **Step 4: Call the new helper alongside the existing ones**

At `synlynk/dispatch.py:2533-2535`, currently:

```python
            _ensure_daemon_job_context_columns(dconn)
            _ensure_daemon_job_session_column(dconn)
            _ensure_daemon_job_gh_write_columns(dconn)
```

Change to:

```python
            _ensure_daemon_job_context_columns(dconn)
            _ensure_daemon_job_session_column(dconn)
            _ensure_daemon_job_agent_id_column(dconn)
            _ensure_daemon_job_gh_write_columns(dconn)
```

- [ ] **Step 5: Thread `agent_id` through the UPDATE branch**

At `synlynk/dispatch.py:2542-2561`, currently:

```python
                dconn.execute(
                    "UPDATE daemon_jobs SET status='running', pid=?, started_at=?, "
                    "log_path=?, agent=?, task=?, story_id=?, "
                    "dispatch_context=COALESCE(dispatch_context, ?), "
                    "context_mode=?, context_bytes=?, "
                    "session_id=COALESCE(session_id, ?) WHERE job_id=?",
                    (
                        proc.pid,
                        job["started_at"],
                        log_file,
                        agent,
                        task,
                        story_id,
                        dispatch_context,
                        context_mode,
                        context_bytes,
                        session_id,
                        job_id,
                    ),
                )
```

Change to:

```python
                dconn.execute(
                    "UPDATE daemon_jobs SET status='running', pid=?, started_at=?, "
                    "log_path=?, agent=?, task=?, story_id=?, "
                    "dispatch_context=COALESCE(dispatch_context, ?), "
                    "context_mode=?, context_bytes=?, "
                    "session_id=COALESCE(session_id, ?), "
                    "agent_id=COALESCE(agent_id, ?) WHERE job_id=?",
                    (
                        proc.pid,
                        job["started_at"],
                        log_file,
                        agent,
                        task,
                        story_id,
                        dispatch_context,
                        context_mode,
                        context_bytes,
                        session_id,
                        agent_id,
                        job_id,
                    ),
                )
```

- [ ] **Step 6: Thread `agent_id` through the INSERT OR REPLACE branch**

At `synlynk/dispatch.py:2563-2589`, currently:

```python
                dconn.execute(
                    "INSERT OR REPLACE INTO daemon_jobs "
                    "(job_id, agent, task, story_id, status, priority, depends_on, pid, "
                    "enqueued_at, started_at, log_path, dispatch_context, context_mode, context_bytes, session_id, "
                    "requires_gh_write, gh_write_target) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        job_id,
                        agent,
                        task,
                        story_id,
                        "running",
                        5,
                        "[]",
                        proc.pid,
                        job["started_at"],
                        job["started_at"],
                        log_file,
                        dispatch_context,
                        context_mode,
                        context_bytes,
                        session_id,
                        1 if requires_gh_write else 0,
                        gh_write_target_value,
                    ),
                )
```

Change to:

```python
                dconn.execute(
                    "INSERT OR REPLACE INTO daemon_jobs "
                    "(job_id, agent, task, story_id, status, priority, depends_on, pid, "
                    "enqueued_at, started_at, log_path, dispatch_context, context_mode, context_bytes, session_id, "
                    "agent_id, requires_gh_write, gh_write_target) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        job_id,
                        agent,
                        task,
                        story_id,
                        "running",
                        5,
                        "[]",
                        proc.pid,
                        job["started_at"],
                        job["started_at"],
                        log_file,
                        dispatch_context,
                        context_mode,
                        context_bytes,
                        session_id,
                        agent_id,
                        1 if requires_gh_write else 0,
                        gh_write_target_value,
                    ),
                )
```

Note: the quota-deferred `INSERT INTO daemon_jobs` branch at `dispatch.py:2112-2118` is deliberately **not** touched — see the plan header's "Deviation from the written spec" note.

- [ ] **Step 7: Run test to verify it passes**

Run: `python3 -m pytest tests/test_dispatch.py::test_dispatch_agent_persists_agent_id_on_daemon_jobs -v`
Expected: PASS

- [ ] **Step 8: Run the full dispatch test file to confirm no regressions**

Run: `python3 -m pytest tests/test_dispatch.py -v`
Expected: All PASS.

- [ ] **Step 9: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: persist agent_id on daemon_jobs write paths"
```

---

### Task 5: Extract `resolve_dispatch_harness()`, fix `--dry-run` + `--as-agent` preview

**Files:**
- Modify: `synlynk/dispatch.py:1985-2022` (extract), `synlynk/dispatch.py:814-837` (`_render_dispatch_preview` signature), `synlynk/cli.py:1142-1166` (dry-run branch)
- Test: `tests/test_agent_cli.py` (new test after `test_cli_dispatch_as_agent_without_explicit_harness`, currently ending at line 293)

**Context:** `dispatch_agent()`'s body (`synlynk/dispatch.py:1985-2022`) inlines `agent_id`→role resolution plus harness auto-selection (story-based first, `_harness_for_org_role` fallback). `cli.py`'s dry-run branch (`cli.py:1142-1166`) calls `_render_dispatch_preview(args.agent, args.task, context_mode)` using `args.agent` directly — when only `--as-agent` is given, `args.agent` is `None` and the preview never runs this resolution, so it prints `agent: None` instead of the harness that would actually be picked.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agent_cli.py`, immediately after `test_cli_dispatch_as_agent_without_explicit_harness` (currently ends at line 293):

```python
def test_cli_dispatch_dry_run_as_agent_without_explicit_harness_shows_resolved_agent(project_dir, capsys):
    from synlynk.cli import main

    main(["agent", "init", "qa"])  # qa -> "verifier" -> agy (see _ORG_ROLE_TO_BASELINE_ROLE)
    capsys.readouterr()

    main(["dispatch", "--task", "run the test suite", "--as-agent", "qa", "--dry-run"])
    captured = capsys.readouterr()
    assert "agent:        agy" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agent_cli.py::test_cli_dispatch_dry_run_as_agent_without_explicit_harness_shows_resolved_agent -v`
Expected: FAIL — output shows `agent:        None` (or the harness positional's default), not `agy`.

- [ ] **Step 3: Extract `resolve_dispatch_harness()` in `dispatch.py`**

`synlynk/dispatch.py:1985-2022` currently reads (inside `dispatch_agent`, right after the `if not task or not task.strip(): raise ValueError(...)` guard):

```python
    resolved_agent_role = None
    if agent_id:
        from synlynk import agent_store
        entry = next(
            (a for a in agent_store.list_agents() if a["agent_id"] == agent_id), None
        )
        if entry is None:
            raise ValueError(
                f"agent_id {agent_id!r} is unregistered — cannot dispatch. "
                f"Run `synlynk agent list` to see registered agents."
            )
        if entry.get("disabled"):
            raise ValueError(
                f"agent {agent_id!r} is disabled — cannot dispatch. "
                f"Use `synlynk agent show {agent_id}` to check status."
            )
        resolved_agent_role = next(
            (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), None
        )
    if session_id is None:
        from synlynk.session import _read_active_session
        session_id = _read_active_session()
    baselines_map = _pkg("AGENT_CAPABILITY_BASELINES", AGENT_CAPABILITY_BASELINES)
    dispatch_time = None
    if not story_id:
        dispatch_time = time.time()
    if not force_agent:
        picked = None
        if story_id:
            best_agent = _pkg("_best_agent_for_story")
            if best_agent:
                best = best_agent(story_id)
                if best and best in baselines_map:
                    picked = best
        if picked is None and resolved_agent_role:
            picked = _harness_for_org_role(resolved_agent_role, baselines_map, requires_gh_write)
        if picked:
            agent = picked
```

Split this into a standalone helper plus a thin call from `dispatch_agent`. Insert the new function immediately before `def dispatch_agent(` (i.e. just above line 1965):

```python
def resolve_dispatch_harness(agent: str, agent_id: str = None, story_id: str = None,
                              force_agent: bool = False, requires_gh_write: bool = False) -> str:
    """Resolve which harness a dispatch will actually run on.

    Side-effect-free (no subprocess spawn, no DB write) so both the live
    dispatch path and the --dry-run preview path can call it and see the
    same answer. Raises ValueError for an unregistered/disabled agent_id,
    same as the live path always has.
    """
    resolved_agent_role = None
    if agent_id:
        from synlynk import agent_store
        entry = next(
            (a for a in agent_store.list_agents() if a["agent_id"] == agent_id), None
        )
        if entry is None:
            raise ValueError(
                f"agent_id {agent_id!r} is unregistered — cannot dispatch. "
                f"Run `synlynk agent list` to see registered agents."
            )
        if entry.get("disabled"):
            raise ValueError(
                f"agent {agent_id!r} is disabled — cannot dispatch. "
                f"Use `synlynk agent show {agent_id}` to check status."
            )
        resolved_agent_role = next(
            (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), None
        )

    if force_agent:
        return agent

    baselines_map = _pkg("AGENT_CAPABILITY_BASELINES", AGENT_CAPABILITY_BASELINES)
    picked = None
    if story_id:
        best_agent = _pkg("_best_agent_for_story")
        if best_agent:
            best = best_agent(story_id)
            if best and best in baselines_map:
                picked = best
    if picked is None and resolved_agent_role:
        picked = _harness_for_org_role(resolved_agent_role, baselines_map, requires_gh_write)
    return picked or agent
```

Then replace the block quoted above (inside `dispatch_agent`) with:

```python
    agent = resolve_dispatch_harness(
        agent, agent_id=agent_id, story_id=story_id,
        force_agent=force_agent, requires_gh_write=requires_gh_write,
    )
    if session_id is None:
        from synlynk.session import _read_active_session
        session_id = _read_active_session()
    baselines_map = _pkg("AGENT_CAPABILITY_BASELINES", AGENT_CAPABILITY_BASELINES)
    dispatch_time = None
    if not story_id:
        dispatch_time = time.time()
```

`baselines_map` and `dispatch_time` stay in `dispatch_agent` because later code in the function (past line 2022, unchanged by this task) already references them directly — only the resolution logic itself moves into the helper.

- [ ] **Step 4: Update `_render_dispatch_preview` to use the helper**

`synlynk/dispatch.py:814-837` currently reads:

```python
def _render_dispatch_preview(agent: str, task: str, context_mode: str) -> dict:
    """Compute task/context digest data for dispatch inspection."""
    task_sha256 = hashlib.sha256(task.encode("utf-8")).hexdigest()
```

Change the signature and first line to:

```python
def _render_dispatch_preview(agent: str, task: str, context_mode: str,
                              agent_id: str = None, story_id: str = None,
                              force_agent: bool = False, requires_gh_write: bool = False) -> dict:
    """Compute task/context digest data for dispatch inspection."""
    agent = resolve_dispatch_harness(
        agent, agent_id=agent_id, story_id=story_id,
        force_agent=force_agent, requires_gh_write=requires_gh_write,
    )
    task_sha256 = hashlib.sha256(task.encode("utf-8")).hexdigest()
```

The rest of the function (lines 817-837, computing `context_digest`/`context_bytes`/building the return dict) is unchanged — it already returns `"agent": agent`, which now reflects the resolved harness.

- [ ] **Step 5: Update `cli.py`'s dry-run branch to pass resolution inputs through**

`synlynk/cli.py:1142-1166` currently reads:

```python
            if getattr(args, "dry_run", False):
                if not args.task or not args.task.strip():
                    raise ValueError(
                        "--task is empty or whitespace-only; refusing to dispatch (see #720)"
                    )
                from synlynk.dispatch import _render_dispatch_preview

                context_mode = getattr(args, "context_mode", "task")
                preview = _render_dispatch_preview(args.agent, args.task, context_mode)
```

Change the `_render_dispatch_preview` call to:

```python
            if getattr(args, "dry_run", False):
                if not args.task or not args.task.strip():
                    raise ValueError(
                        "--task is empty or whitespace-only; refusing to dispatch (see #720)"
                    )
                from synlynk.dispatch import _render_dispatch_preview

                context_mode = getattr(args, "context_mode", "task")
                preview = _render_dispatch_preview(
                    args.agent or (known_agents[0] if not resolved_agent_id else None),
                    args.task, context_mode,
                    agent_id=resolved_agent_id,
                    story_id=getattr(args, "story_id", None),
                    force_agent=getattr(args, "force_agent", False),
                    requires_gh_write=getattr(args, "requires_gh_write", False),
                )
```

`resolved_agent_id` is already computed above this block at `cli.py:1135-1138` (`resolved_agent_id = agent_cli._resolve_or_exit(args.as_agent)` when `--as-agent` is given). Passing `agent=None` when only `--as-agent` was given lets `resolve_dispatch_harness` fall through to its role/story-based resolution instead of defaulting to `known_agents[0]`; when neither `args.agent` nor `--as-agent` is given, the pre-existing `dispatch_parser.error(...)` check at `cli.py:1139-1140` already exits before this branch is reached, so `args.agent or (known_agents[0] if not resolved_agent_id else None)` never needs to fall back to `None` with nothing resolvable.

- [ ] **Step 6: Run test to verify it passes**

Run: `python3 -m pytest tests/test_agent_cli.py::test_cli_dispatch_dry_run_as_agent_without_explicit_harness_shows_resolved_agent -v`
Expected: PASS

- [ ] **Step 7: Run the full dispatch + agent_cli test files to confirm no regressions**

Run: `python3 -m pytest tests/test_dispatch.py tests/test_agent_cli.py -v`
Expected: All PASS.

- [ ] **Step 8: Commit**

```bash
git add synlynk/dispatch.py synlynk/cli.py tests/test_agent_cli.py
git commit -m "fix: --dry-run dispatch preview resolves harness the same way the live path does"
```

---

### Task 6: `_harness_for_org_role` restricted to `CORE_FLEET`

**Files:**
- Modify: `synlynk/dispatch.py:44`
- Test: `tests/test_dispatch.py` (new test near the other `_harness_for_org_role`-adjacent tests, after `test_dispatch_agent_id_auto_selects_harness_by_mapped_role`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dispatch.py`, immediately after `test_dispatch_agent_id_auto_selects_harness_by_mapped_role` (currently ends at line 1652):

```python
def test_harness_for_org_role_ignores_non_core_fleet_baselines(monkeypatch):
    import synlynk.dispatch as dispatch_mod

    # A fake baseline that would win alphabetically ("aardvark" < "agy") and
    # matches the "builder" role, but isn't in CORE_FLEET — must be skipped.
    fake_baselines = {
        "aardvark": {"roles": ["builder"], "can_gh_write": False},
        "agy": {"roles": ["builder", "verifier"], "can_gh_write": False},
    }

    result = dispatch_mod._harness_for_org_role("dev", fake_baselines)
    assert result == "agy"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dispatch.py::test_harness_for_org_role_ignores_non_core_fleet_baselines -v`
Expected: FAIL — `result == "aardvark"`, since today's iteration is `sorted(baselines_map)` with no `CORE_FLEET` restriction.

- [ ] **Step 3: Restrict the iteration to `CORE_FLEET`**

`synlynk/dispatch.py:32-51` currently reads:

```python
def _harness_for_org_role(org_role: str, baselines_map: dict, requires_gh_write: bool = False):
    """Deterministic fallback harness selection for agent_id-driven dispatch.
    ...
    """
    baseline_role = _ORG_ROLE_TO_BASELINE_ROLE.get(org_role)
    if not baseline_role:
        return None
    for name in sorted(baselines_map):
        baseline = baselines_map[name]
        if baseline_role not in baseline.get("roles", []):
            continue
        if requires_gh_write and not baseline.get("can_gh_write", False):
            continue
        return name
    return None
```

Change the `for name in sorted(baselines_map):` line to:

```python
    from synlynk._constants import CORE_FLEET
    for name in sorted(n for n in baselines_map if n in CORE_FLEET):
```

(Add the import inline at the top of the function body, immediately after the `if not baseline_role: return None` guard — matching the existing lazy-import style already used elsewhere in this file, e.g. at `dispatch.py:2193`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_dispatch.py::test_harness_for_org_role_ignores_non_core_fleet_baselines -v`
Expected: PASS

- [ ] **Step 5: Run the full dispatch test file to confirm no regressions**

Run: `python3 -m pytest tests/test_dispatch.py -v`
Expected: All PASS (in particular `test_dispatch_agent_id_auto_selects_harness_by_mapped_role`, which asserts `agy` wins for the real `AGENT_CAPABILITY_BASELINES` map — unaffected since `agy` is in `CORE_FLEET` and still sorts first among real fleet entries).

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "fix: _harness_for_org_role only considers CORE_FLEET harnesses"
```

---

### Task 7: `story_id` vs `agent_id` precedence coverage

**Files:**
- Test only: `tests/test_dispatch.py` (new test after `test_dispatch_agent_id_takes_precedence_over_story_id_for_gh_token_role`, currently ending at line 1679)

**Context:** `test_dispatch_agent_id_takes_precedence_over_story_id_for_gh_token_role` (already in the suite) covers `agent_id`'s role taking precedence over `story_id` for **GitHub identity/token** resolution. It does not cover **harness auto-selection** precedence — confirmed by reading `resolve_dispatch_harness` (Task 5): story-based routing (`_best_agent_for_story`) is tried first, and `_harness_for_org_role` is only consulted as a fallback when story-based routing returns `None`. This task adds the missing coverage for that specific precedence order. No production code changes — this task is pure test coverage, confirming behavior that already exists after Task 5's extraction.

- [ ] **Step 1: Write the test**

Add to `tests/test_dispatch.py`, immediately after `test_dispatch_agent_id_takes_precedence_over_story_id_for_gh_token_role`:

```python
def test_dispatch_agent_story_id_wins_over_agent_id_role_for_harness_selection(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk import agent_cli

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    # "dev" -> "builder" -> _harness_for_org_role would pick "agy" (first
    # alphabetically among CORE_FLEET with "builder" in its roles).
    agent_id = agent_cli.cmd_agent_init("dev")
    monkeypatch.setattr(sl, "_best_agent_for_story", lambda story_id: "grok")

    job = sl.dispatch_agent(
        "claude", "implement the feature", agent_id=agent_id, story_id="story-with-capability-match",
        force_agent=False, context_mode="none",
    )

    assert job["agent"] == "grok"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_dispatch.py::test_dispatch_agent_story_id_wins_over_agent_id_role_for_harness_selection -v`
Expected: PASS immediately (Task 5 already implemented and preserved this precedence order — this step confirms it, doesn't change behavior).

If this test does NOT pass, `resolve_dispatch_harness` (Task 5) diverged from `dispatch_agent`'s original resolution order — stop and re-check Task 5's extraction before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dispatch.py
git commit -m "test: cover story_id precedence over agent_id role for harness selection"
```

---

### Task 8: Final full-suite verification

**Files:** None (verification only).

- [ ] **Step 1: Run the complete test suite**

Run: `python3 -m pytest -q`
Expected: All tests pass (0 failures). The baseline before this plan was 2019 passed, 2 skipped — expect that count plus the 6 new tests added across Tasks 1, 2, 3, 4, 6, 7 (2025 passed, 2 skipped), modulo any pre-existing skip/xfail markers.

- [ ] **Step 2: Confirm branch is clean and ready**

Run: `git status --short`
Expected: No uncommitted changes — every task above ended with its own commit.

- [ ] **Step 3: Report completion**

Summarize: all 5 PR #1003 review items closed (daemon_jobs.agent_id persistence, capability_grants merge-not-replace, --dry-run/--as-agent preview fix, CORE_FLEET restriction, new test coverage), full suite green, ready for `superpowers:finishing-a-development-branch`.
