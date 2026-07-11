# `dispatch --help` Stale Agent List — Design

**Tracks:** [#160](https://github.com/nikhilsoman/synlynk/issues/160) — dispatch --help missing grok in agent list

## Problem

`synlynk dispatch --help` lists the `agent` positional argument's help text as `"Agent name: claude, agy, codex"` (`synlynk/cli.py:407-408`) — hardcoded, and missing `grok`, which drifted out of sync when grok was added to `AGENT_CAPABILITY_BASELINES` (`synlynk/_constants.py:85`). `doctor` output includes a `doctor [grok]` section with passing checks, so the CLI signals inconsistently: `doctor` implies grok is a real dispatch target, `dispatch --help` implies it isn't.

There's also no `choices=` constraint on the argument today, so `synlynk dispatch <typo>` isn't rejected at the CLI layer — it falls through to `dispatch_agent()`'s existing runtime check (`synlynk/dispatch.py:665-666`, `raise ValueError(f"Unknown agent: '{agent}'. Known: {list(baselines_map)}")`), which is correct but only reachable for callers who get that far.

## Design

### What changes

In `main()` (`synlynk/cli.py`), the `from synlynk import (...)` block at the top of the function already imports package internals unconditionally, before the parser is built — `AGENT_CAPABILITY_BASELINES` is exported from `synlynk/__init__.py:16`, so adding it to that same import costs nothing extra (it's on the hot path for every invocation, including `--help`, already).

Replace (`synlynk/cli.py:407-408`):

```python
dispatch_parser.add_argument("agent",
    help="Agent name: claude, agy, codex")
```

with:

```python
known_agents = sorted(AGENT_CAPABILITY_BASELINES)
dispatch_parser.add_argument("agent",
    choices=known_agents,
    help=f"Agent name: {', '.join(known_agents)}")
```

`AGENT_CAPABILITY_BASELINES` is added to the existing `from synlynk import (...)` block in `main()`.

### Why derive from `AGENT_CAPABILITY_BASELINES`, not just add "grok" to the string

Hardcoding the corrected string (`"Agent name: claude, agy, codex, grok"`) fixes today's symptom but reintroduces the identical bug class the next time an agent is added or removed — someone has to remember to update this string by hand again, with no test or type system to catch a miss. Deriving both the help text and the `choices=` list from `AGENT_CAPABILITY_BASELINES` (the single source of truth already used by `dispatch_agent()`, `doctor`, `agent list`, and every other agent-aware code path) makes this structurally unable to drift again.

### Why also add `choices=`, not just fix the text

`choices=known_agents` makes argparse reject an unrecognized agent name immediately, with argparse's own `invalid choice` error and exit code, before the process reaches `dispatch_agent()`. This is a strict improvement in fail-fast behavior for CLI users and costs nothing since the list is already computed for the help string. `dispatch_agent()`'s own `ValueError` check is unchanged — it remains the correct guard for anyone calling `dispatch_agent()` programmatically rather than through the CLI parser (e.g. from tests, from other internal callers).

### What does NOT change

- `dispatch_agent()`'s runtime agent validation (`synlynk/dispatch.py:665-666`) — untouched, still needed for non-CLI callers.
- `doctor`'s per-agent section logic — that path already correctly enumerates all configured agents; the bug was isolated to this one hardcoded string in `cli.py`.
- No behavior change for any of the four currently-known agent names (`agy`, `claude`, `codex`, `grok`) — `sorted(AGENT_CAPABILITY_BASELINES)` produces the same four values `doctor` and `dispatch_agent()` already use.

## Testing

Both tests go in the existing CLI/dispatch test coverage (exact file to be determined during planning — likely `tests/test_synlynk.py` or `tests/test_agy_dispatch_fix.py`, whichever already covers `cli.py`/`dispatch_parser` argparse behavior):

1. **Help text completeness:** invoke `synlynk dispatch --help` (or call the parser-building code directly and inspect `dispatch_parser.format_help()` / the `agent` action's `choices`), assert every key in `sorted(AGENT_CAPABILITY_BASELINES)` (currently `agy`, `claude`, `codex`, `grok`) appears in the output.
2. **Invalid agent rejected at CLI layer:** invoke the CLI with an unrecognized agent name (e.g. `synlynk dispatch nonexistent-agent --task "x"`) and assert it exits non-zero via argparse's own `invalid choice` handling — i.e. verify it fails before ever calling `dispatch_agent()` (so the test doubles as a regression guard that `choices=` is actually wired up, not just present in the help string).

No test needs to change for the four currently-supported agents' happy-path dispatch behavior — this fix only affects the argument's declared metadata (help text, choices), not `dispatch_agent()`'s internal logic.

## Out of scope

- Any change to `dispatch_agent()`'s own validation or error message.
- Any change to `doctor`'s agent enumeration or output formatting.
- Issue #161 (Codex worktree git-ref fix) — separate, already shipped (PR #163).
- Issue #162 (Agy heartbeat/timeout observability) — separate, not yet designed.
