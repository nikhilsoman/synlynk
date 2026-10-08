# PR #TBD - Reconciliation Should Survive Read-Only Sandboxes

At the end of the previous PR, synlynk's broader goal remained reliable autonomous dispatch: every CLI entry point should be able to inspect and advance job state before running its requested command.

Issue #2118 exposed a sharp edge in that goal. Reconciliation used a filesystem lock as a concurrency aid, but treated the lock file as a required dependency. That made read-only review sandboxes fail before any subcommand could run. The strategic shift in this PR is small but important: bookkeeping protection is best effort, while reconciliation itself remains available.

This PR catches `OSError` while creating or opening the reconciliation lock, emits a warning to stderr, and proceeds without the lock. Normal writable environments still use the existing `fcntl` lock. Regression tests simulate `PermissionError` for the lock path both through `_reconcile_jobs()` and through the CLI `status --platform` path, proving that the command continues to its handler.

No brainstorm visual informed this focused maintenance fix. The change keeps the autonomous dispatch path usable in constrained environments while making degraded synchronization visible to operators.

The new goalpost is a CLI whose resilience matches its execution model: optional local coordination must not turn a read-only sandbox into a process-wide outage.
