---
title: "PR #TBD — Phase 4: synlynk doctor --fix agy"
date: 2026-07-30
series: "Building the OS for Multi-Agent Development"
post: 88
pr: "#TBD"
merged: open
---

## The Broader Goal at the End of the Previous PR
Phase 3 established the remediation audit log as the durable record for confirmed config writes. Phase 4 uses that foundation to close the Agy-specific pre-flight manifest gap.

## Strategic Shifts in This PR (if any)
No broad strategy change. This phase narrows remediation to Agy only because the confirmed failure mode is a pre-dispatch permissions gap in `~/.gemini/antigravity-cli/settings.json`, not a runtime prompt loop.

## What This PR Shipped
`synlynk doctor --fix agy` now computes the exact JSON diff for `~/.gemini/antigravity-cli/settings.json`, prints the proposed change, and writes only when the operator passes `--yes` or confirms interactively. On every write, synlynk appends a `remediation_actions` row with the timestamp, target file, exact diff, and confirmation mode, so the write is auditable even when the fix is applied headless.

## Brainstorm Visuals Used
None.

## What This Achieved on the Path to Autonomy
Agy can now be pre-seeded with the needed permission rules before dispatch rather than failing inside the job. That moves the system one step closer to a pre-flight, operator-visible remediation loop instead of a silent runtime permission failure.

## Strategic Note: The Goal at the End of This PR
The next step is wiring this pre-flight remediation into the broader dispatch workflow without turning it into an auto-triggered runtime prompt.
