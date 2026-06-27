# Blog Post 28 — PR #72: Fix Grok Dispatch Prompt Flag

**Series:** Building synlynk — the OS for multi-agent development  
**PR:** #72 `fix/grok-dispatch-prompt-flag`  
**Version:** patch on v0.9.7 baseline  
**Date:** 2026-06-27

---

## Where We Were

v0.9.7 shipped Grok as a first-class fourth agent peer with full baseline registration, dispatch flags (`--always-approve`), and `extract_tokens` nested JSON support. Grok was treated as a `prompt_via_arg` agent — meaning it receives its prompt as a flag argument rather than via stdin. That flag was `-p` (short for `--single`), placed in `non_interactive_flags` alongside the agent's other CLI switches.

## What Broke

Any attempt to dispatch a task to Grok produced:

```
error: a value is required for '--single <PROMPT>' but none was supplied
```

The root cause: the dispatch shell command builder appended `"$PROMPT"` at the end of the full flag list. For Grok, that list was `["-p", "--always-approve", "--output-format", "json"]`, producing:

```sh
grok -p --always-approve --output-format json "$PROMPT"
```

Grok's CLI parser sees `-p` / `--single` as a flag that requires an inline value and attempts to consume the next token (`--always-approve`) as that value. But `--always-approve` starts with `--`, so the parser rejects it as a flag value and leaves `--single` valueless. `$PROMPT` ends up in the positional slot, not as `--single`'s argument. The fix isn't to reorder the list — it's to separate the prompt-introducing flag from the non-interactive flags entirely.

## What Shipped

### `prompt_flag` key in `AGENT_CAPABILITY_BASELINES`

A new optional key separates the "prompt hand-off flag" from the agent's other non-interactive switches:

```python
"agy": {
    "cli": "agy",
    "non_interactive_flags": [],   # was: ["-p"]
    "prompt_flag": "-p",           # placed last, immediately before "$PROMPT"
    "prompt_via_arg": True,
    ...
},
"grok": {
    "cli": "grok",
    "non_interactive_flags": [],   # was: ["-p"]
    "prompt_flag": "--single",     # long form, placed last
    "prompt_via_arg": True,
    "dispatch_flags": ["--always-approve"],
    ...
},
```

### All four `prompt_via_arg` call sites updated

The shell command builder now appends `prompt_flag` as the final element before `"$PROMPT"`:

```sh
grok --always-approve --output-format json --single "$PROMPT"
```

The four sites fixed: `_run_agent_sync()`, `dispatch_agent()`, the daemon worker loop (line ~1700), and `cmd_consult()` (line ~3046).

### Two new assertion tests

- `test_grok_dispatch_single_flag_placed_before_prompt` — asserts `--single` appears after `--always-approve` and directly before `"$PROMPT"` in the generated shell command.
- `test_agy_dispatch_prompt_flag_placed_before_prompt` — same ordering contract for agy's `-p` flag.
- `test_agent_capability_baselines_includes_grok` updated to assert `prompt_flag == "--single"` rather than `"-p" in non_interactive_flags`.

**514 tests pass.**

## What This Achieves

Grok task dispatch now works end-to-end. The `prompt_flag` key is a clean extension point — any future agent with a similar "value-required flag" pattern (e.g. `codex --message`) can use the same mechanism without touching dispatch logic.

## Next Goalpost

The dispatch layer is now correct for all four agents. Next up: BS-7 brainstorm (skill pack interoperability + 4-round benchmark) scheduled for 2026-06-28/29, followed by the BS-5 website implementation sprint.
