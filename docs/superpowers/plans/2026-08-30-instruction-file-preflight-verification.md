# Instruction File Preflight and Receipt Verification — Implementation Plan

**Goal:** Implement closed-loop preflight and runtime verification that dispatched agent CLIs actually loaded and consumed their instruction files, closing Issue #347.

**Architecture:** Defined in `docs/superpowers/specs/2026-08-30-instruction-file-preflight-verification-design.md`.

---

### Task 1: Instruction Version Extraction & Preflight Check (TDD)

**Files:**
- Modify: `synlynk/instructions.py`
- Modify: `synlynk/dispatch.py`
- Modify: `tests/test_instructions.py`
- Modify: `tests/test_dispatch.py`

- [ ] **Step 1: Write unit tests for `extract_instruction_version()`**
  In `tests/test_instructions.py`:
  Test extraction from `<!-- synlynk:start version="0.9.4" -->`, `# synlynk:start version="1.0"`, and `<!-- synlynk:harness v2.0.0 verified:... -->`.

- [ ] **Step 2: Implement `extract_instruction_version()`**
  In `synlynk/instructions.py`:
  Implement regex extraction supporting HTML/hash `synlynk:start` and `synlynk:harness` markers.

- [ ] **Step 3: Wire instruction file presence check into `_preflight_dispatch()`**
  In `synlynk/dispatch.py:_preflight_dispatch()`:
  Verify that the core instruction file exists if the repo has any core instruction files and `force_agent` is False.

- [ ] **Step 4: Run unit tests to confirm passing**
  `python -m pytest tests/test_instructions.py tests/test_dispatch.py -k instruction`

---

### Task 2: Prompt Formatter Instruction Receipt Protocol (TDD)

**Files:**
- Modify: `synlynk/dispatch.py`
- Modify: `tests/test_dispatch.py`

- [ ] **Step 1: Write failing unit test for instruction receipt prompt injection**
  In `tests/test_dispatch.py`:
  Assert `_format_prompt_for_agent()` includes the `SYNLYNK_INSTRUCTION_VERSION` directive with instruction file name, but without disclosing the version value.

- [ ] **Step 2: Implement `_render_instruction_receipt_instruction()` in `synlynk/dispatch.py`**
  Add prompt header instructing the agent to echo `SYNLYNK_INSTRUCTION_VERSION: <version>`.
  Record `instruction_file` and `expected_instruction_version` on the job object.

- [ ] **Step 3: Verify test passes**
  `python -m pytest tests/test_dispatch.py -k instruction_receipt`

---

### Task 3: Job Log Instruction Receipt Checking & Reconciliation (TDD)

**Files:**
- Modify: `synlynk/jobs.py`
- Modify: `tests/test_jobs.py`

- [ ] **Step 1: Write failing unit tests for `_check_instruction_receipt()`**
  In `tests/test_jobs.py`:
  Test `"ok"`, `"mismatch"`, `"none"`, and `"absent"` return codes.

- [ ] **Step 2: Implement `_check_instruction_receipt()` in `synlynk/jobs.py`**
  Parse log output for `SYNLYNK_INSTRUCTION_VERSION: <val>`.
  Wire into `_reconcile_jobs()` and `_reconcile_active_job()` to record `job["instruction_receipt"]` and emit advisory alerts on failure.

- [ ] **Step 3: Verify tests pass**
  `python -m pytest tests/test_jobs.py -k instruction_receipt`

---

### Task 4: Full Test Suite Verification

- [ ] **Step 1: Run complete `tests/test_synlynk.py` (499 tests)**
- [ ] **Step 2: Run `tests/test_dispatch.py`, `tests/test_jobs.py`, and `tests/test_instructions.py`**
- [ ] **Step 3: Run `tests/test_agent_cli.py`**

---

### Task 5: Housekeeping & PR

- [ ] **Step 1: Write blog post in `docs/blog/`**
- [ ] **Step 2: Update `project-docs/memory.md`**
- [ ] **Step 3: Update `project-docs/todo.md` and `project-docs/devlogs/`**
- [ ] **Step 4: Push branch and create PR for Issue #347**
