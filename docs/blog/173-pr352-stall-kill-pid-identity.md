---
title: "PR #TBD — Stall-Kill Must Prove Which Process It Is Killing"
date: 2026-09-04
series: "Building the OS for Multi-Agent Development"
post: 173
pr: "#TBD"
---

## The Broader Goal at the End of the Previous PR

The previous work continued hardening synlynk's autonomous dispatch loop: agents should be observable, recoverable, and safe to supervise over long-running sessions. The next goalpost was to keep operational automation from making a bad assumption when the operating system changes underneath it.

## Strategic Shifts in This PR

The stall circuit breaker had treated a stored PID as sufficient identity. That is safe only while the original process is alive. On a long-running machine, the original can exit and its PID can later belong to an unrelated process. This PR narrows the supervisor's authority: a missing or changed identity is now a reason to skip the signal, not a reason to guess.

## What This PR Shipped

Dispatch now records dependency-free process identity metadata alongside the PID: the OS-reported start time from `ps`, with the command line retained as a fallback. `synlynk.sentinel.process_identity_check()` re-reads that metadata before a circuit-breaker signal and returns either `safe to kill` or `do not kill`. A start-time mismatch is authoritative; when no start time is available, the expected command must still be present.

Both circuit-breaker paths use the check: direct `os.kill(pid, SIGTERM)` for jobs loaded from storage and the `proc.terminate()` path (including its `os.kill` fallback) for in-memory processes. If identity cannot be proven, the job is still marked `stalled_aborted`, but its reason records `PID recycled, skipped kill` so the operator can distinguish a safe skip from a delivered signal.

The tests cover a real subprocess identity capture where supported, matching and mismatching live identities, exited-process rejection, and a mocked circuit breaker assertion that `os.kill` is not called after an identity failure.

## Brainstorm Visuals Used

None directly; the change was a focused safety correction to an existing supervisor contract.

## What This Achieved on the Path to Autonomy

Autonomous dispatch now treats process control as an identity-sensitive operation rather than a PID lookup. That removes a rare but high-impact failure mode in which the system designed to stop a runaway agent could terminate an unrelated process, while preserving the job-state transition and telemetry needed for recovery.

## Strategic Note: The Goal at the End of This PR

The stall breaker can now stop only a process whose recorded identity still matches the dispatched job, and it explains when it safely declines to signal. The next goalpost is continuing the same identity discipline across every supervisor and cleanup path that acts on persisted process handles.
