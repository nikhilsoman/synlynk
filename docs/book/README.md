# "The Supervised Machine" — Book Manuscript

A nonfiction book grounded in synlynk's real build history and three sister projects (rxcc, cc-videoreframing, Playblazer). Written by Claude, sourced from `docs/blog/`, commit history, strategy docs, and project/feedback memory files — see the manuscript's own closing "A Note on Sources" section for full sourcing discipline.

**Status: working draft, one reader so far.** This is versioned by minor number (`v0.1`, `v0.2`, ...), not by "edition" — "1st/2nd Edition" implies a publish event that hasn't happened yet. Every pre-publish version carries a `DRAFT` suffix in its filename and a "WORKING DRAFT — NOT FOR DISTRIBUTION" marker on its cover page. Drop the `DRAFT` suffix (and bump to a real version number) only once the manuscript is actually publish-ready.

## Files

- `the-supervised-machine-v0.5-DRAFT.html` — source of truth. Single-file, self-contained HTML (inline CSS, no external assets).
- `the-supervised-machine-v0.5-DRAFT.pdf` — rendered output, regenerated from the HTML. Do not hand-edit the PDF.
- `the-supervised-machine-v0.5-DRAFT.epub` — rendered output, regenerated from the HTML. Do not hand-edit the EPUB.
- `epub-metadata.yaml` — stable EPUB publication metadata used by the build.
- `epub.css` — reflow-safe Apple Books stylesheet; it is separate from print CSS by design.
- `assets/supervised-machine-cover.png` — RGB cover art used by the EPUB cover page.

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

## Rebuilding the EPUB

Requires `pandoc` (`brew install pandoc`). Chapters split at `<h2>` (the manuscript's actual
chapter-heading level — splitting at `<h1>` produces one giant chapter). Run from `docs/book/`
so relative image paths under `assets/` resolve:

```bash
cd docs/book
pandoc the-supervised-machine-v0.5-DRAFT.html \
  -o the-supervised-machine-v0.5-DRAFT.epub \
  --metadata-file=epub-metadata.yaml \
  --css=epub.css \
  --epub-cover-image=assets/supervised-machine-cover.png \
  --epub-title-page=false \
  --resource-path=. \
  --split-level=2 \
  --toc --toc-depth=2
```

The EPUB build intentionally uses a dedicated cover image and a separate inside title page. The
cover image is RGB PNG at 1024x1536 (under Apple Books' 5.6-million-pixel interior-image limit),
while the title and subtitle remain live XHTML text. This bundled image is the interior EPUB cover;
the separate Apple Books marketing image must be supplied at 1400 pixels or more on its shortest
axis without upscaling a low-resolution source. The Apple delivery `metadata.xml` file, when needed
for Transporter, belongs in the external `.itmsp` delivery package rather than inside this EPUB.

## EPUB validation

Run the official W3C EPUBCheck 5.3.0 validator before distribution:

```bash
epubcheck docs/book/the-supervised-machine-v0.5-DRAFT.epub
```

The current EPUB passes with zero fatals, errors, warnings, or informational messages.

**Regenerate the PDF and EPUB together and commit all three files whenever the HTML changes —
never let them drift.** The EPUB build is now a standard, default step alongside the PDF for
every book write/update, not an occasional extra. When cutting a new minor version, rename all
three files (`vX.Y-DRAFT`), update the cover/title/preface version strings in the HTML, and
update this README.
