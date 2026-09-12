---
title: "Charter Patch: Architect Does Not Hold Merge Authority"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 186
pr: "TBD"
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
## The Broader Goal at the End of the Previous PR

Earlier PRs in the #1436 arc audited workspace agent identity routing, enforced role App tokens on parent auto-PRs, and eliminated fallback to host GitHub credentials for unattended tasks. Live verification already proved that `synlynk-synlynk-qa[bot]` successfully approves and squash-merges PRs under `.synlynk/policy.json` (`can_merge: ["qa"]`). However, living documentation—specifically the agent roles and charters design spec, the glossary, and the road to autonomous operations roadmap—still contained legacy prose claiming that the architect role holds merge authority.

## Strategic Shifts in This PR (if any)

None. Policy truth has been `merge_authority.can_merge: ["qa"]` since v0.18.0. This PR executes the charter patch identified in §5–§7 of the workspace agent identity routing design spec (`docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md`) to reconcile living documentation with runtime policy truth, ensuring architect only owns spec/plan review while merge authority is explicitly qa-only.

## What This PR Shipped

Living document reconciliation across four canonical references:
1. `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md`: Updated the architect charter row, dispatch target table, and end-to-end workflow table so architect owns spec and plan review without claiming merge authority, and explicitly noted that merge authority is qa only (`can_merge: ["qa"]`).
2. `docs/glossary-agent-vs-harness.md`: Updated the architect row to clarify that PR code review sits with architect while merge authority is qa only.
3. `docs/strategy/road-to-autonomous-ops.md`: Aligned the Operating Ownership section so architect owns technical design, spec/plan approval, and review, while qa holds merge authority alongside CI/CD and verification.
4. `docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md`: Marked the charter patch in §5 and §7 as addressed in this PR.

Historical plans recording point-in-time design evolution were preserved untouched.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

Eliminates policy-to-charter contradictions across agent instruction surfaces. When agents read their roles, charters, and glossary definitions, they encounter an unambiguous division of labor: architect provides technical judgment, design spec approval, and code review, while unattended PR merge execution is governed strictly by qa under policy gates.

## Strategic Note: The Goal at the End of This PR

With the charter patch complete and parent auto-PR token injection hardened, remaining items in the #1436 arc include completing live verification of a role-bot-authored PR approved by qa bot and optional qa `actions: write` permission for test rerun workflows.