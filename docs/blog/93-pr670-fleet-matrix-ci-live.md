---
title: "PR #670 — Dry matrix in CI + real live smoke for Proven"
date: 2026-08-02
series: "Building the OS for Multi-Agent Development"
post: 93
pr: "#670"
---

## The Broader Goal at the End of the Previous PR

Fleet operability Phase 1–2 (#661) made Supported/Proven measurable. Dogfood immediately showed nested product `state.db` under job worktrees reappearing (#650 fallback into worktree cwd), keeping Core 4 **unsupported**.

## What This PR Shipped

1. **CI dry matrix** — `synlynk selftest --matrix` on Python 3.12 in test.yml (no model spend).
2. **Prevent re-buildup** — sandbox fallback path uses `$TMPDIR/synlynk-sandbox/<hash>/state.db` when cwd is under worktrees; job finalize purges nested product state under the job worktree.
3. **Real live matrix** — `selftest --matrix --live` runs a trivial headless CLI smoke per Core 4 agent (budget-capped, default $10) so tier-2 greens can lift status to **Proven**.

## Goalpost

Dry matrix is a merge gate. Live Proven is operator-runnable without mock cells. Nested ledger debris should stop growing under normal dispatch.
