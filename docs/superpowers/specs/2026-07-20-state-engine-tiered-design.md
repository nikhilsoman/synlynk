# State Engine: Tiered Reliability Design (Single-User → Team → Enterprise)

**Status:** Approved — Tier 1 PR1 scoped for implementation (see §8 for landing decisions, 2026-07-25)
**Panel decision:** `project-docs/decisions/2026-07-20-design-a-reliable-state-engine-for-synly.md` (Claude, Agy, Codex, Grok — unanimous, no dissent recorded)
**GOVERNS stage:** `visualize` → `execute` (this doc closes `visualize`; a Business Goal record tracks the arc)

## 1. Incident and Motivation

`todo.md` is the only `project-docs/` file that is DB-canonical: it's generated from the `stories` table, hand-editing is forbidden by its own header, and edits round-trip back through `_import_todo_to_stories()`. Every other file — `roadmap.md`, `memory.md`, `costs.md` — is still hand-authored prose, edited directly via commits on feature branches, with no DB as the arbiter of truth.

This already caused a real incident: a shipped-epic roadmap row (Task-Boundary Cost Fence) was added on an orphaned branch that never merged to `main`. A later PR branched `roadmap.md` from the same pre-orphan blob and merged its own rows, silently overwriting the lost row with zero conflict markers — not a git-merge bug, a consequence of mutable narrative text living in git with no enforced sync-before-write.

A parallel audit found two more instances of the identical failure class already live in the codebase:
- `viz.py`'s Vizor roadmap panel reads `roadmap_arcs`/`roadmap_phases` — tables populated once during `synlynk migrate` and never resynced since. It has been serving stale data since migration ran.
- `.synlynk/vizor-workspace-map.json` (Vizor's Architect Map cross-repo edges) is maintained purely by discipline — a protocol in `CLAUDE.md` says to hand-edit it when a PR changes a cross-repo relationship. Same shape of bug, hasn't bitten yet only because it's lower-traffic.

A four-way `synlynk decide` panel (Claude, Agy, Codex, Grok) converged unanimously: the permanent fix is to make `state.db` the sole mutation point for all of `project-docs/`, extending the `todo.md` pattern rather than inventing a new one, with markdown/JSON as disposable, regenerated projections.

## 2. Scope: Three Tiers

This is an evolving state engine, not a single fix. Tier 1 ships in the next release. Tiers 2–3 are sketched at goal-depth only — not designed against yet, per explicit panel agreement.

### Tier 1 — Single-User State Engine (this release)

Sole mutation point: local `state.db`, SQLite, zero new dependencies (stdlib only — this constraint is non-negotiable per `CLAUDE.md`; ruled out PocketBase or any server-based store at this tier, see §5).

Three sequenced PRs, none of which may expand past its boundary before the prior one ships:

**PR1 — DB-canonicalize `roadmap.md` + `memory.md` + `costs.md`, with a mutation guard**

- Extend the existing `roadmap_arcs`, `roadmap_phases`, `memory_entries`, `cost_entries` tables from "written once at migrate time" to "written on every mutating command" (`synlynk roadmap add`, `synlynk memory add`, `synlynk cost log`, etc. — new thin CLI verbs where none exist yet, following `cmd_story_create()`'s existing pattern).
- Regeneration functions mirroring `_generate_todo_md()`: `_generate_roadmap_md()`, `_generate_memory_md()`, `_generate_costs_md()` — called at the end of every mutating command, not just on `exec`/`dispatch` (this is the write-through-on-every-update requirement, not on-demand).
- `check_budgets()` switches its read path from `parse_costs_md()` (regex over markdown) to querying `cost_entries` directly — closes the existing split-brain where the DB row is already written but budget-gating still trusts the markdown.
- **Rotation policy:** the live `roadmap.md`/`memory.md`/`costs.md` show in-flight items + the last N shipped/logged (N configurable, default covers ~1 release cycle). Older entries move to `project-docs/archive/<file>-<period>.md` (e.g. `roadmap-2026-H1.md`), generated the same write-through way. An `INDEX.md` in `project-docs/archive/` lists what's archived and links to each file, so "fresh context" stays small while nothing is lost.
- **Mutation guard (the panel's flagged must-have, not optional):** every generated file gets a header comment identical in spirit to `todo.md`'s existing "generated — do not hand-edit" banner, and `synlynk` commands that read these files for context injection or `pr check` detect a hand-edit and warn loudly — refusing to proceed silently on stale/edited content. This is what prevents the exact incident from recurring one layer down, per Claude/Codex/Grok's shared risk callout.
  - **What counts as a hand-edit (tier-1 scoped, revised after review):** the guard compares the working-tree file against (a) what regeneration would currently produce from the local DB, and (b) the file's content at the last commit that touched it (`git show HEAD:<path>`). Divergence from (a) alone is not sufficient to block — a fresh `git pull`/merge legitimately changes the on-disk file without the local DB having been mutated yet. The guard only refuses when the working tree diverges from **both** the last-known-good git blob **and** current regeneration output in a way regeneration can't explain (i.e., uncommitted local edits that don't correspond to any DB state, committed or pending). A file that matches its last git-committed blob but is stale relative to a `git pull` is not a violation — it's an input to resync, not a hand-edit. §7's DoD is updated to require a test for this pull-then-resync path specifically, since it's the case tier 1's original wording would have wrongly blocked.
  - This distinction is what unblocks Tier 2's reconciliation flow (§2.2) without weakening tier 1's guarantee: tier 1 still refuses genuine uncommitted hand-edits, but doesn't brick every `synlynk` command the instant a teammate's merged change lands via git.

**PR2 — `vizor-workspace-map.json` DB-canonicalization + `viz.py` stale-read fix**

- New `workspace_edges` table (repo-to-repo relationship type, direction, description) — the DB-backed equivalent of the current hand-edited JSON.
- `viz.py` stops reading `roadmap_arcs`/`roadmap_phases` as a one-time snapshot and queries them live (they're already DB tables per PR1 — this closes the standing stale-data bug).
- `.synlynk/vizor-workspace-map.json` becomes a write-through projection of `workspace_edges`, same rotation-free treatment as `todo.md` (it's small, no rotation needed).
- The existing "Workspace Map Update Protocol" in `CLAUDE.md` (manual, conditional) is replaced by a CLI verb (`synlynk workspace-map add-edge`) — same discipline shift as `todo.md`'s ban on hand-editing.

**PR3 — Scoped `dispatch_agent()` context + symbol/story graph tables**

- `generate_context()`'s `context_mode: task` stops concatenating full `roadmap.md`/`memory.md` text and instead queries only DB rows tied to the job's `story_id`/`epic_id` — a real scoped subgraph, not "everything, hope it's relevant."
- Promote `scan --deep`'s currently-discarded symbol/file extraction into DB tables (`files`, `symbols`), joined to `stories` via git-diff-on-PR-merge (`story → touches → file`), giving dispatch and Vizor a queryable code-graph without adopting an external tool (see §4 — CodeGraph/Graphify evaluated and rejected as dependencies, their design patterns borrowed instead).
- Vizor's canvas graph work (Architect Map, future code-graph view) becomes a pure consumer of DB-generated JSON snapshots — explicitly not a second store (Grok's framing).

**Explicit tier-1 non-goals:** concurrent multi-writer conflict resolution beyond what `git merge=union` already does for the generated files' rotation; any server process; any change to `state.db`'s per-worktree-shared location (`_resolve_db_path()` already centralizes correctly).

### Tier 2 — Team State Engine (goal-depth sketch, not designed yet)

Multi-user concurrent writes to the same `state.db` become real once more than one person mutates state in parallel. Candidate concerns, named by the panel but explicitly deferred:
- SQLite binary conflicts on git-tracked DB files (if `state.db` is ever shared via git rather than per-user local) — Agy/Codex flagged this; current architecture keeps `state.db` local per machine (`~/.synlynk/projects/<hash>/`), so this only becomes live if team-sync changes that.
- A reconciliation path (pre-commit hook or explicit `sync` command) that merges divergent local `state.db`s via their generated markdown/JSON, rather than attempting a binary DB merge.
- Real-time sync of state across team members' local DBs — likely an extension of the existing `synlynk team status` / digest mechanism, not a rearchitecture.

**Clarification added after review (resolves a tier-1/tier-2 contradiction flagged during PR review):** the generated markdown/JSON files are disposable projections *within a single local DB's lifecycle* (tier 1's guarantee — never hand-edit, never treat as a second source of truth for your own machine). Across machines, they are also the only thing git can merge, so tier 2's reconciliation necessarily treats a freshly-pulled file as an *input* to re-import into the local DB — the same round-trip `todo.md` already does today via `_import_todo_to_stories()`, extended to `roadmap.md`/`memory.md`/`costs.md`. This is not a second source of truth; it's the same DB-canonical model `todo.md` already proves out, applied at team scope. Tier 2 design work still needs to specify the actual reconciliation command/hook and its conflict rules — not designed against yet — but the mutation-guard contradiction Agy's review caught is resolved by §2.1's revised guard definition, not by weakening tier 1.

### Tier 3 — Enterprise State Engine (goal-depth sketch, not designed yet)

Hosted, multi-repo state aggregation, auth, and audit trail. This is the tier where a server-backed store (PocketBase or similar) is *actually* justified — once realtime multi-user sync and hosted auth are real product requirements, not before. Evaluated in §5; explicitly out of scope for any near-term work.

## 3. Sequencing and Release Target

PR1 → PR2 → PR3, in that order, each fully shipped (merged, tested, blog-posted per protocol) before the next starts. All three target the **next Named Release** (tier-1 single-user state engine is the release theme). Tier 2/3 are not scheduled — they get their own brainstorm-to-spec cycle once tier 1 is live and team/enterprise usage patterns are real, not speculative.

## 4. External Tools Evaluated (CodeGraph, Graphify) — Not Adopted

Both reviewed in depth (see panel discussion and prior thread). Neither is adopted as a dependency:
- **CodeGraph** — pure source-code call-graph tool (MCP server, symbols/call-edges). No relevance to decisions/roadmap/memory data; not evaluated further.
- **Graphify** — broader knowledge-graph tool (code + docs + media → `graph.json`/`graph.html`), with two design ideas worth borrowing without adopting the tool itself: (a) tagging every edge `EXTRACTED` (came directly from a DB row) vs. `INFERRED` (derived at render time) — applied to PR1's mutation-guard provenance and PR3's story↔file joins; (b) Leiden-style community clustering as a *future* nice-to-have for grouping epics/arcs, not required for tier 1.

Both are external Python/Go packages requiring their own runtime/env — incompatible with the zero-stdlib-dependency, single-file CLI constraint. Not revisited unless that constraint itself changes (which would be a much larger, separate decision).

## 5. PocketBase — Evaluated, Not Adopted (Any Tier ≤ 2)

PocketBase embeds SQLite but wraps it in its own collections/migrations/auth/realtime system — it does not let an existing arbitrary schema (`state.db`'s `stories`/`roadmap_phases`/`cost_entries` etc.) attach without remodeling into PocketBase's collection format. It is also a standalone server process (listens on a port, runs an admin UI), which conflicts directly with the zero-dependency, no-daemon constraint that defines tiers 1 and largely 2.

It becomes a legitimate option **only at tier 3**, if/when hosted multi-repo aggregation, realtime team sync, and hosted auth become actual requirements — at that point PocketBase's collections model, built-in auth, and realtime subscriptions solve real problems rather than being a daemon bolted onto a local CLI tool. Not designed against now; flagged here so the option isn't re-litigated from scratch when tier 3 actually comes up.

## 6. Ownership (per project's PM/implementer split)

- **Codex:** PR1 (SQLite schema/migration, regeneration functions, mutation guard, budget read-path fix), PR3's DB/query side (scoped context, symbol/story tables).
- **Agy:** PR1's rotation/archive HTML-adjacent rendering (if archive pages get an HTML index alongside markdown) and any doc-facing templates.
- **Grok:** PR2's viz.py fix and workspace-map consumoption, PR3's canvas/graph consumption of DB-generated JSON, viz-cache invalidation (flagged as a risk: write-through without cache-busting keeps graphs wrong after the DB is already right).
- **Claude:** PM, spec ownership, code review, `pr check` gate design for the mutation-guard drift detection, release cutting.

## 7. Definition of Done (Tier 1)

**PR1:**
- `roadmap.md`, `memory.md`, `costs.md` regenerate from `state.db` on every mutating command, with rotation/archive/index in place.
- `check_budgets()` reads `cost_entries` directly; `parse_costs_md()` regex path removed or demoted to a fallback-only path.
- Hand-editing any of the four `project-docs/` files (including `todo.md`, unchanged) is detected and warned/refused by tooling, not just forbidden by a comment — including a test for the revised guard's git-pull-then-resync case (§2.1), not just the pure-hand-edit case.
- All existing tests pass; new tests cover regeneration idempotency, rotation boundary behavior, and the mutation-guard's detect-and-warn path.

**PR2:**
- `synlynk workspace-map add-edge` CLI command implemented and replaces the manual "Workspace Map Update Protocol" section in `CLAUDE.md` (protocol text removed, not just superseded in spirit).
- `viz.py` roadmap panel reflects live DB state (queries `roadmap_arcs`/`roadmap_phases` directly, no one-time import); `vizor-workspace-map.json` is DB-canonical, written-through from the new `workspace_edges` table.
- Integration tests cover `viz.py`'s live-query path and `vizor-workspace-map.json` regeneration.

**PR3:**
- `dispatch_agent()`'s `context_mode: task` sends scoped DB query results tied to the job's `story_id`/`epic_id`, not full-file concatenation — with a test asserting per-job context token count drops measurably versus the old concatenation path.
- `files` and `symbols` DB tables exist, populated from `scan --deep`'s extraction; `story → touches → file` join populated via git-diff-on-PR-merge, with a test verifying the join is populated correctly for a sample merge.
- Vizor's canvas graph consumes DB-generated JSON snapshots only (no direct DB access from the canvas layer) — verified by a test or explicit code-review check at merge time.

## 8. PR1 Addendum — Landing Decisions (added 2026-07-25, Nikhil review)

Three scoping decisions confirmed during Nikhil's review, ahead of PR1 moving from spec to plan:

**8.1 This repo runs `synlynk migrate` as part of PR1, not a follow-up.** `synlynk`'s own repo has never run `migrate` — `project-docs/` still lives at the repo root, git-tracked, hand-edited, and the just-shipped `memory.md` write-through code (`cmd_memory_add()`, gated behind `_is_migrated()`) is consequently inert here today. This is the direct, confirmed root cause of the repeated `costs.md` drift firefighting this release (backfills in #482, #485; tracked as #481). PR1's Definition of Done (§7) is extended: after the roadmap/memory/costs write-through and mutation guard land and pass tests, PR1 also runs `cmd_migrate()` against this repo, commits the resulting `.synlynk_migrated` sentinel and relocated `project-docs/`, and confirms a live `cost log`/`roadmap add`/`memory add` round-trips correctly against the real repo — not just a test fixture. Skipping this would leave PR1's fix theoretical for the one repo where it's needed most.

**8.2 Mutation guard ships warn-and-continue, not block-and-refuse** — this matches §2.1's already-revised wording (the guard detects genuine uncommitted hand-edits not explained by a `git pull`/merge, and warns loudly on the next `synlynk` invocation rather than halting it), consistent with the project's existing "fail loud, don't fail closed" pattern (e.g. `cmd_migrate()`'s 0-row import check). No change to §2.1's text was needed; recorded here as an explicit confirmation since it was re-litigated during PR1 scoping review.

**8.3 `dr_sync_path`/gdrive DR stays documentation-only in PR1.** The existing `_dr_sync()` mechanism (a generic local-directory file mirror, currently only wired into `cmd_memory_add()`) gets extended to fire from the new `_generate_roadmap_md()`/`_generate_costs_md()` write-through paths alongside `_generate_memory_md()`'s existing call, matching the pattern uniformly across all three files. PR1 does **not** configure `dr_sync_path` for this repo's own `.synlynk/config.json` — no Google Drive folder path is chosen or wired up in this PR. Instead, PR1's DoD gains one line: document in this spec (here) that pointing `dr_sync_path` at a Google Drive Desktop-synced local folder achieves off-machine DR today with zero new code, and that actually setting the config value for this repo is a deliberate follow-up once a folder is chosen — not a PR1 blocker.
