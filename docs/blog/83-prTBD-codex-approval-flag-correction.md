---
title: "PR #TBD — Codex Approval Flag Correction"
date: 2026-07-30
series: "Building the OS for Multi-Agent Development"
post: 83
pr: "TBD"
merged: status open
---

## The Broader Goal at the End of the Previous PR

PR #587 left synlynk with a corrected understanding of Codex's harness surface: the canonical matrix now says Codex uses `--ask-for-approval` with `untrusted|on-request|never`, not the older legacy approval-flag wording that had leaked into prior dispatch notes and examples. The broader goal was still the same: every dispatched harness should either succeed at a granted capability headless, or fail loudly with a remediation path that operators can actually act on.

## Strategic Shifts in This PR

None. This was a straight correctness fix, not a scope change. The only thing that changed was the runtime command construction and the stale documentation around it. That matters because a one-character drift in a flag name is enough to make the repo's dispatch logic and its written contract disagree.

## What This PR Shipped

The Codex permission translation path now emits `--ask-for-approval untrusted` when the current permission set does not include write access. The legacy approval-flag string was removed from the live dispatch path.

The regression coverage was updated in two places:

1. `tests/test_synlynk.py` now asserts the Codex dispatch command contains `--ask-for-approval` and does not contain the old flag name.
2. `tests/test_dispatch_local_agent.py` now uses the corrected flag name in its baseline passthrough test.

The supporting docs were aligned at the same time so the codebase does not keep re-teaching the wrong flag:

1. `CHANGELOG.md`
2. `docs/blog/47-pr119-bs12-agent-autonomy-bridge.md`
3. `docs/blog/48-v011-agent-ecosystem-operational-layer.md`
4. `docs/superpowers/specs/2026-07-05-bs12-agent-autonomy-bridge-design.md`
5. `docs/superpowers/specs/2026-07-29-harness-compatibility-capability-research-brief.md`
6. `docs/superpowers/plans/2026-07-12-local-agent-mlx-driver.md`

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

This closes a small but real contract drift between the runtime and the canonical harness matrix. That kind of drift is dangerous because it looks like a harmless docs typo until it becomes a broken dispatch path or a misleading operator expectation.

## Strategic Note: The Goal at the End of This PR

The immediate goalpost did not move. Codex dispatch now speaks the CLI's real approval vocabulary, and the remaining harness-compatibility work can build on that corrected baseline instead of carrying the wrong flag name forward.
