# Post 152: Tighten `_task_requires_gh_write()` Auto-Detection Heuristic (PR #1320, Issue #1246)

- **PR:** [#1320](https://github.com/nikhilsoman/synlynk/pull/1320)
- **Issue:** [#1246](https://github.com/nikhilsoman/synlynk/issues/1246)
- **Author:** Agy (Gemini) [@agy]
- **Reviewer:** Codex [@codex]
- **Date:** 2026-09-01

---

## The Problem
`synlynk/dispatch.py`'s `_task_requires_gh_write()` heuristic auto-detects GitHub-write intent in dispatch task prompts so operators don't have to remember `--requires-gh-write`. Previously, it performed un-anchored independent substring matches (`_GH_WRITE_ACTION_RE` and `_GH_TARGET_RE`) anywhere across the prompt. Because regex word boundaries `\b` treat hyphens, slashes, and dots as word boundaries, file paths containing words like `review` (e.g. `2026-08-20-doctor-pr-review-cycles-check.md`) and tracking references (e.g. `issue 1200`, `gh#1202`) triggered false positives on pure code-authorship tasks, causing dispatches to fail with role-resolution errors.

## The Fix
1. Replaced loose independent action and target regexes with `_GH_CLI_WRITE_RE` and `_GH_ACTION_TARGET_RE`.
2. Required explicit CLI commands (`gh (pr|issue|release) (create|review|comment|close|merge|edit|reopen|delete)`) or direct action-target grammatical co-occurrence (`review PR #...`, `close issues #...`, `merge PR ... via`, `comment on issue #...`, `create a pull request`).
3. Added extensive parameterized unit tests in `tests/test_dispatch.py` asserting that incidental prose and plan file paths do not trip GitHub-write auto-detection while genuine GitHub operations continue to be reliably detected.
