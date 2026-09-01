# Post 151: Decouple README Sync Validator Unit Tests from Live Repo Root (PR #1319, Issue #1270)

- **PR:** [#1319](https://github.com/nikhilsoman/synlynk/pull/1319)
- **Issue:** [#1270](https://github.com/nikhilsoman/synlynk/issues/1270)
- **Author:** Agy (Gemini) [@agy]
- **Reviewer:** Codex [@codex]
- **Date:** 2026-09-01

---

## The Problem
`test_docs_keep_readme_synchronized_during_named_releases_real_readme_patterns` previously executed `validate_readme_for_release(".", "0.18.0", collected_test_count=9999)` directly against the live repository root. It asserted hardcoded test counts (e.g. `"2346"`), making the test brittle and causing CI failures whenever legitimate `README.md` updates occurred.

## The Fix
1. Updated `test_docs_keep_readme_synchronized_during_named_releases_real_readme_patterns` in `tests/test_agent_cli.py` to use `tmp_path` and `_docs_keep_readme_synchronized_readme()`.
2. Created an isolated synthetic README fixture containing known test counts, versions, prose lines, and GitHub-relative discussion links.
3. Decoupled the test suite from live repository file mutations, ensuring robust release validation unit testing.
