<!-- generated - source of truth is state.db -->
---
decision_id: dec-e36246da
topic: "Split goal-079e2f37 (343-story architectural-review catch-all) into separate goals. goal-85eb189e = remaining review findings (R2/R4/R11/R13/R14/R15/R16) plus standing CI failures, 13 stories, code release v0.39.7. Confirm the phase-1 grouping is coherent as one release and that nothing in it should move. Give a one-paragraph position: approve, approve with changes, or reject."
date: 2026-11-25
panel: [claude]
status: approved
---

## Topic
Split goal-079e2f37 (343-story architectural-review catch-all) into separate goals. goal-85eb189e = remaining review findings (R2/R4/R11/R13/R14/R15/R16) plus standing CI failures, 13 stories, code release v0.39.7. Confirm the phase-1 grouping is coherent as one release and that nothing in it should move. Give a one-paragraph position: approve, approve with changes, or reject.

## Panel Inputs

### claude
[model=sonnet; version=2.1.327 (Claude Code)]

**Position: approve with changes.**

I can't confirm coherence from the evidence I have. I haven't inspected the 13 stories, so this is a structural judgment, not a verified audit.

**What holds up.** The split itself is sound. A 343-story catch-all can't ship as one release or be reasoned about as a unit. Separating the remaining review findings (R2, R4, R11, R13, R14, R15, R16) into their own goal makes the work tractable. The memory notes say R2 is "the real fix" for the LIVE-17 nested-writer deadlock, so it's the highest-value item and should anchor the release. Giving the goal its own version (v0.39.7) fits the #5525 principle that the sweep should package whole goals.

**Concerns.**

1. **Review findings and CI failures are different kinds of work.** Review findings are architectural remediation. Standing CI failures are hygiene. Bundling them is defensible if the failures block the R-items' own verification, since a red baseline makes "green" meaningless. If the failures are unrelated, they should go in a separate patch-level release. I'd ask for an explicit dependency check. If no R-item needs a green CI, move the CI stories out.
2. **The R-items have uneven risk.** R2 is a structural writer/locking change. R11 through R16 are likely smaller. A single release means one regression in R2 blocks the cheap fixes. I'd keep them together only if they touch the same module area or share test surface. Otherwise I'd ship the low-risk items first.
3. **v0.39.7 is a patch number for a code release.** The Named Release Policy reserves `vX.Y.Z` for hotfixes with no new surface area. If any of these stories add behavior, this should be v0.40.0. Check that before tagging.
4. **Orphan check.** Confirm that the other ~330 stories have a destination goal. Otherwise the split leaves them unowned and trips the Roadmap Drift Gate. Also confirm that no story linked to a decision or roadmap arc still points at the old goal-079e2f37.
5. **GOVERNS linkage.** Each of the 13 stories needs a linked parent issue, per the series-tracking protocol.

**Recommendation.** Approve the split and the 13-story membership on condition that (a) CI-failure stories are verified as blockers for the R-items, or moved to a separate patch release, (b) the version number is justified against the hotfix-only rule, and (c) an orphan and drift check runs on the remaining stories before goal-079e2f37 is retired. Nothing else needs to move, though I'd want to see the story list before signing off on R2's coupling with the smaller items.

## Synthesis
Decision: **Approve with changes.** The split of goal-079e2f37 into goal-85eb189e (the 13-story phase-1 goal) is approved, but three conditions apply before it ships as v0.39.7.

1. **CI-failure stories.** Check whether any of the R-items (R2, R4, R11, R13, R14, R15, R16) depends on a green CI baseline to verify its own work. If one does, keep the CI stories in the goal. If none does, move them to a separate patch release. Review remediation and CI hygiene are different kinds of work.
2. **Version number.** Check that v0.39.7 fits the Named Release Policy, which reserves `vX.Y.Z` for hotfixes with no new surface area. If any story adds behavior or a new command, use v0.40.0 instead. Record the justification in the goal.
3. **Orphan and drift check.** Before goal-079e2f37 is retired, confirm that each of the other ~330 stories has a destination goal. Confirm that no decision or roadmap arc still links to the old goal. Run `synlynk roadmap check` for this, so the Roadmap Drift Gate doesn't block later PRs.

R2 is the highest-value item and should anchor the release. It is also the riskiest. If R2's change touches different modules from the smaller R-items and shares no test surface with them, ship the smaller items first. A regression in R2 would otherwise hold them back.

The panel's one input was Claude's, and it did not inspect the 13 stories. I'm taking the coherence verdict as a structural judgment, not a verified audit. Before dispatch, someone should read the 13 stories and confirm each has a linked parent issue, as the series-tracking protocol requires. I haven't run any of these checks.

## Decision
Decision: **Approve with changes.** The split of goal-079e2f37 into goal-85eb189e (the 13-story phase-1 goal) is approved, but three conditions apply before it ships as v0.39.7.

> Signatures: see 2026-11-25-split-goal-079e2f37-343-story-architectu.json
