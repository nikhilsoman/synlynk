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

**Idempotency and marker identity (DECIDE panel, 2026-10-31 — required
revision):** keyed on `(story_id, head_sha)`, but the marker comment itself
must encode that key, not just sit as a bare generic tag — otherwise two
different checkpoints in the same devlog are indistinguishable and the
overwrite-vs-append rule has nothing to match against:

```markdown
<!-- SYNLYNK_CONTEXT_COMPACTION_RESUME story_id=<story_id> head_sha=<head_sha> -->
```

Checkpointing finds the exact `story_id`+`head_sha`-tagged block and replaces
it in place; a different `story_id` or `head_sha` always appends a new block,
never overwrites one. `--dry-run` never writes regardless.

**Dirty working tree:** `head_sha` alone is not a stable identity when the
tree has uncommitted changes — two checkpoints at the same commit with
different uncommitted edits must not collapse into one overwritten block.
When `git status --porcelain` is non-empty, the key becomes
`(story_id, head_sha, dirty_hash)` where `dirty_hash` is a short hash of the
porcelain output; a clean tree omits `dirty_hash` entirely (key stays
`(story_id, head_sha)` as above). The marker comment grows the same extra
field: `dirty_hash=<hash>` appended when present.

**Trigger — explicit enablement × command × `auto_checkpoint_on_pack` truth
table (DECIDE panel, 2026-10-31 — required revision):** manual CLI
invocation of either command is **always available regardless of
`context_compaction`'s enabled state** (Section 9 already establishes this
for the feature generally; stated here precisely for the trigger matrix):

| `context_compaction` enabled? | Command | `auto_checkpoint_on_pack` | Ledger write? | Pack output? |
| --- | --- | --- | --- | --- |
| any | `context checkpoint` (manual) | n/a | Yes | n/a |
| any | `context pack`/`inject` (manual) | `true` | Yes (side effect) | Yes |
| any | `context pack`/`inject` (manual) | `false` | No | Yes |
| disabled | *(no automatic firing exists — this feature has no background trigger; "automatic" above means "as a side effect of an explicitly-invoked pack call," never a process running unprompted)* | — | — | — |

There is no scenario in which `context_compaction` being disabled changes
whether checkpoint/pack *commands* work when run — disabling only ever
affects whether anything invokes them for you implicitly, and this feature
defines no such implicit invocation point (no hook fires `context pack` on
its own; that integration, if any, belongs to whatever future caller adopts
it, out of scope here). "Automatic" in this spec means solely "pack firing
checkpoint as its own side effect," never "firing without being called."

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

**Schema (DECIDE panel, 2026-10-31 — required revision):** the original
"log a `cost_entries` row on every fire" plan has two defects the panel
identified: (a) `context_mode` is an existing column already carrying
dispatch-scope semantics (e.g. `"task"` for `synlynk dispatch`), so reusing
it for compaction events conflates two unrelated taxonomies; (b) if only
compaction *events* get rows, a disabled session logs nothing, and "absence
of a row" cannot serve as the control cohort for a before/after comparison —
there is nothing to compare against.

Fix, in two parts:

1. **New dedicated column, not an overload of `context_mode`:**
   `compaction_event_type` (`"checkpoint" | "pack" | NULL`), populated only
   on rows logged by this feature's own two commands. Carries: the event's
   token count at the moment of firing (checkpoint: `_gather_snapshot()`'s
   estimated size; pack: the generated pack's actual post-truncation token
   count), `story_id`, and whether the call was manual or
   auto-fired-via-pack (reuses the trigger-matrix vocabulary from Section 5).
2. **Control-cohort mechanism — tag the session, not just the event:** every
   `cost_entries` row logged during an interactive session (not only
   checkpoint/pack rows — the session's ordinary cost-log entries too) gains
   a `feature_enabled` boolean, stamped from `is_feature_enabled(
   "context_compaction")` at the moment each row is logged. This is what
   actually answers the before/after question: group all of a session's
   `cost_entries` rows by `feature_enabled` and compare total token volume
   per session/story between the two cohorts, rather than trying to infer
   anything from the presence or absence of a compaction-specific row alone.
   Manual invocation while the feature is disabled (Section 5's trigger
   table — always available) still logs `feature_enabled=false`, so a
   "disabled but manually checkpointed" session remains distinguishable from
   a fully-untouched one.

This is the first dataset of its kind — nothing currently records
per-compaction-event token counts or per-session enablement state — so after
one release cycle, a genuine before/after comparison becomes possible
instead of remaining a hypothesis.

## 11. Testing

- `tests/test_context_compaction.py`:
  - `_gather_snapshot()` shape (branch, test counts, story ID, modified
    files, recent commits all present).
  - Checkpoint idempotency: two calls at the same `(story_id, head_sha)` on a
    clean tree overwrite rather than duplicate the devlog marker block; two
    calls at the same `(story_id, head_sha)` with *different* dirty-tree
    diffs produce two distinct `dirty_hash`-keyed blocks, neither
    overwriting the other.
  - Marker identity: the appended block's HTML comment contains the exact
    `story_id`/`head_sha`(/`dirty_hash`) it was keyed on; a second checkpoint
    call locates and replaces only the matching block, leaving other
    stories'/commits' blocks in the same devlog untouched.
  - Trigger matrix (Section 5): manual `checkpoint`/`pack` both succeed
    regardless of `context_compaction`'s enabled state; `auto_checkpoint_on_
    pack=false` suppresses only the pack-triggered side-effect checkpoint
    call, never the manual command.
  - `pack()` stays under `pack_token_budget` on a fixture with a deliberately
    oversized Fresh Memory Deltas section (truncation, not error).
  - Both `checkpoint()` and `pack()` write a `cost_entries` row with
    `compaction_event_type` set correctly (never written into the existing
    `context_mode` column), the expected token count, `story_id`, and
    manual-vs-auto-fired flag.
  - `feature_enabled` cohort tagging: a session's ordinary (non-compaction)
    `cost_entries` rows carry the enablement state in effect at log time; a
    manual checkpoint while disabled logs `feature_enabled=false`, remaining
    distinguishable from a session that never invoked either command.
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
