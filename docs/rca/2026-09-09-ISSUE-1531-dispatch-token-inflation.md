# RCA: Issue #1531 dispatch token inflation and false failure signals

Date: 2026-09-09
Issue: #1531
Severity: Sev3 platform-health / cost observability

## Finding

The incident combines two independent signals:

1. `job-a4196776` used 4,375,124 input tokens, including 4,247,552 cached
   input tokens, 14,459 output tokens, and 5,332 reasoning tokens. The final
   Codex log contains 124 JSONL events and repeated test/tool turns. This is
   transcript replay across model turns, not repeated dispatch-context assembly.
2. The same job had `context_mode=task` and `context_bytes=3579`. `dispatch_agent`
   generates that per-job context once, writes it to the isolated worktree,
   and passes it in the prompt. It does not feed reconciled logs back into the
   prompt. Daemon polling reconciles external state and reads logs after exit;
   it cannot account for the model-side cached-input total.

Sentinel already detects the completed-job symptom: `check_token_bloat` emits
`TOKEN_BLOAT`/`COST_INFLATION`, and `enforce_job_circuit_breaker` can terminate
an active job that crosses the zero-file token or cost limit. The gap is that
the active circuit-breaker helper is not a model-token streaming meter; it can
only act on metrics supplied by the monitor. The 4.3M total therefore becomes
actionable at reconciliation, not necessarily while the model is still
running.

## Why useful work was marked failed

The `task_delivery_failed` status is produced when the task receipt is absent,
late, or mismatched and there is no corroborating local git activity. That is
safe for unattended code work, but incomplete for review/GitHub-write jobs:
useful remote work can exist without a commit or dirty worktree. The existing
GitHub-write verifier and receipt protocol are separate signals, so a missing
receipt can still dominate before remote-effect evidence is considered.

This is a classification/evidence-ordering problem, not evidence that log
polling retried the worker. Reconciliation is guarded and terminal-state
aware; repeated passes settle the row rather than spawning another model turn.

## Affected components

- `synlynk/dispatch.py`: one-shot task-context generation and prompt assembly.
- `synlynk/costs.py`: structured Codex usage extraction, including cached input.
- `synlynk/sentinel.py`: terminal token/cost anomaly detection and active
  circuit-breaker helper.
- `synlynk/jobs.py`: log reconciliation, receipt classification, git activity
  corroboration, and GitHub-write verification.
- `synlynk/daemon.py`: periodic reconciliation/dispatch polling; not a prompt
  replay source.

## Prioritized remediation

P0 (follow-up): add provider-neutral live usage checkpoints to the dispatch
monitor and invoke the existing circuit breaker at bounded intervals. Include
`input_tokens`, `cached_input_tokens`, output tokens, cost, and turn count in
the checkpoint event; make the cap configurable per task type.

P1 (follow-up): make delivery corroboration an evidence union. For jobs with
`requires_gh_write`, a verified expected GitHub effect should downgrade a
missing/late receipt to a warning, just as local git activity does. Preserve
the worktree and receipt evidence for audit.

P1 (follow-up, related to #1527): emit one structured terminal event per
reconciliation generation and deduplicate Sentinel alerts by `(job_id, code,
generation)`, so repeated polling is observable without repeated cost/alert
side effects.

No dispatch-context truncation change is justified by this incident: the
observed context was already small, and truncating it would risk task fidelity.

## Verification

The focused Sentinel regression test models the observed 4.3M-input shape and
asserts a critical actionable alert. Existing job tests cover receipt
classification, local-work corroboration, terminal reconciliation, and
cost/token persistence.
