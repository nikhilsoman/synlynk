# End-to-End FTUE & Onboarding Deep Dive: Isolated VM Testbed, Provider Discovery & Full Vizor Audit — Implementation Plan

**Date:** 2026-11-15  
**Status:** In Progress  
**Parent Epic:** [#5302](https://github.com/nikhilsoman/synlynk/issues/5302)  
**Design Spec:** [docs/superpowers/specs/2026-11-15-ftue-onboarding-vm-testbed-and-discovery-design.md](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-11-15-ftue-onboarding-vm-testbed-and-discovery-design.md)  
**Associated Issues:** [#5297](https://github.com/nikhilsoman/synlynk/issues/5297), [#5298](https://github.com/nikhilsoman/synlynk/issues/5298), [#5299](https://github.com/nikhilsoman/synlynk/issues/5299), [#5287](https://github.com/nikhilsoman/synlynk/issues/5287)  

---

## 1. Plan Overview

This plan operationalizes the 4-pillar FTUE & Onboarding Deep Dive into 6 executable, verified tasks:
1. **Task 1:** Fix FTUE wizard `[unknown]` job ID resolution ([#5297](https://github.com/nikhilsoman/synlynk/issues/5297)) + unit regression test.
2. **Task 2:** Fix Claude harness environment passthrough for LiteLLM/DGX gateways & custom config directories ([#5298](https://github.com/nikhilsoman/synlynk/issues/5298)) + unit regression test.
3. **Task 3:** Fix coldstart directory creation race condition & hermetic `--dry-run` ([#5299](https://github.com/nikhilsoman/synlynk/issues/5299)) + unit regression test.
4. **Task 4:** Build Universal Provider Mock Matrix & Discovery Engine Test (`tests/testbed_mocks/`).
5. **Task 5:** Build Full Vizor Visual & Route Audit Crawler (`tests/test_vizor_e2e_audit.py`).
6. **Task 6:** Orchestrate End-to-End VM Acceptance Test (`tests/test_ftue_vm_acceptance.py`) via `synlynk/testbed/driver.py`.

---

## 2. Detailed Task Breakdown

### Task 1: Fix FTUE Wizard Job ID Resolution ([#5297](https://github.com/nikhilsoman/synlynk/issues/5297))
- **File:** `synlynk/wizard.py` (lines 224–228)
- **Change:**
  ```python
  job_id = (job.get("id") or job.get("job_id") or "unknown") if isinstance(job, dict) else "dispatched"
  print(f"\n  {_GREEN}▶{_RESET} [{job_id}] {chosen['agent']} dispatched\n"
        f"  {_DIM}Log: synlynk logs --job {job_id}{_RESET}\n")
  ```
- **Test:** In `tests/test_wizard.py`, assert that a mocked `dispatch_agent` returning `{"id": "job-12345678", "agent": "claude"}` prints `[job-12345678] claude dispatched` and `Log: synlynk logs --job job-12345678`.
- **Verification:** `pytest tests/test_wizard.py` exits 0.

---

### Task 2: Claude Subprocess Environment Passthrough for LiteLLM & DGX Gateways ([#5298](https://github.com/nikhilsoman/synlynk/issues/5298))
- **Files:** `synlynk/_constants.py`, `synlynk/probe_binding.py`
- **Changes:**
  1. In `synlynk/_constants.py`, add `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, `CLAUDE_CONFIG_DIR` to `HARNESS_CAPABILITY_BASELINES["claude"]["env_passthrough"]`.
  2. In `synlynk/probe_binding.py:_auth_config_path`, respect `os.environ.get("CLAUDE_CONFIG_DIR")`.
- **Test:** In `tests/test_dispatch_env.py`, set `ANTHROPIC_BASE_URL="http://localhost:4000"` and `CLAUDE_CONFIG_DIR="/tmp/custom-claude"`; call `_build_subprocess_env("claude")` and assert both keys are preserved in the returned environment dictionary.
- **Verification:** `pytest tests/test_dispatch_env.py` exits 0.

---

### Task 3: Hermetic Coldstart, Lazy Reconcile Lock & Canonical Init Marker ([#5299](https://github.com/nikhilsoman/synlynk/issues/5299))
- **Files:** `synlynk/cli.py`, `synlynk/jobs.py`, `synlynk/__init__.py`, `synlynk/coldstart.py`, `synlynk/instructions.py`
- **Changes:**
  1. In `synlynk/cli.py`, bypass `_reconcile_jobs()` when `args.command == "init"` or when `.synlynk/` does not exist.
  2. In `synlynk/__init__.py:3458` and `synlynk/coldstart.py:209`, replace `os.path.exists(".synlynk")` with `os.path.exists(".synlynk/config.json") or os.path.exists(".synlynk/workspace.json")`.
  3. In `synlynk/instructions.py:704`, update the default model template string from `claude-sonnet-4-6` to `claude-sonnet-5`.
- **Test:** In `tests/test_init_clean_coldstart.py`:
  - Assert `synlynk init --dry-run` leaves zero files and zero directories in a temporary directory.
  - Assert `synlynk init --yes` succeeds on a clean directory without `Repository is already initialized` warning.
- **Verification:** `pytest tests/test_init_clean_coldstart.py` exits 0.

---

### Task 4: Universal Provider Mock Matrix & Discovery Engine Suite
- **Directory:** `tests/testbed_mocks/`
- **Deliverables:**
  - `tests/testbed_mocks/gateway_mock.py`: Minimal HTTP server mocking LiteLLM on port 4000 (`/v1/models`, `/v1/messages`) and Ollama on port 11434 (`/api/tags`).
  - Executable CLI mock stubs on temporary `PATH` simulating `claude`, `codex`, `agy`, `grok`, and `muse`.
- **Test:** `tests/test_provider_discovery_matrix.py` asserting `synlynk probe` and `synlynk discover` correctly detect all providers and gateway endpoints.
- **Verification:** `pytest tests/test_provider_discovery_matrix.py` exits 0.

---

### Task 5: Full Vizor Visual & Route Audit Crawler
- **File:** `tests/test_vizor_e2e_audit.py`
- **Deliverables:**
  - Automated route auditor starting `synlynk viz --port 8765 --no-browser` in a background thread.
  - Requests all 8 primary endpoints: `/`, `/roadmap`, `/gantt`, `/tube`, `/radar`, `/graphify`, `/kanban`, `/health`.
  - Verifies status 200, valid HTML content, extracts all `<link rel="stylesheet">`, `<script>`, and `<img src>` tags, and asserts that 100% of static assets resolve with status 200 (zero 404s).
  - Connects to `/events` and verifies SSE heartbeat receipt.
- **Verification:** `pytest tests/test_vizor_e2e_audit.py` exits 0.

---

### Task 6: End-to-End VM Acceptance Test
- **File:** `tests/test_ftue_vm_acceptance.py`
- **Deliverables:**
  - Leverages `synlynk.testbed.driver.OrbDriver` to create an ephemeral `synlynk-ftue-test` node.
  - Builds the production wheel (`python3 -m build --wheel`).
  - Copies wheel into the VM and runs:
    1. `pipx install synlynk-*.whl`
    2. `synlynk --version`
    3. `synlynk doctor`
    4. `synlynk init --dry-run` (verifying no files created)
    5. `synlynk init --yes` (verifying clean first-time setup)
    6. `synlynk launch` replay (verifying real job ID output)
    7. `synlynk viz --port 8765` route audit via curl
  - Tears down the VM instance on completion.
- **Verification:** Acceptance test passes completely on local OrbStack environment.
