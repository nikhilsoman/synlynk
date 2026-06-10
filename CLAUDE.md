# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

synlynk is a single-file Python CLI (`bin/synlynk.py`) that acts as a wrapper around AI CLIs (Claude, Gemini, etc.). It injects project context before each invocation, tracks telemetry/costs, and detects hallucination loops. The entire application logic lives in one file — there is no build step.

## Running the CLI

```bash
# Run directly without installing
python3 bin/synlynk.py <command>

# Or install globally (adds to ~/.synlynk/bin/synlynk and updates PATH)
./install.sh

# After install:
synlynk init           # bootstrap project-docs/ and template files in current dir
synlynk exec claude    # run claude with context injection
synlynk upgrade        # check for updates
synlynk --version
```

No dependencies beyond Python 3 stdlib. No build, compile, or package step needed.

## Architecture

The entire CLI is `bin/synlynk.py`. Key functions and their responsibilities:

| Function | What it does |
|---|---|
| `init()` | Creates `project-docs/` (roadmap.md, todo.md, memory.md, costs.md, devlogs/) and `.synlynk/config.json`. Also writes CLAUDE.md, GEMINI.md, AI_INSTRUCTIONS.md, .cursorrules at the repo root. Skips existing files. |
| `exec_command(cmd_args)` | Main wrapper: calls `generate_context()` → `check_budgets()` → spawns subprocess → `update_costs()` → `log_telemetry()` → `check_sentinel_patterns()` |
| `generate_context()` | Reads `project-docs/memory.md`, `roadmap.md`, `todo.md` and concatenates them into `.synlynk/context.md` |
| `check_sentinel_patterns(output_text, exit_code, cmd)` | Reads `.synlynk/telemetry.json`; detects FLATLINE (3 consecutive failures), SUCCESS_LOOP, QUOTA_EXHAUSTED, and other patterns; writes alerts to `sentinel.md` |
| `check_budgets()` | Compares cumulative cost/request totals from telemetry against limits in `.synlynk/config.json` |
| `update_costs()` | Appends a row to `project-docs/costs.md` and prints the Budget Pulse summary |
| `log_telemetry()` | Appends to `.synlynk/telemetry.json`, keeping only the last 100 entries |
| `extract_tokens()` | Regex-scrapes token counts from captured AI CLI stdout using several known output formats |

## Data Layout

| Path | Purpose |
|---|---|
| `project-docs/` | Human-maintained project state: roadmap, todos, decisions, costs, devlogs per user |
| `project-docs/.synlynk_config.json` | `mode: single|team`, version, init timestamp |
| `.synlynk/context.md` | Auto-generated snapshot (overwritten each `exec` run) — do not edit manually |
| `.synlynk/telemetry.json` | Rolling log of last 100 exec invocations with duration, exit code, cost |
| `.synlynk/config.json` | Budget limits: `limit_usd` and `limit_requests` |

## Cost Estimation

`update_costs()` uses hardcoded rates: `$0.003/1K input tokens` + `$0.015/1K output tokens`. These are not read from config — update them directly in the function if rates change.

## Session Protocol (SYNLYNK_GUIDE.md)

At session start:
1. Read `project-docs/.synlynk_config.json` for mode (`single` vs `team`)
2. Identify current user via `git config user.name`
3. Surface last completed task, next task from `todo.md`, and (in team mode) recent entries from teammates' devlogs

Keep `project-docs/` docs updated during the session: roadmap status, todo checkboxes, memory decisions with `[@username]` attribution, and devlog entry in `project-docs/devlogs/<username>.md`.

## Blog Post Protocol

**For every PR raised in this project, draft a blog post in `docs/blog/` before or immediately after opening the PR.**

Use the template in `docs/blog/README.md`. Each post must:

1. State the broader goal as it was understood at the end of the *previous* PR
2. Explain any strategic shifts that moved the goalpost in *this* PR, and why
3. Describe what the PR shipped, technically — commands, key implementation decisions, data structures, test approach
4. Reference any brainstorm visuals in `docs/brainstorm/` that informed decisions
5. Summarise what was achieved on track to the goal of full autonomous multi-agent dispatch
6. State the new goalpost as understood at the end of this PR

File naming: `docs/blog/NN-prN-<version-or-theme>.md` (e.g. `08-pr29-v0.4.0-trio-bootstrap.md`).

Commit the blog post in the same branch as the PR. Do not wait until after merge.

Always `git pull` before modifying project-docs files to avoid conflicts in team mode.
