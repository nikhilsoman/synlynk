# Implementation Plan: Decouple README Sync Validator Unit Tests from Live Repo Root (#1270)

- **Issue:** [#1270](https://github.com/nikhilsoman/synlynk/issues/1270)
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-09-01

---

## 1. Code Changes

### 1.1 `tests/test_agent_cli.py`
- Modify `test_docs_keep_readme_synchronized_during_named_releases_real_readme_patterns` to take `(tmp_path, monkeypatch)`.
- Use `_docs_keep_readme_synchronized_readme(tmp_path, "0.18.0", test_count=2346, extra=...)` to populate a synthetic README fixture.
- Point `validate_readme_for_release` at `tmp_path` (or chdir into `tmp_path` and use `"."`).
- Verify all assertions hold against the controlled fixture.

### 1.2 Documentation, Memory & Blog Post
- Write blog post 151: `docs/blog/151-pr1319-readme-sync-test-synthetic-fixture.md`.
- Update `docs/blog/README.md`.
- Record decision in `project-docs/memory.md`.
- Append entry to `project-docs/devlogs/nikhilsoman.md`.

---

## 2. Verification
- `pytest tests/test_agent_cli.py -k test_docs_keep_readme_synchronized_during_named_releases_real_readme_patterns -v`
- `pytest tests/test_synlynk.py -q`
- `python -m synlynk pr check`
- Open PR, dispatch review to Codex, and merge.
