# Blog Post 17 — Codex Headless Dispatch: `codex exec` Unlocks the Third Agent

## Broader Goal (End of Previous PR)

PR #50 seeded the capability ledger with 20 PRs of Claude history and proved the AGY dispatch pipeline end-to-end. Codex was confirmed TTY-blocked — `synlynk dispatch codex` started the process but Codex exited immediately with `stdin is not a terminal`. The ledger had Claude and AGY data; Codex was a placeholder.

## What Changed

The fix turned out to be a single baseline update. Codex ships a `codex exec` subcommand designed explicitly for non-interactive use. It reads the prompt from stdin (via `-` argument), runs without a TTY, and exits when done. The only other flags needed:

- `-s read-only` — sandboxes any shell commands Codex issues during the task
- `--dangerously-bypass-approvals-and-sandbox` — skips interactive approval prompts so the process runs unattended

Updated baseline in `AGENT_CAPABILITY_BASELINES["codex"]`:

```python
"non_interactive_flags": [
    "exec", "-",
    "-s", "read-only",
    "--dangerously-bypass-approvals-and-sandbox",
],
```

This generates a dispatch shell command of:

```bash
codex exec - -s read-only --dangerously-bypass-approvals-and-sandbox < prompt.txt > log.txt 2>&1
```

No PTY wrapper, no `tmux`, no `pexpect`. One config change.

## Verification

Dispatched a real task headlessly to confirm:

```
synlynk dispatch codex --task "List the top 3 functions in bin/synlynk.py by line count" --force-agent
```

Codex wrote Python AST code to parse `bin/synlynk.py`, counted lines per function, and returned:

```
1. main — 237 lines
2. _build_templates — 220 lines
3. init — 174 lines
```

Exit 0, 17,850 tokens used, 468 lines of log output including the tool call trace.

## Test

`test_codex_baseline_uses_exec_subcommand` asserts that the shell command built by `dispatch_agent("codex", ...)` contains `codex exec` and `--dangerously-bypass-approvals-and-sandbox`. Test count: 318.

## New Goalpost

All three agents — Claude, AGY, Codex — can now be dispatched headlessly via `synlynk dispatch`. The capability ledger has real data for Claude and AGY; Codex now needs live dispatch stories attested to complete its baseline. Definition B (three-agent Autopilot: PM Agent, Marketing Intern, Support Engineer) can begin.
