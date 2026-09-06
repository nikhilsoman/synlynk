---
title: "PR #TBD - #1436: Operator Runbook for qa App Actions Write Re-approval"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 193
pr: "TBD"
---

## The Broader Goal at the End of the Previous PR

PR #1458 updated the GitHub App manifest builder (`synlynk/team.py`) so new installations for merge-authority roles (`qa`) request `actions: write` alongside `administration: write`. However, GitHub's permission security boundary prevents newly requested permissions from being applied automatically to an already-installed GitHub App (`synlynk-synlynk-qa`).

## Strategic Shifts in This PR

None. The architectural boundary remains strictly intact: autonomous agents cannot self-escalate privileges. Adding `actions: write` for workflow rerun recovery requires the human installer (Nikhil) to re-approve the elevated permissions in the GitHub UI.

## What This PR Shipped

A dedicated operational runbook and spec cross-reference:
- `docs/qa/1436-qa-actions-write-reapproval.md`: A concise operator runbook detailing:
  - Why `gh run rerun --failed` failed with `Resource not accessible by integration` under `actions: read`.
  - The exact UI navigation steps for Nikhil (GitHub → Settings → GitHub Apps → synlynk-synlynk-qa → Permissions & events → Repository permissions → Actions → Read and write → Save → accept installation confirmation prompt).
  - How to verify the updated permission (`synlynk gh --role qa -- api repos/nikhilsoman/synlynk/actions/runs --jq '.[0].id'` or a dry `gh run list`, avoiding the `/user` endpoint which 403s for App tokens).
  - Explicit omission of PEMs, tokens, or installation IDs.
- `docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md`: Cross-referenced the runbook under §7 Optional.

## Brainstorm Visuals Used

None. Spec: `docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md`.

## What This Achieved on the Path to Autonomy

Documents the exact operator intervention required to unblock the qa role's flaky workflow rerun capability without compromising security or leaking credentials.

## Strategic Note: The Goal at the End of This PR

Once Nikhil completes the manual re-approval in the GitHub UI and validates it with `synlynk gh --role qa -- api repos/nikhilsoman/synlynk/actions/runs`, the qa bot will have the necessary permissions to retrigger failed workflow runs autonomously during merge-gate execution.
