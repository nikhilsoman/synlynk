---
title: "Durable PM/TPM charters get a real wake cycle and CLI surface"
date: 2026-10-13
series: "Building the OS for Multi-Agent Development"
post: 279
pr: "#TBD"
status: open
author: "synlynk team"
version: "0.25.0"
tags: [posts]
type: pr
---

## The Broader Goal at the End of the Previous PR

The `pm` and `tpm` roles existed as charter files but had no durable wake-cycle identity — `load_charter()`'s missing-file fallback hardcoded `harness_bindings` for `tpm`/`architect` to `["claude", "codex"]`, and neither role had an `agent run` path, a cron-installable entry, or CLI subcommands of their own. The intake→triage→approval loop (raw GitHub issues → TPM triage → PM approval of the drafted queue) existed conceptually but had no code path a scheduler could actually invoke.

## Strategic Shifts in This PR (if any)

None — this PR is the direct, planned continuation of `docs/superpowers/plans/2026-10-13-finalize-workspace-agent-charters.md` (story-0ad6c02b, GOVERNS goal-a222b393/goal-06758149). The one adjustment made mid-plan: after two consecutive dispatched jobs (Tasks 7 and 8) silently no-op'd while reporting plausible success and cost, the remaining fully-deterministic, zero-judgment tasks were implemented directly rather than risking a third wasted dispatch cycle — documented in each commit and filed as gh:#2245.

## What This PR Shipped

Eleven tasks, executed via Subagent-Driven Development (implementers dispatched to Codex/Claude per the project's role split, reviewer/verification stages retained):

- **Charters (Tasks 1-4):** `synlynk/charters.py` gained `durability`/`wake_cycle_sop` fields and now tolerates missing `harness_bindings`. `.synlynk/charters/pm.json` and `.synlynk/charters/tpm.json` were written as durable charters with 7-step `wake_cycle_sop` specs — autonomous authorities (`triage_issue`/`draft_plan`/`dispatch_track` for TPM) and explicit escalation triggers (`technical_ambiguity`/`priority_ambiguity`/`dispatch_blocked_twice`). `maintainer.json` was promoted to the same durability tier.
- **Wake-cycle logic (Tasks 5-6):** `synlynk/tpm_sweep.py::run_tpm_wake_cycle()` and `synlynk/pm_agent.py::cmd_pm_wake()` implement the actual intake/triage/approval loop against `backlog_items`, with new PM-approval-gate columns and `synlynk/db_schema.py` migration support.
- **Agent configs and routing (Tasks 7-8):** `.agents/pm.json` / `.agents/tpm.json` let `_load_agent_config()` resolve the two roles; `synlynk/support_engineer.py::cmd_agent_run()` now special-cases `name == "pm"`/`"tpm"` to call the wake-cycle functions directly, ahead of the generic signal-collector path.
- **CLI surface (Task 9):** `synlynk pm wake` and `synlynk tpm wake` subcommands, wired into both the argparse subparser registration and the dispatch `elif` chain in `synlynk/cli.py`. Fixing this surfaced a real regression — `COMMAND_TAXONOMY` had no entries for either new leaf command — closed by adding two entries in `synlynk/taxonomy.py` alongside the existing `pm sweep`/`tpm sweep` rows.
- **Verification-only (Tasks 10-11):** confirmed `_install_cron_entry()` is name-agnostic and needs no pm/tpm-specific branching (it already generically shells out to `agent run {name}`, which now hits the new wake-cycle branch); ran the full test suite (4109 passed, 52 failed/18 errors — all independently confirmed pre-existing sparse-checkout/environment artifacts, none caused by this branch) and confirmed `.synlynk/policy.json` and the `qa`/`designer`/`marketing` agent configs (which don't exist) are untouched vs `origin/main`.

A new ticket, gh:#2245, documents a suspected dispatch/logs diff-reporting bug: two dispatched jobs reported real cost and a plausible "files touched" list while making zero actual changes, and both reported lists were byte-for-byte identical to each other despite very different task text — pointing at a stale diff-base in the reporting path rather than a harness failure.

## Brainstorm Visuals Used

None — this PR executes an already-approved implementation plan; no new design exploration was needed.

## What This Achieved on the Path to Autonomy

The PM/TPM roles are no longer charter-only placeholders. A scheduler (cron, or a future daemon wake trigger) can now invoke `synlynk agent run pm` / `synlynk agent run tpm` — or a human/agent can call `synlynk pm wake` / `synlynk tpm wake` directly — and get the actual triage/approval loop, not a signal-collector pass that doesn't know what "pm" or "tpm" durability means.

## Strategic Note: The Goal at the End of This PR

The wake-cycle code paths exist and are tested, but have not yet run against a live GitHub issue backlog outside of unit-test fixtures — that's the natural next step once this PR is reviewed and merged. gh:#2245 (dispatch diff-reporting bug) is filed but not yet investigated; it's worth resolving before relying on dispatch "files touched" output for no-op detection in future plan executions.

## Related Docs

- `docs/superpowers/plans/2026-10-13-finalize-workspace-agent-charters.md`
- GOVERNS story-0ad6c02b, goal-a222b393, goal-06758149
- gh:#2245
