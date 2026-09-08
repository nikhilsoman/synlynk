# Two-Imperatives Roadmap: Execution Autonomy + Workspace Context Accuracy

**Status:** active, self-tracking. This doc is the standing reference for the autonomous work track authorized 2026-08-15. Update its status table as tasks land; do not let it drift out of sync with `TaskList`.

## The two imperatives

1. **Execution autonomy** — workspace agents (dev/qa/designer/marketing) execute implementation and verification tasks through autonomous harnesses (Codex/Grok/Agy); Claude stays PM/review/deploy only.
2. **Workspace context accuracy** — tracked project state (`state.db`, `project-docs/*`, devlogs, memory, roadmap) stays accurate and drift-free, with no silent divergence between what's tracked and reality.

## Priority reconciliation: move quickly without losing trust

Stakeholders are asking for two outcomes that can pull in opposite directions: ship more autonomous execution quickly, while keeping workspace state accurate enough for people to trust the system's decisions. The roadmap resolves this as a sequencing decision rather than a choice between outcomes. Reliability is the release gate; autonomy is the product direction.

- **Near term:** prioritize the smallest reliability slice that protects truth in the pipe (job status, attribution, context, and cleanup). Defer autonomous breadth that would make state harder to inspect or recover.
- **In parallel:** run autonomy as a bounded pilot behind explicit scope, quota, and verification gates. Pilot work can expand only when it produces auditable diffs, accurate completion signals, and repeatable rollback or handoff behavior.
- **Decision rule:** when speed and trust conflict, choose the option that preserves a reversible path and measurable evidence. Revisit the trade-off at each release using delivery throughput, stale-state rate, verification success, and operator intervention as shared metrics.

This keeps the execution-autonomy stakeholder moving toward visible capability while giving the context-accuracy stakeholder a veto over unsafe expansion. Success is not maximum automation; it is automation that earns a wider operating envelope by remaining observable and correct.

### Completed feature status: dispatch reliability under advanced workloads (2026-09-08)

- **Scenario:** An advanced multi-harness dispatch runs a design or review job that exits while its worktree still exists; reconciliation now checks exit evidence and wait status before treating the job as a zombie, preserving truthful completion state.
- **Priority reconciliation:** The autonomy priority is protected by continuing to reap genuinely abandoned workers, while the context-accuracy priority is protected by central logs, preserved worktree logs, per-job exception isolation, and absolute GitHub App key paths.
- **Outcome:** The roadmap can expand autonomous dispatch with a bounded, auditable recovery contract: completed work remains inspectable, failed jobs remain diagnosable, and only confirmed dead workers are cleaned up.

### Positioning boundary

Here, **execution autonomy** describes the operating outcome, not a new product category. The positioning is consistent at two levels: Synlynk is the OS/control plane for multi-agent development, and its concrete product wedge is measurement and arbitration across heterogeneous coding harnesses. Synlynk coordinates, routes, measures, and verifies external work; it does not become a harness, workflow engine, or agent vendor. Reliable context and job evidence are the mechanism that makes greater autonomy safe.

Use the short message when a single sentence is needed: **Synlynk is the control plane for multi-agent development, using measured cross-harness routing to make autonomous execution trustworthy.** “OS for multi-agent development” names the category and long-term ambition; “measurement and arbitration layer” names the differentiated capability inside that category. They are not competing claims.

Every item below is ordered by how directly it closes one or both gaps. See the 2026-08-15 recap conversation for the full audit this roadmap is built from (specs without plans, plans pending implementation, open issues categorized against the two imperatives).

## Why this order

The two imperatives share a dependency: `docs/superpowers/specs/2026-08-14-workspace-context-governance-design.md` (Imperative 2) explicitly designed a workspace-level agent artifact store + `agent_id` registry (Round 7, action items 9-10) as the storage layer that `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` Phase 1 (Imperative 1, charter storage) needs. Building Phase 1 before that slice lands risks designing the storage twice. Separately, job-truth/gh-write reliability (#701) is a *recurring* failure (fixed once via the pre-v0.13.1 epics plan, recurred as #935) — stacking more agent autonomy work on an unreliable execution floor compounds the problem, so it's fixed first, not deferred.

## Track status

| # | Item | Imperative | Status | Blocked by |
|---|---|---|---|---|
| 1 | Brainstorm job-truth/gh-write consolidation (#701) → spec | 1 | done | — |
| 2 | Plan job-truth/gh-write consolidation | 1 | done | — |
| 3 | Execute job-truth/gh-write consolidation plan | 1 | done | — |
| 4 | Plan workspace-context-governance next vertical slice (manifest schema, `audit-docs --fix`, migrate synlynk, agent artifact store + `agent_id` registry) | 2 | done | — |
| 5 | Execute workspace-context-governance vertical slice | 2 | done | — |
| 6 | Ship worktree/job cleanup automation (#559) | 1 | done | — |
| 6a | *(emergent, not in original scope)* Rename `synlynk agent` CLI verb → `harness` (spec + plan + PR #993, 2026-08-15) — required to free the `agent` verb group for item 7 | 1 | done | — |
| 7 | Agent-roles-charters Phase 1 (charter storage + CLI onboarding + dispatch integration, PR #1003; retroactive blog post PR #1006) | 1 | done | — |
| 8 | Cut named release(s) for the completed clusters above | admin | done | — |

**Release cadence decision (2026-08-16):** rather than accumulating everything into one big `v0.14.0`, cut a `vX.Y.0` named release as soon as a themed cluster of 3+ related PRs is complete, per the existing global Named Release Policy's own trigger condition — no policy override needed. Item 8 is that next cut, scoped to the job-truth/gh-write reliability + workspace-context-governance + agent-roles-charters-Phase-1 cluster (items 1-7 above). Future clusters get their own `vX.Y.0` rather than waiting to bundle further.

**Shipped 2026-08-16:** [v0.14.0 — Truth in the Pipe, Identity for the Agents](https://github.com/nikhilsoman/synlynk/releases/tag/v0.14.0) (PR #1012). Bundled items 1-7 above plus the previously-undocumented TPM/session MVP (PRs #934/#944/#950/#954/#959), discovered during CHANGELOG authoring to have merged in the same window with no release of its own.

## Pause points (per standing authorization, 2026-08-15)

- **Brainstorming that needs Nikhil's presence.** Default mode: run decide-panel-driven brainstorms (mirroring the governance spec's 7-round `synlynk decide --panel codex,grok --record` method) autonomously via `synlynk dispatch claude --task-type brainstorm`, then present the finished spec for sign-off — that sign-off is a hard gate (Brainstorm-First Policy) and always happens, but it is a presentation, not a mid-brainstorm check-in. If a brainstorm surfaces a genuine strategic fork only Nikhil can resolve, stop and ask before the panel proceeds.
- **Ready to ship each major release.** Named releases (item 8, and any future `vX.Y.0` cut this roadmap produces) always pause for Nikhil.
- **Harness quota.** Before each dispatch, check `synlynk status` for budget/quota headroom; if a harness is exhausted, either queue (the quota-aware reservation system already defers rather than fails) or fall back per `feedback_grok_auth_agy_fallback.md` / `feedback_prefer_codex_grok_over_agy.md` memory (prefer Codex/Grok over Agy).

## Definition of done for this roadmap

Both imperatives are "met" (for this pass — neither is ever fully finished) when:
- Job-truth/gh-write reliability cluster (#701 and its named sub-issues) is closed with no recurrence for one full release cycle.
- Workspace-context-governance's 11 action items are either shipped or explicitly deferred with a reason, and issue #936 is closed.
- Agent-roles-charters is at minimum through Phase 1 with a real (not speculative) storage design.
- `synlynk worktree audit` / `synlynk jobs --all` show no chronic stale-state accumulation between releases.
