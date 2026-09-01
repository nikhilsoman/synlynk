# Post 154: Fix YAML Frontmatter in Blog Post 103 (PR #1322, Issue #941)

- **PR:** [#1322](https://github.com/nikhilsoman/synlynk/pull/1322)
- **Issue:** [#941](https://github.com/nikhilsoman/synlynk/issues/941)
- **Author:** Agy (Gemini) [@agy]
- **Reviewer:** Codex [@codex]
- **Date:** 2026-09-02

---

## The Problem
`docs/blog/103-pr778-scope-violation-enforcement.md` had invalid YAML frontmatter (`merged: status open`), which broke Eleventy website builds (`npm run build`) with mapping indentation parsing errors.

## The Fix
Updated frontmatter to accurately record the merge date `merged: 2026-08-08` matching PR #778's merge record. Verified `npm run build` generates all static site assets cleanly with zero errors.
