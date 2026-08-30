# Implementation Plan: Claude Harness Alignment (#1284)

- **Proposed Changes:**
  1. In `synlynk/_constants.py`: Update `HARNESS_CAPABILITY_BASELINES["claude"]["roles"]` to `["architect", "pm"]`.
  2. In `tests/`: Update unit tests asserting Claude's baseline roles to reflect `["architect", "pm"]`.
  3. In `docs/harness-capability-baseline.md`: Update Claude notes.
- **Spec:** `docs/superpowers/specs/2026-08-30-claude-harness-alignment-design.md`
- **Issue:** #1284

---

## Proposed Changes

### Layer 1: Baseline Roles (`synlynk/_constants.py`)
- Change line 67 in `synlynk/_constants.py`:
  ```python
  "roles": ["architect", "pm"],
  ```

### Layer 2: Tests (`tests/test_constants.py`, `tests/test_synlynk.py`)
- Search for tests asserting `"builder" in HARNESS_CAPABILITY_BASELINES["claude"]["roles"]` and update them to assert `"pm"` and `"architect"`.

### Layer 3: Documentation (`docs/harness-capability-baseline.md`)
- Update Claude row to note alignment with PM/architect roles.

---

## Verification Plan

1. Run pytest against constants and baseline tests:
   ```bash
   python -m pytest tests/test_constants.py tests/test_synlynk.py -k "claude" -v
   ```
2. Verify all pass with 0 failures.
