---
title: "PR #2257 — add opt-in personal hosted relay with durable replay"
date: 2026-10-13
series: "Building the OS for Multi-Agent Development"
post: 314
pr: "#2257"
status: merged
author: "nikhilsoman"
version: "0.25.0"
tags: [posts]
type: pr
---

## The Broader Goal at the End of the Previous PR

Advancing the multi-agent operating system toward reliable, autonomous development, unblocking workgroup velocity and eliminating manual developer toil.

## Strategic Shifts in This PR

Focused, limited-treatment delta resolving PR #2257 requirements with strict backward compatibility and comprehensive verification.

## What This PR Shipped

- Merged improvements and fixes for PR #2257.

## Verification & Test Evidence

TDD and targeted regression were performed at each task boundary. Real NATS tests use separate CLI processes, databases, and exported credentials; they verify delivery, restart replay, duplicate suppression, independent category cursors, retention gaps, filters, workspace rejection, and revocation after reload. Preview tests cover traversal, symlinks, atomic replacement, read-only output, retryable storage errors, and serialized envelope limits.
Task 10 worker full suite: 4419 passed, 1 sandbox home-log permission failure,
4 skipped, 5 xfailed. The isolated failing Vizor test passed with required
permissions. **Final combined full suite: 4436 passed, 3 skipped,
5 xfailed in 273.59s**, using `pytest -q -n 4 --dist loadfile` with no exclusions
and real NATS available. Final focused verification: 260 passed, including all
ten real authenticated NATS integration cases. Stdlib-only import check passed.
QA fixes register all six commands and regenerate reference docs, detect bridge
queue eviction and resume forwarding with a local loss marker, support trusted
symlinked preview bases without following remote symlinks, and move local I/O off
the NATS loop. Four additional red/green cases verify cancellation during storage
failure and repeated cancellation; shutdown drains owned work before completing.
The optional dependency floor is nats-py 2.16.0, verified with actual credentials.
CI exposed a Python 3.10 test-only TimeoutError class mismatch. The exact
concurrent.futures exception is now asserted: reproduced red on 3.10.20, then
four cleanup cases passed on 3.10.20 and 3.14. Final CI is rerunning on 08788bae.

## What This Achieved on the Path to Autonomy

Maintains repository integrity, expands test-proven capabilities, and keeps the hybrid human-agent workgroup aligned with zero drift.
