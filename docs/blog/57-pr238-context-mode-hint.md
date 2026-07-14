---
title: "PR #238 — A Dispatch Habit, Not a Bad Default: Warning on Redundant --context-mode full"
date: 2026-07-14
series: "Building the OS for Multi-Agent Development"
post: 57
pr: "#238"
issue: "#237"
merged: status: merged
---

## The Broader Goal at the End of the Previous PR

PR #236 (Measurement Ledger Hardening Phase 1, still open at the time) closed the loop on *what a cost row says about itself* — every write now carries explicit provenance. Reviewing the roadmap for what would strengthen that same "trust the numbers" theme turned up a smaller, adjacent waste: `synlynk dispatch` callers (including this project's own PM workflow) kept passing `--context-mode full` out of habit, even when a task prompt was already fully self-contained — exact code, exact file paths, exact commit message. Full-context dispatches inject the whole roadmap/memory/todo snapshot into the implementer's prompt, burning tokens the task didn't need.

## Strategic Shifts in This PR (if any)

None — this and #202 (next post) were explicitly sequenced by the user ("take up #237 first, then #202") as two independent, additive pieces of the same v0.12.0 "Trust & Cost-Aware Routing" release theme, not a change in direction.

Worth noting what this PR is *not*: it's not fixing a bad CLI default. `synlynk cli.py` already defaults `--context-mode` to `"task"` — confirmed before writing any code. This is purely about catching an explicit, unnecessary override.

## What This PR Shipped

**`_context_mode_hint(context_mode, task)`** — a pure, unit-testable heuristic in `synlynk/dispatch.py`. It only fires when `context_mode == "full"`, and only when the task text shows two independent self-containedness signals at once: a code fence (` ``` `) and something that looks like an exact commit message (`re.search(r"commit\s+-m|commit message", task, re.IGNORECASE)`). Both signals together are a reasonable proxy for "this prompt doesn't need project background" — either alone (code with no commit message, or a commit message with no code) isn't a strong enough signal to warn on.

**Non-blocking by design.** The hint prints to stdout right after `dispatch_agent()` resolves `context_mode`:

```python
hint = _context_mode_hint(context_mode, task)
if hint:
    print(f"    {hint}")
```

It never changes behavior or dispatch outcome — a caller who wants full context anyway (e.g. deliberately, for an agent that benefits from broader project awareness even on a spec'd task) is not stopped.

**Tests target the pure function, not the side-effecting one.** `dispatch_agent()` has heavy side effects (git worktree creation, subprocess spawning, preflight checks), so the six new tests in `tests/test_dispatch_context_mode_hint.py` exercise `_context_mode_hint()` directly: all four combinations of code-fence/commit-message presence at `context_mode="full"`, plus confirmation the hint never fires at `"task"` or `"none"` even when both signals are present.

## Brainstorm Visuals Used

None — pure logic fix, no visual/UI decisions.

## Practicing What It Preaches

The dispatch prompt used to implement this fix (written to the scratchpad, then handed to `codex` via `synlynk dispatch codex --context-mode task`) was itself fully self-contained: exact diff blocks, exact test cases, exact commit message template. `--context-mode task` was chosen deliberately over `full` — the same discipline the fix now nudges other callers toward. Cost: 26,016 in / 6,504 out tokens (~$0.18), 161s, first-pass with no rework.

## What This Achieved on the Path to Autonomy

A small, compounding token-efficiency win: every dispatch this hint successfully steers away from `full` context saves the implementer agent a roadmap/memory/todo injection it didn't need, on every future dispatch that pattern-matches. It's a much smaller piece of the "every number and every dispatch is deliberate, not habitual" theme than PR #236, but it's the same theme.

## Strategic Note: The Goal at the End of This PR

Merged into `main` directly (squash merge, explicit user authorization). Next up in the same sequence: #202 (stall-killer status bug), covered in the next post. Both feed the still-open v0.12.0 "Trust & Cost-Aware Routing" release, which also depends on PR #236 landing.
