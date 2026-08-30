# Implementation Plan: Agy Headless Parity Package (#1283)

- **Proposed Changes:**
  1. In `synlynk/_constants.py`: Add `--print-timeout` and `--mode` to `HARNESS_CAPABILITY_BASELINES["agy"]["dispatch_flags"]["valid_flags"]`.
  2. In `synlynk/dispatch.py`:
     - Update `_permissions_to_flags()`: When `agent == "agy"` and `set(permissions) <= {"read:*"}`, return `["--mode", "plan"]` instead of raising `PermissionEnforcementError`.
     - In `dispatch_agent()`: Append `["--print-timeout", "30m0s"]` to `flags` when `agent == "agy"` and `--print-timeout` is not already present.
  3. In `synlynk/costs.py`: Update `_extract_agy_structured()` to parse `cache_read_tokens = int(usage.get("cache_read_tokens", 0))` and return it in `_TokenCounts`.
  4. In `tests/`: Add and update unit tests verifying all three capabilities.
- **Spec:** `docs/superpowers/specs/2026-08-30-agy-headless-parity-design.md`
- **Issue:** #1283

---

## Proposed Changes

### Layer 1: Permissions & Flags (`synlynk/dispatch.py`, `synlynk/_constants.py`)

#### [synlynk/dispatch.py](file:///Users/nikhilsoman/dev/synlynk/synlynk/dispatch.py)
- In `_permissions_to_flags()`:
  ```python
  if agent == "agy":
      if not permissions:
          print(...)
          return []
      if set(permissions) <= {"read:*"}:
          return ["--mode", "plan"]
      return ["--dangerously-skip-permissions"]
  ```
- In `dispatch_agent()` (around line 2553):
  ```python
  if agent == "agy":
      flags = flags + ["--output-format", "json"]
      if "--print-timeout" not in flags:
          flags = flags + ["--print-timeout", "30m0s"]
  ```

#### [synlynk/_constants.py](file:///Users/nikhilsoman/dev/synlynk/synlynk/_constants.py)
- Update `HARNESS_CAPABILITY_BASELINES["agy"]["dispatch_flags"]["valid_flags"]` to include `"--print-timeout"` and `"--mode"`.

---

### Layer 2: Prompt Cache Telemetry (`synlynk/costs.py`)

#### [synlynk/costs.py](file:///Users/nikhilsoman/dev/synlynk/synlynk/costs.py)
- Update `_extract_agy_structured()`:
  ```python
  cache_read_tokens = int(usage.get("cache_read_tokens", 0))
  return _TokenCounts(in_tokens, out_tokens, cache_read_tokens, "structured_output")
  ```

---

### Layer 3: Unit Tests (TDD)

#### [tests/test_dispatch.py](file:///Users/nikhilsoman/dev/synlynk/tests/test_dispatch.py)
- Add `test_agy_permission_flags_read_only_emits_mode_plan`:
  Verify `_permissions_to_flags("agy", ["read:*"]) == ["--mode", "plan"]`.
- Add `test_agy_dispatch_flags_includes_print_timeout`:
  Verify `dispatch_agent("agy", ...)` produces command line containing `--print-timeout 30m0s`.

#### [tests/test_costs.py](file:///Users/nikhilsoman/dev/synlynk/tests/test_costs.py)
- Add `test_extract_agy_structured_captures_cache_read_tokens`:
  Pass JSON containing `cache_read_tokens: 32533` and assert `extracted.cache_read_tokens == 32533`.

---

## Verification Plan

1. Run pytest against updated test files:
   ```bash
   python -m pytest tests/test_dispatch.py tests/test_costs.py tests/test_constants.py -v
   ```
2. Verify all pass with 0 failures.
