# Design Spec: Tighten `_task_requires_gh_write()` Auto-Detection Heuristic (#1246)

- **Issue:** [#1246](https://github.com/nikhilsoman/synlynk/issues/1246)
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-09-01
- **Status:** APPROVED

---

## 1. Context & Problem Statement

`_task_requires_gh_write()` in `synlynk/dispatch.py` auto-detects GitHub-write intent in dispatch task prompts so operators do not have to pass `--requires-gh-write` manually for review and issue-closing tasks.

Previously, `_task_requires_gh_write()` checked `bool(_GH_WRITE_ACTION_RE.search(text) and _GH_TARGET_RE.search(text))` across the entire prompt. This resulted in frequent false positives:
1. **Hyphenated file names & flags:** Words like `review` in `...doctor-pr-review-cycles-check.md` or `gh` in `--requires-gh-write` matched because regex word boundaries `\b` treat hyphens, slashes, and dots as non-word boundaries.
2. **Incidental prose words:** Prompts mentioning "Tracking issue: 1200", "Fix issue #1200", or "review error handling" matched independent action + target regexes even when the task was pure code authorship.
3. **Dispatch Failure:** Inferred `requires_gh_write` forced role resolution, causing jobs without explicit `--role` or `--as-agent` to fail closed with `RuntimeError: Dispatch refused: --requires-gh-write requires a resolvable role identity...`.

---

## 2. Proposed Architecture

### 2.1 Tighten Co-Occurrence and Grammar
Instead of checking independent un-anchored substrings anywhere in the prompt, `_task_requires_gh_write()` requires:
1. **Explicit CLI write commands:** `\bgh\s+(?:issue|pr|release)\s+(?:create|review|comment|close|merge|edit|reopen|delete)\b`.
2. **Direct Action-Target Pairing:** Action verbs directly connected to their GitHub target:
   - PR Review: `\b(?:review|approv(?:e|ing))\s+(?:(?:the|this)\s+)?(?:github\s+)?(?:pr|pull\s+request)\s*#?\d+\b`, `\b(?:post|submit|add)\s+(?:(?:a|an)\s+)?(?:formal\s+)?(?:github\s+)?(?:pr\s+|pull\s+request\s+)?review\b`, `\breview\s+and\s+post\b`.
   - Issue/PR Close: `\bclose\s+(?:(?:the|this|all)\s+)?(?:github\s+)?(?:issues?|prs?|pull\s+requests?)\s*#?\d+\b`, `\bclose\s+issues?\s*#?\d+\s+(?:as|citing)\b`.
   - PR Merge: `\bmerge\s+(?:(?:the|this)\s+)?(?:github\s+)?(?:pr|pull\s+request)\s*#?\d+\b`, `\bmerge\s+(?:the\s+)?(?:pr|pull\s+request)\s+via\b`.
   - Issue/PR Comment: `\bcomment\s+on\s+(?:(?:the|this)\s+)?(?:github\s+)?(?:issues?|prs?|pull\s+requests?)\s*#?\d+\b`, `\bpost\s+(?:a\s+)?comment\s+(?:on|to)\s+(?:github\s+)?(?:issues?|prs?)\s*#?\d+\b`.
   - PR Creation: `\b(?:create|open)\s+(?:a\s+)?(?:new\s+)?(?:github\s+)?(?:pr|pull\s+request)\b`.
3. **Explicit `task_type="review"`:** If `task_type == "review"` is passed, returns `True`.

### 2.2 Replaced Patterns
Replace loose `_GH_WRITE_ACTION_RE` and `_GH_TARGET_RE` with focused regexes `_GH_CLI_WRITE_RE` and `_GH_ACTION_TARGET_RE`.

---

## 3. Testing & Verification Plan

- Unit tests in `tests/test_dispatch.py`:
  - Verify all documented false-positive cases from #1246 return `False` (file paths like `2026-08-20-doctor-pr-review-cycles-check.md`, flag strings `--requires-gh-write`, tracking references `gh#1202`, prose `review error handling`).
  - Verify all true-positive cases return `True` (closing issues, merging PRs, posting PR reviews, `gh pr merge`, `gh issue close`).
- Full suite verification: `pytest tests/test_synlynk.py -q`.
- PR check: `python -m synlynk pr check`.
