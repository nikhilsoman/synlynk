# Agent-Roles-Charters Phase 1 — Follow-Up Cleanup — Design

**Date:** 2026-08-16
**Status:** Approved (pending final user sign-off on this written doc)
**Author:** Claude (pm), brainstormed with Nikhil Soman
**Parent:** `docs/superpowers/specs/2026-08-16-agent-dispatch-integration-design.md` (Phase 1, PR #1003)

## 1. Motivation

PR #1003 shipped `synlynk agent init/list/show/edit/disable` and `agent_id`-driven dispatch
integration. Its non-authoring review (Grok, `gh pr view 1003`) approved and merged the PR but flagged
five non-blocking follow-up items. This spec closes all five in one small, same-file-neighborhood PR —
distinct from the larger "Phase 2: Memory + gated learning" scope in the parent roadmap
(`docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` §10), which is tracked
separately.

None of these five items requires new infrastructure or design risk — each is a small, pattern-following
fix in code that already exists.

## 2. Scope

**In scope — all five review notes:**
1. `agent_id` not persisted on `daemon_jobs`
2. `capability_grants` clobbered on `agent edit`
3. `--dry-run` + `--as-agent` (no explicit harness) preview bug
4. `_harness_for_org_role` sort-order includes non-fleet harnesses
5. Two missing test cases (story_id/agent_id precedence, `--as-agent` threading)

**Explicitly not in scope:**
- Any display/grouping UI for jobs-by-agent (e.g. a "recent jobs" section on `synlynk agent show`) — the
  review's stated purpose ("so jobs can be grouped by workspace agent") is satisfied by the column existing
  and being queryable; a dedicated display surface is deferred as a separate future item if ever needed.
- `capability_grants` enforcement — that's Phase 3 (capability registry + scoped access grants) per the
  parent roadmap §10, unscheduled.
- The `dispatch_agent(agent=...)` parameter rename (harness vs. agent terminology) — already filed as a
  follow-up per the parent spec §6, tracked separately.
- Real Phase 2 (memory + gated learning) — separate spec, separate brainstorm.

## 3. Item 1 — `daemon_jobs.agent_id` Persistence

**Problem:** `dispatch_agent()` resolves `agent_id` (when provided) into `resolved_agent_role`, but the
resolved `agent_id` itself is never written to `daemon_jobs`. Only `session_id` (TPM/session MVP,
PRs #934-959) is currently persisted per-job. Once dispatch returns, a job's originating workspace agent
identity is lost.

**Fix — mirror the existing `session_id` migration pattern exactly** (`synlynk/dispatch.py`,
`_ensure_daemon_job_session_column`):

- New `synlynk/db.py` migration: `ALTER TABLE daemon_jobs ADD COLUMN agent_id TEXT` (guarded by
  `PRAGMA table_info` check, same as the existing `session_id`/`context_mode`/`requires_gh_write` migrations
  at `synlynk/db.py:301-349`).
- New `_ensure_daemon_job_agent_id_column(conn)` helper in `synlynk/dispatch.py`, called alongside
  `_ensure_daemon_job_context_columns` / `_ensure_daemon_job_session_column` /
  `_ensure_daemon_job_gh_write_columns` at `dispatch.py:2533-2535`.
- Add `agent_id` to both `daemon_jobs` write paths in `dispatch_agent()`:
  - The `UPDATE ... SET ... session_id=COALESCE(session_id, ?) WHERE job_id=?` branch
    (`dispatch.py:2542-2561`) — add `agent_id=COALESCE(agent_id, ?)`, same COALESCE-preserve semantics as
    `session_id`.
  - The `INSERT OR REPLACE INTO daemon_jobs (...)` branch (`dispatch.py:2564-2589`) — add `agent_id` to the
    column list and values tuple.
  - The quota-deferred `INSERT INTO daemon_jobs` branch (`dispatch.py:2112-2118`) — add `agent_id` to the
    column list and values tuple (the `agent_id` parameter passed into `dispatch_agent()`, not
    `resolved_agent_role`).
- The value written is the `agent_id` parameter passed into `dispatch_agent()` (the UUID), not
  `resolved_agent_role` (the role string) — `daemon_jobs.agent_id` identifies *which* workspace agent
  dispatched the job, matching `agent_store`'s registry key.
- No new display surface (§2).

## 4. Item 2 — `capability_grants` Clobbered on `agent edit`

**Problem:** `regenerate_agent_projection(agent_id, repo_overrides=None)`
(`synlynk/agent_store.py:338-352`) fully replaces the projection's `overrides` dict on every call — it does
not read the existing file first. `cmd_agent_init` (`agent_cli.py:53-55`) correctly seeds
`capability_grants: {}` on a brand-new agent. But `cmd_agent_edit` (`agent_cli.py:115`) *also* hardcodes
`repo_overrides={"capability_grants": {}}` on every charter edit, unconditionally wiping any overrides a
future mechanism (e.g. Phase 3's capability registry) may have written in between — a Phase 3 footgun.

**Fix:**
- Change `regenerate_agent_projection()` to **merge-not-replace**: before writing, read the existing
  projection file at `.synlynk/agents/<agent_id>.yaml` if it exists, parse its `overrides` block, and merge
  `repo_overrides` on top of it (new keys win, existing keys not present in `repo_overrides` are preserved).
  If no projection file exists yet (first `regenerate_agent_projection` call for an agent), start from `{}`
  as today.
- `cmd_agent_init` is unaffected — for a new agent there is no existing file, so the merge starts from `{}`
  and `capability_grants: {}` is still seeded correctly.
- `cmd_agent_edit` drops its hardcoded `repo_overrides={"capability_grants": {}}` entirely and calls
  `agent_store.regenerate_agent_projection(agent_id)` with no overrides — existing `overrides` (including
  `capability_grants`, whatever they are at edit time) pass through untouched.
- This changes `regenerate_agent_projection`'s semantics for its two existing callers plus tests; verified
  no caller relies on replace-not-merge behavior (`grep` confirms only `agent_cli.py`'s two call sites and
  `tests/test_agent_store.py` use this function — test expectations are updated as part of this same task,
  see §7).

## 5. Item 3 — `--dry-run` + `--as-agent` (No Explicit Harness) Preview Bug

**Problem:** In `synlynk/cli.py`'s `dispatch` command handler, the dry-run branch
(`cli.py:1142-1166`) calls `_render_dispatch_preview(args.agent, args.task, context_mode)` using
`args.agent` directly. When the user runs `synlynk dispatch --as-agent <id> --task "..." --dry-run` without
an explicit harness positional, `args.agent` is `None` and the preview never invokes the same
role→harness auto-selection the live path uses (`dispatch_agent()`'s internal resolution at
`dispatch.py:2001-2020`) — the preview prints `agent: None` instead of the harness that would actually be
selected.

**Fix:** Extract the live path's harness-resolution step (`resolved_agent_role` lookup +
`_harness_for_org_role` fallback + existing `_best_agent_for_story`-style auto-select,
`dispatch.py:1985-2020`) into a standalone helper function, `resolve_dispatch_harness(agent, agent_id,
story_id, force_agent, requires_gh_write)`, callable without side effects (no subprocess spawn, no DB
write). `dispatch_agent()`'s body calls this helper instead of inlining the logic. `cli.py`'s dry-run branch
calls the same helper before building the preview, so `preview['agent']` reflects the harness that would
actually be picked — including when only `--as-agent` was given.

## 6. Item 4 — `_harness_for_org_role` Sort-Order Bug

**Problem:** `_harness_for_org_role` (`dispatch.py:32-51`) iterates `sorted(baselines_map)` — the full
`AGENT_CAPABILITY_BASELINES` key set, which includes experimental/non-fleet entries (e.g. `local`). Today's
winner is unaffected (`agy`/`claude` sort first alphabetically), but a later baseline addition could win the
pick over a real fleet harness purely by sorting earlier.

**Fix:** Restrict the iteration to `CORE_FLEET` (`synlynk._constants.CORE_FLEET`, already used as a guard
elsewhere at `dispatch.py:2193`): `for name in sorted(n for n in baselines_map if n in CORE_FLEET):`.

## 7. Item 5 — Missing Test Coverage

**`tests/test_dispatch.py`:**
- `test_dispatch_agent_story_id_wins_over_agent_id_role_when_both_present` — construct a scenario where
  `story_id` has an existing `_best_agent_for_story` match for a *different* harness than
  `_harness_for_org_role(resolved_agent_role, ...)` would pick; assert the story-based match wins (mirrors
  the existing `story_id`-only auto-selection tests, confirming §5's resolution-order precedence: story-based
  routing is tried first, `_harness_for_org_role` is the fallback only when story-based routing yields
  nothing).

**`tests/test_cli.py`** (or wherever `--as-agent` CLI routing is currently tested):
- `test_cli_dispatch_as_agent_without_explicit_harness_threads_agent_id` — invoke the `dispatch` CLI command
  with `--as-agent <alias>` and no harness positional; assert `dispatch_agent()` (mocked) is called with the
  resolved `agent_id` keyword argument set, not `None`.

**`tests/test_agent_store.py`** (updated for §4's merge-not-replace change):
- Existing tests (`test_regenerate_agent_projection_writes_flat_yaml`,
  `test_regenerate_agent_projection_is_idempotent`,
  `test_regenerate_agent_projection_path_is_gitignored`, the `pinned_role` test at line 332) are reviewed
  and updated where they assert replace-not-merge semantics; a new test asserts a second
  `regenerate_agent_projection(agent_id, repo_overrides={"new_key": "value"})` call preserves an
  `overrides` key written by a prior call that the second call's `repo_overrides` doesn't mention.

## 8. Error Handling

No new error paths — all five items are internal-logic/persistence fixes with no new user-facing failure
modes. Existing error handling (disabled/unregistered `agent_id` raising `ValueError`, `RevisionConflictError`
on stale charter edits, CLI resolution failures exiting 1) is unchanged.

## 9. Out of Scope for This Spec

- `capability_grants` enforcement (Phase 3, unscheduled — parent spec §10)
- Display/grouping UI for jobs-by-agent (§2)
- `dispatch_agent(agent=...)` parameter rename (parent spec §6, filed separately)
- Real Phase 2 (memory + gated learning) — separate spec
