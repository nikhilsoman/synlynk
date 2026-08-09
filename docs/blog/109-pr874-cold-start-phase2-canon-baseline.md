---
title: "PR #874 — cold-start Phase 2: The Canon Baseline"
date: 2026-08-09
series: "Building the OS for Multi-Agent Development"
post: 109
pr: "#874"
---

# cold-start Phase 2 — The Canon Baseline

## Broader goal (previous)

`synlynk start` already told an operator, on a warm re-run against an existing repo, what stack it detected and which harnesses were functional, and seeded a story from a one-line intent. It did not yet produce any durable artifact of what the tool actually knows about the workspace — that was explicitly deferred as "cold-start Phase 2" in the Phase 1 docstring.

## Why this PR

Every other synlynk surface (roadmap, memory, telemetry) accumulates state that operators and agents can trust. Cold-start had nothing comparable: each `synlynk start` run re-derived context from scratch and threw it away. The design goal for Phase 2 was narrow and deliberate — produce a `workspace-canon.md` baseline that states only what a shallow scan can *prove*, never what it merely guesses, and make that provenance checkable and stale-detectable over time.

## What shipped

1. **`synlynk/canon.py`** (new module) — a Documentation Index (real content: every markdown file found under `project-docs/`/`docs/`) plus a 3-claim provenance receipt. Each claim (stack detected, git repository, harness on PATH) is sourced directly from scan data and **skipped, never fabricated**, if its backing field is missing.
2. **Skeleton stubs** for the sections Phase 2 doesn't attempt yet (Retrospective Roadmap, Current State, projection views) — present in the file, explicitly marked as not-yet-generated, no provenance stamp.
3. **Provenance/staleness** — a single `<!-- canon:section=baseline sha=<sha> assessed_at=<iso8601> -->` HTML comment stamps only the baseline section. `sha=unknown` (no git repo at generation time) is treated as never stale, so a non-git workspace doesn't get spuriously flagged.
4. **Wiring** — `_run_existing_project_flow` in `synlynk/coldstart.py` now calls `canon.run_canon_baseline(root, scan)`. First run offers deep-scan consent once; re-runs skip the prompt entirely and print a staleness banner if HEAD has moved since the stamped SHA.
5. **Post-review fix** — the final review subagent caught a real spec violation: the git-repository claim could fire for a directory with no `.git` at all, reachable via the ambiguous-mode-defaults-to-"existing" path in `_resolve_cold_start_mode`. Fixed by gating the claim on an actual `os.path.isdir(.../".git")` check, with regression tests for both the negative and positive case.

Execution was fully subagent-driven per this repo's role split: spec → plan → 7 TDD tasks, each dispatched to `synlynk dispatch codex`, independently verified (worktree diff read, tests re-run myself, not trusted from job self-report) and merged one at a time by Claude/PM. A dedicated final-review subagent then checked the assembled diff against the spec before the fix task and PR.

## On the long arc

This is the first synlynk surface that writes a durable, provenance-stamped claim about a workspace rather than an ephemeral scan summary. The "never fabricate, always cite a source, mark staleness explicitly" discipline built here is the same discipline the deferred Retrospective Roadmap and Current State sections will need — Phase 2 proved the pattern on the smallest possible surface (2 real sections) before it gets reused on the harder ones.

## New goalpost

`workspace-canon.md` exists and is trustworthy for its two real sections. The deferred skeleton sections (Retrospective Roadmap, Current State, 5 projection views) are the next cold-start increment, each requiring its own claim-sourcing design before it can move past "skeleton stub."
