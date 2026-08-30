---
title: "PR #1286 — Eliminating Agy Headless 5-Minute Timeout, Enabling Plan Mode, and Capturing Prompt Cache Telemetry"
date: 2026-08-30
series: "Building the OS for Multi-Agent Development"
post: 137
pr: "#1286"
merged: 2026-08-30
---

## The Broader Goal at the End of the Previous PR

After establishing full headless parity for OpenAI Codex (PR #1275) and xAI Grok (PR #1279), the objective shifted to evaluating harness parity for the remaining core fleet members: Google Agy (Antigravity CLI) and Anthropic Claude.

## Strategic Shifts in This PR

For months, Agy dispatches that lasted longer than 5 minutes failed intermittently with `Error: timeout waiting for response` (`HARNESS_INTERNAL_TIMEOUT`), often leaving zombie jobs in `daemon_jobs`. Simultaneously, Agy could not be dispatched for read-only audits or code reviews without write permissions due to an unnecessary `PermissionEnforcementError` fail-closed check. In addition, prompt cache hits in Gemini were discarded as `0` cache reads, distorting cost tracking.

PR #1286 resolves all three structural defects natively.

## What This PR Shipped

1. **Pass `--print-timeout 30m0s` on All Headless Agy Dispatches:**
   - Declared `--print-timeout` and `--mode` in `synlynk/_constants.py` under `HARNESS_CAPABILITY_BASELINES["agy"]["dispatch_flags"]["valid_flags"]`.
   - In `synlynk/dispatch.py:dispatch_agent()`, dynamically appends `["--print-timeout", "30m0s"]` for `agy` dispatches, preventing the default 5-minute client-side timeout.
2. **Native Read-Only Planning Mode:**
   - In `synlynk/dispatch.py:_permissions_to_flags()`, replaced the `PermissionEnforcementError` for `permissions <= {"read:*"}` with `["--mode", "plan"]`, allowing Agy to be safely dispatched for read-only audits and reviews.
3. **Capture Gemini Prompt Cache Telemetry:**
   - In `synlynk/costs.py:_extract_agy_structured()`, extracted `cache_read_tokens = int(usage.get("cache_read_tokens", 0))` instead of hardcoding `0`. During our dogfooding run, 7.14M prompt cache tokens were accurately captured!
4. **Comprehensive Test Coverage:**
   - Added unit tests verifying `--print-timeout 30m0s` injection, `--mode plan` translation, and cache token extraction across `tests/test_dispatch.py`, `tests/test_agent_cli.py`, `tests/test_constants.py`, `tests/test_cost_ledger.py`, and `tests/test_costs.py`.

## What This Achieved on the Path to Autonomy

Agy can now reliably execute deep, multi-minute implementation tasks and read-only reviews without premature aborts or distorted billing telemetry.
