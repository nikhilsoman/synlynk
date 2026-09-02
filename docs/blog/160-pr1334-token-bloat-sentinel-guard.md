---
title: "PR #1334 — Sentinel Guard for Token Bloat and Cost Inflation"
date: 2026-09-02
series: "Building the OS for Multi-Agent Development"
post: 160
pr: "#1334"
merged: status open
---

## The Broader Goal at the End of the Previous PR

Prior to this investigation, synlynk focused on establishing full fleet parity and operational stability across its four primary harnesses (Claude, Codex, Agy, and Grok). Sentinel monitors existed to catch command repetition loops (`SUCCESS_LOOP`), recurring subprocess crashes (`FLATLINE`), quota exhaustion (`QUOTA_EXHAUSTED`), and verification skips (`VERIFY_SKIP`). However, the system lacked a metric-driven guard to evaluate the economic efficiency and token intensity of individual job executions.

## Strategic Shifts in This PR (if any)

Issue #1073 surfaced a live incident on `job-cf837848` (dispatch for issue #1068), where an agent job consumed **7.6M input tokens** and accumulated **$5.26 USD** across 6+ hours before timing out, without touching a single file in the worktree. 

This investigation shifted Sentinel from purely checking process health and stderr patterns to actively monitoring **resource consumption anomalies** — specifically calculating the **token-per-file-touched ratio** and alerting on **cost inflation**.

## What This PR Shipped

1. **Root-Cause Investigation of `job-cf837848` (#1073):**
   - Dispatched under `--context-mode full`, injecting extensive project-wide documentation and state tables.
   - Headless multi-turn execution caused the context history to expand monotonically turn after turn.
   - The agent stalled in internal loops without landing changes, leading to an infinite token-to-file ratio (7.65M tokens across 0 files touched).
2. **New Sentinel Guard in `synlynk/sentinel.py` (`check_token_bloat`):**
   - **Zero-File Token Bloat (`TOKEN_BLOAT`):** Triggers a `WARN` (at $\ge 500\text{k}$ tokens) or `CRITICAL` (at $\ge 2\text{M}$ tokens) when a job finishes or times out with zero files modified.
   - **Anomalous Token-to-File Ratio (`TOKEN_BLOAT`):** Computes $\frac{\text{total\_tokens}}{\text{files\_touched}}$ and triggers alerts when consumption exceeds $500\text{k}$ tokens/file (with `CRITICAL` at $\ge 1\text{M}$ tokens/file).
   - **Cost Inflation (`COST_INFLATION`):** Flags jobs accumulating $\ge \$3.00$ (`WARN`) or $\ge \$5.00$ (`CRITICAL`).
   - **Telemetry Scanning:** Reads `.synlynk/telemetry.json` to identify historical anomalies when invoked during periodic daemon passes or CLI checks.
3. **Reconciliation Integration in `synlynk/jobs.py`:**
   - Evaluated automatically in `_reconcile_jobs()` and `_reconcile_daemon_jobs()` upon job completion.
4. **Comprehensive Test Suite:**
   - Unit tests in `tests/test_sentinel.py` verifying ratio calculations, threshold boundaries, zero-file detections, and telemetry parsing.
   - Issue regression test `test_investigate_rootcause_costtoken_bloat_on_jobcf837848_and_add_costratio_sentinel_guard_1073` in `tests/test_agent_cli.py`.

## Brainstorm Visuals Used

- `docs/brainstorm/sentinel-observability/sentinel-observability-system.html` (Sentinel Observability Architecture)

## What This Achieved on the Path to Autonomy

In an unattended autonomous loop, runaway agents can silently burn budgets and rate limits if not checked. By adding token-per-file ratio and cost inflation guards into Sentinel, synlynk ensures that inefficient context usage and spinning agents are immediately flagged in `.synlynk/sentinel.md`, `synlynk status`, and Vizor dashboards before budget limits are breached.

## Strategic Note: The Goal at the End of This PR

With token bloat and cost inflation detection active in the Sentinel layer, future work can implement dynamic context pruning and automated throttle/re-prompt policies when in-flight turn tokens exceed expected bounds.
