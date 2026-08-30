# Implementation Plan: Eliminate Grok Headless Cancellation by Adopting --always-approve / bypassPermissions (#1277)

- **Proposed Changes:** Update `synlynk/dispatch.py`, `synlynk/_constants.py`, `docs/harness-capability-baseline.md`, and test suites so Grok headless execution avoids the fatal `--permission-mode dontAsk` auto-cancellation trap.
- **Spec:** `docs/superpowers/specs/2026-08-30-grok-headless-permission-mode-design.md`
- **Issue:** #1277

---

## Proposed Changes

### Layer 1: Core Dispatch Permission Translation

#### [synlynk/dispatch.py](file:///Users/nikhilsoman/dev/synlynk/synlynk/dispatch.py)
- In `_grok_permission_flags(permissions: list)`:
  - When `permissions` includes `run:shell` or `run:tests` (or when non-empty in headless dispatch), return `["--always-approve"]` (or `["--permission-mode", "bypassPermissions"]`).
  - Do not emit `--permission-mode dontAsk` when shell or testing actions are permitted, as Grok's internal risk classifier automatically cancels multi-command executions in `dontAsk` mode.

#### [synlynk/_constants.py](file:///Users/nikhilsoman/dev/synlynk/synlynk/_constants.py)
- Under `HARNESS_CAPABILITY_BASELINES["grok"]["dispatch_flags"]`:
  - Ensure `--always-approve` and `--permission-mode` are valid dispatch flags.
  - Set `"required_flags": ["--always-approve"]` if appropriate for headless Grok invocation.

---

### Layer 2: Test Suite Updates (TDD)

#### [tests/test_dispatch.py](file:///Users/nikhilsoman/dev/synlynk/tests/test_dispatch.py)
- Add `test_grok_permission_flags_emits_always_approve_when_shell_or_tests_granted`:
  - Assert that `_grok_permission_flags(["read:*", "run:shell"])` returns `["--always-approve"]`.
  - Assert that `_grok_permission_flags(["read:*", "run:tests"])` returns `["--always-approve"]`.
  - Assert that `--permission-mode dontAsk` is not emitted when execution grants exist.

---

### Layer 3: Documentation Updates

#### [docs/harness-capability-baseline.md](file:///Users/nikhilsoman/dev/synlynk/docs/harness-capability-baseline.md)
- Update Grok row notes:
  - Document that the recurring `stopReason: "cancelled"` failure mode was traced to Grok's internal shell AST splitter flagging compound commands in `--permission-mode dontAsk`.
  - Document the fix via `--always-approve` / `bypassPermissions`.

---

## Verification Plan

### Automated Tests
1. Run pytest against the new and updated dispatch tests:
   ```bash
   python -m pytest tests/test_dispatch.py -k "grok_permission" -v
   ```
2. Run pytest on the full dispatch suite:
   ```bash
   python -m pytest tests/test_dispatch.py -k "grok" -v
   ```
3. Verify all pass with 0 failures.
