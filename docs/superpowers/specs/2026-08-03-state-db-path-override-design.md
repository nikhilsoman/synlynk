# State DB path override for sandboxed/workspace-restricted execution

**Date:** 2026-08-03
**Issue:** #681 — State database outside workspace fails under sandboxed harness execution
**Status:** Design approved by Nikhil, pending implementation plan

## Problem

`_get_db()` (`synlynk/__init__.py:1031`) resolves the product state DB to
`~/.synlynk/projects/<repo-hash>/state.db`. When that path is unwritable
(`OSError` or `sqlite3.OperationalError`, e.g. a sandbox mounting `$HOME`
read-only), it falls back once via `sandbox_fallback_db_path()`
(`synlynk/fleet.py:68`).

That fallback prefers `<cwd>/.synlynk/state.db`, but when `cwd` is a nested
job/feature worktree (`is_nested_worktree_state_path()` matches
`/worktrees/`, `/.worktrees/`, `/.claude/worktrees/`), it deliberately routes
to `$TMPDIR/synlynk-sandbox/<hash>/state.db` instead — to avoid stray
product ledgers under worktrees (#330, fleet S2a).

**Gap:** when a sandbox restricts filesystem access to the repository
workspace root only, both the primary path (`~/.synlynk`, outside workspace)
and the tmpdir fallback (also outside workspace) are unreachable. Dispatch
running inside a nested worktree under such a sandbox has no working DB path
at all (#681, incident: Dialify/cc-videoreframing#92). `tried_fallback` is
already `True` by the second failure, so the error propagates as a raw
`sqlite3.OperationalError` with no indication of *why* or what to do about
it.

## Scope

This spec covers **only** an explicit override mechanism. Out of scope
(potential follow-ups, not committed to here):
- A preflight diagnostic command/flag reporting the resolved DB path and
  writability.
- Written documentation of the external-writable-state requirement.

## Design

Add a `SYNLYNK_STATE_DB_PATH` environment variable, checked at the very top
of `_get_db()`, ahead of the canonical path and the existing auto-fallback
chain.

```python
def _get_db() -> _sqlite3.Connection:
    override = os.environ.get("SYNLYNK_STATE_DB_PATH")
    if override:
        os.makedirs(os.path.dirname(override), exist_ok=True)
        conn = _sqlite3.connect(override)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _migrate_db(conn)
        return conn

    # ...existing DB_PATH / sandbox_fallback_db_path try/fallback chain,
    # unchanged...
```

### Precedence

When set, the override is authoritative:
- Skips the canonical `~/.synlynk/projects/<hash>/state.db` attempt.
- Skips `sandbox_fallback_db_path()` and its tmpdir/nested-worktree logic.
- Skips `assert_not_nested_product_ledger()` — the guard exists to catch
  *accidental* nested ledgers produced by auto-detection, not to
  second-guess an operator's or harness's explicit instruction. A caller
  setting this env var has already made a deliberate choice about where the
  ledger lives.

### Failure mode

If the override path itself is unwritable, `_get_db()` does **not** fall
back further. The `OSError`/`sqlite3.OperationalError` (or any exception
during `os.makedirs`/`connect`/`PRAGMA`/`_migrate_db`) propagates uncaught.
Rationale: an explicit override that fails should surface loudly with the
exact path in the exception, not be silently papered over by a fallback the
operator didn't ask for — consistent with the diagnostic spirit of #681.
No wrapping or re-raising is needed since `os.makedirs`/`sqlite3.connect`
already include the failing path in their exception messages.

### Interaction with nested-worktree state

Because the guard is bypassed under override, this is the one legitimate
way to place a product ledger under a worktree tree on purpose (e.g., a
sandbox that only grants access to the workspace root, where an in-workspace
`.synlynk/state.db` is the only viable location). This is expected to be an
uncommon, explicit opt-in — not the default behavior for normal nested
worktrees, which should continue to hit `sandbox_fallback_db_path()`'s
existing tmpdir routing.

## Testing

Add cases to the existing DB-fallback test suite (`tests/test_db.py` and/or
`tests/test_get_db_sandbox_fallback.py`):

1. `SYNLYNK_STATE_DB_PATH` set → connection opens at that exact path,
   verbatim (no `sandbox_fallback_db_path()` computation happens).
2. Override set even when the canonical home path would normally succeed →
   override still wins (precedence, not just a fallback).
3. Override path unwritable → the original exception propagates; no
   fallback to home path or tmpdir is attempted.
4. Override path is under a nested-worktree layout (e.g. contains
   `/.claude/worktrees/`) → succeeds despite normally triggering
   `assert_not_nested_product_ledger` (guard bypass verified).
5. `SYNLYNK_STATE_DB_PATH` unset → existing behavior (home path, then
   fallback chain) is unchanged; regression guard for today's tests.

## Documentation touch point

`synlynk/__init__.py`'s `_get_db()` docstring should mention the override
env var and its bypass semantics, matching the existing docstring's style
of citing the relevant issue number (#681).
