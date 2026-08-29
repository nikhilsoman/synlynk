# Implementation Plan: Grant Codex Full Harness Parity Across Review and GH-Write Tasks (#1274)

- **Proposed Changes:** Update `synlynk/_constants.py`, `.synlynk/policy.json`, `docs/harness-capability-baseline.md`, instruction files, and associated test suites to grant OpenAI Codex first-class parity for GitHub write and PR review operations.
- **Spec:** `docs/superpowers/specs/2026-08-30-codex-full-harness-parity-design.md`
- **Issue:** #1274

---

## User Review Required

> [!IMPORTANT]
> This plan permanently removes the automatic rerouting of Codex GitHub-write dispatches to Claude by setting `can_gh_write: True` in `HARNESS_CAPABILITY_BASELINES["codex"]` and adding `"verifier"` to Codex's baseline roles.

---

## Proposed Changes

### Layer 1: Core Constants & Configuration

#### [synlynk/_constants.py](file:///Users/nikhilsoman/dev/synlynk/synlynk/_constants.py)
- Change `HARNESS_CAPABILITY_BASELINES["codex"]["can_gh_write"]` from `False` to `True`.
- Add `"verifier"` to `HARNESS_CAPABILITY_BASELINES["codex"]["roles"]`.
- Update `"strengths"` to include `"pr review"`, `"code inspection"`.

#### [.synlynk/policy.json](file:///Users/nikhilsoman/dev/synlynk/.synlynk/policy.json)
- Update `overrides.dev_authority.task_allocation.review` to:
  `{"harness": "codex", "fallback": ["claude", "agy"]}`
- Update `overrides.dev_authority.task_allocation.gh_write` to:
  `{"harness": "codex", "fallback": ["claude", "agy"]}`

---

### Layer 2: Test Suite Updates (TDD)

#### [tests/test_synlynk.py](file:///Users/nikhilsoman/dev/synlynk/tests/test_synlynk.py)
- In `test_can_gh_write_baselines_match_live_verified_reality()`:
  - Update: `assert HARNESS_CAPABILITY_BASELINES["codex"]["can_gh_write"] is True`

#### [tests/test_dispatch.py](file:///Users/nikhilsoman/dev/synlynk/tests/test_dispatch.py)
- In `test_dispatch_agent_requires_gh_write_force_agent_warns_and_proceeds`:
  - Change target agent from `"codex"` to `"grok"` (since Grok remains `can_gh_write: False`).
- Add `test_dispatch_agent_requires_gh_write_allows_codex_without_reroute`:
  - Asserts that dispatching Codex with `requires_gh_write=True` without `force_agent=True` resolves to agent `"codex"` with no `#426` reroute warning.

#### [tests/test_agent_cli.py](file:///Users/nikhilsoman/dev/synlynk/tests/test_agent_cli.py)
- Add `test_codex_harness_baseline_includes_verifier_role_and_can_gh_write`:
  - Asserts that `"verifier"` is in `roles` and `can_gh_write` is `True`.

---

### Layer 3: Documentation & Baseline Records

#### [docs/harness-capability-baseline.md](file:///Users/nikhilsoman/dev/synlynk/docs/harness-capability-baseline.md)
- Update Codex row:
  - GitHub write: **Reliable** (PR #1271, verified live in job `job-836e13a4`).
  - PR review (non-authoring): **Reliable** (tested live and authorized in `policy.json`).

#### [CLAUDE.md](file:///Users/nikhilsoman/dev/synlynk/CLAUDE.md), [AGENTS.md](file:///Users/nikhilsoman/dev/synlynk/AGENTS.md), [GEMINI.md](file:///Users/nikhilsoman/dev/synlynk/GEMINI.md)
- Update capability allocation tables to include Codex in review.
- Update GitHub write routing section to reflect that Codex is proven capable of headless GitHub writes.

---

## Verification Plan

### Automated Tests
1. Run updated test suite:
   ```bash
   python -m pytest tests/test_synlynk.py -k "test_can_gh_write_baselines" -v
   python -m pytest tests/test_dispatch.py -k "requires_gh_write" -v
   python -m pytest tests/test_agent_cli.py -k "codex" -v
   ```
2. Verify all pass with 0 failures.
