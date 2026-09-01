# Design Spec: Decouple README Sync Validator Unit Tests from Live Repo Root (#1270)

- **Issue:** [#1270](https://github.com/nikhilsoman/synlynk/issues/1270)
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-09-01
- **Status:** APPROVED

---

## 1. Problem Statement

In `tests/test_agent_cli.py`, `test_docs_keep_readme_synchronized_during_named_releases_real_readme_patterns` executed `validate_readme_for_release(".", "0.18.0", collected_test_count=9999)` directly against the live repository root `repo_root`. It hardcoded assertions expecting specific test count values (previously `"1140"`, then `"2346"`).

Whenever legitimate README updates occur (e.g. updating test count badges, updating release version summaries, or syncing commands during named releases), this test fails because its assertions are brittle and tightly coupled to the live file state rather than testing the release validator in isolation.

---

## 2. Proposed Architecture

### 2.1 Use Synthetic Fixture via `tmp_path`
Instead of executing against `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`, use pytest's `tmp_path` fixture and the helper function `_docs_keep_readme_synchronized_readme()` to generate a synthetic `README.md` containing known test counts (e.g. `2346`), version strings (`"0.18.0"`), prose lines, and GitHub-relative discussion links.

### 2.2 Verify Behavior
- The validator correctly validates matching version (`"0.18.0"` -> no version findings).
- The validator identifies the discrepancy between the fixture's test badge (`2346`) and the collected test count (`9999`).
- The validator ignores ordinary prose lines without false positives.
- The validator permits repository-relative links (such as `../../discussions`) without flagging them as escaping the repository root.

---

## 3. Testing & Verification Plan

- Run unit test: `pytest tests/test_agent_cli.py -k test_docs_keep_readme_synchronized_during_named_releases_real_readme_patterns -v`
- Run full test suite: `pytest tests/test_synlynk.py -q`
- Verify `python -m synlynk pr check` passes.
