---
title: "8080 vs. 8000 — When the Design Doc and the Actual Binary Disagree"
date: 2026-08-02
series: "Building the OS for Multi-Agent Development"
post: 93
pr: "TBD"
merged: status open
---

## The Broader Goal at the End of the Previous PR

PR #657 (post #92) closed the last known gap in the Local agent's onboarding surface: `synlynk local doctor` now checks for Aider on `PATH`, not just oMLX reachability and the model roster. That left "finish the rollout" complete on the code side, with only two operational steps remaining before the 5th agent was actually usable on this machine: install Aider, and bring up `omlx serve`.

## Strategic Shifts in This PR

Walking through those two remaining operational steps surfaced a second gap — smaller than #657's, but real. Aider was already installed (`~/.local/bin/aider`, 0.86.2, via the official installer script, confirmed live). oMLX, once started, came up on port **8000** — its actual default — not port 8080, which is what `.agents/local.json`, `synlynk/local_agent.py`'s fallback config, and `synlynk/_constants.py`'s preflight `required_endpoints` check all hardcoded. The design spec had apparently carried this literal forward without ever running the real binary against it. No architecture changed; the fix is a value correction, not a design revision, so no spec/plan backfill was warranted this time (unlike #657, which touched a genuine behavioral gap in a shipped function).

## What This PR Shipped

Two commits: the config fix directly (a JSON literal, not source code — outside the implementer/PM split), and the two source-code literals dispatched to Codex per the locked role split.

- **`.agents/local.json`**: `endpoint` corrected from `http://127.0.0.1:8080` to `http://127.0.0.1:8000`.
- **`synlynk/local_agent.py`**: `_DEFAULT_LOCAL_CONFIG["endpoint"]` corrected to match.
- **`synlynk/_constants.py`**: `AGENT_CAPABILITY_BASELINES["local"]["network_deps"]["required_endpoints"]` corrected to `["127.0.0.1:8000"]` — this is the value doctor's preflight reachability check actually probes.

Verified via direct worktree diff (exactly the two intended literals, nothing else touched) and a full local test-suite run before merge, not from job-status summary alone: 1564 passed, 2 skipped. No test fixtures needed changing — every test that hardcodes `8080` does so as standalone mock config data, not an assertion against the real default.

## Brainstorm Visuals Used

None — a two-line literal correction across three files.

## What This Achieved on the Path to Autonomy

`synlynk local doctor`'s reachability check now probes the port oMLX actually binds to, closing the gap between "doctor says healthy" and "oMLX is actually reachable" that #657 closed for Aider. Between #657 and this PR, every doctor claim about the Local agent's onboarding state is now backed by a real, verified check against the real binaries — not an assumption baked into the original design spec.

## Strategic Note: The Goal at the End of This PR

The Local agent rollout's operational checklist is now fully clear: Aider installed, oMLX port corrected, model download still pending (`ornith-1.0-9b` / `mlx-community/Ornith-1.0-9B`, the pinned default). Next up: the herdr-integration sub-project's brainstorm, and separately, the still-open fleet-parity reliability cluster spec (`docs/superpowers/specs/2026-08-02-fleet-parity-reliability-cluster-design.md`) awaiting user review before its implementation plan can be written.
