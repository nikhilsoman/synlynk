---
title: "PR #1309 — Fleet Parity: Instruction File Preflight Check and Closed-Loop Receipt Verification"
date: 2026-08-30
series: "Building the OS for Multi-Agent Development"
post: 142
pr: "#1309"
issue: "#347"
status: merged
---

# PR #1309 — Fleet Parity: Instruction File Preflight Check and Closed-Loop Receipt Verification

## The Broader Goal at the End of the Previous PR

PR #1308 closed issue #342 by enforcing `--cwd` for Grok and `-C` for Codex, securing working-directory root containment across all autonomous dispatches. That left issue #347 as the final remaining open ticket from the original dogfooding-readiness fleet-parity cluster.

## What Was Missing

Synlynk coordinates multi-agent workflows through instruction files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md`), where role boundaries, commit trailer requirements, and PR review protocols are defined.

However, the pipeline previously relied on unverified trust:
1. `_preflight_dispatch()` did not verify that a Core 4 agent's directive file was actually present and readable in an initialized repo. In issue #343, `AGENTS.md` was missing entirely, yet dispatches executed blindly.
2. Even when a file exists on disk, there was zero closed-loop verification that the spawned CLI actually read and internalized it. A job could report success while silently violating all repo conventions.

## What Shipped

1. **Instruction Version Extraction:**
   - Added `extract_instruction_version()` and `get_instruction_file_for_agent()` in `synlynk/instructions.py`, extracting canonical version tokens from both `synlynk:start` and `synlynk:harness` markers.
2. **Preflight Gate in `_preflight_dispatch`:**
   - Fails closed with `INSTRUCTION_FILE_MISSING` if an instruction file for a Core 4 agent is absent in an initialized repo, unless explicitly bypassed with `--force-harness` / `--force-agent`.
3. **Closed-Loop Instruction Receipt Protocol:**
   - In `synlynk/dispatch.py:_format_prompt_for_agent()`, prompts the agent to echo `SYNLYNK_INSTRUCTION_VERSION: <version>` without revealing the version string in the prompt text.
   - The agent must genuinely inspect its loaded directive file to return the matching token.
4. **Log Analysis & Advisory Signals:**
   - In `synlynk/jobs.py`, added `_check_instruction_receipt()` to classify output as `ok`, `mismatch`, `none`, or `absent`.
   - Wired into `_reconcile_jobs()` and `_reconcile_active_job()` to record telemetry and emit advisory sentinel alerts on convention drift.
5. **Comprehensive TDD Tests:**
   - Added unit tests in `tests/test_instructions.py`, `tests/test_dispatch.py`, and `tests/test_jobs.py`.
   - All 499 tests in `tests/test_synlynk.py` pass cleanly.
