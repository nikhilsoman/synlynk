# Two-Imperatives Roadmap: Execution Autonomy + Workspace Context Accuracy

**Status:** active, self-tracking. This doc is the standing reference for the autonomous work track authorized 2026-08-15. Update its status table as tasks land; do not let it drift out of sync with `TaskList`.

## The two imperatives

1. **Execution autonomy** — workspace agents (Agy/Grok/Codex) take over all implementation/testing/dispatch work; Claude stays PM/review/deploy only.
2. **Workspace context accuracy** — tracked project state (`state.db`, `project-docs/*`, devlogs, memory, roadmap) stays accurate and drift-free, with no silent divergence between what's tracked and reality.

Every item below is ordered by how directly it closes one or both gaps. See the 2026-08-15 recap conversation for the full audit this roadmap is built from (specs without plans, plans pending implementation, open issues categorized against the two imperatives).

## Why this order

The two imperatives share a dependency: `docs/superpowers/specs/2026-08-14-workspace-context-governance-design.md` (Imperative 2) explicitly designed a workspace-level agent artifact store + `agent_id` registry (Round 7, action items 9-10) as the storage layer that `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` Phase 1 (Imperative 1, charter storage) needs. Building Phase 1 before that slice lands risks designing the storage twice. Separately, job-truth/gh-write reliability (#701) is a *recurring* failure (fixed once via the pre-v0.13.1 epics plan, recurred as #935) — stacking more agent autonomy work on an unreliable execution floor compounds the problem, so it's fixed first, not deferred.

## Track status

| # | Item | Imperative | Status | Blocked by |
|---|---|---|---|---|
| 1 | Brainstorm job-truth/gh-write consolidation (#701) → spec | 1 | in_progress (dispatched 2026-08-15) | — |
| 2 | Plan job-truth/gh-write consolidation | 1 | pending | 1 (spec sign-off) |
| 3 | Execute job-truth/gh-write consolidation plan | 1 | pending | 2 |
| 4 | Plan workspace-context-governance next vertical slice (manifest schema, `audit-docs --fix`, migrate synlynk, agent artifact store + `agent_id` registry) | 2 | pending | — (spec already committed, gh#936) |
| 5 | Execute workspace-context-governance vertical slice | 2 | pending | 4 |
| 6 | Ship worktree/job cleanup automation (#559) | 1 | pending | — (can run in parallel once quota allows) |
| 7 | Agent-roles-charters Phase 1 (charter storage) | 1 | pending | 5 (needs the storage design) |
| 8 | Cut v0.14.0 named release | admin | pending | — (opportunistic, not gap-closing) |

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
