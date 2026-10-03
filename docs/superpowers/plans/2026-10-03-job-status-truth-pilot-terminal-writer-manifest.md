# Terminal-writer manifest (PR1)

The canonical terminal decision entry point is
`synlynk.job_truth.record_evidence_and_reconcile`. It is the only PR1 API
that may append `job_terminal_decision` rows or project a decision to
`daemon_jobs.status`.

| Existing path | PR1 disposition |
| --- | --- |
| `synlynk.jobs._reconcile_jobs_unlocked` | compatibility observer; emits evidence in the follow-up routing PR |
| `synlynk.jobs._reconcile_daemon_jobs` | canonical SQLite observer; uses the PR1 ledger entry point |
| `synlynk.verify_effects.verify_job_effects` | pure effect observer; returns evidence, never writes status |
| `synlynk.daemon._reconcile_orphans_on_startup` | requests reconciliation; never owns a terminal decision |
| `synlynk.dispatch` process/receipt/timeout paths | evidence producers; legacy summary remains compatibility output |

The enforcement test in `tests/test_job_truth.py` requires the manifest to
contain the canonical writer and the canonical writer to remain importable.
Legacy JSON summary updates are intentionally retained as read-only
compatibility output until the structured-ingestion PR.
