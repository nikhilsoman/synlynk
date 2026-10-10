# Invariant 2: Hard In-Flight Token Circuit Breakers & Runaway Worker Killer Design Spec

- **Target Release:** v1.0.0 Developer Preview (October 1, 2026)
- **Status:** Approved
- **Epic:** #1805 (v1.0.0 Dev Preview Mandatory Architectural Invariants)
- **Tracking Issue:** #1808
- **Tracking Story:** `story-ea693cf8`
- **Goal:** `goal-5be4eb8b` (governed by master loop `goal-eacab0dc`)

---

## 1. Problem Statement & Motivation

In autonomous multi-agent development fleets, agents executing headless tasks can occasionally enter runaway states:
1. **Infinite Tool Error Loops:** Repeatedly executing failing commands or invalid tool calls without backoff.
2. **Context Streaming Runaways:** Emitting hundreds of thousands of tokens of redundant logs, recursive file dumps, or unstructured thoughts.
3. **Runaway Cost Accumulation:** A single unchecked worker can burn $10–$50 in minutes before post-hoc reconciliation or human operators intervene.

Passive post-mortem checks (such as checking token totals *after* a job exits) fail to prevent real-time financial and quota bleeding. Invariant 2 mandates hard, in-flight, real-time circuit breakers that actively sample process outputs and terminate runaway workers immediately when thresholds are breached.

---

## 2. Mathematical Invariant & Specification

$$\forall \text{ active job } J \in \text{RunningJobs}, \quad \big(\text{Tokens}(J) \ge T_{\max}(J) \lor \text{Cost}(J) \ge C_{\max}(J)\big) \implies \text{KillProcessTree}(J) \land \text{Status}(J) \leftarrow \text{circuit\_breaker\_tripped}$$

### Guarantees
1. **Active Real-Time Enforcement:** In-flight logs are inspected on every reconciliation tick and daemon loop interval (every $\le 5$ seconds).
2. **Deterministic Termination:** When limits are exceeded, the job's process tree receives `SIGTERM`, waits a grace period ($\le 2$ seconds), and escalates to `SIGKILL`.
3. **Explicit Failure Classification:** The job status is definitively marked `circuit_breaker_tripped` (not generic `failed` or `unknown`), preserving exact token counts and trigger reasons in `state.db` and `project-docs/costs.md`.
4. **Critical Sentinel Alerting:** Raises a high-priority `[CRITICAL]` alert `TOKEN_CIRCUIT_BREAKER_TRIPPED` in `.synlynk/sentinel.md` and telemetry.
5. **Autonomous DAG Failover:** The milestone orchestrator intercepts `circuit_breaker_tripped` and attempts failover to an alternative harness or prompts for escalation without freezing independent DAG tasks.

---

## 3. Configuration & Threshold Tiers

Stored in `.synlynk/config.json` under the `circuit_breaker` namespace, with intelligent defaults:

```json
{
  "circuit_breaker": {
    "enabled": true,
    "max_job_tokens": 300000,
    "max_job_cost_usd": 3.00,
    "zero_file_token_threshold": 150000,
    "check_interval_seconds": 5,
    "grace_period_seconds": 2,
    "tier_overrides": {
      "fast": { "max_job_tokens": 100000, "max_job_cost_usd": 0.50 },
      "pro": { "max_job_tokens": 300000, "max_job_cost_usd": 3.00 },
      "reasoning": { "max_job_tokens": 500000, "max_job_cost_usd": 5.00 }
    }
  }
}
```

---

## 4. Architecture & Module Design

### 4.1 In-Flight Circuit Breaker Engine (`synlynk/circuit_breaker.py`)
- Reads running job's `log_file` from disk using unbuffered/tail reads.
- Invokes `extract_tokens(log_text, agent)` and `_job_cost_usd(agent, in_tokens, out_tokens, model_version)`.
- Compares against resolved token and cost thresholds.
- If threshold exceeded:
  1. Validates process identity via `process_identity_check(pid, pid_identity)`.
  2. Sends `SIGTERM` to process / process group.
  3. Rechecks after grace period; if still alive, sends `SIGKILL`.
  4. Updates job status to `STATUS_CIRCUIT_BREAKER_TRIPPED`.
  5. Writes `TOKEN_CIRCUIT_BREAKER_TRIPPED` Sentinel alert with exact token and cost breakdown.
  6. Logs structured telemetry event `{"type": "circuit_breaker", "job_id": ..., "tokens": ..., "cost": ...}`.

### 4.2 Job Status Taxonomy Extension (`synlynk/jobs.py`)
- Adds `STATUS_CIRCUIT_BREAKER_TRIPPED = "circuit_breaker_tripped"`.
- Adds `STATUS_CIRCUIT_BREAKER_TRIPPED` to `TERMINAL_JOB_STATUSES` and `ALL_JOB_STATUSES`.
- Wires in-flight evaluation into `_reconcile_jobs_unlocked()` loop before stall checks.

### 4.3 Autonomous Milestone DAG Failover (`synlynk/launch_dag.py`)
- `LaunchDAG.handle_job_outcome()` checks `status == STATUS_CIRCUIT_BREAKER_TRIPPED`.
- If `retry_count < max_retries`, re-dispatches to secondary harness with lower token-bloat risk.
- If retries exhausted, marks node failed and raises escalation ticket.

### 4.4 Vizor HUD & Badging (`synlynk/viz.py`)
- Styles `circuit_breaker_tripped` with `.status-chip.circuit-breaker` (`⚡ BREAKER` badge in vivid red `#ef4444` with glowing border).

---

## 5. Verification & Acceptance Criteria

1. **Unit Tests (`tests/test_circuit_breaker.py`):**
   - In-flight log accumulation tripping token ceiling terminates process with `SIGTERM`/`SIGKILL`.
   - Cost inflation ceiling trigger terminates process.
   - Status transitions to `circuit_breaker_tripped` with Sentinel alert created.
   - Respects config overrides and per-tier ceilings.
2. **DAG Failover Tests (`tests/test_milestone_effect_failover.py`):**
   - Verifies `circuit_breaker_tripped` initiates autonomous failover to secondary harness.
3. **Regression Integrity:** 100% of the 3,336+ test matrix passing on Python 3.10 and 3.12.
