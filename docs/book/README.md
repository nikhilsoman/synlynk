# "The Supervised Machine" — Book Manuscript

A nonfiction book grounded in synlynk's real build history and three sister projects (rxcc, cc-videoreframing, Playblazer). Written by Claude, sourced from `docs/blog/`, commit history, strategy docs, and project/feedback memory files — see the manuscript's own closing "A Note on Sources" section for full sourcing discipline.

**Status: working draft, one reader so far.** This is versioned by minor number (`v0.1`, `v0.2`, ...), not by "edition" — "1st/2nd Edition" implies a publish event that hasn't happened yet. Every pre-publish version carries a `DRAFT` suffix in its filename and a "WORKING DRAFT — NOT FOR DISTRIBUTION" marker on its cover page. Drop the `DRAFT` suffix (and bump to a real version number) only once the manuscript is actually publish-ready.

## Files

- `the-supervised-machine-v0.5-DRAFT.html` — source of truth. Single-file, self-contained HTML (inline CSS, no external assets).
- `the-supervised-machine-v0.5-DRAFT.pdf` — rendered output, regenerated from the HTML. Do not hand-edit the PDF.

## Editorial history

This draft's structure and content were shaped by a formal editorial-panel review, recorded as a Decision at `project-docs/decisions/2026-08-29-editorial-review-the-supervised-machine.md`. That review's four targeted edits (front-matter glossary + endnoted citations, Part One/Two chapter consolidation, Chapter 14 dedup fix, Chapter 16 reframed as a coda, Chapters 17–19 merged) are reflected in this version.

This draft also incorporates the first chapters written under the multi-author
repositioning: see `docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md`
for the chapter-ownership map and the live claude/codex/grok/agy consultation this design
was based on.

This draft also adds Part II ("The Onboarding"): see
`docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md` Section 4 for
the lead/contributor split (Agy leads, Codex contributes a named practical recipe within
the same chapter rather than a separate byline).

This draft also restructures Part III ("Field Notebook"): the existing rxcc,
cc-videoreframing, and Playblazer chapters are retitled and relabeled under the new
framing, joined by two new chapters (Grok on the fleet's own infra evidence, Claude on
the reviewer's seat) and a Codex fact-check/rigor annotation layer running across all
five chapters. See
`docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md` Section 4.

This draft incorporates the Strategic Review integration — see
`docs/superpowers/specs/2026-09-03-book-strategic-review-integration-design.md` — adding
the Part Two Neutral Layer chapter (new Chapter Ten) and the Part Four Three Positions in
the Sun chapter (new Chapter Eighteen), deep-dive expansions of the rxcc and
cc-videoreframing Part III chapters (including a LIVE-5/#99 framing correction, from a
fabricated-timestamps account to the actual root cause, a variable-frame-rate
declared-vs-true timing mismatch), expansions of Chapter Sixteen (a competitive
product-stack scorecard) and the closing chapter (Gartner-sourced market sizing), and
embedded Stitch UI mockups for the rxcc chapter (`docs/book/assets/`). Also adds the
pre-Part-0 cold-open, written per the same spec's Section 4a ahead of this plan's own
execution.

## Rebuilding the PDF

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=docs/book/the-supervised-machine-v0.5-DRAFT.pdf \
  "file://$(pwd)/docs/book/the-supervised-machine-v0.5-DRAFT.html"
```

Regenerate the PDF and commit both files together whenever the HTML changes — never let them drift. When cutting a new minor version, rename both files (`vX.Y-DRAFT`), update the cover/title/preface version strings in the HTML, and update this README.
