# LIVE-13: Grok Headless Dispatch Shell Execution Denial & Missing Permission Bypass

**Date:** 2026-09-22  
**Severity:** Sev2 (Major agent harness headless execution degraded; production fallback routing to Codex/Claude/Agy active)  
**Status:** Declared & Investigated  
**Related Specs & Issues:**
- `docs/superpowers/plans/2026-09-11-cluster-c-fleet-diagnostic-truth-concurrency.md`
- `docs/blog/149-pr1316-doctor-tc9-live-gh-write-probe.md`
- Issue #1213, Issue #1522, PR #1316, PR #1727

---

## Executive Summary

During headless multi-harness dispatch and calibration benchmarks (jobs `job-2ad8db24`, `job-32efed8b`, `job-b069d09d`, `job-1bd26739`, `job-57265dd9`, `job-983c58e4`), all headless code generation tasks assigned to the Grok harness failed to execute subshell commands or produce workspace artifacts. 

Investigation revealed that Grok CLI (v1.0.30) headless invocation defaults to `--permission-mode dontAsk` without explicit bypass flags (`--always-approve` and `--permission-mode bypassPermissions`). Under this configuration, the internal Grok tool execution engine automatically cancels compound bash and file-mutation tools with `stopReason: cancelled`. Furthermore, because Grok emits a conversational refusal (*"I am unable to execute shell commands in this sandbox"*) while returning exit code 0, outer reconcilers originally treated these runs as completed without writing files (a silent no-op), until fail-closed canary checks were established in #1522.

---

## Timeline & Diagnostic Trace

1. **PR #1271 / PR #1316 (Doctor TC-9 Probe):** Discovered that Grok headless dispatch sandbox denied GitHub write and shell execution (`sandbox_denied`). Introduced `_run_tc9()` in `synlynk/probe.py` to classify Grok as non-write capable for GitHub actions.
2. **2026-09-11 (Issue #1522 / Milestone v0.20.0 Cluster C):** Implemented preflight write canary validation (`check_grok_sandbox_write_capability()`) in `synlynk/dispatch.py` to intercept write-demanding tasks and fail over to Codex.
3. **2026-09-19 (Capability Calibration Sweep):** Dispatched 6 coding calibration tasks to Grok. In `synlynk/dispatch.py:_grok_permission_flags()`, permissions without `run:shell` or `run:tests` translated to `--permission-mode dontAsk`, causing Grok to reject tool execution and return empty payloads to verifying review agents (`job-6e02683f`, `job-aa61faeb`, `job-154a8c03`).
4. **2026-09-22 (Live Probe & Incident Declaration):** Probed `/Users/nikhilsoman/.grok/bin/grok` directly. Confirmed both headless permission cancellation mechanics and upstream 402 Payment Required status on x.ai API balance.

---

## Root Causes

### 1. Headless Permission Mode Cancellation
- **Mechanism:** In Grok CLI v1.0.x, `--permission-mode dontAsk` treats any unconfirmed interactive tool execution as rejected.
- **Defect in Dispatch:** `synlynk/dispatch.py:_grok_permission_flags()` only passed `--always-approve` when `run:shell` or `run:tests` was explicitly present in the permission set. For standard code generation or file writing tasks, it set `--permission-mode dontAsk` with individual tool allow lists, which the Grok runtime aborted non-interactively.
- **Fix Required:** Pass `--always-approve` and `--permission-mode bypassPermissions` for all trusted headless dispatch invocations.

### 2. Silent No-Op & Process Exit Code Decoupling
- **Mechanism:** When Grok cancels tools in headless mode, it explains the restriction in plain text and terminates the process with code 0 instead of a non-zero exit code.
- **Defect in Harness Contract:** Reconcilers inspecting only process return codes failed to catch the cancellation. Mitigated by `task_requires_write()` and `check_grok_sandbox_write_capability()`, but requires explicit bypass flags when Grok is intended to write.

### 3. Upstream Account Quota Depletion
- **State:** Live probe returned HTTP 402 `Grok Build usage balance exhausted`. Requires account balance top-up on x.ai console.

---

## Corrective Action Plan

| Action | Description | Owner | Target |
| :--- | :--- | :--- | :--- |
| **Action 1** | Update `_grok_permission_flags()` in `synlynk/dispatch.py` to always supply `--always-approve` and `--permission-mode bypassPermissions` for headless dispatches | Codex / Agy | Linked Fix PR |
| **Action 2** | Add comprehensive unit tests in `tests/test_dispatch_permissions.py` / `tests/test_grok_write_guard.py` verifying Grok command arguments | Codex / Agy | Linked Fix PR |
| **Action 3** | Re-run TC-9 live write probe in `synlynk doctor` once x.ai quota is replenished | Operator | Live Ops |
