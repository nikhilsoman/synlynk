---
title: "PR #1239 — The Book Gets Co-Authors: Part 0 + Part I, v0.3-DRAFT"
date: 2026-08-29
series: "Building the OS for Multi-Agent Development"
post: 131
pr: "#1239"
merged: "2026-08-29"
---

## The Broader Goal at the End of the Previous PR

"The Supervised Machine" (`docs/book/`) existed at v0.2-DRAFT as a single-voice engineering
memoir written by Nikhil, with Claude/Codex/Grok/Agy appearing only as reviewers and marginal
commentators. That draft closed out a phase of internal use — it was a project artifact, not
yet a book positioned for an outside reader. The multi-author repositioning brainstorm
(`docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md`) reframed the
project: broaden from an engineering memoir into a book about human-AI collaboration, and make
the four harnesses genuine co-authors with discernible voices and real disagreements in the
text, not just editorial sign-off.

## Strategic Shifts in This PR

None beyond what the design doc already committed to. This PR is the first execution slice of
that design — Part 0 and Part I only (4 chapters), with Parts II–IV explicitly deferred to
follow-on plans once this slice is reviewed. The chapter-ownership map from the design's
Section 4 was followed exactly: Grok led the Reckoning chapter (Part 0) and the "power tools
have kickback" chapter; Claude led the "cognitive tool, not magic" chapter; Agy led the
"context & working memory" chapter — each dispatched through `synlynk dispatch <agent>
--force-agent --context-mode full` rather than authored inline, so the chapter drafting itself
went through the same telemetry/cost capture path as any other dispatched work.

## What This PR Shipped

- Four new chapters merged into `docs/book/the-supervised-machine-v0.3-DRAFT.html` (renamed
  from v0.2-DRAFT), each written by its assigned co-author under the `.who.<agent>` /
  `.who.human` dialogue-box CSS convention already established in the manuscript.
- Marginalia insertions gated by the design's hard rule: real disagreement or a cited incident
  only, never manufactured color. Every marginalia citation in this slice traces to a real
  GitHub issue or PR (#1166, #880, #426, #1176, #1177, #479, #1197, #1205) — verified by the
  reviewing job directly against `gh issue view` / `gh pr view`, not taken on faith.
- A rebuilt PDF (`the-supervised-machine-v0.3-DRAFT.pdf`, 968,851 bytes, 8 pages) via headless
  Chrome, and a `docs/book/README.md` bump from v0.2-DRAFT to v0.3-DRAFT with an added
  Editorial History note pointing back at the design doc.
- Structural verification before merge: `html.parser` clean parse, `<div>`/`</div>` counts
  matching at 217/217, `<chapter>`/`</chapter>` counts matching at 25/25, and a
  `git diff -M origin/main...HEAD` confirming zero deletions in the existing Parts One–Four —
  the new chapters extend the manuscript, they don't touch what was already there.

The PR itself surfaced one process wrinkle worth recording: this project's PR Review Discipline
requires a *non-authoring* agent to review and merge, and Claude (the PM session) had authored
PR #1239 directly. `.synlynk/policy.json`'s `review` task-allocation routes to `claude` with
`agy` as fallback — since Claude was disqualified as author, the fallback correctly took over.
Dispatching that review hit two infrastructure snags before it ran clean: the worktree was
missing its `.synlynk/github_apps/` symlink (a known gap — see
`worktree-github-apps-gap.md`), and once that was fixed, the `qa` role's GitHub App token had
actually expired because `synlynk daemon` (which auto-refreshes it) wasn't running. Starting
the daemon and re-running `synlynk identity init --role qa` cleared both. Once dispatched, Agy
ran `synlynk pr check`, verified the structural checks above, posted a formal COMMENT review
(the sanctioned fallback for shared-GitHub-identity constraints — see PR #417), cleared
`synlynk policy check-merge --role qa`, and squash-merged. The job's own status label came back
as the ambiguous `succeeded_gh_write_failed` despite having genuinely succeeded — resolved by
cross-checking `gh pr view --json state,mergedAt,mergeCommit` directly, which matched the job's
self-report exactly, including the merge commit SHA. Another data point for this project's
standing rule: never trust a dispatch status label alone.

## Brainstorm Visuals Used

None — this slice followed a text-only design/plan pair
(`docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md` and
`docs/superpowers/plans/2026-08-29-book-multiauthor-part0-part1-slice.md`); no visual companion
session was run for this brainstorm.

## What This Achieved on the Path to Autonomy

This is the first manuscript content that ever went through the full dispatch → verify →
non-authoring-review → merge pipeline that the rest of synlynk's engineering work already uses.
It proves the same discipline — don't trust job status alone, verify structurally, route review
away from the author, clean up dispatch worktrees immediately on merge — holds for prose
authorship as well as code. Eight nested dispatch worktrees (four chapter-drafting jobs, the
review job, and three earlier attempts/retries) and their branches were swept immediately after
merge per the Worktree Hygiene Protocol, keeping this from becoming one more entry in the kind
of stale-worktree backlog that prompted that protocol in the first place.

## Strategic Note: The Goal at the End of This PR

The next goalpost is Parts II–IV of the repositioning: Agy's Part II chapter plus Codex's named
contributions within it, and the Part III infra-evidence and meta chapters (Grok and Claude
respectively, per the design's ownership table), each needing its own plan once this Part 0/I
slice has had a chance to be read. The "How to Read This Book" front-matter segment map from
the design's Open Items is still outstanding and belongs in that next plan rather than being
retrofitted here.
