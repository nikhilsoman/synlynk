---
title: "PR #606 — _scan_repo_requirements: Presence-Only Repo Requirement Discovery"
date: 2026-07-30
series: "Building the OS for Multi-Agent Development"
post: 87
pr: "#606"
merged: status open
---

## The Broader Goal at the End of the Previous PR

PR #587 closed the loop on harness-capability reality checking: synlynk had a canonical way to describe what each harness can actually do, where the headless failure modes are, and which assumptions had to be corrected. The next gap was narrower and more operational: the dispatch layer still had no cheap way to tell whether a repo itself carries static requirements like Docker, MCP, or GitHub Actions. This PR starts that separation by adding a pure repository-signal scanner instead of folding policy into dispatch.

## Strategic Shifts in This PR

The main strategic decision was to keep the new code strictly as a discovery primitive. That means:

1. it scans for presence only;
2. it returns a requirement set, not a block/degrade decision;
3. it lives in `probe.py`, alongside the other inspection helpers;
4. it stays out of `dispatch.py` until the later preflight phase wires it in.

That boundary matters because the next phase needs a clean signal to consume. If discovery and enforcement get mixed together now, the preflight gate becomes harder to reason about and harder to test.

## What This PR Shipped

PR #606 added `_scan_repo_requirements(repo_path)` in `synlynk/probe.py` and exported it through `synlynk/__init__.py`.

The helper is intentionally small and deterministic:

- it returns `set[str]`;
- it inspects the repo root with presence checks only;
- `Dockerfile`, `docker-compose.yml`, or `docker-compose.yaml` map to `docker`;
- `.mcp.json` or `mcp.json` map to `mcp`;
- any non-empty `.github/workflows/` directory maps to `gh-actions`;
- filesystem errors are swallowed and treated as "no detectable requirement".

The tests in `tests/test_probe.py` cover all eight combinations of those artifact families so the function stays presence-only and does not regress into policy or parsing logic. The test matrix also documents the intended contract: this function is a signal source, not an enforcement layer.

Notably, this PR does **not** wire the scan into dispatch yet. That work is reserved for the later preflight gate phase, where repo requirements will be combined with declared job needs and the existing capability checks.

## Brainstorm Visuals Used

None. This PR was an implementation slice of the harness-compatibility plan, not a separate brainstormed design.

## What This Achieved on the Path to Autonomy

This is a small but important layer boundary. Autonomous dispatch needs to know more than "can the agent run" - it also needs to know "does this repo imply extra tooling expectations." `_scan_repo_requirements()` creates that signal without pretending to know what to do with it.

That separation is what makes the later preflight gate feasible:

- discovery stays cheap and testable;
- enforcement stays centralized;
- repo-specific requirements can be handled consistently instead of being inferred ad hoc in multiple places.

## Strategic Note: The Goal at the End of This PR

The goal after PR #606 is not "block unsupported repos." The goal is narrower: make repo requirements observable so the future preflight gate can make an explicit decision from a real input. In other words, the repo now has a factual scanner, but policy still belongs to the next phase.
