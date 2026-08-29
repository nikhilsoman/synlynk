# "The Supervised Machine" — Book Manuscript

A nonfiction book grounded in synlynk's real build history and three sister projects (rxcc, cc-videoreframing, Playblazer). Written by Claude, sourced from `docs/blog/`, commit history, strategy docs, and project/feedback memory files — see the manuscript's own closing "A Note on Sources" section for full sourcing discipline.

## Files

- `the-supervised-machine-2nd-edition.html` — source of truth. Single-file, self-contained HTML (inline CSS, no external assets).
- `the-supervised-machine-2nd-edition.pdf` — rendered output, regenerated from the HTML. Do not hand-edit the PDF.

## Editorial history

The 2nd Edition's structure and content were shaped by a formal editorial-panel review, recorded as a Decision at `project-docs/decisions/2026-08-29-editorial-review-the-supervised-machine.md`. That review's four targeted edits (front-matter glossary + endnoted citations, Part One/Two chapter consolidation, Chapter 14 dedup fix, Chapter 16 reframed as a coda, Chapters 17–19 merged) are reflected in this version.

## Rebuilding the PDF

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=docs/book/the-supervised-machine-2nd-edition.pdf \
  "file://$(pwd)/docs/book/the-supervised-machine-2nd-edition.html"
```

Regenerate the PDF and commit both files together whenever the HTML changes — never let them drift.
