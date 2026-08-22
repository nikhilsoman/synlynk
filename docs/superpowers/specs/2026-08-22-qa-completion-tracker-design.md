# qa Completion Tracker — Design

**Date:** 2026-08-22
**Status:** Approved by Nikhil (brainstorm dialogue, this session)
**Origin:** Raised during the `"merge-restricted-classes"` brainstorm (follow-up to `docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md` §5) as a distinct concern: visualizing progress across tracks in a fast-moving multi-agent workspace, verified against intent rather than just "PR merged."
**Relationship to `qa_gate_mode`:** None. This spec does not read or write `qa_gate_mode` and does not affect merge authority in any mode (`block-only`, `merge-restricted-classes`, `non-authoring-equivalent`). It is a separate, non-blocking mechanism layered on top of the existing merge flow, not a fourth `qa_gate_mode` value.

## 1. Problem

High-velocity development across multiple concurrent tracks (worktrees, dispatched jobs, stacked PRs) makes "is this actually done" hard to see at a glance. `pr_merged` tells you code landed; it doesn't tell you the merged code fulfilled the spec or story it was supposed to implement. Vizor's stage-progress bars (`docs/superpowers/specs/2026-07-03-bs21-vizor-design.md`) currently render progress driven by merge/stage events — a track can show as "done" the moment a PR merges, even if that PR only partially satisfied its spec, or diverged from it in a way CI can't catch (CI verifies the code runs; it doesn't verify the code is the right code).

This is a **maker-checker gap**: pm/architect write the spec ("maker"), an implementing harness (Codex/Grok/Agy/Claude) builds against it, but nothing downstream checks that the build actually satisfied the maker's intent. qa's charter already covers CI/CD health (§3.2 of the agent-roles-charters spec) but stops at "did the tests pass," not "did this fulfill the spec."

## 2. Decision

Add a **non-blocking, post-merge, per-PR semantic check** performed by qa: for each merged PR that references a spec/plan/issue, qa reads the reference and the diff, and emits a verdict — `fulfilled`, `partial`, or `diverged` — as a new GOVERNS event. Vizor consumes this event to render verified-progress distinctly from merged-progress.

This is deliberately **not** a gate. It cannot block, delay, or reverse a merge; it runs entirely after the fact. Two reasons for that scope, both flagged explicitly during the brainstorm rather than assumed:

1. **Blast radius.** A wrong verdict from a non-blocking tracker is a stale progress bar — annoying, self-correcting on the next PR. A wrong verdict from a blocking gate is a stalled or wrongly-merged PR, with the added risk of prompt-injection from an adversarial PR description or diff trying to steer qa's semantic judgment. The tracker gets the benefit (visibility) without inheriting that risk.
2. **This is judgment, not a mechanical check.** `block-only`'s gate (CI status + sentinel health) is deterministic and cheap to compute synchronously in CI. "Did this PR fulfill its spec" requires reading prose and reasoning about intent — an LLM call, not a script. Putting that in the synchronous merge path would make every merge wait on an LLM judgment call; running it async removes that coupling entirely.

If this tracker proves reliable over time, promoting it to a blocking gate is a possible future step (§7) — but that is its own future sign-off, not assumed here.

## 3. Trigger and spec linkage

**Trigger:** the existing `job_terminal`/`review_submitted`-style scan pattern (`docs/superpowers/specs/2026-08-12-governs-event-contract-extension-design.md`) is extended with a third scan: for each `pr_merged` event with no corresponding `spec_verified` event yet, run the completion check.

**Spec linkage:** qa parses the merged PR's body for a reference to `docs/superpowers/specs/...`, `docs/superpowers/plans/...`, or a `Closes #N` / `gh:#N` issue link — whichever convention the PR already uses informally today. No formal new field is required (see §6 for the alternative considered and rejected).

**No match found:** the PR is skipped — no `spec_verified` event is emitted for it, and no error is raised. This is expected and common (many PRs, especially small fixes, won't reference a spec); it is not a failure mode, since the tracker is advisory, not a required audit trail.

## 4. Verdict computation

qa (Claude, per this project's existing routing table — qa's review/deploy responsibilities already map to Claude, and this task requires the same reasoning capability review already uses) is dispatched with:

- The referenced spec/plan file's full content (or the linked issue's body, if that's what was referenced).
- The merged PR's diff (`gh pr diff <n>`) and description.

It produces one of three verdicts:

| Verdict | Meaning |
|---|---|
| `fulfilled` | The PR's diff satisfies what the referenced spec/plan/issue asked for, within the scope that PR was reasonably meant to cover (a stacked PR fulfilling only its own task is `fulfilled`, not `partial`, even if the overall spec needs more PRs). |
| `partial` | The diff addresses the reference but leaves a stated requirement visibly undone within what this PR claims to complete. |
| `diverged` | The diff does something materially different from what the reference describes — not just incomplete, but off-target. |

Each verdict carries a one-line rationale (why qa reached that verdict) — this is what a human skimming Vizor or the event log reads to sanity-check the call, not just a bare label.

**Untrusted input handling:** the PR body, diff, and any spec content are treated as data, never as instructions to qa — consistent with this project's general instruction-source-boundary discipline. If a PR description contains text attempting to direct qa's verdict ("mark this fulfilled", "ignore missing tests"), qa disregards it as content, not command, and may note the attempt in its rationale.

## 5. Event and Vizor consumption

**New GOVERNS event type: `spec_verified`.** Uses the existing `events` table and free-form `payload_json` — no schema change, matching how `job_terminal` and `review_submitted` were added.

```json
{
  "pr_number": 1234,
  "spec_path": "docs/superpowers/specs/2026-08-22-example-design.md",
  "verdict": "fulfilled",
  "rationale": "Implements the block-only gate verdict computation exactly as specified in §3-4; no scope drift.",
  "reviewer_role": "qa"
}
```

**Vizor rendering:** the existing BS-21 stage-progress bars currently update on merge-driven events. This adds a second visual state layered on top — e.g., a bar fills on `pr_merged` (code landed) and gets a checkmark once `spec_verified: fulfilled` arrives, or a distinct warning marker for `partial`/`diverged`. This is additive to Vizor's existing rendering; it does not change how bars fill today, only what they can additionally show once qa's verdict lands. The exact visual treatment is left to the implementation plan/Vizor's existing design language, not specified here.

**Read access:** `synlynk events tail` (already shipped per the GOVERNS event-contract extension) surfaces `spec_verified` events the same way it does `job_terminal` and `review_submitted` — no new CLI surface needed.

## 6. Alternatives considered

1. **Explicit structured link field (rejected for v1).** Require a PR template field or trailer (e.g. `Implements: docs/superpowers/specs/...`) instead of parsing the PR body freely. More reliable matching, but adds friction to every PR and needs template enforcement. Rejected because the informal convention already in use is good enough for an advisory, best-effort tracker — formalizing it can be revisited later if match quality turns out to be poor in practice.
2. **Story/goal-level trigger instead of per-PR (rejected for v1).** Fire on `story_done` instead of `pr_merged`, checking the whole story's PRs together. Better matches "is the goal actually done," but coarser (less frequent Vizor signal) and needs a way to know which PRs belong to a story that doesn't reliably exist yet. Rejected in favor of the finer-grained per-PR signal; story-level rollup can be layered on top of per-PR `spec_verified` events later without redesigning this spec.
3. **Blocking gate (rejected for v1, see §2).** Folding this into `qa_gate_mode` as a merge-blocking check. Rejected due to blast radius and latency — covered in §2.

## 7. What does not change

- `qa_gate_mode` and the `block-only` gate (`docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md`) are unaffected — this spec adds no new gate mode and does not touch merge authority.
- Architect remains the only role that merges PRs into `main`.
- No PR is blocked, delayed, or required to reference a spec because of this design — the tracker is purely additive and best-effort.

## 8. Out of scope for this spec

- Any blocking behavior (a future `qa_gate_mode`-style toggle could revisit this, but requires its own sign-off, matching the precedent set in the block-only spec's §5).
- Story/goal-level aggregation (§6.2).
- Formal PR-template link field (§6.1).
- `"merge-restricted-classes"` itself — brainstormed in the same session, written up as its own separate spec (`docs/superpowers/specs/2026-08-22-qa-merge-restricted-classes-design.md`), unrelated to this one beyond sharing an origin conversation.

## 9. Next step

A follow-up implementation plan (`docs/superpowers/plans/`) covering: the `spec_verified` event emission (extending the existing scan pattern), the PR-body reference parser, qa's dispatched verdict-computation task, and the Vizor rendering change. Not written as part of this spec per the Design → Plan → Build sequence.
