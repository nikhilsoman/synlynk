# Design Spec: Fix YAML Frontmatter in Blog Post 103 (#941)

- **Issue:** [#941](https://github.com/nikhilsoman/synlynk/issues/941)
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-09-02
- **Status:** APPROVED

---

## 1. Context & Problem Statement

Issue #941 reported that `docs/blog/103-pr778-scope-violation-enforcement.md` had invalid/unquoted YAML frontmatter (`merged: status open`), which broke 11ty website builds (`npm run build`).

---

## 2. Proposed Fix

Update `docs/blog/103-pr778-scope-violation-enforcement.md` frontmatter to accurately reflect the merge date:
```yaml
merged: 2026-08-08
```

---

## 3. Testing & Verification Plan

- Verify `docs/blog/103-pr778-scope-violation-enforcement.md` parses as valid YAML.
- Run `npm run build` in `website/` to ensure the Eleventy static site generator compiles all pages with zero errors.
- Run Python test suite: `pytest tests/test_synlynk.py -q`.
