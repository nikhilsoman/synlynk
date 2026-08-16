# Agent Roles & Charters — Phase 1 CLI Onboarding Surface — Design

**Date:** 2026-08-16
**Status:** Approved (pending final user sign-off on this written doc)
**Author:** Claude (pm), brainstormed with Nikhil Soman

## 1. Motivation

The parent design (`docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md`, §10) lays
out a 5-phase roadmap from Agent/Harness terminology to full portability. Phase 0 (terminology) shipped as
PR #993 (`chore/rename-agent-cli-to-harness`), which also freed the `agent` CLI verb group from its old
harness-execution meaning. The storage half of Phase 1 — per-agent artifact storage (charter, memory,
Statements of Record, with revisioned/provenance-tracked writes) — shipped as PR #988
(`synlynk/agent_store.py`, see `docs/superpowers/specs/2026-08-15-workspace-agent-artifact-storage-design.md`).

What's still missing is the CLI onboarding surface itself: `agent init/list/show/edit/disable`, the
human-facing way to actually create and manage an agent record on top of that storage layer. Per parent
spec §11, each phase gets its own spec before a plan — this is that spec, scoped strictly to the CLI layer.
No new storage logic is introduced; this is wiring on top of `agent_store.py`'s existing functions.

## 2. Scope

**In scope:** `synlynk agent init/list/show/edit/disable` — argument parsing, handler logic, one small
registry schema addition (a `disabled` flag), output formatting, and tests.

**Out of scope (deferred to later phases or follow-ups, per parent spec §8/§10):**
- Web UI (explicitly deferred by parent spec §10 Phase 1 row — CLI is the onboarding surface)
- GitHub App identity linkage (binding an agent to its provisioned `app_slug` from parent spec §6) — a
  later step, not blocking this CLI surface
- Memory/Statements-of-Record CLI exposure — `agent edit` only touches the charter; memory/SoR entries are
  meant to be written during agent runs, not hand-edited via this CLI, for Phase 1
- Dispatch-path enforcement of the `disabled` flag (routing code skipping disabled agents) — this spec adds
  the flag and the CLI to set it; wiring dispatch to respect it is a follow-up
- Multiple agents per role — Phase 1 keeps role_slug unique per workspace (1:1), matching today's 1:1
  role→GitHub-App-identity provisioning from parent spec §6

## 3. CLI Surface

New top-level `agent` subparser in `synlynk/cli.py`, following the same shape as the existing `harness`
subparser (`synlynk/cli.py:467-481`). Handler functions live in a new module, `synlynk/agent_cli.py` —
`cli.py` only wires arguments and dispatches; all logic (registry reads/writes, charter seeding, error
formatting) lives in the handler module. This mirrors the existing split between `cli.py`'s argument wiring
and dedicated modules like `synlynk/team.py`.

### 3.1 `agent init <role>`

```
synlynk agent init <role>
```

- `role` is a required positional argument, `choices=["dev", "qa", "pm", "architect", "tpm", "designer",
  "marketing", "synlynk-bot"]` (the 8 roles from parent spec §2's org chart) — argparse rejects anything
  else before handler code runs.
- Fails loudly (exit 1, clear message) if an agent with that `role_slug` alias is already registered —
  looked up via a full registry scan (same pattern as `agent_store.resolve_agent_id`, but checking alias
  *kind+value* pairs rather than resolving one). Phase 1 is 1:1 role→agent.
- On success:
  1. `agent_id = str(uuid.uuid4())`
  2. `agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": role}])`
  3. Seed the charter: `agent_store.propose_charter_revision(agent_id, SEED_CHARTERS[role], actor="cli", parent_revision=0)` — `SEED_CHARTERS` is a small dict in `agent_cli.py` holding each role's one-line charter prose, copied verbatim from parent spec §2's table (e.g. `"dev": "Implementation — writes the code."`).
  4. `agent_store.regenerate_agent_projection(agent_id)`
  5. Print: `Created agent <agent_id> (role: <role>)`

### 3.2 `agent list`

```
synlynk agent list
```

- Reads the registry directly (a new small helper, `agent_store.list_agents()` — see §4).
- Prints one line per agent, plain text, tab-aligned:
  ```
  AGENT_ID                              ROLE         STATUS     CREATED_AT
  3f9a1c2e-...                          dev          active     2026-08-16T10:00:00Z
  ```
- Empty registry: prints `No agents registered. Run \`synlynk agent init <role>\` to create one.`

### 3.3 `agent show <id_or_alias>`

```
synlynk agent show <id_or_alias>
```

- Resolves `id_or_alias`: if it matches a full registered `agent_id`, use it directly; otherwise try
  `agent_store.resolve_agent_id(id_or_alias)`. If neither resolves, exit 1 with
  `No agent found matching '<id_or_alias>'.`
- Prints role, status (active/disabled), created_at, full history (from the registry entry), and the
  current charter content + revision number (via `agent_store.read_charter`).

### 3.4 `agent edit <id_or_alias> --charter <file>`

```
synlynk agent edit <id_or_alias> --charter <file>
```

- `--charter` is required in Phase 1 (the only editable artifact — see §2 scope). `<file>` is a path to
  read new charter content from; passing `-` reads from stdin.
- Resolves `id_or_alias` the same way as `show`. Exit 1 with a clear message if unresolvable.
- Reads current charter via `agent_store.read_charter(agent_id)` to get `parent_revision`, then calls
  `agent_store.propose_charter_revision(agent_id, new_content, actor="cli", parent_revision=parent_revision)`.
- On `agent_store.RevisionConflictError`: exit 1 with
  `Charter was updated by someone else since you last viewed it. Run \`synlynk agent show <id>\` and retry.`
  No auto-merge — the user re-reads and re-applies their edit manually.
- On success: calls `agent_store.regenerate_agent_projection(agent_id)`, prints
  `Updated charter for <agent_id> (revision <n>)`.

### 3.5 `agent disable <id_or_alias>`

```
synlynk agent disable <id_or_alias>
```

- Resolves `id_or_alias` the same way as `show`.
- If already disabled: no-op, prints `Agent <agent_id> is already disabled.` (idempotent, exit 0).
- Otherwise: sets `disabled: true` on the registry entry, appends
  `{"event": "disabled", "at": <now_iso>}` to its `history` list, writes the registry back. Prints
  `Disabled agent <agent_id>.`

## 4. Storage Layer Changes

`synlynk/agent_store.py` gains two small additions — no changes to existing function signatures or
behavior:

1. **`disabled` field**: `register_agent` continues to create entries without a `disabled` key (absence ==
   active, for backward compatibility with any registry file written before this change). A new helper:

   ```python
   def set_agent_disabled(agent_id: str, actor: str) -> None:
       """Idempotently mark an agent disabled, appending a history event."""
   ```

   Looks up the entry by `agent_id`, no-ops if `entry.get("disabled")` is already `True`, otherwise sets
   `disabled = True` and appends `{"event": "disabled", "at": _now_iso(), "actor": actor}` to `history`,
   then writes the registry back via `_write_json_atomic`.

2. **`list_agents()` helper**:

   ```python
   def list_agents() -> list:
       """Return all registry entries (agent_id, aliases, disabled, created_at, history)."""
   ```

   Thin wrapper over `_load_registry()["agents"]` — exists so `agent_cli.py` doesn't need to know the
   registry's on-disk shape directly (matches the existing encapsulation `resolve_agent_id` already
   provides for alias lookups).

Role-collision checking for `agent init` (§3.1) uses `list_agents()` plus a filter over each entry's
aliases for `kind == "role_slug"` — no new storage function needed for that check, it's handler-side logic
using data `list_agents()` already exposes.

## 5. Data Flow

```
synlynk agent init dev
  → agent_cli.cmd_agent_init(role="dev")
    → agent_store.list_agents()          # collision check
    → agent_store.register_agent(...)     # registry.json write
    → agent_store.propose_charter_revision(...)  # charter.md + charter.revisions.jsonl write
    → agent_store.regenerate_agent_projection(...)  # .synlynk/agents/<id>.yaml write
```

All writes go through `agent_store.py`'s existing atomic-write (`_write_json_atomic`) and
append-only-revision-log patterns — this spec introduces no new persistence mechanism.

## 6. Error Handling

| Condition | Behavior |
|---|---|
| `agent init` with unknown role | argparse `choices=` rejects before handler runs; standard argparse usage error |
| `agent init` with already-registered role | Exit 1: `Role '<role>' already has an agent (<agent_id>). Only one agent per role is supported.` |
| `agent show/edit/disable` with unresolvable id/alias | Exit 1: `No agent found matching '<id_or_alias>'.` |
| `agent edit` with stale `parent_revision` (`RevisionConflictError`) | Exit 1, clear retry message (§3.4) |
| `agent disable` on already-disabled agent | Exit 0, idempotent no-op message |
| `agent edit` with missing `--charter` | argparse `required=True` rejects before handler runs |

## 7. Testing

New file `tests/test_agent_cli.py`, following the CLI-route-testing pattern already used in
`tests/test_roles.py` and the storage-isolation fixtures already used in `tests/test_agent_store.py`
(PR #988 — isolates `.synlynk/config.json` and `~/.synlynk/workspaces/` per test via `tmp_path` +
monkeypatching `os.path.expanduser`/cwd).

Cases:
- `init`: happy path (registry entry created, charter seeded with the role's §2 prose, projection file
  written); duplicate-role collision fails loudly; invalid role rejected by argparse (`SystemExit`)
- `list`: empty registry message; N-agent output includes all roles/statuses
- `show`: resolves by full `agent_id`; resolves by alias; unknown id/alias errors clearly
- `edit`: happy path increments revision and regenerates projection; stale `parent_revision` surfaces
  `RevisionConflictError` as a clean CLI error, not a traceback
- `disable`: sets flag + appends history event; idempotent second call is a no-op with exit 0; unknown
  id/alias errors clearly
- `agent_store.list_agents()` and `agent_store.set_agent_disabled()`: direct unit tests in
  `tests/test_agent_store.py` for the two new storage functions, independent of the CLI layer

## 8. Out of Scope for This Spec

- Web UI (parent spec §10 Phase 1 explicitly defers this)
- GitHub App identity linkage between an agent record and its provisioned `app_slug` (parent spec §6)
- Memory/Statements-of-Record CLI exposure (`agent edit --memory`/`--sor`)
- Dispatch-path code respecting the `disabled` flag (routing enforcement is a follow-up, not this spec)
- Multiple agents per role / human-facing disambiguation naming
- Phase 2 (memory + gated learning), Phase 3 (capability registry), Phase 4 (portability) — each gets its
  own spec per parent spec §10/§11 when its turn comes
