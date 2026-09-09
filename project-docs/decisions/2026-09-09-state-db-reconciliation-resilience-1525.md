# Decision: State DB fallback and reconciliation resilience (#1525)

[@codex] The effective state DB must be write-capable for write-capable
commands. Automatic selection therefore probes a transaction and falls back
when the central path is inaccessible or read-only; explicit
`SYNLYNK_STATE_DB_PATH` remains exact and fail-fast. The selected path is
observable without mutating live state.

[@codex] Capability-rating and cost/telemetry persistence are isolated per
job. Sentinel records degraded persistence and critical integrity failures,
while status, logs, dispatch monitoring, and worktree audit continue. The
flat-file reconciler is serialized to make concurrent callers safe.
