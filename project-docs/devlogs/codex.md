# Codex Devlog

## 2026-09-02 - Subscription Cost Amortization and True-Up (#787)

- Added `harness_billing` configuration with subscription, metered overage,
  and zero-cost modes while retaining legacy payment-model compatibility.
- Implemented prior-month subscription amortization, capped extra usage, and
  `synlynk cost true-up` reconciliation rows.
- Added focused cost tests and blog post 161.
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
