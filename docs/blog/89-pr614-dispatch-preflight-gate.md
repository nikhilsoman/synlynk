---
title: "PR #614 — Dispatch Preflight Capability Gate"
date: 2026-07-31
series: "Building the OS for Multi-Agent Development"
post: 89
pr: "#614"
merged: status open
---

## The Broader Goal at the End of the Previous PR

Phase 5 (`#606`) shipped `_scan_repo_requirements()` as a presence-only discovery primitive — Docker, MCP, and GitHub Actions signals from the repo tree, with no policy attached. Phase 3 (`#607`) and Phase 4 (`#612`) landed the remediation audit log and `doctor --fix agy` path. The remaining integration gap was dispatch-time enforcement: nothing in `dispatch_agent()` yet combined probe age/status, declared job needs, and repo signals into a single block-or-degrade decision before the subprocess spawned.

## Strategic Shifts in This PR

Two hard constraints from the design spec shaped the implementation more than the happy path did:

1. **#578/#580 are still unmerged.** Literal TC1–5 pass/fail values are not trustworthy. The gate therefore routes every real dispatch through the **no-coverage** branch today via a single `_probe_results_trustworthy()` function that returns `False`. Stale and failing branches are implemented and tested, but effectively dead until that fix stack lands and the gate flips.
2. **#419 is still open.** This PR deliberately does **not** add an `UNVERIFIED_CAPABILITY` telemetry tag on degrade. Degrade is logged/returned as a decision only; taxonomy for that tag waits on #419.

Also: declared need is explicit. A generic `--requires <capability>` flag (repeatable) generalizes the existing `--requires-gh-write` pattern. Presence of a repo artifact alone can only degrade; hard-block requires an explicit `--requires` declaration.

## What This PR Shipped

- `_probe_results_trustworthy()` in `synlynk/dispatch.py` — hard-coded `False` until #578/#580 land.
- `_dispatch_capability_preflight()` called from `dispatch_agent()` before spawn, implementing the four-way branch:
  - **stale** → sync re-probe, timeout/fail = block
  - **failing** → hard block
  - **no-coverage + required** → hard block with inline remediation (e.g. `synlynk doctor --fix agy`)
  - **no-coverage + optional** → degrade (no new telemetry field)
- Wires Phase 5's `_scan_repo_requirements(cwd)` for the presence-vs-declared split.
- CLI: `--requires` (append) on `synlynk dispatch`, plumbed through `requires=` on `dispatch_agent()`.
- Tests: one per four-way branch, one for presence-vs-declared, one asserting the trust gate forces no-coverage even for a fresh probe.

## Brainstorm Visuals Used

None. Implementation slice of `docs/superpowers/plans/2026-07-30-harness-compatibility-capability.md` Phase 6.

## What This Achieved on the Path to Autonomy

Dispatch can now fail loud *before* a job id is allocated when the operator has declared a capability the gate cannot verify — instead of spawning a process that idles or no-ops. While probes remain untrusted, that loud path is reserved for explicit `--requires`; everything else degrades with a reason string so operators still see the gap without a false hard-block storm.

## Strategic Note: The Goal at the End of This PR

Flip `_probe_results_trustworthy()` when #578/#580 merge; add `UNVERIFIED_CAPABILITY` only after #419's taxonomy is known. Until then, the structure is ready and the live path is intentionally conservative: no-coverage for every real dispatch, hard-block only on declared requirements.
