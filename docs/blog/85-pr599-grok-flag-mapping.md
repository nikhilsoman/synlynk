---
title: "PR #599 — Grok Flag Mapping: Real Permission Translation in `_permissions_to_flags`"
date: 2026-07-30
series: "Building the OS for Multi-Agent Development"
post: 85
pr: "#599"
merged: status open
---

## The Broader Goal at the End of the Previous PR

PR #587 established the harness-compatibility goal in design form: synlynk should stop guessing at harness behavior and instead dispatch against confirmed capability surfaces, with loud failures and actionable remediation. The Grok branch of that spec exposed a concrete gap in the live code path: `_permissions_to_flags("grok", ...)` still fell through to `[]`, which meant synlynk could recognize Grok as a target but not translate any permission intent into Grok's own native flag surface.

## Strategic Shifts in This PR

No product-direction shift. This PR takes the phase-2 correction from the plan and makes it real in the dispatch layer: Grok is treated as a full-flag harness, not as a configless Claude-inheritor. The other important choice is negative scope: this phase intentionally does **not** mutate `~/.grok/config.toml` or any other durable config file. Per the plan, per-job dispatch-time flags come first; config diffs stay reserved for later, sticky policy work.

## What This PR Shipped

PR #599 closes the Grok branch of `_permissions_to_flags` in `synlynk/dispatch.py` with native flag mapping instead of the old empty fallthrough.

- Permission roles now map to Grok's real dispatch surface:
  - `--permission-mode` for the coarse mode selection
  - `--allow` / `--deny` for the actual role-scoped permission translation
- `--always-approve` is no longer treated as the default escape hatch for normal grants. It is reserved for full-grant cases only, where synlynk is intentionally asking Grok to run broad and unrestricted.
- The implementation stays at dispatch time only. No `config.toml` writes were added in this phase, so the change is limited to the command-line contract that synlynk constructs for a single job.

The regression coverage matches that split:

- tests verify the Grok permission mapping path now emits the expected flags instead of `[]`
- tests verify full-grant handling still routes through the broad-approval path
- tests verify the old no-op behavior is gone

That is the actual fix here: Grok stops being "recognized but unmapped" and becomes a first-class permission target in the dispatch path.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

This closes a silent failure mode in the orchestrator. Before this PR, synlynk could believe it had translated a job's permission posture for Grok while actually sending no permission flags at all. After this PR, Grok receives explicit, machine-generated intent that matches its real CLI surface, which is what headless dispatch needs if it is going to be deterministic instead of aspirational.

That matters for the larger autonomy goal because the system can now express a least-privilege or broad-grant decision in a way the target harness can actually consume. The next step is to keep the same standard across the rest of the remediation flow: durable audit logging, then preflight/fix behavior that can explain and repair gaps instead of silently eliding them.

## Strategic Note: The Goal at the End of This PR

Grok permission translation is no longer a missing branch in synlynk's dispatch logic. The remaining work in the harness-compatibility plan is now about the surrounding control plane: auditability, targeted remediation, and preflight gating. In other words, this PR makes Grok dispatchable with real permission intent; the next phases make that intent observable and repairable.
