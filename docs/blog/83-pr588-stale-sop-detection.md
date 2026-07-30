---
title: "PR #588 — #583: Teaching synlynk to Notice Its Own Instructions Went Stale"
date: 2026-07-29
series: "Building the OS for Multi-Agent Development"
post: 83
pr: "#588"
merged: 2026-07-29
---

## The Broader Goal at the End of the Previous PR

With #339 merged (PR #584), doctor/probe output was trustworthy again, and the PM's next queued task was finally regenerating CLAUDE.md/GEMINI.md/GROK.md with the up-to-date GitHub-write-routing text (#426/#569) — an ask that had been outstanding across multiple prior sessions.

## Strategic Shifts in This PR

Attempting that regeneration surfaced issue #583: `synlynk sync --repair-sops` only detected and filled *missing* harness SOP sections. If a section already existed but its content had drifted stale (exactly the CLAUDE.md situation — the `## Capability-Based Task Allocation` block existed but still said "Grok only" instead of the current Grok-by-default-with-caveats text), sync silently left it alone. The regeneration task itself couldn't proceed until this tooling gap was fixed — consistent with this project's standing policy of fixing root-cause tooling bugs rather than hand-patching the harness-managed files directly.

## What This PR Shipped

Stale-vs-missing detection for harness SOP blocks in `synlynk/probe.py`, scoped narrowly: it fires only inside an already-existing harness fence, and only for the `## Capability-Based Task Allocation` header specifically (narrower than the originally-scoped "3 cfg-driven headers" — Grok's review flagged this as a discrepancy between the PR description and the actual diff, judged acceptable since it's safer to start narrow).

Two correction rounds:
- First pass broke two existing tests — one expecting no duplicate header when no fence exists yet, one expecting deliberately-custom fence content to survive untouched. Fixed by narrowing stale detection to fire only inside a live fence, for that one header.
- Second: the fix pushed `synlynk/__init__.py` to 4043 lines against CI's hard 4000-line "guard against `__init__.py` regrowth" gate (same class of failure that hit PR #574 earlier in the project). Fixed by extracting the SOP-repair helper logic into `synlynk/probe.py`, landing at 3776 lines — though this fix arrived on a fresh branch forked from post-#584 main rather than stacked on the original branch, requiring the original PR (#585) to be closed as superseded and replaced with this one (#588), verified independently rather than reconciling branch histories.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

`synlynk sync --repair-sops` can now actually keep the harness-managed instruction files current, not just present. That's a prerequisite for every future SOP-block update landing automatically instead of via manual diffing — but this PR's own stale-refresh logic shipped with a spacing bug (see PR #591) that blocked the very regeneration it was built to unblock.

## Strategic Note: The Goal at the End of This PR

The stale-detection engine works, but its output had a formatting defect discovered on the very next real-world run. The CLAUDE.md regeneration task is still blocked, now one layer deeper than before.
