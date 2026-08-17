# Agent-Roles-Charters Phase 2 (Memory + Gated Learning) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Role/`agent_id`-driven dispatches (no `story_id`) read from and write to the existing
`capability_scores`/`capability_ratings` learning pipeline via a synthetic per-org-role placeholder story, closing
the gap where `_harness_for_org_role`'s static baseline never learns from real outcomes — plus a `--static-baseline`
opt-out flag to force the raw baseline pick on demand.

**Architecture:** A deterministic synthetic `story_id` (`__role_dispatch_<org_role>__`) lets role-driven dispatches
reuse the exact same `_best_agent_for_story()` / `_write_capability_rating()` machinery real stories already use,
with zero changes to `resolve_dispatch_harness()`'s control flow — only what `story_id` value reaches it. The
synthetic ID is never persisted to `daemon_jobs.story_id` or any other real-story-consuming field.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest, argparse (existing `synlynk` CLI conventions — no new deps).

---

## Reference: Spec

Full design: `docs/superpowers/specs/2026-08-17-agent-roles-phase2-memory-gated-learning-design.md`

## File Structure

- **Modify `synlynk/_constants.py`**: add `_role_dispatch_story_id(org_role)` — pure function, no DB access, safe
  for both `dispatch.py` and `jobs.py` to import directly without circularity.
- **Modify `synlynk/jobs.py`**: add `_ensure_role_dispatch_story(conn, org_role, story_id)` (seeding helper, mirrors
  `_seed_capability_ledger_from_baseline`) and change `_write_capability_rating()` to use it when `story_id` is
  falsy but a role can be resolved.
- **Modify `synlynk/dispatch.py`**: change `resolve_dispatch_harness()` to try the synthetic-story lookup before
  falling back to `_harness_for_org_role`; add `static_baseline` parameter threaded through `dispatch_agent()`,
  `_render_dispatch_preview()`, and the job-dict construction (add `agent_id` / `resolved_agent_role` fields so the
  write path in `jobs.py` can resolve role without a DB round-trip).
- **Modify `synlynk/cli.py`**: add `--static-baseline` argparse flag, thread through both the dry-run preview call
  and the live `dispatch_agent()` call.
- **Modify `synlynk/__init__.py`**: export `_ensure_role_dispatch_story` and `_role_dispatch_story_id` alongside the
  existing `_best_agent_for_story` / `_write_capability_rating` exports, so tests and `_pkg()` lookups can reach
  them the same way.
- **Test files**: `tests/test_capability_scoring.py` (write-path + seeding tests, alongside existing
  `_write_capability_rating` / `_best_agent_for_story` tests), `tests/test_dispatch_github_identity.py` or a new
  `tests/test_resolve_dispatch_harness.py` (read-path tests — created fresh since no existing test file covers
  `resolve_dispatch_harness` directly), `tests/test_synlynk.py` (CLI flag threading test, following the existing
  `--force-agent` test pattern in that file).

---

### Task 1: Synthetic Story ID Helper + Seeding Function

**Files:**
- Modify: `synlynk/_constants.py` (append near the end of the file)
- Modify: `synlynk/jobs.py:845` (add new function immediately above `_write_capability_rating`)
- Modify: `synlynk/__init__.py:179-191` (export the new seeding function)
- Test: `tests/test_capability_scoring.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_capability_scoring.py` (append at end of file):

```python
# --- Phase 2: role-dispatch synthetic story ---

def test_role_dispatch_story_id_is_deterministic():
    from synlynk._constants import _role_dispatch_story_id
    assert _role_dispatch_story_id("dev") == "__role_dispatch_dev__"
    assert _role_dispatch_story_id("dev") == _role_dispatch_story_id("dev")
    assert _role_dispatch_story_id("qa") != _role_dispatch_story_id("dev")


def test_ensure_role_dispatch_story_seeds_synthetic_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, _ensure_role_dispatch_story
    from synlynk._constants import _role_dispatch_story_id

    conn = _get_db()
    story_id = _role_dispatch_story_id("dev")
    _ensure_role_dispatch_story(conn, "dev", story_id)
    row = conn.execute(
        "SELECT story_id, title, discipline, org_domain, industry, phase, role "
        "FROM stories WHERE story_id=?",
        (story_id,),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "__role_dispatch_dev__"
    assert "synthetic, not a real story" in row[1]
    assert row[2] == "general"
    assert row[3] == "general"
    assert row[4] == "general"
    assert row[5] == "build"
    assert row[6] == "dev"


def test_ensure_role_dispatch_story_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, _ensure_role_dispatch_story
    from synlynk._constants import _role_dispatch_story_id

    conn = _get_db()
    story_id = _role_dispatch_story_id("qa")
    _ensure_role_dispatch_story(conn, "qa", story_id)
    _ensure_role_dispatch_story(conn, "qa", story_id)  # second call must not raise or duplicate
    count = conn.execute(
        "SELECT COUNT(*) FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()[0]
    conn.close()
    assert count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_capability_scoring.py -k "role_dispatch_story" -v`
Expected: FAIL — `ImportError: cannot import name '_role_dispatch_story_id'` (and `_ensure_role_dispatch_story`).

- [ ] **Step 3: Add `_role_dispatch_story_id` to `synlynk/_constants.py`**

Append at the end of `synlynk/_constants.py`:

```python


def _role_dispatch_story_id(org_role: str) -> str:
    """Deterministic synthetic story_id for role/agent_id-driven dispatches with no real story.

    Pure function — safe to call from both the read path (resolve_dispatch_harness,
    no DB access) and the write path (_write_capability_rating, seeds this ID lazily).
    Never persisted to daemon_jobs.story_id or any other real-story-consuming field.
    """
    return f"__role_dispatch_{org_role}__"
```

- [ ] **Step 4: Add `_ensure_role_dispatch_story` to `synlynk/jobs.py`**

Insert immediately before `_write_capability_rating` at `synlynk/jobs.py:845` (i.e. right after
`_count_tool_calls`, before the existing `def _write_capability_rating(job: dict, log_text: str) -> None:` line):

```python
def _ensure_role_dispatch_story(conn, org_role: str, story_id: str) -> None:
    """Lazily seeds the synthetic per-org-role story row (Phase 2 role-dispatch learning).

    Mirrors _seed_capability_ledger_from_baseline's INSERT OR IGNORE pattern in
    capability_sweep.py — idempotent, safe under concurrent dispatches for the same role.
    Role-dispatch capability signal is intentionally coarse (discipline="general" for every
    role) rather than discipline-aware; real story_id-based dispatches keep their own
    discipline value untouched.
    """
    conn.execute(
        "INSERT OR IGNORE INTO stories "
        "(story_id, title, discipline, org_domain, industry, phase, role) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            story_id,
            f"Role-dispatch capability signal ({org_role}) — synthetic, not a real story",
            "general",
            "general",
            "general",
            "build",
            org_role,
        ),
    )
    conn.commit()

```

- [ ] **Step 5: Export `_ensure_role_dispatch_story` from `synlynk/__init__.py`**

Read `synlynk/__init__.py:179-191` first to see the exact current import block shape (it currently reads
`from synlynk.jobs import (` followed by `_best_agent_for_story,` and other names). Add
`_ensure_role_dispatch_story,` to that same `from synlynk.jobs import (...)` tuple, alphabetically placed or
adjacent to `_best_agent_for_story` — match whatever ordering convention the existing block already uses.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_capability_scoring.py -k "role_dispatch_story" -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add synlynk/_constants.py synlynk/jobs.py synlynk/__init__.py tests/test_capability_scoring.py
git commit -m "feat: add synthetic role-dispatch story seeding helper (Phase 2)"
```

---

### Task 2: Read Path — `resolve_dispatch_harness()` Synthetic-Story Lookup + `static_baseline` Flag

**Files:**
- Modify: `synlynk/dispatch.py:1990-2032` (`resolve_dispatch_harness`)
- Modify: `synlynk/dispatch.py:833-862` (`_render_dispatch_preview` — thread `static_baseline` through)
- Test: `tests/test_resolve_dispatch_harness.py` (new file)

**Context:** `resolve_dispatch_harness()` currently: resolves `resolved_agent_role` from `agent_id` if given, returns
`agent` immediately if `force_agent`, then tries `_best_agent_for_story(story_id)` (only if `story_id` truthy),
then falls back to `_harness_for_org_role(resolved_agent_role, ...)` if nothing picked yet. This task inserts a new
middle step: when nothing picked yet and `resolved_agent_role` exists, try `_best_agent_for_story` again against
the synthetic per-role story_id, before falling through to the static baseline. A new `static_baseline` parameter
disables both the real-story and synthetic-story lookups uniformly.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resolve_dispatch_harness.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _register_agent(tmp_path, monkeypatch, agent_id, org_role):
    """Registers a workspace agent with the given org role, returning its agent_id."""
    monkeypatch.chdir(tmp_path)
    from synlynk import agent_store
    agent_store.init_agent(agent_id, role=org_role, charter="test agent")
    return agent_id


def test_role_only_dispatch_uses_synthetic_story_capability_score(tmp_path, monkeypatch):
    """A role-only dispatch (no story_id) with an existing synthetic-story rating picks the
    learned harness, not the alphabetical-first static baseline."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, agent_store
    from synlynk._constants import _role_dispatch_story_id
    from synlynk.dispatch import resolve_dispatch_harness

    agent_store.init_agent("dev-agent-1", role="architect", charter="test")
    story_id = _role_dispatch_story_id("architect")
    conn = _get_db()
    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title, discipline, org_domain, industry, phase, role) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (story_id, "seed", "general", "general", "general", "build", "architect"),
    )
    # "codex" would never win _harness_for_org_role's static architect pick (codex isn't
    # tagged "architect" in AGENT_CAPABILITY_BASELINES) — so a codex pick here proves the
    # synthetic-story score path fired, not the static fallback.
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, discipline, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (story_id, "codex", "codex-1", "general", "general", "general", "build", "auto", 9.5, 9.5),
    )
    conn.commit()
    conn.close()

    result = resolve_dispatch_harness("claude", agent_id="dev-agent-1")
    assert result == "codex"


def test_role_only_dispatch_cold_start_falls_back_to_static_baseline(tmp_path, monkeypatch):
    """No prior synthetic-story rating for this role -> unchanged _harness_for_org_role pick."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import agent_store
    from synlynk.dispatch import resolve_dispatch_harness

    agent_store.init_agent("dev-agent-2", role="architect", charter="test")
    result = resolve_dispatch_harness("claude", agent_id="dev-agent-2")
    # architect baseline role: "agy" sorts first alphabetically among CORE_FLEET agents
    # tagged "architect" in AGENT_CAPABILITY_BASELINES.
    assert result == "agy"


def test_static_baseline_forces_static_pick_over_synthetic_story_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, agent_store
    from synlynk._constants import _role_dispatch_story_id
    from synlynk.dispatch import resolve_dispatch_harness

    agent_store.init_agent("dev-agent-3", role="architect", charter="test")
    story_id = _role_dispatch_story_id("architect")
    conn = _get_db()
    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title, discipline, org_domain, industry, phase, role) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (story_id, "seed", "general", "general", "general", "build", "architect"),
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, discipline, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (story_id, "codex", "codex-1", "general", "general", "general", "build", "auto", 9.5, 9.5),
    )
    conn.commit()
    conn.close()

    result = resolve_dispatch_harness("claude", agent_id="dev-agent-3", static_baseline=True)
    assert result == "agy"  # static baseline pick, ignoring the codex score


def test_static_baseline_forces_static_pick_even_with_real_story_id_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, agent_store
    from synlynk.dispatch import resolve_dispatch_harness

    agent_store.init_agent("dev-agent-4", role="architect", charter="test")
    conn = _get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, discipline, org_domain, industry, phase) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("story-real-1", "Real story", "general", "general", "general", "build"),
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, discipline, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-real-1", "codex", "codex-1", "general", "general", "general", "build", "auto", 9.5, 9.5),
    )
    conn.commit()
    conn.close()

    result = resolve_dispatch_harness(
        "claude", agent_id="dev-agent-4", story_id="story-real-1", static_baseline=True
    )
    assert result == "agy"  # static baseline pick, ignoring the real story_id's codex score
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_resolve_dispatch_harness.py -v`
Expected: FAIL — `TypeError: resolve_dispatch_harness() got an unexpected keyword argument 'static_baseline'`
(first three fail on that; the cold-start test may fail with an assertion mismatch since it should already pass
under current behavior — confirm which fail for which reason before proceeding).

- [ ] **Step 3: Implement the read-path change**

Replace `synlynk/dispatch.py:1990-2032` (the full current `resolve_dispatch_harness` function body) with:

```python
def resolve_dispatch_harness(agent: str, agent_id: str = None, story_id: str = None,
                              force_agent: bool = False, requires_gh_write: bool = False,
                              static_baseline: bool = False) -> str:
    """Resolve which harness a dispatch will actually run on.

    Side-effect-free (no subprocess spawn, no DB write) so both the live
    dispatch path and the --dry-run preview path can call it and see the
    same answer. Raises ValueError for an unregistered/disabled agent_id,
    same as the live path always has.

    static_baseline=True bypasses learned capability-score routing entirely
    (both real story_id and synthetic role-dispatch story lookups) and
    forces the deterministic _harness_for_org_role static pick.
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
    if story_id and not static_baseline:
        best_agent = _pkg("_best_agent_for_story")
        if best_agent:
            best = best_agent(story_id)
            if best and best in baselines_map:
                picked = best
    if picked is None and resolved_agent_role and not static_baseline:
        from synlynk._constants import _role_dispatch_story_id
        synthetic_story_id = _role_dispatch_story_id(resolved_agent_role)
        best_agent = _pkg("_best_agent_for_story")
        if best_agent:
            best = best_agent(synthetic_story_id)
            if best and best in baselines_map:
                picked = best
    if picked is None and resolved_agent_role:
        picked = _harness_for_org_role(resolved_agent_role, baselines_map, requires_gh_write)
    return picked or agent
```

- [ ] **Step 4: Thread `static_baseline` through `_render_dispatch_preview`**

Replace `synlynk/dispatch.py:833-840`:

```python
def _render_dispatch_preview(agent: str, task: str, context_mode: str,
                              agent_id: str = None, story_id: str = None,
                              force_agent: bool = False, requires_gh_write: bool = False,
                              static_baseline: bool = False) -> dict:
    """Compute task/context digest data for dispatch inspection."""
    agent = resolve_dispatch_harness(
        agent, agent_id=agent_id, story_id=story_id,
        force_agent=force_agent, requires_gh_write=requires_gh_write,
        static_baseline=static_baseline,
    )
```

(Leave the rest of `_render_dispatch_preview`, lines 841-862, unchanged.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_resolve_dispatch_harness.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Run the full existing dispatch test suite to check for regressions**

Run: `pytest tests/test_dispatch.py tests/test_dispatch_github_identity.py tests/test_dispatch_cycle.py tests/test_agy_dispatch_fix.py -v`
Expected: PASS, no regressions (this task changed `resolve_dispatch_harness`'s internals but not its behavior for
any call site that doesn't pass `static_baseline` and has no role-dispatch synthetic story seeded yet — cold-start
behavior is identical to before).

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py tests/test_resolve_dispatch_harness.py
git commit -m "feat: read learned routing for role-only dispatches via synthetic story (Phase 2)"
```

---

### Task 3: Write Path — `_write_capability_rating()` Records Role-Only Dispatches

**Files:**
- Modify: `synlynk/dispatch.py:2532-2563` (job dict construction — add `agent_id` / `resolved_agent_role` fields)
- Modify: `synlynk/jobs.py:845-856` (`_write_capability_rating` — resolve synthetic story when `story_id` is empty)
- Test: `tests/test_capability_scoring.py`

**Context:** `_write_capability_rating(job, log_text)` reads `job.get("story_id")`. Today's `job` dict — the one
appended to `.synlynk/jobs.json` inside `dispatch_agent()` — does **not** carry `agent_id` or `resolved_agent_role`
at all (only the separate `daemon_jobs` SQLite table has an `agent_id` column, added in PR #1022). This task adds
both fields to the jobs.json job dict so the completion-time write path can resolve org role without a DB
round-trip, then updates `_write_capability_rating` to seed and use the synthetic story when `story_id` is empty.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_capability_scoring.py` (append at end of file):

```python
def test_write_capability_rating_role_only_job_writes_synthetic_story_rating(tmp_path, monkeypatch):
    """A completed job with no story_id but a resolved_agent_role writes a capability_ratings
    row keyed to the synthetic role-dispatch story, seeding it on first write."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import synlynk as sl
    from synlynk._constants import _role_dispatch_story_id
    monkeypatch.setattr(sl, "_sign_capability_rating", lambda d: "")

    job = {
        "story_id": "", "agent": "claude", "model_at_dispatch": "claude-3",
        "resolved_agent_role": "dev",
        "started_at": "2026-06-01T10:00:00", "ended_at": "2026-06-01T10:05:00",
        "exit_code": 0, "dispatch_rework": 0, "micro_rework": 0,
    }
    sl._write_capability_rating(job, "19 passed in 2.1s")

    story_id = _role_dispatch_story_id("dev")
    conn = sl._get_db()
    story_row = conn.execute(
        "SELECT title FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    rating_row = conn.execute(
        "SELECT agent, role, discipline FROM capability_ratings WHERE story_id=?", (story_id,)
    ).fetchone()
    conn.close()
    assert story_row is not None
    assert "synthetic, not a real story" in story_row[0]
    assert rating_row is not None
    assert rating_row[0] == "claude"
    assert rating_row[1] == "dev"
    assert rating_row[2] == "general"


def test_write_capability_rating_role_only_second_job_does_not_reseed(tmp_path, monkeypatch):
    """A second completed job for the same role writes a second rating without duplicating
    the synthetic stories row."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import synlynk as sl
    from synlynk._constants import _role_dispatch_story_id
    monkeypatch.setattr(sl, "_sign_capability_rating", lambda d: "")

    job_common = {
        "story_id": "", "agent": "claude", "model_at_dispatch": "claude-3",
        "resolved_agent_role": "qa",
        "started_at": "2026-06-01T10:00:00", "ended_at": "2026-06-01T10:05:00",
        "exit_code": 0, "dispatch_rework": 0, "micro_rework": 0,
    }
    sl._write_capability_rating(dict(job_common), "19 passed in 2.1s")
    sl._write_capability_rating(dict(job_common), "20 passed in 2.3s")

    story_id = _role_dispatch_story_id("qa")
    conn = sl._get_db()
    story_count = conn.execute(
        "SELECT COUNT(*) FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()[0]
    rating_count = conn.execute(
        "SELECT COUNT(*) FROM capability_ratings WHERE story_id=?", (story_id,)
    ).fetchone()[0]
    conn.close()
    assert story_count == 1
    assert rating_count == 2


def test_write_capability_rating_no_story_no_role_still_no_ops(tmp_path, monkeypatch):
    """Regression check: a job with neither story_id nor a resolvable role still early-returns
    with no rating written, unchanged from pre-Phase-2 behavior."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import synlynk as sl
    monkeypatch.setattr(sl, "_sign_capability_rating", lambda d: "")

    job = {
        "story_id": "", "agent": "claude", "model_at_dispatch": "claude-3",
        "started_at": "2026-06-01T10:00:00", "ended_at": "2026-06-01T10:05:00",
        "exit_code": 0, "dispatch_rework": 0, "micro_rework": 0,
    }
    sl._write_capability_rating(job, "19 passed in 2.1s")

    conn = sl._get_db()
    count = conn.execute("SELECT COUNT(*) FROM capability_ratings").fetchone()[0]
    conn.close()
    assert count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_capability_scoring.py -k "write_capability_rating_role_only or no_story_no_role" -v`
Expected: FAIL — the first two tests fail (no rows written, since `job.get("story_id", "")` is empty and the
function returns immediately today); the third test currently passes already (confirm it does, as a baseline).

- [ ] **Step 3: Add `agent_id` and `resolved_agent_role` to the jobs.json job dict**

In `synlynk/dispatch.py`, the job dict is built at line 2532-2563 inside `dispatch_agent()`. Add two new keys to
that dict literal, immediately after `"task_type": task_type or "",` (currently the last key before the closing
`}`):

```python
        "task_type": task_type or "",
        "agent_id": agent_id or "",
        "resolved_agent_role": resolved_agent_role or "",
    }
```

(`resolved_agent_role` is already computed earlier in `dispatch_agent()`, at lines 2059-2068 — no new resolution
logic needed, just persisting the value that already exists in scope.)

- [ ] **Step 4: Update `_write_capability_rating` to seed and use the synthetic story**

Replace `synlynk/jobs.py:845-856`:

```python
def _write_capability_rating(job: dict, log_text: str) -> None:
    """Writes a capability_ratings row for a completed job."""
    story_id = job.get("story_id", "")
    org_role = None
    if not story_id:
        org_role = job.get("resolved_agent_role") or ""
        if not org_role:
            return
        from synlynk._constants import _role_dispatch_story_id
        story_id = _role_dispatch_story_id(org_role)

    conn = _pkg("_get_db")()
    if org_role:
        _ensure_role_dispatch_story(conn, org_role, story_id)
    exists = conn.execute("SELECT 1 FROM stories WHERE story_id=?", (story_id,)).fetchone()
    if not exists:
        conn.close()
        return
```

(The rest of the function, from `agent = job.get("agent", "unknown")` onward, is unchanged — it already reads
`story_id` from the local variable, which now holds either the real story_id or the resolved synthetic one.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_capability_scoring.py -k "write_capability_rating_role_only or no_story_no_role" -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Add the isolation-invariant test**

Add to `tests/test_capability_scoring.py` (append at end of file):

```python
def test_role_only_job_never_persists_synthetic_story_id_to_daemon_jobs(tmp_path, monkeypatch):
    """The synthetic story_id must never leak into daemon_jobs.story_id — role-only dispatches
    keep story_id NULL/empty in job persistence exactly as before Phase 2."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    from synlynk.dispatch import _ensure_daemon_job_agent_id_column

    conn = _get_db()
    _ensure_daemon_job_agent_id_column(conn)
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, priority, depends_on, "
        "agent_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("job-role-only-1", "claude", "do work", None, "completed", 5, "[]", "dev-agent-1"),
    )
    conn.commit()
    row = conn.execute(
        "SELECT story_id FROM daemon_jobs WHERE job_id=?", ("job-role-only-1",)
    ).fetchone()
    conn.close()
    assert row[0] is None
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_capability_scoring.py -k test_role_only_job_never_persists_synthetic_story_id_to_daemon_jobs -v`
Expected: PASS (this test asserts an invariant that this task's changes never touch `daemon_jobs.story_id` — it
passes by construction since no code in this task writes to that column, but it locks the invariant in as a
regression guard for future changes).

- [ ] **Step 8: Commit**

```bash
git add synlynk/dispatch.py synlynk/jobs.py tests/test_capability_scoring.py
git commit -m "feat: record capability ratings for role-only dispatches via synthetic story (Phase 2)"
```

---

### Task 4: `--static-baseline` CLI Flag

**Files:**
- Modify: `synlynk/cli.py:611-616` (argparse flag definition)
- Modify: `synlynk/cli.py:1142-1188` (dry-run preview call + live `dispatch_agent()` call)
- Modify: `synlynk/dispatch.py:2035-2058` (`dispatch_agent()` signature + `resolve_dispatch_harness` call)
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test**

First, find the existing `--force-agent` CLI threading test to confirm the exact pattern to mirror:

Run: `grep -n "force_agent\|force-agent" tests/test_synlynk.py`

Add a new test to `tests/test_synlynk.py`, placed near whatever existing test that grep surfaces (same file, same
style — use `argparse`/`main()` invocation consistent with the existing `--force-agent` test's structure). If the
existing pattern invokes `main()` with `sys.argv` patched and asserts on a mocked `dispatch_agent` call, follow that
exact shape:

```python
def test_dispatch_static_baseline_flag_threads_to_resolve_dispatch_harness(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import agent_store
    agent_store.init_agent("dev-agent-cli-1", role="architect", charter="test")

    from synlynk.dispatch import _render_dispatch_preview

    captured = {}
    real_resolve = None
    import synlynk.dispatch as dispatch_mod

    def fake_resolve(*args, **kwargs):
        captured["static_baseline"] = kwargs.get("static_baseline")
        return "agy"

    monkeypatch.setattr(dispatch_mod, "resolve_dispatch_harness", fake_resolve)

    import sys
    from synlynk.cli import main
    monkeypatch.setattr(sys, "argv", [
        "synlynk", "dispatch", "--as-agent", "dev-agent-cli-1",
        "--task", "do the thing", "--static-baseline", "--dry-run",
    ])
    main()
    out = capsys.readouterr().out
    assert captured.get("static_baseline") is True
    assert "agent:        agy" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_synlynk.py -k test_dispatch_static_baseline_flag_threads_to_resolve_dispatch_harness -v`
Expected: FAIL — `error: unrecognized arguments: --static-baseline`

- [ ] **Step 3: Add the argparse flag**

In `synlynk/cli.py`, immediately after the existing `--force-agent` flag definition at lines 611-612:

```python
    dispatch_parser.add_argument("--force-agent", action="store_true", dest="force_agent",
        help="Bypass capability routing — dispatch to the exact agent specified")
    dispatch_parser.add_argument("--static-baseline", action="store_true", dest="static_baseline",
        help="Bypass learned capability-score routing for this dispatch — use the "
             "deterministic static baseline pick instead (Phase 2, #914-adjacent)")
```

- [ ] **Step 4: Thread the flag through the dry-run preview call**

In `synlynk/cli.py`, the dry-run branch at lines 1150-1157 calls `_render_dispatch_preview(...)`. Add
`static_baseline=getattr(args, "static_baseline", False),` as a new keyword argument:

```python
                preview = _render_dispatch_preview(
                    args.agent or (known_agents[0] if not resolved_agent_id else None),
                    args.task, context_mode,
                    agent_id=resolved_agent_id,
                    story_id=getattr(args, "story_id", None),
                    force_agent=getattr(args, "force_agent", False),
                    requires_gh_write=getattr(args, "requires_gh_write", False),
                    static_baseline=getattr(args, "static_baseline", False),
                )
```

- [ ] **Step 5: Thread the flag through the live dispatch call**

In `synlynk/cli.py`, the live `dispatch_agent(...)` call at lines 1175-1188. Add
`static_baseline=getattr(args, "static_baseline", False),` as a new keyword argument, placed after
`force_agent=getattr(args, "force_agent", False),`:

```python
            job = dispatch_agent(args.agent or known_agents[0], args.task, story_id=args.story_id,
                                 agent_id=resolved_agent_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 static_baseline=getattr(args, "static_baseline", False),
                                 requires_gh_write=getattr(args, "requires_gh_write", False),
                                 task_type=getattr(args, "task_type", None),
                                 requires=getattr(args, "requires", []),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False),
                                 base=getattr(args, "base", None),
                                 grants=getattr(args, "grant", []),
                                 revokes=getattr(args, "revoke", []),
                                 issue=getattr(args, "issue", None),
                                 scope_paths=getattr(args, "scope_paths", []),
                                 session_id=getattr(args, "session_id", None))
```

- [ ] **Step 6: Add `static_baseline` to `dispatch_agent()`'s signature and forward it**

In `synlynk/dispatch.py`, `dispatch_agent()`'s signature at lines 2035-2050. Add `static_baseline: bool = False,`
as a new parameter, placed after `force_agent: bool = False,`:

```python
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   agent_id: str = None,
                   force_agent: bool = False,
                   static_baseline: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   requires_gh_write: bool = False,
                   task_type: str = None,
                   requires: list = None,
                   grants: list = None,
                   revokes: list = None,
                   job_id: str = None,
                   issue: int = None,
                   base: str = None,
                   scope_paths: list = None,
                   session_id: str = None) -> dict:
```

Then in the body, the `resolve_dispatch_harness(...)` call at lines 2055-2058 — add `static_baseline=static_baseline,`:

```python
    agent = resolve_dispatch_harness(
        agent, agent_id=agent_id, story_id=story_id,
        force_agent=force_agent, requires_gh_write=requires_gh_write,
        static_baseline=static_baseline,
    )
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_synlynk.py -k test_dispatch_static_baseline_flag_threads_to_resolve_dispatch_harness -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add synlynk/cli.py synlynk/dispatch.py tests/test_synlynk.py
git commit -m "feat: add --static-baseline dispatch flag to bypass learned routing (Phase 2)"
```

---

### Task 5: Full-Suite Verification

**Files:** None modified — verification only.

- [ ] **Step 1: Run the complete test suite**

Run: `pytest -q`
Expected: all tests pass (existing count plus the 3 + 4 + 4 + 1 new tests from Tasks 1-4 — 12 new tests total), 0
failures.

- [ ] **Step 2: Spot-check the isolation invariant against a live dry-run**

Run: `python3 bin/synlynk.py agent init --role dev --charter "test dev agent" 2>&1 | tail -5` (or the current
`synlynk agent init` invocation shape — check `synlynk agent init --help` if this fails) to register a test agent
in a scratch directory, then:

Run: `python3 bin/synlynk.py dispatch --as-agent <the-registered-alias> --task "no-op verification task" --dry-run`
Expected: prints a preview with a concrete `agent:` line (not `agent: None`), confirming the synthetic-story read
path resolves cleanly end-to-end through the CLI on a cold-start role (no prior rating yet, so it falls through to
the static baseline pick — this confirms Task 2's fallback path, not the learned path, since this is a fresh
scratch DB).

- [ ] **Step 3: Report completion**

No commit needed for this task (verification only). If any test fails, return to the relevant task above, fix, and
re-run the full suite before proceeding to `finishing-a-development-branch`.
