# Harness Capability Drift & Regression Classification — Design

**Status:** Approved (brainstorm session 2026-07-31)

**Source:** Recurring Agy (command-permission) and Codex (sandbox) flakiness during the Harness Compatibility & Capability rollout (`docs/superpowers/specs/2026-07-29-harness-compatibility-capability-design.md`), plus the #616/#617 incident — a synlynk-side regression (host-side PR-auto-create fallback ignoring `job['base_branch']`) that shipped undetected because nothing exercised that code path.

## Problem

Two related gaps exist in how synlynk keeps its harness integrations trustworthy:

1. **Staleness.** Harness capability data (`AGENT_CAPABILITY_BASELINES`, `docs/reference/harness-capability-matrix.md`, probe results) only refreshes reactively — at dispatch time, when the cached probe result is older than 1 hour (`_reprobe_harness_sync` in `synlynk/dispatch.py`). There is no periodic, install-wide mechanism keeping this data fresh, and `_probe_results_trustworthy()` is currently hardcoded to `return False` (tracked separately as #578/#580 — not in scope here).
2. **No classification.** When a harness-facing failure occurs, there's no systematic way to tell "synlynk broke this" (a regression in synlynk's own code, like #617) from "the harness changed underneath us" (a CLI version bump, a sandbox policy change, an instruction-file drift). Today this is pure human triage.

There's a third, adjacent gap: `synlynk selftest --live` already exists as a taxonomy-driven live smoke test, but its scenarios never exercised the exact code path #617 broke (worktree-job PR finalization), hardcode a single harness per paid scenario instead of looping over all configured harnesses, and heavily mock the internals most likely to drift. It shipped complete against its own original scope, but that scope predates this concern.

## Goal

- Keep harness capability data fresh via a lightweight, local, install-wide trigger — without depending on the (separately-specced) daemon's periodic-tick mechanism, which remains a placeholder dependency for now.
- Give every probe/smoke-test failure an automatic first-pass classification: **regression** (synlynk's own code changed on the failing path) vs. **drift** (only the harness side changed).
- Extend `selftest.py` so its live scenarios actually catch #617-class bugs: multi-harness coverage, GitHub write-action coverage (the flakiness that triggered this whole initiative), and reduced reliance on mocks that hide real regressions.
- Stay strictly local — no service dependency. (See "Explicitly deferred" below for why.)

## Non-goals / explicitly deferred

- **Daemon periodic-tick mechanism.** This spec's triggers are self-contained (piggybacked on CLI invocation). A future daemon spec may later subsume them into a proactive background tick; that's an implementation detail swap, not a dependency of this spec.
- **`project-docs/` DR-backup mechanics.** Separate spec (Daemon Consolidation & DR Backup).
- **Fixing `_probe_results_trustworthy()`'s hardcoded `False`.** Known, pre-existing landmine (#578/#580). Real, but orthogonal to this spec's detection/classification scope.
- **New enforcement logic for "route around unsupported combos."** The existing preflight system (`_dispatch_capability_preflight`, `AGENT_CAPABILITY_BASELINES`) already blocks/routes at dispatch time. This spec's job is to keep the data that system consumes fresh and classified — not to build a second enforcement layer.
- **Centralizing this as a synlynk-run service.** Considered explicitly (see Discussion below) and rejected for this spec: this codebase is single-file-CLI, zero-dependency, local-first by design (CLAUDE.md; the state-engine tiered design scopes any server infra to Tier 3/Enterprise as a "goal-depth sketch, not designed against yet"). A hosted service that runs regression classification or smoke tests on a user's behalf would require holding their GitHub credentials (a trust boundary this project has never crossed) or testing something too generic to catch the bugs this spec exists for. The one piece with a real efficiency argument — a shared, read-only capability-matrix data feed — is logged as a v2 signal instead (see `docs/reference/capability-framework-generalization-notes.md`), decoupled from this spec's local-only mechanism.

## Architecture

### 1. Free staleness trigger (capability re-probe)

- New `capability_watch` table in `state.db`: `last_probe_at`.
- Hooked into the CLI's main entrypoint (`synlynk/cli.py`): on every invocation, check staleness against a configurable threshold (default: 24h). If stale, kick off the existing free TC1-TC5 probe (`synlynk/probe.py`) in a background thread — never blocks the invoking command.
- Zero cost: TC1-TC5 are structural checks (CLI presence, version, flag support), not LLM calls.

### 2. Opt-in paid smoke-test trigger

- Same staleness pattern against `last_smoke_test_at`, default threshold 7 days.
- Only fires automatically if `auto_smoke_test: true` is set in `.synlynk/config.json`. Default is `false`.
- When due but not opted in, `synlynk status` surfaces "smoke test overdue — run `synlynk selftest --live` or enable `auto_smoke_test`" rather than spending silently.
- When it does run, it invokes the extended `selftest --live` (below), respecting its existing $2 budget cap.

### 3. Extended `selftest.py` (three phases)

**Phase 1 — Execution-mode + harness matrix scaffolding.**
`ScenarioContext` gains a `mode: Literal["home", "headless"]` field and a `harness` field. `_dispatch_scenario` and `_exec_scenario` (currently hardcoded to `"codex"` and `"claude"` respectively) loop over all harnesses configured in the repo instead of a single one. `_dispatch_scenario` is extended to wait for worktree-job finalization and assert the resulting PR's base branch matches `job['base_branch']` — this is the specific check that would have caught #617. This phase is a prerequisite for Phase 2 (GH-write scenarios need both mode axes to test the actual flaky condition, not just presence).

**Phase 2 — GitHub write-action scenarios.**
New scenarios that actually attempt `gh pr review`, `gh pr merge`, and `gh issue comment` for each (harness × mode) cell, using Phase 1's scaffolding. Results populate a new `gh_write_capability` table (columns: `harness`, `mode`, `action`, `status`, `checked_at`), cross-referenced against `harness-capability-matrix.md`'s existing per-harness GitHub-write notes (the Agy headless-permission-allowlist caveat, Codex's sandboxed network block). This is the first automated check against those documented caveats — previously operator-asserted prose only.

**Phase 3 — Mocking-depth reduction pass.**
Audit existing scenarios (`init`, `join`, `decide`, `scan`, etc.) for mocks hiding the highest-risk internals (`_run_agent_sync`, `_static_scan`, `discover_agents`). Where the cost/safety tradeoff allows, replace with real invocation, using Phase 1's live-mode budget accounting to keep spend bounded. Lower priority than Phases 1-2; ships in the same spec but can slip a release if needed.

### 4. Regression-vs-drift classifier

Triggered on any probe or smoke-test failure (from either the automatic triggers above or a manual `selftest --live` run):

1. Identify the failing code path (the function/module the failure traces to — e.g. `_maybe_open_worktree_pr`).
2. `git log` that path since the last known-green run (tracked via `capability_watch.last_green_probe_at` / `last_green_smoke_at`).
3. Compare against the harness-side fingerprint already tracked by the capability system (CLI version string, instruction-file section hash).
4. Classification:
   - Synlynk-side commits touched the failing path since last green → **regression**. Logged with the specific commit range implicated, surfaced prominently (this is the "our own bug" signal).
   - Only the harness fingerprint changed → **drift**. `harness-capability-matrix.md` and `AGENT_CAPABILITY_BASELINES` get flagged stale for that harness; existing preflight enforcement naturally routes around it once the matrix is updated.
   - Neither changed (e.g. transient network failure) → **unclassified**, retried once before logging.
5. All classifications land in a new `capability_incidents` table: `id`, `harness`, `failing_path`, `classification`, `evidence` (commit range or fingerprint diff), `detected_at`. This becomes the audit trail this initiative was missing.

### 5. v2 generalization stub doc

New file: `docs/reference/capability-framework-generalization-notes.md`. Not a spec — a running list of directional signals for applying this probe/classify/matrix pattern elsewhere. Seeded at creation with:
- Community capability feed: a read-only, opt-in, hosted snapshot of `AGENT_CAPABILITY_BASELINES`-equivalent data that installs could optionally pull to pre-seed/cross-check local probes, reducing redundant re-probing of the same harness CLI versions across users. Explicitly not part of this spec (see Non-goals) — logged here as a future, decoupled initiative.
- Email/notification signup and GitHub-star-based engagement — raised during this brainstorm as a possible layer on top of a future community feed. Explicitly a product/growth concern, not a technical extension of this framework; noted here only so it isn't lost, not endorsed as in-scope for any near-term spec.
- Open question: could the same probe/classify/matrix pattern apply to MCP server compatibility or IDE integration compatibility as synlynk grows beyond CLI harnesses?

## Data flow

```
CLI invocation
   → staleness check (capability_watch)
       → [stale, free tier]  → probe.py TC1-TC5 → update AGENT_CAPABILITY_BASELINES / matrix
       → [stale, paid tier, opted in] → selftest --live (Phases 1-3) → ScenarioResults
   → any failure in either path
       → classifier (git-blame vs fingerprint diff)
       → capability_incidents row written
       → regression → surfaced as "our bug" (existing issue-filing flow)
       → drift → matrix updated → existing preflight/remediation reacts on next dispatch
```

## Error handling

- Background probe/smoke-test threads never block or fail the user's actual command; failures are logged to `capability_incidents` and surfaced via `synlynk status`, not raised inline.
- Classifier failures to determine a clean signal (e.g. ambiguous git history, missing fingerprint data) fall back to `unclassified` rather than guessing — matches this project's existing "never overclaim confidence" pattern from the harness-capability-matrix's own maintenance section.
- Opt-in paid smoke test respects the existing $2 budget cap; a cap-reached scenario is marked `skipped`, not `fail`, consistent with current `selftest.py` behavior.

## Testing

- `tests/test_selftest.py` extended for Phase 1-3 scenario changes, following the existing mocked-orchestration pattern (tier ordering, fallback behavior, budget-cap skip logic already covered; new coverage for multi-harness looping and mode-axis behavior).
- New `tests/test_capability_classifier.py`: unit tests for the git-blame-vs-fingerprint classification logic with synthetic git histories (regression case, drift case, ambiguous/unclassified case).
- Staleness trigger and background-thread behavior tested via mocked `state.db` timestamps — no real time-based waits in CI.
- The `--live` smoke-test path itself remains a manual, spend-incurring action not run in CI, consistent with the original `selftest` design.

## Discussion: why not a synlynk-run service

Raised directly during this brainstorm: should this become a service synlynk itself runs, enabling a more aggressive central probing schedule, email notifications, eventual MCP/server infra, and a team/enterprise tie-in?

Decision: no, not for this spec. Three distinct things were bundled in that proposal, evaluated separately:

- **Capability matrix data centralization** — genuinely has a case (the same harness-CLI-version fact is true for every user, so N independent re-probes is wasteful). Logged as a v2 signal, not built here.
- **Regression classification / smoke tests as a hosted service** — rejected. This would require synlynk to hold user GitHub credentials to exercise `gh pr review`/`merge` on their behalf, or test something too generic to catch repo-specific regressions like #617. Neither serves this spec's actual goal.
- **Email signup / GitHub-star engagement** — not a technical concern; a product/growth decision orthogonal to drift detection, noted in the v2 stub doc so it isn't lost, not pursued here.

This keeps the spec aligned with the project's existing local-first, zero-dependency, no-server constraint (CLAUDE.md; state-engine tiered design), which explicitly scopes any server infra to a not-yet-designed Tier 3/Enterprise.
