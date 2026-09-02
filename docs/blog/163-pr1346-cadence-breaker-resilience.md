# PR #1346 - Cadence-Breaker Resilience

Autonomous systems fail in surprisingly ordinary ways: two agents append to
the same markdown index, a stalled process spends its budget without changing
a file, a harness rejects a startup option, or a dead PID leaves a worktree
behind. This change gives each failure a bounded recovery path.

The resilience engine adds a conservative markdown auto-rebaser, a sentinel
circuit breaker at 500,000 zero-file tokens or $5, startup failover to the next
harness, and an SRE reaper for dead daemon jobs. Recovery is observable: the
job state and sentinel telemetry record what happened, while unsupported git
conflicts remain fail-closed for human review.

The goal is not to hide failures. It is to keep a routine failure from
breaking the cadence of the autonomous loop.
