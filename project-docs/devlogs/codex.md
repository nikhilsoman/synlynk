# Codex Devlog

## 2026-09-16 - Unattended stacked-PR rebase (#1604)

- Added a mocked `BEHIND`/`MERGEABLE` PR repair helper that fetches `origin/main`, rebases cleanly, and force-pushes with lease; conflicts abort without pushing.
- Wired the helper into the QA merge path and removed the `--admin` merge flag.
- Verification: 143 tests passed, 1 skipped across the modified test files.
[@codex]

## 2026-10-03 — Job status truth pilot PR3 (#1933)

- Added the `job-status-truth.v1` machine-readable boundary projection with
  canonical status, legacy alias visibility, evidence summary, contract
  predicates, verification confidence, decision revision, and correction history.
- Added persisted legacy-vs-oracle shadow comparisons with explicit false
  failure/success and disagreement reason codes, low-cardinality metrics,
  promotion gates, and `SYNLYNK_JOB_TRUTH_MODE` rollout control.
- Added `synlynk jobs --json` and `synlynk jobs reconcile <job-id>`; manual
  reconciliation appends evidence through the canonical oracle.
- Verification: focused projection/CLI/oracle suite 32 passed; affected
  jobs/DB/dispatch integration suite 302 passed.
[@codex]

## 2026-09-28 — Rollback stash race hardening (#1834)

- Updated rollback dirty-path collection to ignore transient `.sentinel-*`
  files and status entries that disappeared before stash.
- Added a one-time surviving-path retry for the stash race, while preserving
  failures when real dirty paths still cannot be stashed.
- Added regression coverage; focused rollback/init tests passed (27), and the
  force-init end-to-end test passed 20 consecutive runs.
- Full suite: 3396 passed, 4 skipped, 1 unrelated environment failure in
  `test_poll_once_isolates_failures` because the default daemon log path was
  not writable; the test passed with a writable HOME.
[@codex]

## 2026-09-09 - PR #1518 QA follow-up

- Serialized local capability-envelope seeding and the final local dispatch
  capacity check with SQLite write transactions.
- Made local deferral fail loudly when its queue-row persistence fails.
- Verification: focused local-agent and dispatch/jobs tests passed (265 tests).
[@codex]

## 2026-09-09 - Local Capability Envelope and Concurrency Guard (Task Group 2)

- Made local capability seeding available on direct local dispatch, preserving
  idempotency and avoiding a mandatory `local doctor` prerequisite.
- Changed local-at-capacity dispatches to return a queued/deferred outcome and
  enforced the configured cap in the scheduler launch loop as well as direct
  dispatch.
- Added a safe default for malformed concurrency configuration and regression
  coverage for scheduler deferral.
- Verification: 180 dispatch/local-agent tests and 135 scheduler/jobs tests
  passed.
[@codex]

## 2026-09-02 - Subscription Cost Amortization and True-Up (#787)

- Added `harness_billing` configuration with subscription, metered overage,
  and zero-cost modes while retaining legacy payment-model compatibility.
- Implemented prior-month subscription amortization, capped extra usage, and
  `synlynk cost true-up` reconciliation rows.
- Added focused cost tests and blog post 161.
[@codex]

## 2026-09-02 — First-Class Model Registry (#1339)

- Added `ModelFamily`, `ModelSpec`, rate cards, context geometry, entitlement
  tiers, and a built-in catalog in `synlynk/models.py`.
- Added SQLite model-family/model tables, migration version 6, persistence and
  querying helpers, CLI commands, taxonomy entries, and doctor coverage.
- Added CLI harness, Ollama, and oMLX discovery probes plus blog/index updates.
- Verification: Python compilation and registry smoke test passed; full pytest
  verification remains to be run.
[@codex]

## 2026-09-02 — CLI Version Drift Warning (#1188)

- Added the design spec and implementation plan for detecting a stale
  pipx-installed CLI inside a synlynk checkout.
- Added `_synlynk_repo_root()` and `_warn_stale_repo_version()` in `synlynk/cli.py`.
  The check compares package `VERSION` with repository `VERSION`, emits an
  actionable stderr warning only when the installed version is behind, and is
  silent for unrelated or malformed projects.
- Added TDD coverage in `tests/test_agent_cli.py` for stale and current versions.
- Added blog post 154 and indexed it in `docs/blog/README.md`.
- Targeted test passed: `pytest tests/test_agent_cli.py -k 'cli_detect_and_warn_on_stale_pipxinstall' -v`.
[@codex]

## 2026-09-02 — Review Dispatch Read-Only Scope (#937)

- Added a read-only permission-resolution mode that strips `write:*` grants
  from review dispatches, including explicit caller grants.
- Kept Codex GitHub review submission network access while selecting the
  read-only workspace sandbox.
- Added regression tests in `tests/test_dispatch.py`, plus spec, plan, blog
  post 157, and index/memory updates.
[@codex]

## 2026-09-02 — Grok Boolean Dispatch Flag Deduplication (#1327)

- Added stable normalization of known boolean CLI flags at the final dispatch
  assembly boundary, preventing duplicate `--always-approve` values.
- Added Grok launch coverage in `tests/test_dispatch.py` and the focused
  regression test requested by the verification command in `tests/test_agent_cli.py`.
- Added the design spec, plan, blog post 159, and blog index entry.
[@codex]

## 2026-09-09 — State DB and reconciliation resilience (#1525)

- Added a non-mutating write-capability probe so automatic state DB selection
  rejects inaccessible/read-only central paths and uses a writable fallback;
  explicit overrides remain fail-fast and the selected path is observable.
- Isolated cost/telemetry and capability-rating persistence failures per job,
  preserving structured Sentinel visibility for degraded and integrity cases.
- Serialized flat-file reconciliation across concurrent callers and added
  regression coverage for fallback, persistence failure, concurrency, and
  continued operation.
[@codex]

## DR readiness and second-machine restore preparation (2026-09-18)

- Added `synlynk backup package`, which stages an online SQLite snapshot in a
  temporary directory, encrypts it to a workspace DR recipient, and removes
  plaintext staging before returning.
- Added the provider-neutral state DB disaster-recovery runbook covering
  encrypted retention, key custody, second-machine restore, and acceptance
  evidence.
- Focused backup verification: 5 passed, 2 skipped.
[@codex]

## 2026-10-03 — Job status truth pilot PR1 (#1933)

- Added immutable versioned effect contracts, append-only evidence, and
  revisioned terminal decisions in the canonical SQLite schema.
- Added the pure tri-state completion oracle with closed statuses, aliases,
  precedence rules, remote-only review regression coverage, duplicate/correction
  tests, and compatibility routing from both reconciliation paths.
- Verification: focused truth/oracle/reconciliation tests passed; migration,
  cost-ledger, and dispatch suites passed; `git diff --check` passed.
[@codex]

## 2026-10-03 — Job status truth pilot PR2 (#1933)

- Added versioned `lifecycle.v1` queued/running/observing/verifying/terminal/correction
  events with contract/job identity, sequence, process results, and evidence refs.
- Added append-only, idempotent lifecycle ingestion that records out-of-order events
  as rejected observations; adapter and jobs reconciliation paths retain legacy text
  only as compatibility evidence.
- Extended GitHub effect verification evidence with actor/target/SHA attribution and
  bounded read-after-write retry/quorum metadata. The canonical job-truth ledger
  remains the only terminal decision writer.
- Verification: focused telemetry/GitHub/effect suites 75 passed; broader jobs,
  dispatch, DB, and GitHub guard suites 304 passed; `git diff --check` passed.
[@codex]

## 2026-10-03 — Job status truth pilot PR3 QA remediation (#1962)

- Made persisted contract predicates authoritative: target, actor, and SHA
  mismatches cannot produce a completed decision; unresolved predicates remain
  verifying or fail closed after the verification budget.
- Hardened promotion gates with explicit verification-age, retry, unknown-state,
  and harness/effect-agreement thresholds plus reason-coded exclusions.
- Verification: focused job-truth/projection tests passed; integration suite
  verification is recorded with the PR update.
[@codex]
