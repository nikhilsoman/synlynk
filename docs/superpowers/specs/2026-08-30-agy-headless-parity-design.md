# Design Spec: Eliminate Agy Headless 5m Timeout, Enable Read-Only Plan Mode, and Capture Prompt-Cache Tokens

- **Topic:** Agy Headless Parity Package
- **Author:** Agy (Gemini)
- **Status:** Approved / In Implementation
- **Target Release:** v0.18.1 / Fleet Parity
- **Goal:** goal-005ea87d
- **Story:** story-fa040af0
- **Issue:** #1283
- **Related Issues:** #750, #162, #437, #1106

---

## 1. Problem Statement & Background

Our comprehensive fleet harness audit (documented in `docs/harness-parity-reference.md`) identified three critical operational gaps in Google Antigravity (`agy`) headless execution:

1. **5-Minute Timeout Boundary (`HARNESS_INTERNAL_TIMEOUT` / #750, #162):**
   In print mode (`-p`), the Antigravity CLI enforces a built-in default timeout of `--print-timeout 5m0s`. Headless dispatches exceeding 300 seconds are aborted by the CLI with `Error: timeout waiting for response`, leaving jobs in a dead `status=running` state in `daemon_jobs`.
2. **Read-Only Permission Lockout (`PermissionEnforcementError`):**
   `synlynk/dispatch.py:437-442` raises `PermissionEnforcementError` when `permissions <= {"read:*"}`, preventing Agy from being dispatched for read-only audits or code reviews without write/shell grants. Agy natively supports `--mode plan` to constrain execution to read-only/planning.
3. **Ignored Prompt-Cache Telemetry:**
   `synlynk/costs.py:_extract_agy_structured()` hardcodes `cache_read_tokens = 0`. Live inspection of `agy --output-format json` proves `usage.cache_read_tokens` is actively emitted by the CLI.

---

## 2. Proposed Architecture & Changes

### Layer 1: Headless Timeout Override (`synlynk/dispatch.py`, `synlynk/_constants.py`)
- In `synlynk/dispatch.py`, when preparing flags for `agy` (around line 2553), append `["--print-timeout", "30m0s"]` if not already specified, aligning Agy's internal timer with synlynk's 30-minute stall threshold.
- In `synlynk/_constants.py`, add `--print-timeout` and `--mode` to `HARNESS_CAPABILITY_BASELINES["agy"]["dispatch_flags"]["valid_flags"]`.

### Layer 2: Read-Only Mode Permission Translation (`synlynk/dispatch.py`)
- In `_permissions_to_flags()`, replace the `raise PermissionEnforcementError` when `permissions <= {"read:*"}` with:
  ```python
  if set(permissions) <= {"read:*"}:
      return ["--mode", "plan"]
  ```
  This allows read-only and review tasks to be dispatched to Agy safely without giving write permissions or failing closed.

### Layer 3: Prompt Caching Token Extraction (`synlynk/costs.py`)
- In `_extract_agy_structured(output_text: str)`, extract `cache_read_tokens` from `usage`:
  ```python
  cache_read_tokens = int(usage.get("cache_read_tokens", 0))
  return _TokenCounts(in_tokens, out_tokens, cache_read_tokens, "structured_output")
  ```

---

## 3. Test & Verification Strategy

### TDD Plan
1. **Unit Tests (`tests/test_dispatch.py`):**
   - Assert `_permissions_to_flags("agy", ["read:*"])` returns `["--mode", "plan"]`.
   - Assert `dispatch_agent("agy", ...)` includes `["--print-timeout", "30m0s"]` in the constructed command.
2. **Unit Tests (`tests/test_constants.py` / `tests/test_costs.py`):**
   - Assert `_constants.py` contains `--print-timeout` and `--mode` in `valid_flags`.
   - Assert `_extract_agy_structured()` returns `cache_read_tokens` when present in the JSON usage object.
