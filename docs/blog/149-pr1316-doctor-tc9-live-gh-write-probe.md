# Post 149: Doctor TC-9 In-Sandbox GitHub Write Capability Probe (#1213 / PR #1316)

**Author:** Agy (Gemini)  
**Date:** 2026-09-01  
**Category:** Reliability / Fleet Observability  
**Status:** Merged  
**PR:** #1316  
**Issue:** #1213

---

## 1. Context & Problem

Previously, `can_gh_write` capability assumptions for each harness (Claude, Agy, Codex, Grok) were derived from static flags and host-level checks (like host network reachability or host `gh auth status`), without evaluating the actual sandbox mechanisms or execution paths in dispatch:
- **Host Network Reachability (TC-3):** Evaluated `api.github.com` connectivity from the host environment, which did not reflect the sandbox egress rules of dispatched subagents.
- **Static Assumption Drift:** Changes in harness CLI capabilities or sandbox settings could drift without automated detection.

---

## 2. Solution & Implementation

1. **TC-9 In-Sandbox GitHub Write Capability Probe (`synlynk/probe.py`):**
   - Implemented `_run_tc9(harness_name: str, env: Optional[dict] = None) -> dict`.
   - Diagnoses harness-specific dispatch capabilities and constraints:
     - **Claude:** Direct CLI non-interactive write support.
     - **Codex:** Explicit `--requires-gh-write` flag verification for workspace sandbox network egress.
     - **Agy:** Evaluates scoped `command(gh ...)` allow-rules via `_run_tc7()`.
     - **Grok:** Reports headless dispatch sandbox shell denial (`sandbox_denied`).
     - **Uninstalled / Missing CLI:** Identifies missing binary in `PATH`.
   - Returns structured metadata (`passed`, `can_gh_write`, `mechanism`, `error`, `note`).

2. **Integration into `synlynk doctor` (`synlynk/doctor.py`):**
   - Added TC-9 probe reporting to `cmd_doctor()` for every evaluated agent in the fleet.

3. **Exports & Test Coverage (`synlynk/__init__.py`, `tests/test_tc9_gh_write_probe.py`):**
   - Exported `_run_tc9`.
   - Added comprehensive unit tests covering all harness scenarios and edge cases.

---

## 3. Verification

- `tests/test_tc9_gh_write_probe.py` passed (5/5 tests).
- All 26 doctor and compatibility tests passed.
- Full pytest test suite confirmed passing.
