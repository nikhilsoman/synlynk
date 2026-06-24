# Post 23 — P0 Fix: Dispatch Context Scoping

**Branch:** `fix/dispatch-context-scoping`  
**Version target:** patch on top of v0.9.3

---

## Where we were

At the end of PR #30 (v0.9.3 async daemon), synlynk had a working background job dispatcher. `dispatch_agent()` could fan out tasks to claude, agy, or codex, queue them in `daemon_jobs`, and stream logs. The daemon was operational.

But a concrete failure mode surfaced during BS-1 brainstorm: an rxcc PR review dispatch injected 119KB of full project context into a task that needed ~400 bytes. The `generate_context()` function was also writing to a single shared `.synlynk/context.md` file — a race condition waiting to happen under concurrent dispatches.

## What moved the goalpost

BS-1 (2026-06-24) answered Q1–Q10 on the context layer. Two decisions required a P0 patch before v0.9.4 work could begin:

1. **In-memory delivery (Q8):** `generate_context()` should return the string; dispatch should use the return value directly, never reading back from a global file.
2. **Context mode (Q1):** dispatch needs a `context_mode` flag so self-contained tasks can opt out of context injection entirely.

These were P0 because every v0.9.4 story that touches `dispatch_agent()` would otherwise be building on a broken foundation.

## What this PR ships

**`_generate_task_context()` refactored to return a string**

Rewrote to accumulate into a `StringIO` buffer, build the string, write to `.synlynk/context.md` for daemon HTTP endpoint compatibility, then return the string. The file write is preserved — external tooling and the daemon's `/context` HTTP endpoint are unchanged.

**`generate_context()` return value added**

Changed return type from `None` to `str`. Task-scope path now returns the `_generate_task_context()` return value directly. Full-scope path returns `open(context_file).read()` after the write block. Early-exit paths return `""`.

**`dispatch_agent()` — in-memory delivery + `context_mode` param**

Removed the `context_path = ".synlynk/context.md"` file-read block. Replaced with:

```python
context_text = ""
if context_mode != "none":
    scope = f"task:{story_id}" if (context_mode == "task" and story_id) else "full"
    context_text = generate_context(scope=scope) or ""
_warn_context_size(context_text)
```

`context_mode` values:
- `"none"` — no context injection (self-contained tasks, cross-repo dispatches)
- `"task"` — story-scoped slim context, default (~400–2000 bytes)
- `"full"` — full project context (explicit opt-in only)

**`_warn_context_size()` helper**

New helper: warns at 80KB (`_CONTEXT_WARN_BYTES = 81920`) with the `--context-mode task` escape hatch printed inline. Warns but does not block — hard limit via `context_tokens_max` config is v0.9.4 T3.

**7 new tests, all passing. 439 total (432 baseline).**

## Visuals

BS-1 brainstorm visuals that informed this fix: `docs/brainstorm/bs1-context-dispatch-relay/context-flow-today.html`, `context-delivery-options.html`.

## What this achieves

The race condition is gone. Concurrent dispatches no longer compete over a single file. A self-contained task (PR review, one-shot instruction) can now dispatch with `context_mode="none"` and inject exactly 0 bytes of project context. The default `"task"` mode gives ~400–2000 bytes vs the previous 119KB for the same dispatch.

## New goalpost

`fix/dispatch-context-scoping` merged → v0.9.4 implementation begins. Next: T1 (SQLite canon — `stories` as primary, todo.md as generated view), T2 (`.agents/<agent>.json` profile loading), T3 (`synlynk jobs` + pre-flight gate), T4 (relay wire protocol), T5 (sentinel `VERIFY_SKIP`).
