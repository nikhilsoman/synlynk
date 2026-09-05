---
title: "PR #1430 — EPUB Joins the Book's Default Output Set"
date: 2026-09-05
series: "Building the OS for Multi-Agent Development"
post: 174
pr: "#1430"
status: open
---

## The Broader Goal at the End of the Previous PR

By PR #1409, "The Supervised Machine" had a real visual identity layered onto the HTML source of
truth, and the PDF rebuild step was an established, documented ritual in `docs/book/README.md`.
The book's distribution story was "HTML source, PDF render" — two formats, one manual Chrome
headless-print command, committed together whenever the manuscript changed.

## Strategic Shifts in This PR

None — this is a small, deliberate gap-close, not a repositioning. The book has been growing
(multi-author chapters, Part II/III/IV expansions, embedded UI mockups) and PDF-only distribution
doesn't serve e-readers well: no reflow, no adjustable type size, no proper e-reader TOC
navigation. EPUB was the obvious missing format, and the user asked for it to become a *default*
step, not an occasional extra — matching the existing "regenerate the PDF and commit both files
together" discipline this project already holds for the HTML/PDF pair.

## What This PR Shipped

- Installed `pandoc` via Homebrew (not previously present in this environment).
- Generated `docs/book/the-supervised-machine-v0.5-DRAFT.epub` from the existing single-file HTML
  source, with `--resource-path=.` (run from `docs/book/`) so the three rxcc Stitch mockup PNGs
  under `assets/` embed correctly instead of producing `PandocResourceNotFound` warnings.
- The key technical catch: pandoc's EPUB writer splits into chapter files at `<h1>` by default, but
  this manuscript's real chapter headings are `<h2 class="chap-title">` — the manuscript wraps
  everything in a handful of top-level `<h1>`s (front matter, Part dividers) with actual chapters
  one level down. Splitting at the default level produced a single 216KB chapter file with no real
  per-chapter navigation. Passing `--split-level=2` fixed this, producing 36 properly split chapter
  files and a correct nav.xhtml TOC (verified by unzipping the EPUB and spot-checking that TOC
  entries map to the right chapter titles).
- Verified EPUB structural validity by hand (no `epubcheck` available in this environment):
  confirmed `mimetype`, `META-INF/container.xml`, `EPUB/content.opf`, `EPUB/toc.ncx`, and
  `EPUB/nav.xhtml` are all present and well-formed via `unzip -l` / `unzip -p`.
- Documented the exact rebuild command in `docs/book/README.md`, right alongside the existing PDF
  rebuild command, and updated the file list and "regenerate together, never let them drift"
  language to cover all three formats (HTML, PDF, EPUB) instead of two.

## Brainstorm Visuals Used

None — this PR is build tooling, not new manuscript content.

## What This Achieved on the Path to Autonomy

Nothing autonomy-related directly, but it closes a real distribution gap for a project asset that
synlynk itself produces and maintains (the book is written by the same Claude/Codex/Grok/Agy fleet
that builds synlynk). It also sets a precedent worth generalizing later: any generated-artifact
pair (source + rendered output) in this repo should default to *every* commonly consumed target
format, not just the first one someone thought to add.

## Strategic Note: The Goal at the End of This PR

The book's default output set is now HTML (source of truth) + PDF + EPUB, generated and committed
together on every content change. The next book-adjacent PR should treat EPUB regeneration as
non-optional the same way PDF regeneration already is — no separate reminder needed, it's just
part of "the book changed."
