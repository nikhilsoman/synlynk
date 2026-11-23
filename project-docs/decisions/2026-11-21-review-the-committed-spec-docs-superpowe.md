<!-- generated - source of truth is state.db -->
---
decision_id: dec-e16e0f4c
topic: "Review the committed spec (docs/superpowers/specs/2026-11-21-stable-roadmap-arc-phase-identity-design.md) and implementation plan (docs/superpowers/plans/2026-11-21-stable-roadmap-arc-phase-identity.md) on branch chore/claude/stable-roadmap-arc-phase-identity-spec, which add durable arc_uid/phase_uid identity columns to goals (gh:#5443 item 3 / LIVE-34) so github_sync_map stops drifting when roadmap_arcs/roadmap_phases positional ids shift. Evaluate against this goal: roadmap arcs, phases, and their GitHub milestone sync must remain flexible to rename/reorder/restructure right up until an arc/phase actually ships, and the identity model must generalize to other domains beyond just milestones (e.g. any future consumer keying off an arc or phase, not just github_sync_map) -- not be a narrow one-off fix. Flag any place the design is too rigid, too narrowly scoped to the current github_sync_map bug, or would make pre-ship restructuring harder than it is today. Recommend whether to proceed with this plan as written, or what to change first."
date: 2026-11-21
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Review the committed spec (docs/superpowers/specs/2026-11-21-stable-roadmap-arc-phase-identity-design.md) and implementation plan (docs/superpowers/plans/2026-11-21-stable-roadmap-arc-phase-identity.md) on branch chore/claude/stable-roadmap-arc-phase-identity-spec, which add durable arc_uid/phase_uid identity columns to goals (gh:#5443 item 3 / LIVE-34) so github_sync_map stops drifting when roadmap_arcs/roadmap_phases positional ids shift. Evaluate against this goal: roadmap arcs, phases, and their GitHub milestone sync must remain flexible to rename/reorder/restructure right up until an arc/phase actually ships, and the identity model must generalize to other domains beyond just milestones (e.g. any future consumer keying off an arc or phase, not just github_sync_map) -- not be a narrow one-off fix. Flag any place the design is too rigid, too narrowly scoped to the current github_sync_map bug, or would make pre-ship restructuring harder than it is today. Recommend whether to proceed with this plan as written, or what to change first.

## Panel Inputs

### claude
[model=sonnet; version=2.1.327 (Claude Code)]

**Position: proceed, but fix four things before implementation.**

The core move is sound. It adds opaque, write-once uids to `goals`, keeps `roadmap_arcs` and `roadmap_phases` as views, and leaves `id` as a display-only value. Plain renames and reorders are uid-stable with no special code, which matches the goal of staying flexible until an arc ships. I read the spec in full but only skimmed the plan, so the points below come from the spec.

**Where it is too rigid or too narrow**

1. **Merge, split and move are manual or unspecified.** The spec says merging arcs by rename needs `UPDATE goals SET arc_uid = NULL` first, and it defers this to a doctor step. Merging, splitting and renaming phases is exactly the pre-ship restructuring the goal wants to keep cheap, and the manual procedure makes it more fragile than it is today.
   - The fix is one supported API, for example `roadmap_merge_arc(src_uid, dst_uid)`, `split` and `move_phase`. These would do explicit uid rewrites and record the old uid in a redirect.
   - Without redirects, `github_sync_map` rows keyed on a retired uid are orphaned silently.

2. **uid lifetime is undefined.** Unplacing every goal in an arc and re-placing it later produces a fresh uid, so the old consumer row orphans. The spec needs a tombstone or alias table (`roadmap_uid_aliases(old_uid, new_uid)`), or an explicit statement that a uid dies with its last goal. That alias table also solves merge and split.

3. **Phase uids don't survive a move.** Under `(arc_version, phase_title)` keying, a phase renamed or moved to another arc gets the new group's uid if one already exists, or a fresh one. This contradicts the stated rename goal for phases. The spec checks a rename only for `arc_version`. The phase case, including a rename combined with an arc rename in a single UPDATE, needs explicit tests.

4. **Nothing registers the identity for other consumers.** The spec says the uid is for "anything future", but only `github_sync_map` is migrated. The issue was that a consumer persisted a positional id. I'd add the following:
   - A `roadmap_uid` resolver helper (`resolve_arc(uid_or_alias)`).
   - A lint or test that fails when a table persists `roadmap_arcs.id` or `roadmap_phases.id`.
   - A short "how to reference an arc" doc.

   Consider also whether `cost_entries` and `stories` need arc references.

**Smaller issues**
- The assignment uses `rowid` and `LIMIT 1` with no ordering. Two groups that already disagree on a uid would be adopted arbitrarily, so add a divergence check to `doctor`.
- The `MIN(arc_uid)` aggregate hides divergent uids when a group has more than one. Prefer `COUNT(DISTINCT)` surfaced as an invariant.
- The backfill depends on live `gh api` calls inside a migration. Make the migration offline-safe, and run the verification as a separate step.

**Recommendation:** keep Approach C, but revise the spec and plan first. Add the alias/redirect table, supported merge/split/move operations, phase-move semantics and a consumer rule. These are cheap now and expensive to retrofit after `github_sync_map` is migrated.

### agy
[model=default; version=1.5.14]

Last completed task: Committed stable arc/phase identity spec and plan on `chore/claude/stable-roadmap-arc-phase-identity-spec`.
Next task from `todo.md`: Decision panel review of `2026-11-21-stable-roadmap-arc-phase-identity-design.md` and implementation plan.

***

### Evaluation & Analysis

The proposal correctly identifies that persisting ephemeral `ROW_NUMBER()` IDs in `github_sync_map` is flawed. However, the design as written is **too rigid for pre-ship roadmap manipulation** and contains a critical modeling defect caused by denormalizing arc/phase identities onto individual `goals` rows:

1. **Pre-Ship Restructuring Breakdown (Goal Moving & Splitting):**
   The triggers use `WHEN NEW.arc_uid IS NULL` to make renames stable. However, SQL triggers on `goals` cannot distinguish an arc-wide rename from an engineer reassigning or splitting goals between arcs/phases. If a goal is moved (`UPDATE goals SET arc_version='v0.40.0' WHERE goal_id='g-1'`), its non-null `arc_uid` persists. That goal carries its old arc identity into the new version, causing multiple distinct arcs to share a UID or splintering `MAX(arc_uid)` in the view. Requiring manual SQL nulling (`UPDATE goals SET arc_uid = NULL`) for merges and splits adds operational friction right when pre-ship roadmaps need maximum agility.
2. **Interface Leakage & Narrow Ingress:**
   The implementation plan contradicts the spec: the spec calls for changing `sync_arc(arc_id: int)` to `sync_arc(arc_uid: str)`, but the plan retains `arc_id: int` to minimize call-site churn in `gh_sync_cli.py`. Leaving positional IDs as the primary API ingress preserves the exact conceptual coupling that caused LIVE-34.
3. **Deferred Domain Generalization:**
   Excluding `cost_entries` (gh:#5446) treats durable identity as an isolated patch for `github_sync_map` rather than establishing a unified identity layer across the codebase.

### Final Position & Recommendation

**Position: Do not proceed with the plan as written.** Before implementation begins, amend the design to support fluid pre-ship restructuring: ensure reassignment triggers correctly re-key goals moved to new or existing arcs/phases without manual SQL intervention, fully migrate public signatures (including `sync_arc` and CLI handlers) to accept `arc_uid`, and validate compatibility with `cost_entries` to ensure the identity model genuinely generalizes beyond GitHub milestones.

### codex
[model=default; version=codex-cli 0.169.1]

The design correctly eliminates the immediate positional-ID failure: opaque IDs on `goals`, view exposure, rename stability, and regression coverage for reordered arcs are all sound foundations. Keeping `ROW_NUMBER()` as display order is also appropriate.

However, it is not yet a sufficiently general identity model for the stated goal. The trigger strategy assumes that every goal already carrying a UID remains in the same logical arc/phase forever. Moving one goal or phase to an existing arc, splitting a group, or merging groups can leave multiple UIDs under one `(arc_version)` or `(arc_version, phase_title)`. The views’ `MIN()` then conceal that inconsistency rather than reject it. The documented merge procedure only covers one manual case and is easy to miss; ordinary restructuring remains capable of producing ambiguous identity. That makes future consumers unsafe even if `github_sync_map` works.

The model is also operationally narrower than the spec claims. There is no canonical arc/phase identity record, uniqueness constraint, invariant-enforcing write path, or reusable API for consumers. Identity is duplicated across goals and inferred through aggregation. `phase_uid` is added and exposed, but the plan does not demonstrate a phase consumer or a complete lifecycle for phase moves, merges, and splits. The plan’s “not invoked live” migration also weakens the cutover: shipping code before existing mappings are converted leaves the production bug unresolved until a separate manual operation.

Before implementation, require: (1) explicit semantics for move, split, merge, and rename operations; (2) enforcement that each active group resolves to exactly one UID, with migration failing loudly on conflicts; (3) a shared identity-resolution interface or canonical identity table suitable for non-GitHub consumers; and (4) an explicit, audited production cutover plan, including phase mappings if applicable.

I recommend **do not proceed with the plan as written**. Proceed after tightening the identity lifecycle and invariant enforcement; otherwise this risks replacing positional drift with silent group/UID drift.

### grok
[model=default; version=grok 1.0.77 (50ca579fa996) [stable]]

I'll review the committed spec and plan against the flexibility goal, starting with both documents and the identity model they introduce.The durable-uid idea is the right fix for LIVE-34. `roadmap_arcs.id` is a live `ROW_NUMBER()`, and persisting it in `github_sync_map` is the anti-pattern the November derived-roadmap spec forbade. An opaque `arc_uid` / `phase_uid` on `goals`, shared by every member of a group, with the positional `id` left as a display index, is a general join key. A whole-group rename keeps the uid because the assign trigger runs only when the column is null, and priority or sort changes never touch it. That part matches the goal.

The freeze is too early, and the regroup rule is missing. Identity sticks at first placement, while the arc is still `planned`. The goal is that rename, reorder, split, merge, and phase moves stay cheap until an arc or phase ships. Today those are updates to `arc_version` / `phase_title`. Under this plan a partial move keeps the source uid, so two versions share one key. The view's `MAX(arc_uid)` and the `github_sync_map` primary key then collide. A merge keeps two uids under one version unless someone nulls `arc_uid` first — a ritual the spec mentions and the plan neither documents nor tests. The phase `INSTEAD OF UPDATE` already rewrites `arc_version` and `phase_title` and would leave both uids behind. Nothing distinguishes shipped (a milestone binding exists, so freeze) from pre-ship (regroup must recompute membership).

Scope is still the milestone bug. `phase_uid` is written and never read. `sync_arc` still takes the positional `arc_id`; only the stored `entity_id` changes, which reverses the spec's rule that this path stop holding the view id. `cost_entries.epic_id` / `phase_id` stay on the drifting id (gh:#5446). The one-time migration deletes entity ids `"2"` and `"10"` by that same unstable positional key, with no live title check, and the read path switches to `arc_uid` before that migration runs. Existing integer maps miss, and title fallback rebinds milestones.

Change the membership rule before any code. On `arc_version` / `phase_title` change: all members moving together keep the uid; a subset adopts the destination uid or mints one; a merge is an explicit adopt. Freeze that uid only once an external binding exists. Land the `github_sync_map` rewrite in the same change as the lookup switch, keyed by current uid. Keep `phase_uid` only under that same rule.

**Position:** Do not implement this plan as written. The column-on-`goals` approach can stay. The sticky-at-placement semantics and the milestone-only cutover should change first.

## Synthesis
The panel agrees on the core design and disagrees only on how firmly to hold the plan back. Every member backs opaque, write-once `arc_uid` and `phase_uid` columns on `goals`, with the positional `id` kept as a display index. A whole-group rename is uid-stable with no special code, and that fixes LIVE-34. This synthesis relies on the panel's reading of the spec and plan. I haven't re-checked it against the files, and the claude member only skimmed the plan.

**Where the panel agrees**
- **Regrouping is undefined.** The uid is assigned once at first placement and never recomputed. A partial move carries the old uid into the new arc, and a merge leaves two uids under one `arc_version`. Both are the pre-ship restructuring the goal wants to keep cheap. The only documented merge procedure is a manual `UPDATE goals SET arc_uid = NULL`.
- **Inconsistency is hidden.** The views use `MIN` and `MAX` over uids. If a group ends up with two uids, they pick one silently, and the `github_sync_map` primary key can then collide.
- **uid lifetime is unspecified.** Retired uids from a merge, a split or an emptied arc leave consumer rows orphaned, because there is no alias or redirect table.
- **Phase moves are unhandled.** A phase renamed or moved to another arc picks up the destination's uid or a fresh one. The `INSTEAD OF UPDATE` trigger rewrites both columns and leaves the uid behind.
- **The scope is still the milestone bug.**
  - The plan keeps `sync_arc(arc_id: int)`, which contradicts the spec's `arc_uid` signature.
  - `phase_uid` is written but never read.
  - `cost_entries` (gh:#5446) is excluded.
  - No consumer rule or resolver exists for other domains.
- **The cutover is weak.**
  - The read path switches to `arc_uid` before the mapping rewrite.
  - The migration deletes entity ids `"2"` and `"10"` by the same unstable positional key.
  - Backfill makes live `gh api` calls inside the migration.

**Required changes before any code**
1. **Regroup semantics:**
   - When all members move together, the uid is kept.
   - When a subset moves, it adopts the destination uid or mints a new one.
   - A merge is an explicit adopt.
   - The uid freezes only once an external binding such as a milestone exists. Before that point regrouping recomputes membership.
2. **Supported operations:** add `merge`, `split` and `move_phase` APIs that rewrite uids and record the old uid in a `roadmap_uid_aliases(old_uid, new_uid)` table. Define uid lifetime explicitly.
3. **Invariant enforcement:**
   - Each active group must resolve to exactly one uid.
   - Use `COUNT(DISTINCT)` instead of `MIN` and `MAX`.
   - Add a deterministic ordering to the assignment query.
   - The migration fails loudly on conflicts.
   - `doctor` checks for divergence.
4. **Generalize beyond milestones:**
   - Add a shared resolver such as `resolve_arc(uid_or_alias)`.
   - Add a lint or test that fails when a table persists `roadmap_arcs.id` or `roadmap_phases.id`.
   - Add a short "how to reference an arc" doc.
   - Migrate `sync_arc` and the CLI handlers to `arc_uid`.
   - Give `phase_uid` a real consumer or tests.
   - Validate the model against `cost_entries`.
5. **Cutover:**
   - Make the migration offline-safe and run the `gh api` verification as a separate step.
   - Land the `github_sync_map` rewrite in the same change as the lookup switch, keyed by current uid.
   - Replace deletion by positional id with a title-verified, audited step.
   - Include phase mappings.

**Decision:** Do not implement the plan as written. Keep the uid-on-`goals` approach, with the views and the display-only `id`, and revise the spec and plan first. The revision covers five things:
- regroup semantics that freeze identity only once an external binding exists;
- supported merge, split and move operations backed by an alias table;
- one-uid-per-group invariants enforced in the views, migration and `doctor`;
- a shared resolver and consumer rule, with `sync_arc` moved to `arc_uid` and `cost_entries` validated;
- an atomic, audited cutover that rewrites mappings together with the lookup switch.

Once the revised spec is committed, regenerate the plan and its GOVERNS-linked stories, then dispatch implementation to a non-Claude harness. Claude's own position was "proceed after fixing four things". That is the same revise-first path, since all four of its fixes are in this list.

## Decision
Once the revised spec is committed, regenerate the plan and its GOVERNS-linked stories, then dispatch implementation to a non-Claude harness. Claude's own position was "proceed after fixing four things". That is the same revise-first path, since all four of its fixes are in this list.

> Signatures: see 2026-11-21-review-the-committed-spec-docs-superpowe.json
