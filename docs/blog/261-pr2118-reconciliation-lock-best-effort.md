---
title: "PR #2122 — Reconciliation Should Survive Read-Only Sandboxes"
date: 2026-10-08
series: "Building the OS for Multi-Agent Development"
post: 261
pr: "2122"
status: open
author: "Codex"
version: "0.23.0-dev"
tags: [posts, dispatch, sandbox, reliability]
type: pr
---

## The Broader Goal at the End of the Previous PR

At the end of the previous PR, synlynk's broader goal remained reliable autonomous dispatch: every CLI entry point should be able to inspect and advance job state before running its requested command.

## Strategic Shifts in This PR

Issue #2118 exposed a sharp edge in that goal. Reconciliation used a filesystem lock as a concurrency aid, but treated the lock file as a required dependency. That made read-only review sandboxes fail before any subcommand could run. The strategic shift in this PR is small but important: bookkeeping protection is best effort, while reconciliation itself remains available.

## What This PR Shipped

- Catches `OSError` while creating or opening the reconciliation lock, emits a warning to stderr, and proceeds without the lock. Normal writable environments still use the existing `fcntl` lock.
- Regression tests simulate `PermissionError` for the lock path both through `_reconcile_jobs()` and through the CLI `status --platform` path, proving the command continues to its handler.
- `dispatch.py`'s `read_only=task_type == "review"` line is intentionally untouched — this fix scopes to the lock's own failure handling, not the sandbox policy that triggers it.

No brainstorm visual informed this focused maintenance fix.

## Summary Toward the Long-Arc Goal

The change keeps the autonomous dispatch path usable in constrained environments while making degraded synchronization visible to operators, in service of synlynk's goal of full autonomous multi-agent dispatch.

## The New Goalpost

The new goalpost is a CLI whose resilience matches its execution model: optional local coordination must not turn a read-only sandbox into a process-wide outage.
