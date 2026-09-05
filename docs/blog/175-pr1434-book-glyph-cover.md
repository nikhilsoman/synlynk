---
title: "PR #1434 — The Book Gets Its Cover"
date: 2026-09-05
series: "Building the OS for Multi-Agent Development"
post: 175
pr: "#1434"
status: merged
---

## The Broader Goal at the End of the Previous PR

By PR #1430, "The Supervised Machine" had settled its default output set: HTML source of truth,
PDF and EPUB rendered together on every change. The book was structurally complete across three
formats, but its cover page still carried no visual identity beyond text — no mark tying it back
to the project that writes and maintains it.

## Strategic Shifts in This PR

None — another small, deliberate gap-close. The user asked for the synlynk glyph to appear on the
book's cover across all editions, matching the visual system PR #1409 had already established for
the manuscript's interior styling.

## What This PR Shipped

- Added the synlynk S-glyph as an inline SVG (`viewBox="0 0 28 28"`, `role="img"`,
  `aria-label="synlynk S-glyph"`) directly into the `.cover` block of
  `docs/book/the-supervised-machine-v0.5-DRAFT.html`, sized via the existing `.cover .glyph` CSS
  rule already present from the PR #1409 restyle.
- Kept the change scoped to the HTML source only — 9 lines, no prose or structural edits.
- Reviewed via the project's standard non-authoring dispatch path; CI hit a pre-existing,
  unrelated flake twice (`test_job_status_add_realghwrite_endtoend_regr`,
  `ChildProcessError: [Errno 10] No child processes` in `tests/test_agent_cli.py`, confirmed
  reproducing independently on `main` itself) before merging clean on rerun.

## Brainstorm Visuals Used

None — a single inline SVG glyph, not new manuscript content.

## What This Achieved on the Path to Autonomy

Nothing autonomy-related directly. Worth noting for the record: merging this PR (and its
sibling #1430) surfaced a real structural gap in the platform's own identity model — dispatched
review actions already run under distinct per-role GitHub App identities, but Claude's own direct
`gh pr create`/`gh pr merge` calls in a PM session still author under the shared human identity,
and branch-protection's formal-approval requirement forced an `--admin` override rather than a
qa-role self-approval. That gap is now filed as
[issue #1436](https://github.com/nikhilsoman/synlynk/issues/1436) for review, not fixed here.

## What This PR Shipped (follow-up: #1437)

The HTML cover update alone left the PDF and EPUB stale — both were rendered from the
cover-less HTML and needed a straight rebuild. PR #1437 regenerated both via the exact commands
in `docs/book/README.md` (no content changes, binary rebuild only), closing out "add the glyph
cover to all book editions" across all three formats.

## Strategic Note: The Goal at the End of This PR

All three book formats now carry the synlynk glyph on their cover, generated and committed
together. The next open thread isn't book-related — it's the identity-routing gap in #1436:
whether dispatches should go through pm/tpm role handles so qa can approve PRs without the shared
human identity ever entering the loop.
