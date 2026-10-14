---
title: "Dispatch cost inflation had three separate causes"
date: 2026-10-14
series: "Building the OS for Multi-Agent Development"
post: 268
pr: 2277
status: merged
author: "synlynk team"
version: "0.25.0"
tags: [posts]
type: pr
---
# Dispatch cost inflation had three separate causes

The previous goalpost was to stop harness context from growing until a job hit forced compaction. The circuit breaker already contains a runaway job after the token bill explodes. It does not stop the dispatch from starting with a contaminated diff, a rewritten project snapshot, or a verbose test transcript that later turns keep resending.

## What changed

Three independent root causes were still open.

**Worktree base (gh:#2229).** `dispatch.stacking=auto` treated every non-main checkout as a stack parent. A dispatch started from a long-lived workspace branch such as `docs/claude/dev-preview-roadmap-execution` cut the job worktree from that branch tip. The job diff against `origin/main` then included the workspace's unrelated history, and a PR opened from that branch carried the same files. Auto mode now stacks only on task branches (`feat/`, `fix/`, `chore/`, `dispatch/`, `release/`). Any other checkout resolves to the fresh `origin/main` tip. `stacking=always` and an explicit `--base` are unchanged.

**Generated docs (gh:#2237).** `_docs_dir()` returns the relative string `project-docs`. PR #2238 anchored the main `todo.md` write to `_project_root()`, but roadmap, costs, and memory rotation still archived through that relative path, so a job worktree could receive `project-docs/archive/`. Generated-doc writes and that rotation now go through `_resolved_docs_dir()`, which joins a relative docs dir to the shared project root. A real linked worktree regression covers both `todo.md` and the archive.

**Verify contract (gh:#2240).** When the worktree had changed tests, the injected How to Verify command was `pytest <files> -v`. A wide run prints one line per test, and that block is resent on later turns. The contract now asks for `pytest -q`, including the fallback text used when no test file list is known.

Circuit-breaker thresholds and `.synlynk/policy.json` are untouched. Those gates still contain a blowup after the fact. This change removes the three inputs that were inflating the bill.

## Goalpost

A dispatched job should start from `origin/main` unless it is intentionally stacked on a task branch, should not dirty its worktree with a project-wide generated doc, and should verify with quiet pytest output. The next measurement is whether job cost stays near the dispatch estimate once these three sources are gone.
