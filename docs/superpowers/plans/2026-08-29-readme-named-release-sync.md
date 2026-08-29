# README Named-Release Sync — Plan

> **For agentic workers:** implement task-by-task. Spec: `docs/superpowers/specs/2026-08-29-readme-named-release-sync-design.md`.

**Goal:** Gate named releases on README version/test-count/hero/install/link/command consistency.

**Architecture:** New `synlynk/release_readme.py` validator; `cmd_release` fail-closed; `--check-docs` / `--waive` flags; CLAUDE.md protocol.

---

## Task 1: Validator module

- Create: `synlynk/release_readme.py`
- Tests: `tests/test_agent_cli.py` (`test_docs_keep_readme_synchronized_during_named_releases*`)

Functions: `collect_pytest_test_count`, `parse_waivers`, `validate_readme_for_release`, `format_readme_check_report`.

Review follow-ups (#1242 comment): snippet-only command scan, abspath-normalized root, GitHub UI routes, collect-only semantics.

## Task 2: Wire `synlynk release`

- Modify: `synlynk/__init__.py` (`cmd_release`), `synlynk/cli.py`
- Tests: existing `tests/test_release.py` fixtures get a synced README for the version about to be written; checklist asserts README line

## Task 3: Protocol

- Modify: `CLAUDE.md` — Named Release README Sync section before the harness fence
