---
title: "Harness Context Compaction Protocol Design"
date: 2026-10-31
status: draft
author: "Claude (Home Conductor)"
goal: "goal-85656c82"
epic: "#2458"
milestone: "v0.26.8"
arc: "developer-experience"
depends_on: "docs/superpowers/specs/2026-10-31-configurability-framework-design.md"
supersedes:
  - "Cluster C (docs/superpowers/specs/2026-09-12-v0.21.0-swarm-engine-and-context-compaction-design.md)"
  - "docs/superpowers/specs/2026-10-25-task-boundary-context-injection-design.md (gh:#2603)"
---

# Harness Context Compaction Protocol Design

## 1. Problem

v0.26.8's roadmap calls for "automated context compaction for interactive
Home Conductors before `/clear` or task handoffs." Two predecessor designs
already proposed pieces of this, neither implemented, neither registered
against the Configurability Framework:

- **Cluster C** (`2026-09-12` swarm-engine design): a reactive monitor that
  raises a `.synlynk/sentinel.md` alert at 75% of a harness's context window,
  an AST-grounded state checkpointer, and a Markdown resumption ledger
  appended to devlogs.
- **gh:#2603** (`2026-10-25` design): proactive, task-boundary context-pack
  injection — a bounded (<2,500 token) 5-part context packet generated and
  injected whenever a conductor crosses a task/story boundary.

The two were explicitly designed as complementary (reactive vs. proactive)
but never reconciled into one coherent protocol, and neither registers as a
feature under the now-approved
[Configurability Framework](2026-10-31-configurability-framework-design.md).
This spec does both: it reconciles the two predecessor designs into a single
`context_compaction` feature, and resolves one real gap discovered during
exploration — Cluster C's 75%-threshold monitor has no backing data source.

## 2. Why the reactive 75%-threshold monitor is dropped

Investigation during brainstorming found no cross-harness signal for live
interactive-session context-window usage:

- `.synlynk/telemetry.json` and `cost_entries` only ever log **per-dispatch-job
  aggregate token totals** (confirmed: every stored `turn_usage_json` array
  has exactly one entry — no per-turn growth curve exists anywhere in
  synlynk's own data).
- The one place a live context-usage percentage is actually computed is
  Claude Code's own statusline hook (`~/.claude/statusline-command.sh`,
  reading `.context_window.used_percentage` from hook-supplied JSON) — this
  is Claude-Code-native plumbing, invisible to synlynk's own code, and
  doesn't exist at all for Agy/Grok/Codex running interactively.

Building a 75%-threshold monitor on top of nothing would mean either (a)
Claude-only coverage with silent gaps for every other harness, or (b)
inventing a new self-reporting protocol with no real accuracy guarantee, for
a mechanism whose job is reactive, best-effort cleanup. Given that the
**proactive** half (task-boundary context-pack injection) already covers the
actual goal — bounded, fresh context at defined transition points, for every
harness — the reactive percentage-threshold trigger is dropped entirely.
**Non-goal, explicitly:** no interactive-session token-percentage monitor in
this spec, for any harness.

## 3. What survives, reconciled into one protocol

| Predecessor piece | Disposition |
| --- | --- |
| 75%-threshold monitor | **Dropped** (Section 2). |
| `CONTEXT_BUDGET_WARNING` sentinel alert | **Dropped** — tied to the monitor above; no replacement alert type introduced. |
| AST-grounded checkpointer + resumption ledger | **Kept**, decoupled from any percentage trigger — becomes a manual-or-boundary-fired safety net (Section 5). |
| Task-boundary context-pack injection (gh:#2603) | **Kept as designed**, unchanged 5-part content model and `<2,500` token bound (Section 6). |

Both mechanisms live in one new module, `synlynk/context_compaction.py` —
named deliberately to avoid colliding with the existing, unrelated
`synlynk/context.py` (the **headless-dispatch** prompt-context generator used
by `synlynk dispatch`; it has nothing to do with this feature and is not
modified by this spec). They share a private `_gather_snapshot()` helper
(active branch, test pass/fail counts, active story ID, modified files,
recent 3 commits) but produce two intentionally distinct artifacts — see
Section 7 for why they are not unified into one.

## 4. Framework registration

```python
from synlynk.features.registry import FeatureSpec, register_feature

register_feature(FeatureSpec(
    name="context_compaction",
    extra_name=None,          # no non-stdlib dependency; Layer 1 always "present"
    import_probe=lambda: True,
    settings_schema=CONTEXT_COMPACTION_SETTINGS_SCHEMA,
    default_enabled=False,
    supports_packs=False,     # no pack concept for this feature
))
```

`synlynk.context_compaction` is added to `_FEATURE_MODULES` in
`synlynk/features/__init__.py`, per the Configurability Framework's bootstrap
hook requirement — no new call site in `synlynk/cli.py`'s `main()`, since it
already calls `load_all_features()` once.

`CONTEXT_COMPACTION_SETTINGS_SCHEMA` (validated via `config_schema.py`'s
existing `validate()`/`validate_fields()` helpers):

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `ledger_verbosity` | enum | `"standard"` | `minimal \| standard \| full` — how much detail the AST pass captures into the resumption ledger |
| `pack_token_budget` | int | `2500` | hard ceiling enforced by `context pack`; must validate `> 0` |
| `auto_checkpoint_on_pack` | bool | `true` | decouples the dual-trigger (Section 5) if a user wants packs without ledger writes |

## 5. Mechanism 1 — Resumption ledger (checkpoint)

`synlynk context checkpoint [--dry-run]`:

1. Calls `_gather_snapshot()` for branch, test status, active story, modified
   files, recent commits.
2. Runs an AST/Tree-sitter pass over recently-modified files to capture key
   symbol changes, depth controlled by `ledger_verbosity`.
3. Renders a dense Markdown resumption ledger:
   ```markdown
   <!-- SYNLYNK_CONTEXT_COMPACTION_RESUME -->
   ## Resumption Checkpoint: <story_id> @ <short_sha>
   - Active Branch: `<branch>`
   - Verified Passing: <passed>/<total> tests
   - Next Action: <inferred from most recent incomplete step>
   ```
4. Appends it to `project-docs/devlogs/<agent>.md` under that marker, and
   upserts a row in `state.db:session_checkpoints`.

**Idempotency:** keyed on `(story_id, head_sha)`. Checkpointing twice at the
same repo state for the same story overwrites the existing marker block for
that key rather than appending a duplicate — `--dry-run` never writes
regardless.

**Trigger (both, per design decision):**
- **Manual:** run directly by the user/conductor before `/clear` or a
  handoff.
- **Automatic:** fired as a side effect of every `synlynk context pack` call
  (Section 6), unless `auto_checkpoint_on_pack` is set to `false`. Same
  underlying function, two call sites — no divergent logic between the two
  trigger paths.

No `.synlynk/sentinel.md` alert type is introduced by this mechanism (that
alert type belonged to the now-dropped reactive monitor).

## 6. Mechanism 2 — Context-pack injection

Carried forward from gh:#2603 unchanged in content model and bound:

- `synlynk context pack [--task <id>] [--format json|markdown]` synthesizes:
  1. **Governing Anchors** — active Goal ID, parent epic, target milestone,
     subsystem arc.
  2. **Repository Baseline** — active commit SHA, worktree-vs-shared-main
     status, recent 3 merged commits.
  3. **Task Scope & Invariants** — story ID, acceptance criteria, allocated
     harness/model, file-touch fences.
  4. **Attestation & Cost Bounds** — review model-tier rule, historical burn
     rate, required commit trailers.
  5. **Fresh Memory Deltas** — memory entries added since the previous
     session boundary.
- `synlynk context inject --story <id>` outputs the bounded markdown block,
  enforced under `pack_token_budget` (default 2,500 tokens) — oversized
  Fresh Memory Deltas are truncated to fit, never causing an error.
- Internally calls `_gather_snapshot()` for Repository Baseline (same helper
  Mechanism 1 uses), and — unless `auto_checkpoint_on_pack=false` — also
  calls `checkpoint()` as a side effect.

## 7. Why the two artifacts stay distinct

The resumption ledger and the context pack are not unified into one artifact.
The ledger is durable devlog history with no token budget, read by humans
and future sessions scanning a devlog; the pack is an ephemeral, strictly
bounded injection payload consumed immediately by the next task. Forcing the
ledger's content into the pack's `Fresh Memory Deltas` field (the unification
alternative considered during design) would mean either truncating
devlog-worthy detail to fit 2,500 tokens, or blowing the pack's bound to
preserve it — both wrong. They share only the data-gathering step
(`_gather_snapshot()`), never the output format or storage location.

## 8. CLI surface

```
synlynk context checkpoint [--dry-run]
synlynk context pack [--task <id>] [--format json|markdown]
synlynk context inject --story <id>
synlynk config feature context_compaction enable|disable
synlynk config feature context_compaction set <key> <value>
```

## 9. Compatibility

- No existing module is modified except `_FEATURE_MODULES` (one new entry)
  — `synlynk/cli.py`'s `main()` already calls `load_all_features()` once,
  per the Configurability Framework spec; no new call site needed here.
- `synlynk/context.py` (the unrelated headless-dispatch context generator)
  is untouched and unreferenced by this feature.
- `.synlynk/sentinel.md` gains no new alert type under this spec.
- With the feature disabled (default), `synlynk context checkpoint`/`pack`/
  `inject` remain available as explicit CLI invocations (a user can still run
  them manually) but the automatic pack→checkpoint side effect at task
  boundaries does not fire — matches the Configurability Framework's
  fail-closed default for *automatic* behavior while keeping manual commands
  usable, consistent with how other v0.26.8 features treat opt-in automation
  vs. always-available manual commands.

## 10. Measuring impact (instrumentation, required for this spec)

Investigation during brainstorming found no historical dataset that can
validate "does shedding and repopulating context reduce token spend" — every
stored `cost_entries.turn_usage_json` row logs exactly one aggregate
snapshot, never a per-turn growth curve, so there is no way to attribute
*when* within a session token volume ballooned. A cross-sectional look at the
155 genuinely-interactive `cost_entries` rows in `state.db` found the top 10%
by token volume account for 66.7% of all tokens and 55% of all cost in that
sample, concentrated in sessions explicitly noted as multi-attempt retries or
long multi-task reviews — directionally consistent with the hypothesis that
unshed, accumulated context across task boundaries drives a disproportionate
share of spend, but not proof, since large sessions can also simply reflect
large genuine tasks.

To let this question be answered rigorously once this feature ships, both
mechanisms **must** log a `cost_entries` row (or a lightweight sibling event
table, implementer's choice) each time they fire:

- `synlynk context checkpoint`: logs `context_mode="checkpoint"`, the
  snapshot's token count at the moment of checkpointing (estimated via the
  same token-counting utility `synlynk dispatch` already uses for its own
  cost logging), `story_id`, and whether the call was manual or
  auto-fired-via-pack.
- `synlynk context pack`/`inject`: logs `context_mode="pack"`, the generated
  pack's actual token count (post-truncation if truncation occurred),
  `story_id`, and the originating `--task`/`--story` id.

This is the first dataset of its kind — nothing currently records
per-compaction-event token counts — so after one release cycle, a genuine
before/after comparison (sessions with the feature enabled vs. disabled,
or pre- vs. post-adoption token volume per story) becomes possible instead of
remaining a hypothesis.

## 11. Testing

- `tests/test_context_compaction.py`:
  - `_gather_snapshot()` shape (branch, test counts, story ID, modified
    files, recent commits all present).
  - Checkpoint idempotency: two calls at the same `(story_id, head_sha)`
    overwrite rather than duplicate the devlog marker block.
  - Dual-trigger equivalence: calling `checkpoint()` directly vs. as a side
    effect of `pack()` produces identical ledger output for the same repo
    state.
  - `auto_checkpoint_on_pack=false` suppresses the side-effect call; `pack()`
    still succeeds and returns its own payload.
  - `pack()` stays under `pack_token_budget` on a fixture with a deliberately
    oversized Fresh Memory Deltas section (truncation, not error).
  - Both `checkpoint()` and `pack()` write a `cost_entries` row (or sibling
    event) with the expected `context_mode`/token-count/`story_id` fields
    (Section 10) — asserted via a temp `state.db` fixture.
- `tests/test_cli_config_feature_context_compaction.py`: enable/disable/set
  round-trip against a temp `features.json`.

## 12. Out of scope

- Any interactive-session token-percentage monitor, for any harness
  (Section 2).
- Unifying the resumption ledger and context pack into one artifact
  (Section 7).
- Designing or reconciling Herdr Customizations — its own document,
  registering independently against the same Configurability Framework.
- Retroactive backfill of `cost_entries` rows for compaction events that
  predate this feature (none exist, by definition — see Section 10).
