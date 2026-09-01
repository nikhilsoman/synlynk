# Preflight Verification That Dispatched Agent Loaded Instruction File — Design

**Date:** 2026-08-30
**Status:** Approved
**Author:** Agy (implementer), brainstormed with Nikhil Soman
**Issue:** Resolves #347
**Tracking Story:** `story-e5383d22`
**Linked Goals:** `goal-a222b393`

---

## 1. Motivation & Problem Statement

Synlynk relies on project-root instruction files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md`) to deliver harness contracts, attribution trailers, branch naming rules, role boundaries, and PR review disciplines to each CLI.

Previously:
1. `_preflight_dispatch()` verified flag drift and network/permission requirements, but did not formally assert that the harness's core instruction file existed and was readable before dispatching.
2. Crucially, host-side file presence alone does not prove that a spawned subshell or agent CLI actually read and internalized the instructions. For example, in issue #343, `AGENTS.md` was missing entirely, yet dispatches attempted execution. In other incidents, CLI cwd misconfigurations caused agents to execute without ever reading their directive files.
3. Once a job started, synlynk had zero closed-loop verification of whether instructions were consumed, meaning jobs could produce silent convention drift (wrong commit trailers, wrong worktree operations) without detection.

---

## 2. Design & Architecture

To solve this, we introduce closed-loop instruction verification mirroring the proven task-receipt protocol (#720):

### A. Host-Side Instruction Version & Fingerprint Resolution
In `synlynk/instructions.py` (and exported to `synlynk/dispatch.py` and `synlynk/jobs.py`):
`extract_instruction_version(content: str) -> Optional[str]`
Extracts the version string from:
1. `synlynk:start version="([^"]+)"` or `# synlynk:start version="([^"]+)"`
2. `synlynk:harness (?:v)?(\S+) verified:`

`get_instruction_file_for_agent(agent: str) -> Optional[str]`
Returns the canonical instruction file name for the harness:
`{"claude": "CLAUDE.md", "agy": "GEMINI.md", "codex": "AGENTS.md", "grok": "GROK.md"}`.

### B. Preflight Gate in `_preflight_dispatch`
In `synlynk/dispatch.py:_preflight_dispatch()`:
When `harness_name` is in `CORE_FLEET` and the workspace contains any core instruction files:
1. Check that `get_instruction_file_for_agent(harness_name)` exists in the current repo/workspace root.
2. If missing and `force_agent` is False:
   Return `{"passed": False, "sentinel": "INSTRUCTION_FILE_MISSING", "reason": f"Missing instruction file '{instruction_file}' for Core 4 agent '{harness_name}' (LIVE-1 / #343 class error)"}`.

### C. Closed-Loop Instruction Receipt Protocol in Prompt Formatter
In `synlynk/dispatch.py:_format_prompt_for_agent()`:
Inject an Instruction Receipt section:
```markdown
## Instruction Receipt (required)
Confirm that your project instruction file ({instruction_file}) is loaded.
Print this exact line as your second output line (immediately after SYNLYNK_TASK_RECEIVED if present):
SYNLYNK_INSTRUCTION_VERSION: <version>
where <version> is the version string from your instruction file (e.g. from `synlynk:start version="..."` or `synlynk:harness ...`).
If no instruction file was loaded, print:
SYNLYNK_INSTRUCTION_VERSION: none
```
*Crucial Design Detail:* The prompt intentionally does **not** disclose the expected `<version>` string. The agent must genuinely have loaded and parsed its directive file to echo the matching version token.

### D. Job Construction & Reconcile Verification
In `synlynk/dispatch.py:dispatch_agent()`:
When creating the `job` record:
- Inspect the instruction file in the target worktree/repo root.
- Store `job["instruction_file"] = instruction_file` and `job["expected_instruction_version"] = expected_version`.

In `synlynk/jobs.py`:
- Introduce `_INSTRUCTION_RECEIPT_MARKER_PREFIX = "SYNLYNK_INSTRUCTION_VERSION:"`.
- `_check_instruction_receipt(log_text: str, expected_version: Optional[str]) -> Optional[str]`:
  - Scans log for `SYNLYNK_INSTRUCTION_VERSION: <val>`.
  - Returns:
    - `"ok"`: marker found and matches `expected_version`.
    - `"mismatch"`: marker found with different version.
    - `"none"`: agent explicitly indicated no instruction file was loaded.
    - `"absent"`: marker never printed.
    - `None`: check does not apply (no expected version or empty log).
- In `_reconcile_jobs()` and `_reconcile_active_job()`:
  - Check instruction receipt.
  - Record `job["instruction_receipt"] = status`.
  - If `status in ("mismatch", "none", "absent")` and `expected_version`:
    Emit an advisory sentinel warning (`INSTRUCTION_LOAD_MISMATCH` or `INSTRUCTION_LOAD_ABSENT`).
    Like task receipts, if real git activity landed, it remains an advisory warning without failing the job.

### E. Telemetry & Visibility
- In `synlynk jobs` and `synlynk status`:
  Surface the instruction load status alongside the task receipt status.

---

## 3. Verification & Test Plan (TDD)

1. `test_extract_instruction_version()`:
   Tests extraction of version from `synlynk:start` and `synlynk:harness` across various file formats.
2. `test_preflight_blocks_missing_instruction_file()`:
   Tests that `_preflight_dispatch` fails closed when a core instruction file is missing in an initialized repo unless forced.
3. `test_instruction_receipt_prompt_formatting()`:
   Tests that `_format_prompt_for_agent` injects the `SYNLYNK_INSTRUCTION_VERSION` directive without revealing the version value.
4. `test_check_instruction_receipt()`:
   Tests log parsing for `ok`, `mismatch`, `none`, and `absent`.
5. Full regression test suite: 499+ tests in `tests/test_synlynk.py` and all dispatch tests pass cleanly.
