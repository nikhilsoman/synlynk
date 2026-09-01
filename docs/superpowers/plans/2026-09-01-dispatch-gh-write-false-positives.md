# Implementation Plan: Tighten `_task_requires_gh_write()` Auto-Detection Heuristic (#1246)

- **Issue:** [#1246](https://github.com/nikhilsoman/synlynk/issues/1246)
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-09-01

---

## 1. Code Changes

### 1.1 `synlynk/dispatch.py`
- Replace `_GH_WRITE_ACTION_RE` and `_GH_TARGET_RE` with `_GH_CLI_WRITE_RE` and `_GH_ACTION_TARGET_RE`.
- Update `_task_requires_gh_write(task, task_type)`:
  - If `task_type == "review"`, return `True`.
  - If `_GH_CLI_WRITE_RE.search(text)`, return `True`.
  - If `_GH_ACTION_TARGET_RE.search(text)`, return `True`.
  - Otherwise return `False`.
- Update `_infer_task_type(task)` to use `_REVIEW_TASK_RE` with tightened action targets.

### 1.2 `tests/test_dispatch.py`
- Add parameterized tests covering false-positive negative cases:
  - File paths containing action words: `docs/superpowers/plans/2026-08-20-doctor-pr-review-cycles-check.md`.
  - CLI flag literals: `--requires-gh-write`.
  - Tracking issue citations: `Tracking issue: 1200`, `gh#1202`, `(closes #1317)`.
  - Internal code review prose: `write tests and review error handling`.
- Add parameterized tests covering true-positive positive cases:
  - `Close GitHub issues #935 and #701, citing the implementation PR`.
  - `Review PR #1303 (fix/1295-qa-admin-permission) and merge PR 1303`.
  - `review PR 1038`.
  - `Post a GitHub PR review for PR #1164`.
  - `gh pr merge 1303 --squash --delete-branch --admin`.
  - `Comment on issue #1200 with the benchmark results`.
  - `Merge pull request #1294 using gh pr merge`.

### 1.3 Documentation & Devlogs
- Blog post 152: `docs/blog/152-pr1320-dispatch-gh-write-false-positives.md`.
- Update `docs/blog/README.md`.
- Record decision in `project-docs/memory.md`.
- Update `project-docs/devlogs/nikhilsoman.md`.

---

## 2. Verification Plan
- `pytest tests/test_dispatch.py -k "gh_write or infer_task_type" -v`
- `pytest tests/test_task_type_inference.py -v`
- `pytest tests/test_synlynk.py -q`
- `python -m synlynk pr check`
- Open PR, dispatch review to Codex, and merge.
