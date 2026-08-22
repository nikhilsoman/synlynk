## Goal at the End of the Previous PR

Post #123 landed the qa-merge-gate-authority stack: `synlynk pr check` computes a
real block/pass verdict from CI + sentinel state, and `apply_qa_gate_branch_protection.sh`
exists (dry-run verified, not yet applied for real). Three things were explicitly
deferred: applying branch protection for real, landing #1079's original design spec
doc, and the follow-up work each of those specs called out as "not built yet" —
including a reserved-but-unbuilt `qa_gate_mode` value (`merge-restricted-classes`)
and a way to verify that a merged PR actually fulfilled the spec/plan it claimed to
implement, not just that its own tests passed.

## No Strategic Shift

Both plans executed this PR were written and approved before #123 merged
(`docs/superpowers/plans/2026-08-22-qa-completion-tracker.md` off spec #1091,
`docs/superpowers/plans/2026-08-22-qa-merge-restricted-classes.md` off spec #1079 §5).
Nikhil approved running both in parallel via subagent-driven-development once #123
was stable. No goalpost moved — this is the two follow-ups #123 named, built.

## What Shipped, Technically

**PR #1100 — Completion Tracker (qa-completion-tracker plan, 4 tasks):**

- `synlynk/completion_tracker.py`: `parse_spec_reference()` extracts a spec/plan
  path or issue reference out of a PR body; `compute_completion_verdict()` +
  `_load_reference_content()` produce a fulfilled/partial/diverged verdict with
  rationale by comparing the referenced spec against the actual PR diff.
- `synlynk/events.py`: `_scan_pr_completion()` + `_existing_spec_verified_pr_numbers()`
  wired into `scan_local_events()` — mirrors the existing `review_submitted` scan
  pattern from the GOVERNS event-contract extension, finding `pr_merged` events with
  no matching `spec_verified` event yet and emitting one once a verdict is computed.
- `synlynk/viz.py`: new Vizor panel on the existing BS-21 stage-progress bars —
  `_load_spec_verifications()` loader, `spec_verifications` key in `_base_data()`,
  `renderVerified()` / `toggleVerifiedPanel()` / `renderVerifiedEntry()` JS, plus a
  summary card and panel in the HTML — so merged-but-not-yet-verified PRs are now
  visually distinct from merged-and-verified ones, closing the gap #123 flagged: a
  dispatched agent's own tests passing was never the same claim as "this PR actually
  did what the spec said."
- Tests: `tests/test_completion_tracker.py`, `tests/test_completion_tracker_vizor.py`,
  extensions to `tests/test_events.py`.

**PR #1101 — Merge-Restricted-Classes Gate Mode (qa-merge-restricted-classes plan, 4 tasks):**

- `synlynk/merge_class.py`: `is_docs_only_change()` — a file-pattern matcher that
  classifies a PR's changed files as docs-only or not.
- `synlynk/qa_gate.py`: `_qa_gate_mode()` reads `qa_gate_mode` from
  `.synlynk/config.json` (default `"block-only"`); `_gh_pr_changed_files()` wraps
  `gh pr diff <n> --name-only`. A real bug surfaced and was self-corrected mid-task
  here: the first commit (`353e38e`) read `synlynk/config.json` instead of
  `.synlynk/config.json`; a follow-up commit (`a37e3e8`) fixed it before the PR was
  finalized — caught by the implementer's own review pass, then independently
  re-verified in this session's spec-compliance review.
- `synlynk/db.py`: wired the fast path into `cmd_pr_check()` — when
  `qa_gate_mode == "merge-restricted-classes"` and the PR is docs-only, qa merges it
  directly rather than routing through the full block-only gate. Task 3 also added
  module-level wrapper functions (`_qa_gate_mode`, `_gh_pr_changed_files`,
  `_is_github_remote`, `_current_pr_number`, `_extract_pr_review_cycles`,
  `_apply_review_cycle_multiplier`) re-exporting the real implementations from
  `qa_gate.py`/`pr_multiplier.py`/`sentinel.py` — necessary, not scope creep: the
  plan's own test fixtures patch these exact names as `synlynk.db.*` module
  attributes, which requires them to exist at module scope.
- Task 4: since `.synlynk/config.json` is gitignored, this task landed as a
  spec-doc note (in the gate-authority design doc) rather than a code default —
  correctly scoped to what's actually committable.

Both PRs were reviewed directly by Claude (spec-compliance first, then code
quality — no sub-delegated review) against their authoritative plan text, comparing
diffs section-by-section rather than trusting the implementer's own summary. Zero
blocking findings on either. Both merged via the #423 COMMENT-review-with-checklist
fallback (`gh pr review --approve` fails under the shared bot identity), then
`gh pr merge --squash`.

## Process Note: Dispatch Stacking Produced 8+ PRs for 2 Plans

Both plans stacked 4 tasks each via `synlynk dispatch <agent> --base <branch>`.
Every stacked task opened its own PR against `main` rather than against the parent
task's branch — not a one-off, a `--base` behavior. The two 4-task plans produced
8+ PRs and 16 worktrees/branches total, requiring a full Worktree Hygiene Protocol
sweep after both terminal PRs (#1100, #1101) merged: cross-referencing every branch
against `gh pr list --state all` and, since squash merges break literal ancestry,
validating no-PR branches against their pre-squash terminal branch tips instead of
`origin/main` directly. All 16 worktrees and local branches removed, 12 remote
branches explicitly deleted (4 had already been auto-pruned by GitHub on
merge/close). This is now recorded as a standing process note for future stacked
dispatch sessions — worth a synlynk issue to make `--base` target the parent
branch as PR base instead of always opening against `main`.

## Brainstorm Visuals Used

None — both plans executed directly off their already-approved spec/plan documents;
no new brainstorming was needed.

## What This Achieved on the Path to Autonomy

The completion tracker closes a trust gap the qa-gate stack (#123) opened but didn't
close: a green qa-gate proves CI passed, not that the PR did what it claimed. Vizor
now distinguishes merged from verified, giving a human (or eventually another agent)
a place to see that distinction without re-reading every diff. The merge-restricted-
classes mode is the first concrete, narrow answer to #1079 §5's deferred question —
"what PR class is safe to let qa merge unattended" — landing exactly the example the
original spec named (docs-only) rather than the broader, harder case (dependency
bumps, CI config) that still needs its own design pass.

## Strategic Note: The Goal at the End of This PR

Both #1091 and #1079's design-doc PRs (still open) now have their concrete follow-up
plans fully implemented, reviewed, and merged. What remains, unchanged from #123's
own deferred list: actually applying branch protection for real (still a deliberate
human-confirmed step, not yet scheduled), and landing #1079/#1091 themselves as
merged design docs rather than leaving the implementation ahead of the spec. The new
goalpost: extend `qa_gate_mode == merge-restricted-classes` to the harder PR classes
#1079 §5 named but deferred (dependency bumps, CI config), now that the docs-only
case has a working, reviewed reference implementation to build from.
