# Session Topic Discipline & Cross-Harness Context Transfer — Design

## Problem

Interactive harness sessions (Claude Code today; potentially Codex, Agy, Grok whenever used
interactively) are meant to be topic/goal-scoped, but the convenience of resuming a conversation
(`/rc` or equivalent) makes it easy to keep piling unrelated work onto one long-running session
instead of closing and reopening. synlynk already has a `session open/status/checkpoint/close` CLI
(TPM/session MVP) with goal-linking and disposition tracking, but it's underused — both because the
CLI lacks drift detection and because closing/reopening a session today loses the harness's own
conversational context, so staying in one long session feels like the only way to keep continuity.

Separately: work on a single topic sometimes needs to continue under a *different* harness (e.g. a
human moves from an interactive Claude Code session to Codex or Gemini CLI for the same goal).
Harness-native memory systems (Claude's Session Memory/MEMORY.md, Codex's consolidated
`~/.codex/memories/`, Gemini CLI's GEMINI.md/save_memory) are mutually opaque — none can read
another's format — so today that context is simply lost on a harness switch.

## Goal

1. Detect and soft-nudge topic drift within an open synlynk session, using both a cheap mechanical
   proxy and the harness's own semantic judgment at natural checkpoints.
2. Make closing and reopening sessions low-cost by writing a structured memory entry into the
   closing harness's own memory system, so a **fresh** session (no resume) can recall prior context.
3. Track which harness opened a session and (where discoverable) that harness's own native session
   identifier, so sessions are traceable across harness boundaries.
4. Provide a harness-agnostic transfer mechanism for continuing a session's context under a
   *different* harness, built as a local-only ("Tokq lite") subset of the already-frozen Tokq
   memory-unit schema — so it upgrades into the real Tokq bridge later instead of being a dead end.

## Scope

Interactive harness sessions only — any of Claude, Codex, Agy, or Grok when used as a live,
turn-by-turn conversation. Dispatched (`synlynk dispatch`) tasks are out of scope: they are already
bounded by their task prompt and don't exhibit this drift failure mode.

## Non-goals

- Hard-blocking or auto-closing sessions. All drift handling is a soft, informational nudge.
- Encryption, agent identity (Ed25519), or marketplace/ledger mechanics — those remain exclusively
  Tokq Alpha concerns (see `memory/tokq-bridge.md`). This design produces **plaintext, local-only**
  memory units with the same schema shape, nothing more.
- A generic cross-harness memory reader (e.g. Codex parsing Claude's MEMORY.md directly). Direct
  harness-to-harness transfer is left as an unimplemented, pluggable hook for later; the
  synlynk-mediated export/import path is the only transfer mechanism this design implements.

## Components

### 1. Mechanical goal-mismatch nudge

Extends the existing NUDGE pattern already present in `cmd_session_status()` and
`cmd_session_checkpoint()` (`synlynk/db.py`), which currently flags jobs with no `session_id` at
all. Add a second check: jobs attributed to the active session (`daemon_jobs.session_id = <id>`)
whose linked `stories.goal_id` differs from the session's own `sessions.goal_id`.

```sql
SELECT COUNT(*) FROM daemon_jobs dj
JOIN stories s ON dj.story_id = s.story_id
WHERE dj.session_id = ? AND s.goal_id IS NOT NULL AND s.goal_id != ?
```

Printed as:

```
NUDGE: 3 job(s) in this session belong to a different goal (goal-xyz vs session's goal-abc) —
consider `synlynk session close` + `session open` to keep this session goal-scoped.
```

Only fires when the session itself has a non-null `goal_id` — sessions opened without one
(exploratory/parked dispositions) are exempt by design; they were never meant to be single-goal.

### 2. Harness + native-session-ref tracking (schema change)

New columns on `sessions`:

- `harness TEXT` — which CLI opened the session: `claude` / `codex` / `agy` / `grok`.
- `harness_session_ref TEXT` — opaque string holding that harness's own native session/conversation
  identifier, where discoverable. **Nullable and best-effort.** Grok currently exposes no such
  identifier and will always be null; that is an expected state, not an error.

Resolution at `session open` time is a small per-harness lookup function
(`_resolve_harness_session_ref(harness: str) -> str | None`) in `synlynk/session.py`:

| harness | lookup |
|---|---|
| `claude` | Claude Code's own transcript-path session UUID, if resolvable from the running process's environment/cwd conventions |
| `codex` | current `~/.codex/sessions/*.jsonl` file id, if resolvable |
| `agy` | Gemini CLI's chat-session id under `~/.gemini/tmp/<project_hash>/chats/`, if resolvable |
| `grok` | none known today — always returns `None` |

Each lookup fails soft (returns `None` on any error, never raises) — this is a traceability nicety,
not a dependency for the rest of the design to function.

### 3. Harness detection on `session open`

`session open` gains a `--harness <name>` flag. Resolution order:

1. Auto-detect via a per-CLI environment marker where one reliably exists (e.g. an env var Claude
   Code itself sets). Implemented as a best-effort probe, not a hard requirement.
2. If auto-detection is inconclusive, `--harness` becomes required — `session open` errors with a
   clear message rather than silently guessing.

Each harness's own directive file (CLAUDE.md/AGENTS.md/GEMINI.md/GROK.md, generated via
`synlynk/probe.py`) gets a line telling it to pass `--harness` explicitly if self-detection can't be
relied on for that CLI.

### 4. `## Session Topic Discipline` SOP (new `probe.py` template section)

New template string, following the same pattern used for the existing `## PR Review Discipline`
section (module-level constant + a `_repair_session_topic_discipline_sop()`-style regeneration
function, both producing the `## Session Topic Discipline` heading so `roles --fix` can re-detect and
regenerate it). Content instructs the harness to, at existing checkpoint moments (the periodic
maintenance / mid-session token-threshold triggers already defined in the user's global CLAUDE.md
protocol):

- Compare current work against the open session's title/goal.
- If diverged, soft-nudge toward `session close --summary "..."` + `session open` for the new topic
  — never auto-close, never block.
- On `session close`, write a structured memory entry into the closing harness's own memory system
  (Claude: MEMORY.md via the existing auto-memory mechanism; Agy: `save_memory` / GEMINI.md; Codex:
  best-effort note, since its memory is an offline consolidation process, not a live write path),
  tagged with `session_id`, `goal_id`, and `disposition`, summarizing what was accomplished.

### 5. `synlynk session context export` / `import` — the Tokq-lite bridge

The harness-agnostic transfer mechanism, implemented as a **local-only subset of the already-frozen
Tokq `context` memory-unit type** (see `memory/tokq-bridge.md`, Gap 2), not a new ad-hoc format:

- `memory_id = sha256(workspace_id + "context" + session_id + version_counter)` — identical hash
  construction to the full Tokq schema, so a unit minted here is byte-compatible with what the real
  bridge will expect once Tokq Alpha activates.
- Payload is a structured JSON view sourced from synlynk's own tables — `sessions`, `devlog_entries`,
  `daemon_jobs`, `goals` for the given `session_id` — matching the shape of the existing `context`
  unit type's `workspace.id`-keyed source. Not a freeform markdown dump.
- `encrypted_data` is **not populated** in this design — that field belongs to Tokq Alpha's
  AES-256-GCM/ZK layer (Gap 3). Units are stored as plaintext JSON locally under
  `.synlynk/memory_units/`, following the same file-marker convention as `active_session.json` and
  `telemetry.json`.
- `synlynk session context export --session <id>` writes the unit to
  `.synlynk/memory_units/<memory_id>.json` and prints its path.
- `synlynk session context import --unit <path>` (or `session open --from-unit <path>`) reads a unit
  back and prints/returns its payload so a **different** harness's first turn can be seeded with it.
- **Upgrade path, not a fork:** when Tokq Alpha activates, these same local units gain the
  `encrypted_data`/identity layer and become publishable exactly as Gap 2/3 already specify — no
  schema migration required, only an additional layer on top.
- Direct harness-to-harness transfer (harness A's native memory format read straight by harness B,
  bypassing synlynk) is explicitly left as an unimplemented, pluggable hook
  (`_direct_transfer_adapters: dict[tuple[str, str], Callable]`, empty today) for a future increment
  if such an adapter becomes practical for a specific harness pair. The synlynk-mediated
  export/import path above is the only transfer mechanism actually implemented now, and it always
  works because it depends only on synlynk's own local SQLite state, never on a harness-proprietary
  store.

## Data flow

```
session open --harness <name>
  → auto-detect or require explicit --harness
  → resolve harness_session_ref (best-effort, may be null)
  → INSERT sessions row (harness, harness_session_ref, goal_id, ...)
work happens
  → dispatches/devlogs stamped with session_id as today
at checkpoint (session status / session checkpoint, or periodic-maintenance trigger)
  → mechanical goal-mismatch nudge runs (SQL, always)
  → harness self-assesses drift per Session Topic Discipline SOP (judgment, at coarser cadence)
if drifted, or topic genuinely finished:
  → session close --summary "..."
  → harness writes a memory entry into its own native memory system
if the same goal continues under a DIFFERENT harness:
  → session context export --session <id>   (mints a local Tokq-lite `context` unit)
  → new harness: session open --harness <new> --from-unit <path>
  → new harness's first turn seeded from the exported unit's payload
```

## Testing

- Unit test for the new goal-mismatch SQL query (mirrors the existing unattributed-jobs nudge test).
- Migration test for the two new `sessions` columns (nullable, default null, existing rows unaffected).
- Unit tests for each `_resolve_harness_session_ref` per-harness lookup: returns a string when the
  convention is discoverable in a controlled fixture, returns `None` (never raises) when it isn't.
- `probe.py` template test for the new `## Session Topic Discipline` section, mirroring the existing
  PR Review Discipline SOP test — confirms it renders and survives `roles --fix` regeneration.
- `session context export`/`import` round-trip test: export a session with known jobs/devlogs/goal,
  import it, assert the payload matches and `memory_id` is deterministic (same inputs → same hash).
- No behavioral test is possible for "harness self-assesses drift" — that is a documented instruction
  for the harness's own judgment, not code path. Covered by SOP text review only.

## Open questions for implementation time

- Exact per-CLI environment marker to probe for auto-detection (needs a quick look at what each of
  Claude Code, Codex CLI, and Gemini CLI actually set in their process environment when running
  interactively — not yet confirmed, just assumed to exist for at least Claude Code).
- Whether `harness_session_ref` resolution for Claude/Codex/Agy needs filesystem access to each
  harness's home-directory convention (`~/.claude/`, `~/.codex/`, `~/.gemini/`) at `session open`
  time, and what happens if that directory doesn't exist yet on a fresh machine (should degrade to
  `None`, not error).
