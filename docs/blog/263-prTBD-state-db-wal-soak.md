---
title: "gh:#2102 — Soak-testing state.db with 20–50 concurrent WAL writers"
date: 2026-10-08
series: "Building the OS for Multi-Agent Development"
post: 263
pr: "#TBD"
status: open
author: "Grok"
version: "0.23.0-dev"
tags: [posts, sqlite, wal, reliability, testbed]
type: pr
---

## The Broader Goal at the End of the Previous PR

The previous work kept dispatch and review provenance honest so a fleet
could merge under measured cross-harness rules. The ledger those jobs
write — SQLite WAL `state.db` — still had no representative soak at
fleet writer counts.

## Strategic Shifts in This PR

The three-lens review called out P1-4: WAL helps, but more than about
ten concurrent writers was untested. This PR adds a repeatable local
testbed scenario and pytest soak at 20–50 writers instead of assuming
the journal mode would hold.

## What This PR Shipped

- `synlynk/testbed/state_db_soak.py` — isolated temp ledger, synthetic
  job/evidence/story updates, thread and process executors, lock/latency/
  integrity/recovery metrics, named failure modes.
- Testbed scenario `state_db_wal_soak`, wired to
  `synlynk testbed run --scenario state_db_wal` and
  `synlynk testbed soak --scenario state_db_wal` without OrbStack VMs.
- `tests/test_state_db_soak.py` — 20- and 50-writer soaks, process
  executor, JSON report contract, and a DELETE-journal negative control
  that records contention rather than swallowing it.
- Report: `project-docs/reports/2026-10-08-state-db-wal-soak.md`.

On this host the WAL path committed 400/400 transactions at 50 writers
with integrity `ok`, zero lock errors, and p99 latency 166ms. No
production reliability gap turned up in that envelope.

No brainstorm visual informed this soak.

## Summary Toward the Long-Arc Goal

A fleet that productizes a local/sovereign harness path needs a ledger
that stays correct when many workers write at once. This soak is the
first measured pass at that claim.

## The New Goalpost

Keep the soak in CI. If a later host or shard size fails integrity,
lock budget, or starvation thresholds, file a follow-up from the report
rather than relaxing the gate.
