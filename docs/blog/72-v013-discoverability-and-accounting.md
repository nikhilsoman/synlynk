# v0.13.0 — Discoverability & Accounting

**Date:** 2026-07-22
**Tag:** [v0.13.0](https://github.com/nikhilsoman/synlynk/releases/tag/v0.13.0)
**PRs:** #274–#440 (~60 PRs since v0.12.0)

---

**One sentence:** synlynk learns to explain itself — every command now has a discoverable taxonomy entry with a maturity-tiered reveal, a live selftest exercises all 59 commands end-to-end, cost accounting gets payment-model awareness and a task-boundary fence around actual spend, and dispatch routing gets capability-aware enough to stop sending GitHub-write work to agents that structurally can't do it.

---

## What v0.13.0 Is

v0.12.0 closed the H0 measurement gate — every cost figure synlynk displays is now sourced or labeled. Seven days and roughly sixty PRs later, v0.13.0 answers the next question the platform needed to answer: *does synlynk know what it can do, and does it tell you honestly?* A full command taxonomy now backs FTUE, docs, and trigger phrases from one source of truth; a live selftest actually runs all 59 commands instead of trusting unit-test coverage; cost accounting learns the difference between a subscription seat and a metered API call; and dispatch routing gained a first real capability gate — `can_gh_write` — instead of relying on an SOP a dispatched agent has no way to enforce on itself.

This is a wide release, like v0.12.0 before it. `[Unreleased]` accumulated a full feature cluster without an intermediate cut — this release rolls it all up rather than retroactively splitting seven days of history.

Six interlocking epics shipped, plus two live-issue fixes:

1. **Command Taxonomy, Maturity-Tiered Reveal, and Trigger Registry** (#303) — one registry drives FTUE, docs generation, and trigger phrases.
2. **Task-Boundary Cost Fence** (story-615bc8f4) — shared, allowlist-gated cost display at dispatch-start and job-completion.
3. **Live Command Selftest** (#328) — a taxonomy-driven smoke test exercising all 59 commands against a real scratch workspace.
4. **Capability Sweep + Industry Taxonomy** (#367) — NAICS/APQC/SFIA-coded calibration scoring for agent capability.
5. **Payment-Model-Aware Cost Accounting** (#374) — real dollars vs. pay-as-you-go-equivalent estimates, per agent.
6. **`can_gh_write` Capability Routing** (#423/#426/#438) — structural enforcement of who can complete GitHub-write dispatch work.
7. **Two live-issue fixes** (#421) — `synlynk watch`'s `CYCLES.index("work")` crash and `synlynk viz --serve`'s daemon-thread hang, both root-caused and shipped in this release.

---

## The Milestones

### Command Taxonomy, Maturity-Tiered Reveal, and Trigger Registry (#303)

New `synlynk/taxonomy.py` — `COMMAND_TAXONOMY` classifies all 59 CLI commands/subcommands by `governs_stage`, `maturity_tier` (FTUE / Goal / Execute / Team-Enterprise / latent), `prominence`, `orientation_gateway`, `audience`, `trigger_phrases`, and `hook_event`. This single registry now drives three previously-separate, previously-drifting surfaces: the FTUE wizard and `synlynk launch` task picker (#319), the auto-generated command reference docs (#316), and tier-scoped trigger phrases in the `synlynk:start`/`synlynk:end` session fence (#320). A pre-commit hook installed at `synlynk init` (#321) now gates instructions drift between the taxonomy and the generated CLAUDE.md/GEMINI.md/AGENTS.md content, closing the class of bug where the docs quietly stopped matching the CLI.

### Task-Boundary Cost Fence (story-615bc8f4)

Cost/token data now surfaces at two fixed points — dispatch-start (an estimate) and job-completion (the actual) — in one shared, allowlist-gated format (`synlynk/fencing.py`: `FenceData`, `render_task_fence()`, `is_fenced_command()`), instead of being computed ad hoc at each call site. `dispatch_agent()` attaches an estimate to the job dict so both the direct `dispatch` CLI path and `schedule --execute` print it without duplicated estimation logic, and `exec_command()`'s and `_format_job_summary()`'s cost prints route through the same renderer. `release` is explicitly out of scope.

### Live Command Selftest (#328)

The GTM checklist's item 1 — "deep review of every synlynk command and its testing in a live repo scenario" — got a real answer instead of a manual audit. New `synlynk/selftest.py` runs a taxonomy-driven smoke test against a real scratch git repo, grouped into lifecycle/free/paid scenario tiers (paid scenarios — `dispatch`/`exec`/`schedule` — gated behind explicit opt-in since they spend real tokens). A follow-up fix (#337) closed a real isolation gap: the paid scenarios chdir'd into the scratch workspace but never rebound `synlynk.DB_PATH`, so a live paid run could still write real rows into the host's actual central DB.

### Capability Sweep + Industry Taxonomy (#367)

Static NAICS/APQC/SFIA lookup tables plus a migration crosswalk for legacy free-text `discipline`/`org_domain`/`industry` values (unmatched values tagged `legacy_unmapped`, never silently dropped). `synlynk capability sweep` runs a taxonomy-driven calibration sweep — CLI model discovery, SFIA-scoped calibration tasks, independent cross-agent verification scoring — under a configurable `$10` cost guardrail. A `capability_baseline.json` seeds cold-start capability rows so new agents don't start from zero. `synlynk pr check` also gained a geometric review-cycle multiplier at merge time, rewarding clean first-pass approvals and decaying quality credit across requested-changes rounds.

### Payment-Model-Aware Cost Accounting (#374)

Closes a real accuracy gap the Measurement Ledger epic didn't cover: two agents on different payment models (subscription seat vs. metered API) were being reported at the same blended token rate. `payment_models` config, a `credit_grants` ledger table, and `resolve_payment_value()` now branch correctly across subscription overage billing, oldest-first multi-grant consumption, and plain pay-as-you-go — with `costs.md` splitting rows into api-equivalent and actual-dollars-spent columns, and `check_budgets()`'s Budget Pulse gaining a per-agent payment-model rollup.

### `can_gh_write` Capability Routing (#423/#426/#438)

The root problem: dispatched agents share a single GitHub identity, so `gh pr review --approve` always fails as self-approval, and only Claude/Grok can structurally complete GitHub-write work headless — a fact that lived only in SOP text, unenforced by code. This epic makes it structural: `can_gh_write: bool` on `AGENT_CAPABILITY_BASELINES`, a new `--requires-gh-write` dispatch flag, and enforcement in `dispatch_agent()`. A non-blocking gap remains open: reroute-target selection currently favors `claude` over `grok` due to dict insertion order, despite the SOP's "Grok only" intent — tracked, not yet fixed. The deeper identity half of #423 (distinct per-agent GitHub identities so a real `gh pr review --approve` becomes possible, not just a comment-review workaround) stays out of scope for this release.

### Two live-issue fixes (#421)

Both reported directly during real usage, both fully root-caused before any fix shipped:

- **`synlynk watch` crash** — `ValueError: 'work' is not in list`. The `v0.12.0` tag shipped `cmd_watch()` still looking up a `"work"` cycle name that had already been renamed out of `hud.py`'s `CYCLES` list under the GOVERNS seven-stage vocabulary rollout. The fix (`CYCLES.index("execute")`) had actually merged to `main` via #301 two days after the `v0.12.0` tag — it just never made it into a release until now.
- **`synlynk viz --serve` immediate exit** — reported as a suspected sandbox/daemonization artifact, but reproduced identically outside the sandbox: `_start_server()` spawned the HTTP server on a `daemon=True` thread and returned immediately, so the process (and its daemon thread) died right after printing "Serving at...". New `_serve_until_stopped()` blocks the main thread until `KeyboardInterrupt`, then shuts the server down cleanly. Verified with a new regression test using a fake HTTP server (the sandbox blocks real localhost binds in CI).

---

## Test Count

| Milestone | Tests |
|---|---|
| v0.12.0 (tag) | 1140 passed, 2 skipped |
| **v0.13.0** | **1319 passed, 2 skipped** |

---

## What's Next

Grok's non-blocking observation on `can_gh_write` reroute-target ordering (favoring `claude` over `grok` by dict insertion order) is still open. Issue #423's GitHub-identity half (per-agent PAT/App so a real `gh pr review --approve` is possible) remains unscoped. Adding `watch`/`viz` real-launch coverage to the Live Command Selftest, flagged as a natural companion fix during this release's investigation, hasn't been scoped yet either. The security-hardening cluster (#348–#355) and the job-status/reconciliation cluster (#329–#331, #419, parked #202) remain open and untouched by this release.
