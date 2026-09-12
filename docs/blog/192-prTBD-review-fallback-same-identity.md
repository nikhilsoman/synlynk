---
title: "Review Fallback is Conditional on Same-Identity Collisions"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 192
pr: "TBD"
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
## The Broader Goal at the End of the Previous PR

The #1436 identity-routing arc separated autonomous GitHub operations across distinct role GitHub Apps (`qa`, `dev`, `pm`, etc.), ensuring autonomous writes no longer leak into the human operator's personal GitHub identity. Live verification proved that `synlynk-synlynk-qa[bot]` successfully submits approving reviews (`gh pr review --approve`) and squash-merges PRs authored by both human and sibling role bots (#1455).

However, historical configurations encoded a blanket `#423` fallback (`review_fallback: comment_checklist`), originally introduced when all dispatches shared the repository owner's GitHub identity and self-approval failed. With distinct App identities in place, qa App approvals are the default when reviewer and author identities differ; comment-checklist fallback is needed only on same-login collisions.

## Strategic Shifts in This PR

None. Reconciles policy and instructions with the target end-state defined in §5, §6.4, and §7 of `docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md`.

## What This PR Shipped

1. **Policy Configuration:**
   - Updated `.synlynk/policy.json` and default workspace policy in `synlynk/policy.py` to set `review_fallback: "same_identity_comment_checklist"`.
   - Updated policy test fixtures in `tests/test_policy.py` to reflect the new default value and added assertions validating it.

2. **Living Instructions and SOPs:**
   - Updated `_PR_REVIEW_SOP` and `_repair_pr_review_sop` in `synlynk/probe.py` so the `#423` identity note explicitly documents that `qa APPROVE` (`gh pr review --approve`) is the default whenever reviewer identity differs from PR author login, reserving comment-checklist fallback strictly for same-identity collisions. Sessions are instructed never to skip `--approve` by default.
   - Synchronized living agent directives (`GEMINI.md`, `GROK.md`, `AGENTS.md`) with the updated PR review discipline SOP.

3. **UX Core Helper:**
   - Updated `synlynk/uxcore.py`'s `approve_pr` docstring and comment-checklist message to reflect that `--approve` is the default and formal comment review is triggered only upon same-login collision.

4. **Design Spec Alignment:**
   - Marked §5's `#423` sentence and §7's Policy follow-up item in `docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md` as addressed in this PR (#1436 leftover).

## Brainstorm Visuals Used

None. Spec: `docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md`.

## What This Achieved on the Path to Autonomy

Formal approvals are now the unambiguous default across both policy configuration and agent directives when reviewing across distinct personas. The `#423` comment fallback is properly scoped to true identity collisions (same author and reviewer logins), ensuring GitHub pull request review gates receive real approvals from authorized verification agents.

## Strategic Note: The Goal at the End of This PR

With the `review_fallback` policy, living SOPs, and spec tracking reconciled, #1436 leftover tasks are resolved without modifying `jobs.py`, dispatch environments, or sibling execution paths.