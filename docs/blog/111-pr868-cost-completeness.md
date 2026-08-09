---
title: "PR #868 — Cost Completeness: No More Jobs Without cost_entries (Epic A2)"
date: 2026-08-09
series: "Building the OS for Multi-Agent Development"
post: 111
issue: 752
---

# Cost Completeness — No More Silent $0 Windows

## Goal
Epic A2 / #752: terminal jobs must leave a `cost_entries` row, and ops must flag when they do not.

## Shipped
1. **Ops** — `jobs_missing_cost`, `cost_missing_rate`, samples; finding when gap is large or entries=0 with many terminal jobs.
2. **Reconcile** — `_ensure_daemon_job_cost_entry` so preferred-summary short-circuit still writes costs; retry if `update_costs` throws.
3. Epic plan marks A2.1/A2.2 shipped.

## Next
A3 home/headless `dispatch_context` (#740). Pricing accuracy (#787) remains Epic C.
