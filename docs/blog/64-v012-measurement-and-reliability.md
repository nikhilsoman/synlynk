# v0.12.0 — Measurement & Reliability

**Date:** 2026-07-15
**Tag:** [v0.12.0](https://github.com/nikhilsoman/synlynk/releases/tag/v0.12.0)
**PRs:** #122–#267 (71 PRs since v0.11.0)

---

**One sentence:** the operational backbone gets provably reliable and provably accounted for — dispatched jobs finish their own git steps, a 5th zero-cost local agent joins the fleet, story routing gets real capability+quota+cost scoring with a fleet batch scheduler, and every dollar synlynk reports is now either structurally sourced or visibly flagged as an estimate.

---

## What v0.12.0 Is

v0.11.0 made the agent fleet observable and permissioned. Ten days and 71 PRs later, v0.12.0 makes it *trustworthy*: dispatched work reliably lands in git without babysitting, story routing is a real scoring engine instead of a first-match heuristic, a zero-cost on-device agent joins the roster, and — closing out the arc that prompted this release — every cost figure synlynk shows you is either measured or clearly labeled as a guess.

This is a wider release than most. Several independently-shippable epics accumulated in `[Unreleased]` between v0.11.0 and today without an intermediate cut; rather than retroactively split ten days of history into several small releases, this one rolls them up together.

Five interlocking epics shipped:

1. **Job Lifecycle Ground-Truth Verification** (#126–#129) — dispatch worktree isolation, git-state-verified reconciliation, real `files_touched`, fail-loud migration.
2. **Dispatch git-finalization reliability chain** (#182–#199) — synlynk finishes agents' git steps for them, because they don't reliably do it themselves.
3. **Capability Matrix Hardening + Fleet Scheduler** (epic #137) — 3-stage routing (capability → quota gate → cost tie-break) and a batch scheduler that clears backlogs unattended.
4. **Local Agent** — a 5th dispatch agent running Aider over on-device oMLX inference, $0 per token.
5. **Measurement Ledger Hardening** (epic #210) — the H0 gate from Fable's strategic review: every number is structurally sourced or visibly flagged.

---

## The Milestones

### Job Lifecycle Ground-Truth Verification (#126–#129)

Four sequenced fixes closing the gap between "a dispatched job says it's done" and "a dispatched job's work is verifiably real": per-job git worktree isolation so concurrent dispatches can't collide, git-state cross-checking when a job's exit sentinel is missing (`failed_unverified` instead of a blind hard failure), real `files_touched` via `git diff`, and `cmd_migrate()` failing loud instead of printing a green banner over a 0-row import.

### Dispatch git-finalization reliability chain (#182–#199)

The core finding, confirmed repeatedly across one long session: dispatched agents (Codex, Agy) frequently do real, correct, fully-tested work but don't reliably finish the meta-step — commit, push, open PR — even with explicit instructions. synlynk now does it for them: `_finalize_completed_worktree_job()` fires once on a job's `running`→terminal transition, idempotent by construction, staging everything except a hard-exclusion list, committing, pushing, and opening a PR via `gh pr create` if none exists. Wrapped in try/except everywhere so a git/gh hiccup never crashes reconciliation. Sibling fixes: borrowed-worktree completions no longer misattributed as zero-work, `HARNESS_INTERNAL_TIMEOUT` jobs auto-retry, and a job that raced its own disk writes gets one re-inspection instead of staying stuck in a stale `failed` forever.

### Capability Matrix Hardening + Fleet Scheduler (epic #137)

`_best_agent_for_story()` went from a simple match to a real 3-stage engine: a weighted capability score (VERIFIER tier, PR review cycles, CI-verification signals), a hard quota-headroom gate across five time windows with a degraded-mode fallback, and a cost tie-break when top scores land within 0.15 of each other. On top of that, `synlynk/scheduler.py` adds fleet-level batch scheduling — `synlynk schedule [--execute] [--max-stories N]` — with in-batch headroom accounting so story 5 in a batch of 10 sees stories 1–4's projected spend before it's assigned, and capped retry/reassignment so one flaky story doesn't eat a whole run.

### Local Agent — the 5th dispatch agent

`local` joins claude/codex/agy/grok, dispatching as an `aider` CLI subprocess against an on-device oMLX OpenAI-compatible endpoint. Zero per-token cost, hardware-gated (an opt-in pytest tier exercises the real integration when hardware is present, cleanly skips otherwise), starting from a conservative capability whitelist that self-widens with verified results. The architecture pivoted mid-design — the original single-shot chat-completion runner couldn't edit files, so it moved to a real CLI-over-local-endpoint shape before implementation began.

### Measurement Ledger Hardening (epic #210)

The reason this release got cut in the first place. Fable's 2026-07-12 strategic review named the H0 gate explicitly: *"every number synlynk displays is either structurally sourced or visibly labeled as an estimate."* Three phases closed it:

- **Phase 1** — `cost_entries` gained real provenance columns (`cost_source`, `estimate_basis`), a single sanctioned writer (`_insert_cost_row()`, enforced by a call-site audit test), a rate file (`.synlynk/model_rates.json`) replacing hardcoded pricing, and a 3-tier t-shirt-size fallback for surfaces with no real token count.
- **Phase 2** — four structured-output token adapters, one per vendor CLI (Codex, Claude, Agy, Grok), each replacing the old 80/20 heuristic split with a real per-field extraction from that CLI's structured output.
- **Display layer** — Vizor's Effort & Cost tab visually flags estimated-vs-measured rows, and `synlynk status` gained a `RATES` line showing when the rate table was last updated (with an explicit `⚠ never updated` warning when it's missing).

Every PR in this arc followed the same discipline: dispatched to a rotating real CLI agent, independently verified via `git diff` against the plan (never trusting the agent's self-report), full-suite regression re-run, cherry-picked, blogged.

### Also in this release

**Vizor Architect Map v2** replaced a static hand-authored tube-map SVG with a live force-directed graph of workspace repos and typed cross-repo edges, plus an IDE-style file-tree drawer. **Vizor Business Goals Panel** surfaces goal/story rollups in the HUD. A second `__init__.py` re-modularization pass extracted 11 focused modules, finishing the transition away from a single-file monolith.

---

## Test Count

| Milestone | Tests |
|---|---|
| v0.11.0 (tag) | 868 |
| **v0.12.0** | **1140 passed, 2 skipped** |

---

## What's Next

Deferred follow-ups from the Measurement Ledger arc, filed as issues and explicitly scoped out of this release: #260 (Savings Ledger), #261 (dispatch-path unification), #262 (surface consolidation), #263 (stage constants staleness). #202 (`synlynk jobs` stale status display) remains open and tracked separately — not blocking, but unresolved.

The 30-day observation window on `synlynk schedule` (v1) runs through 2026-08-10 before Fleet Scheduler v2 gets scoped into stories. The bigger open question is what comes after the H0 measurement gate on Fable's roadmap — decide the next horizon's priority before scoping the next named release.
