# Agent-Roles Phase 1 — CLI Onboarding + Dispatch Integration — Design

**Date:** 2026-08-16
**Status:** Approved (pending final user sign-off on this written doc)
**Author:** Claude (pm), brainstormed with Nikhil Soman
**Supersedes:** `2026-08-16-agent-roles-phase1-cli-design.md` (CLI-onboarding-only scope, found insufficient — see §1)

## 1. Motivation

The original Phase 1 CLI spec (`2026-08-16-agent-roles-phase1-cli-design.md`) scoped `agent
init/list/show/edit/disable` as a pure onboarding/bookkeeping layer on top of the already-shipped
storage layer (`synlynk/agent_store.py`, PR #988). Before implementation, the user validated that spec
against the project's actual goal — **increasing velocity of execution of all types of tasks** — with six
concrete questions:

1. Does this separate harness and workspace agents (roles)?
2. Can workspace agents parallelize tasks by dispatching to any/all harnesses?
3. Can workspace agents use all tools/skills/MCPs available to each harness?
4. Can workspace agents use advanced subagent/multiagent/loop/goal mechanics offered by harnesses?
5. Can workspace agents use interactive/headless/auto/accept-edits/manual modes?
6. Does agent identity give direct/full GitHub & local-environment access?

The honest answer, grounded in reading `synlynk/dispatch.py` and `synlynk/_constants.py`: the original spec
answered none of these. It built an identity/charter record that nothing in the dispatch path consults.
Meanwhile:

- `dispatch.py`'s own `dispatch_agent(agent: str, ...)` function still uses `agent` to mean *harness*
  (claude/agy/codex/grok, keyed into `AGENT_CAPABILITY_BASELINES`) — the exact terminology collision Phase
  0 (PR #993) was meant to resolve, just not yet cleaned up inside `dispatch.py` itself.
- Capability-based harness routing (`_best_agent_for_story`) and GitHub identity resolution
  (`_role_for_story` → `_resolve_dispatch_gh_token`) **already exist and already work** — but both are keyed
  off `story_id` (a row in the `stories` DB table), not off any agent identity.
- Tools/skills/MCPs/subagent-mechanics/modes are inherent to whichever harness executes a task; nothing in
  `agent_store.py` or the original CLI spec touches or needs to touch them for a single-operator workspace.

This spec keeps the original CLI onboarding surface (§3, mostly unchanged) but adds the missing piece: wiring
`agent_id` into the dispatch path as a first-class routing/identity key, reusing existing story-based
mechanisms rather than building new ones. The design also reserves one forward-compatible field so a future
Phase 3 (capability registry / scoped grants, per the parent roadmap) can slot in later without a schema
migration — decided explicitly with the user as "design for the mediated-orchestrator model, build the thin
router first."

## 2. Scope

**In scope:**
- `synlynk agent init/list/show/edit/disable` CLI (unchanged from the original spec — see §3, carried
  forward with one addition: an unenforced `capability_grants` field)
- `agent_id` as an optional first-class key on `dispatch_agent()`, reusing existing story-based
  capability-routing and GitHub-identity-resolution code paths
- Parallel task execution: multiple concurrent `dispatch_agent(agent_id=...)` calls, one per subtask — no
  new fan-out/orchestration engine

**Explicitly not built now (unmediated by design, per the "thin router first" decision):**
- Any restriction on which tools/skills/MCPs/subagent mechanics/modes a harness may use once dispatched —
  full native harness capability is available, always, for this spec. There is nothing to build here; it's
  a deliberate non-restriction, not a gap.
- A capability registry, scoped-access enforcement, or any runtime read of `capability_grants` — the field
  is stored but not consulted by any code path in this spec. Enforcement is Phase 3, unscheduled.
- Redundant fan-out (same task sent to multiple harnesses for racing/merging) — only subtask-level fan-out
  is in scope (see §5.3)
- GitHub App identity *linkage as a stored field* on the agent registry — GitHub identity resolution stays
  role-string-keyed (already works, §5.4), not agent_id-keyed; no new identity storage
- Web UI (parent spec §10 Phase 1 explicitly defers this)

## 3. CLI Surface — `agent init/list/show/edit/disable`

Unchanged from the superseded spec's §3, with one addition: `agent init` also writes an empty
`capability_grants: {}` into the projection file (§4). Full command reference:

### 3.1 `agent init <role>`

```
synlynk agent init <role>
```

- `role` ∈ `["dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot"]`
  (argparse `choices=`, the 8 roles from the parent spec's §2 org chart).
- Fails loudly if an agent with that `role_slug` alias is already registered (1:1 role→agent, Phase 1).
- On success: mints `agent_id = str(uuid.uuid4())`, calls `agent_store.register_agent(agent_id,
  [{"kind": "role_slug", "value": role}])`, seeds `charter.md` from `SEED_CHARTERS[role]` (verbatim §2
  prose from the parent spec) via `propose_charter_revision`, calls `regenerate_agent_projection(agent_id,
  repo_overrides={"capability_grants": {}})`. Prints `Created agent <agent_id> (role: <role>)`.

### 3.2 `agent list`

Prints one line per agent: `AGENT_ID  ROLE  STATUS  CREATED_AT`. Empty registry prints a hint to run
`agent init`.

### 3.3 `agent show <id_or_alias>`

Resolves via `resolve_agent_id` if not already a full `agent_id`. Prints role, status, created_at, history,
current charter content + revision.

### 3.4 `agent edit <id_or_alias> --charter <file>`

`--charter` required (only editable artifact in Phase 1; memory/SoR stay CLI-invisible, meant to be
agent-authored during runs). Reads current `parent_revision` via `read_charter`, calls
`propose_charter_revision`. `RevisionConflictError` surfaces as a clean retry message, not a traceback.

### 3.5 `agent disable <id_or_alias>`

Sets `disabled: true` + appends a history event. Idempotent no-op if already disabled.

## 4. Storage Layer Changes

Same two additions as the superseded spec, `synlynk/agent_store.py`:

```python
def set_agent_disabled(agent_id: str, actor: str) -> None:
    """Idempotently mark an agent disabled, appending a history event."""

def list_agents() -> list:
    """Return all registry entries (agent_id, aliases, disabled, created_at, history)."""
```

Plus: `regenerate_agent_projection(agent_id, repo_overrides=None)` already accepts `repo_overrides` — no
signature change needed. `agent init` (§3.1) passes `{"capability_grants": {}}` through it, so the projection
YAML at `.synlynk/agents/<id>.yaml` has the field present from day one. No other code reads this field in
this spec; it exists purely so Phase 3 can start writing/reading it later without migrating every existing
agent's projection file.

## 5. Dispatch Integration

### 5.1 `agent_id` as a dispatch key

`synlynk/dispatch.py`'s `dispatch_agent()` gains an optional `agent_id: str = None` parameter. When
provided:

1. Resolve the agent's role: look up the registry entry for `agent_id` (reuse `agent_store.list_agents()`
   from §4, filter for the matching entry, extract the `role_slug` alias value). Raise a clear `ValueError`
   if `agent_id` is unregistered or disabled (`"agent '<id>' is disabled — cannot dispatch. Use `synlynk
   agent show <id>` to check status."`).
2. **Harness auto-selection**: if `force_agent` is `False` and no explicit harness capability override is
   given, reuse the exact mechanism already used for `story_id` (`_best_agent_for_story` /
   `AGENT_CAPABILITY_BASELINES`-based routing at `dispatch.py:1957-1962`) — but keyed by the resolved
   **role** instead of a story row, since `AGENT_CAPABILITY_BASELINES[<harness>]["roles"]` already lists
   which roles each harness is a good fit for (e.g. `"claude": {"roles": ["architect", "builder"], ...}`).
   Concretely: extend the existing role-fit lookup so it accepts a role string directly, not only a
   `story_id`-derived one — a small refactor of the existing matching logic, not new matching logic.
3. **GitHub identity resolution**: reuse `_resolve_dispatch_gh_token(role)` (`dispatch.py:176`) directly with
   the resolved role, exactly as it already works for `story_id`-linked dispatches
   (`dispatch.py:410-411`, currently `role = _role_for_story(story_id) or "dev"`). When `agent_id` is
   provided, that line becomes `role = _agent_role(agent_id) or _role_for_story(story_id) or "dev"` —
   `agent_id` takes precedence when both are present, falls through to existing behavior otherwise. No
   change to `_resolve_dispatch_gh_token` itself.

This directly answers Q1 (agent_id and harness selection are now visibly distinct fields, not conflated —
though see §6 for the separate `dispatch_agent(agent: str, ...)` naming cleanup this does *not* do) and Q6
(GitHub identity was already role-based and already works; this just makes it reachable without requiring a
`story_id`/DB row to exist first).

### 5.2 CLI surface for dispatch

`synlynk dispatch <harness> --task "..." --as-agent <id_or_alias>` — the existing `dispatch` command gains
an `--as-agent` flag. Resolution (full id or alias, same as `agent show`) happens before calling
`dispatch_agent`, so a bad `--as-agent` value fails fast with a clear CLI error rather than a deep
`ValueError` traceback.

When `--as-agent` is given **without** an explicit harness (`synlynk dispatch --as-agent dev --task
"..."`), the harness positional argument becomes optional and auto-selection (§5.1 step 2) picks it — this
is the "any/all harnesses" behavior from Q2.

### 5.3 Parallel fan-out (Q2)

No new orchestration primitive. A workspace agent's work is parallelized the same way multiple independent
`dispatch_agent()` calls already run concurrently today (each becomes its own daemon job, per existing
`synlynk jobs`/telemetry infrastructure) — the only difference is each call now optionally carries the same
`agent_id`, so `synlynk jobs --all` / `agent show <id>` can show all of that agent's in-flight and completed
work grouped together. A human or TPM's dispatch loop issuing N `dispatch_agent(agent_id="dev-uuid",
task=subtask_i)` calls for N independent subtasks *is* the fan-out mechanism — this spec doesn't add
anything to make that possible (concurrent dispatch already works), it adds `agent_id` as the field that
makes the resulting jobs attributable to one workspace agent afterward.

### 5.4 Tools/skills/MCPs/subagent-mechanics/modes (Q3–Q5)

Unrestricted by design (§2). Once `dispatch_agent` selects a harness (whether via `--as-agent`
auto-selection or an explicit harness name, as today), that harness runs with its full existing native
capabilities — Claude Code's own subagent/skill system, Codex's sandbox and exec modes, Grok's tooling,
Agy's tooling — exactly as `synlynk exec`/`dispatch` already invoke them today via
`AGENT_CAPABILITY_BASELINES`'s existing `non_interactive_flags`/`dispatch_flags`/`headless_contract` per
harness. Nothing in this spec adds, removes, or mediates any of that. There is no unlock needed here beyond
what dispatch already does — the earlier CLI-only spec's gap on these questions was that it *didn't touch
dispatch at all*, not that dispatch itself was missing this capability.

## 6. Known Follow-Up (Not This Spec)

`dispatch.py`'s own `dispatch_agent(agent: str, ...)` parameter is still named `agent` and means *harness*
throughout the module (`AGENT_CAPABILITY_BASELINES`, error messages like `"Unknown agent: '{agent}'"`). This
spec adds a second, clearly-named `agent_id` parameter alongside it rather than renaming the existing
`agent` parameter — a rename would touch every call site of `dispatch_agent` across the codebase
(`dispatch.py`, CLI wiring, tests, TPM code) and is a larger, separate refactor with its own blast-radius
review, not bundled into this feature spec. Filing as a follow-up issue during implementation (§8 of the
plan) rather than expanding this spec's scope further.

## 7. Error Handling

| Condition | Behavior |
|---|---|
| `agent init` with unknown/duplicate role | argparse rejects unknown; duplicate exits 1 with clear message |
| `agent show/edit/disable` with unresolvable id/alias | Exit 1: `No agent found matching '<id_or_alias>'.` |
| `agent edit` with stale `parent_revision` | Exit 1, clear retry message |
| `agent disable` on already-disabled agent | Exit 0, idempotent no-op |
| `dispatch --as-agent <id>` unresolvable | Exit 1 before any dispatch attempt, same resolution error as `agent show` |
| `dispatch --as-agent <id>` where agent is disabled | Exit 1: `agent '<id>' is disabled — cannot dispatch.` |
| `dispatch_agent(agent_id=...)` with unregistered id (non-CLI callers) | `ValueError`, same message |

## 8. Testing

`tests/test_agent_cli.py` — same cases as the superseded spec's §7 (init/list/show/edit/disable happy paths
and error paths), plus: `agent init` writes `capability_grants: {}` into the projection file.

`tests/test_agent_store.py` — direct unit tests for `list_agents()` and `set_agent_disabled()` (unchanged
from superseded spec).

`tests/test_dispatch.py` (existing file, extend) — new cases:
- `dispatch_agent(agent_id=<registered dev agent>, task=..., force_agent=False)` auto-selects a harness
  whose `AGENT_CAPABILITY_BASELINES[...]["roles"]` includes `"dev"`'s mapped role-fit (mirrors existing
  `story_id`-based auto-selection tests)
- `dispatch_agent(agent_id=<disabled agent>, ...)` raises `ValueError` before any subprocess spawn
- `dispatch_agent(agent_id=<registered agent>, requires_gh_write=True)` resolves the GitHub token via the
  agent's role, verified by mocking `_resolve_dispatch_gh_token` and asserting it's called with the
  correct role string (mirrors the existing `story_id`-based gh-write test)
- `dispatch_agent(agent_id=<id>, story_id=<other story with different role>)` — `agent_id` takes precedence
  over `story_id` for role resolution (§5.1 step 3 precedence rule)

CLI-route test in `tests/test_cli.py` (or wherever `dispatch` CLI routing is currently tested) —
`--as-agent <alias>` resolves before dispatch, unresolvable alias fails fast with a CLI error not a
traceback.

## 9. Out of Scope for This Spec

- Renaming `dispatch_agent`'s `agent` parameter to something harness-specific (§6 — filed as a follow-up)
- Any enforcement of `capability_grants` (Phase 3, unscheduled — parent spec §10)
- Redundant multi-harness fan-out / result racing or merging
- GitHub App identity as a stored field on the agent registry (identity resolution stays role-string-keyed,
  which already works — see §5.1 step 3)
- Web UI (parent spec §10 Phase 1)
- Memory/Statements-of-Record CLI exposure (`agent edit --memory`/`--sor`)
- Phase 2 (memory + gated learning), Phase 3 (capability registry), Phase 4 (portability) — each gets its
  own spec per parent spec §10/§11 when its turn comes
