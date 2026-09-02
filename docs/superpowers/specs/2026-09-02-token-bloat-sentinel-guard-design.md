# Sentinel Token Bloat & Cost Inflation Guard — Design

**Date:** 2026-09-02  
**Status:** Approved  
**Author:** Agy (Gemini)  
**Tracking Issues:** #1073 (Investigation & Guard), relates to #1068 (Incident Job `job-cf837848`)  

---

## 1. Executive Summary & Incident Investigation (#1073)

On 2026-08-19, headless dispatch job `job-cf837848` was executed to address issue #1068 (*"prevent global state DB corruption from unisolated migration/DB tests"*). Historical telemetry records in `.synlynk/projects/13267207/state.db` and execution metadata revealed severe resource exhaustion:

- **Input Tokens:** 7.6M (7,600,000 tokens)
- **Accumulated Cost:** $5.26 USD
- **Files Touched:** 0 files modified
- **Runtime & Status:** Ran from `2026-08-19T04:22:21` to `2026-08-19T10:44:00` (6+ hours) before terminating with `status: timed_out` (exit code `-9`).

### 1.1 Root Cause Analysis

1. **Context Mode Selection & Monotonic Context Expansion:**  
   The task was dispatched with `context_mode="full"` (injecting 5,123 bytes of raw project documentation, memory files, and full roadmap arcs). In multi-turn headless agent loops, each tool invocation re-transmits prior turn history alongside the base context. Over dozens of turn cycles across 6 hours, cumulative prompt tokens expanded into 7.6M input tokens.
2. **Infinite Stalling & Timeout without File Mutation:**  
   The agent entered an extended internal reasoning/test execution stall where zero code changes landed in the checked-out worktree before timing out. The resulting token-to-file ratio was infinite (7.6M tokens for 0 files touched).
3. **Absence of Post-Job Sentinel Anomaly Guard:**  
   While synlynk possessed `FLATLINE` (command failures), `SUCCESS_LOOP` (tight loops), and `QUOTA_EXHAUSTED` sentinel checks, it lacked an automated detection pattern to evaluate anomalous **token-per-file-touched ratios** or **cost inflation** on completed or timed-out jobs.

---

## 2. Guard Architecture & Detection Specification

We implement a dedicated Sentinel guard in `synlynk/sentinel.py` (`check_token_bloat`) that runs both on completed job reconciliation and during telemetry scans.

### 2.1 Detection Metrics & Ratios

Let:
- $T_{\text{in}}$ = input tokens, $T_{\text{out}}$ = output tokens, $T_{\text{total}} = T_{\text{in}} + T_{\text{out}}$
- $C$ = calculated cost in USD
- $F$ = count of files touched in worktree (or remote commits)
- $R = \frac{T_{\text{total}}}{\max(1, F)}$ = token-per-file-touched ratio

### 2.2 Alert Triggers & Thresholds

| Alert Code | Severity | Condition | Description |
| :--- | :--- | :--- | :--- |
| `TOKEN_BLOAT` | `WARN` | $F = 0 \land T_{\text{total}} \ge 500\text{k}$ | High token burn with zero files modified. |
| `TOKEN_BLOAT` | `CRITICAL` | $F = 0 \land T_{\text{total}} \ge 2\text{M}$ | Runaway token burn with zero files modified. |
| `TOKEN_BLOAT` | `WARN` | $F > 0 \land R \ge 500\text{k}$ | High token-per-file ratio. |
| `TOKEN_BLOAT` | `CRITICAL` | $F > 0 \land (R \ge 1\text{M} \lor T_{\text{total}} \ge 2\text{M})$ | Extreme token-per-file ratio or multi-million token consumption. |
| `COST_INFLATION` | `WARN` | $C \ge \$3.00$ | Single job cost exceeds warning threshold ($3.00). |
| `COST_INFLATION` | `CRITICAL` | $C \ge \$5.00$ | Single job cost exceeds critical ceiling ($5.00). |

---

## 3. Integration & Lifecycle Wiring

1. **Direct Reconciliation Hook:**  
   Invoked in `synlynk/jobs.py` within `_reconcile_jobs()` and `_reconcile_daemon_jobs()` immediately after token extraction and cost calculation.
2. **Telemetry File Scanning:**  
   `check_token_bloat()` without explicit arguments reads `.synlynk/telemetry.json` to flag historical anomalies.
3. **Execution Gate Pattern:**  
   `check_sentinel_patterns()` invokes `check_token_bloat()` to ensure historical telemetry is continuously validated.
4. **Structured Alert Emission:**  
   Emits structured lines to `.synlynk/sentinel.md` via `_write_sentinel_alert()`, surfaced cleanly in `synlynk status` and Vizor dashboards.

---

## 4. Verification & Testing Strategy

- **Unit Tests (`tests/test_sentinel.py`):**
  - Zero files touched with 7.6M tokens & $5.26 cost (`job-cf837848` reproduction).
  - High token-per-file ratio (>1M tokens/file across multiple files).
  - Normal baseline executions (zero false positives).
  - Cost inflation warning ($3.50) and critical ($5.26) thresholds.
  - Telemetry file scanning from `.synlynk/telemetry.json`.
- **Integration Test (`tests/test_agent_cli.py`):**
  - Issue #1073 regression test `test_investigate_rootcause_costtoken_bloat_on_jobcf837848_and_add_costratio_sentinel_guard_1073`.
