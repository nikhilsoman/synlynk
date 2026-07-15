# v0.12.0 Docs Refresh — Plan 1: README.md Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `README.md`'s Commands table current with the v0.12.0 CLI surface, reorganized by user journey stage, and add an "Upgrading?" section for existing users.

**Architecture:** Pure content edit to two files (`README.md`, light-touch `SYNLYNK_GUIDE.md` check). No code changes, no tests to write — verification is a grep audit of command names against `synlynk/cli.py`.

**Tech Stack:** Markdown only.

---

This plan is one of 4 independent, parallel-dispatchable plans derived from `docs/superpowers/specs/2026-07-15-v0.12.0-docs-onboarding-refresh-design.md`. It touches only `README.md` and (conditionally) `SYNLYNK_GUIDE.md` — disjoint from the other 3 plans' files.

### Task 1: Replace the `## Commands` table with a journey-staged version

**Files:**
- Modify: `README.md:99-126` (the existing `## Commands` table, from the `## Commands` heading through the `> **Note:**` line after it)

- [ ] **Step 1: Read current state**

Run: `sed -n '99,127p' README.md`

Confirm it still matches this (if it has drifted, adapt the replacement below to the new content rather than blindly overwriting):

```
## Commands

| Command | Description |
| --- | --- |
| `synlynk init [--force] [--wizard]` | ... |
... (25 rows) ...
| `synlynk --version` | Print current version |

> **Note:** `synlynk watch` uses `os.fork()` and requires macOS or Linux. `synlynk dispatch` works on all platforms.
```

- [ ] **Step 2: Cross-check every command name against `synlynk/cli.py`**

Run: `grep -n 'add_parser(' synlynk/cli.py`

For each top-level and sub-command found, capture its exact `help="..."` string (some span multiple lines — read the surrounding 5 lines with `sed -n 'N,N+5p' synlynk/cli.py` when the grep line doesn't show the help text inline). This is the source of truth for command names and one-line descriptions — do not invent descriptions.

- [ ] **Step 3: Replace lines 99-126 of `README.md`** with a table organized into 4 subsections by journey stage. Use this structure (fill in the `Description` column from Step 2's actual `help=` text — do not copy the placeholder text below verbatim if it has drifted from what `cli.py` says):

```markdown
## Commands

Commands are grouped by where you'll reach for them in a typical project lifecycle.

### Getting Started

| Command | Description |
| --- | --- |
| `synlynk init [--force] [--wizard]` | Initialize synlynk in a repository |
| `synlynk doctor` | Run health checks on your synlynk installation |
| `synlynk probe` | Check reachability of configured AI CLI tools |
| `synlynk exec <cmd>` | Execute an AI CLI with synlynk context |
| `synlynk status [--json]` | Show project state dashboard (active tasks, budget, sentinel alerts, watcher state, rate-table staleness) |
| `synlynk upgrade` | Check GitHub releases for a newer version and apply it |

### Daily Use

| Command | Description |
| --- | --- |
| `synlynk dispatch <agent> --task <text> [--story <id>] [--context-mode none\|task\|full]` | Dispatch a task to an agent in the background (claude, codex, agy, grok, local) |
| `synlynk jobs [--all] [--watch]` | List dispatched background jobs |
| `synlynk jobs handoff <job-id> <agent>` | Transfer a stalled job to another agent |
| `synlynk watch` | Live workspace HUD |
| `synlynk launch <agent> [--story <id>]` | Prompt for a task, then dispatch interactively |
| `synlynk run --trio <task>` | Dispatch the same task to all functional agents in parallel |
| `synlynk checkpoint` | Archive completed tasks to devlog, refresh context, emit telemetry |
| `synlynk logs --job <id> [--tail N]` | Tail a job's stdout log |
| `synlynk shell [--story <id>]` | Open an interactive agent shell with story context |
| `synlynk open <resource>` | Open a resource (job, story, doc) |
| `synlynk config set <key> <value>` | Set a config key |
| `synlynk sentinel list\|clear [--severity] [--code]` | View or dismiss sentinel alerts |
| `synlynk cost log` | Log a manual cost entry for native/unwrapped sessions |

### Team / PM

| Command | Description |
| --- | --- |
| `synlynk join` | Onboard as a new member to an existing project |
| `synlynk team status` | Show team digest: members, stories, budget |
| `synlynk decide` | Run a multi-agent consensus decision |
| `synlynk goal create\|list\|link\|status` | Manage Business Goals |
| `synlynk story create\|list\|ready\|draft` | Manage stories |
| `synlynk score add\|list\|attest` | Manage capability scores |
| `synlynk schedule [--execute] [--max-stories N]` | Fleet batch scheduler for ready stories (dry-run by default) |
| `synlynk relay start [--port N]` | Start HTTP SSE relay broker in foreground (port 27472) |
| `synlynk relay broadcast <body> [--kind motd\|wellness\|message\|joke\|custom]` | Publish a broadcast event to the relay |
| `synlynk instructions status\|diff\|update\|ack` | Manage tracked instruction files (CLAUDE.md/GEMINI.md/AGENTS.md) |
| `synlynk pr check` | Block PR if model versions are unattested |
| `synlynk roles [--fix]` | Check/fix role and permission configuration |

### Advanced / Operate

| Command | Description |
| --- | --- |
| `synlynk agent configure\|run\|list` | Manage and run autopilot agents |
| `synlynk identity init` | Create `~/.synlynk/identity.key` (Ed25519) and print public key |
| `synlynk local doctor` | Check oMLX endpoint reachability and model roster (5th agent, on-device) |
| `synlynk scan [--refresh] [--add path] [--remove path] [--dry-run] [--deep] [--status]` | Re-runnable repository analysis that scans the source tree and updates the source architecture context |
| `synlynk migrate [--dry-run] [--recover] [--setup-dr]` | One-shot import to migrate existing flat-file `project-docs/` to `state.db` |
| `synlynk repair` | Repair inconsistent state.db records |
| `synlynk sync` | Sync state with a remote source |
| `synlynk exit` | Exit/clean up a running session |
| `synlynk release [--dry-run] [--version] [--minor]` | Cut a named release |
| `synlynk viz [--serve\|--generate\|--open\|--stop\|--port]` | Open the local browser workspace dashboard (Vizor — Architect Map, Effort & Cost tab, Business Goals Panel) |
| `synlynk daemon` | Manage the always-on context daemon |
| `synlynk --version` | Print current version |

> **Note:** `synlynk watch` uses `os.fork()` and requires macOS or Linux. `synlynk dispatch` works on all platforms.

## Upgrading?

If you installed synlynk before 2026-07, here's what's new:

- `synlynk schedule` — fleet batch dispatch, dry-run by default
- `synlynk cost log` — manual cost entries for native/PM-session work
- `local` agent — 5th dispatch target, zero-cost on-device inference via oMLX
- `synlynk status` now shows a `RATES` line (rate-table staleness)
- `synlynk viz` — local web HUD (Architect Map, Effort & Cost tab, Business Goals Panel)

Run `synlynk upgrade` to get the latest, then `synlynk doctor` to verify.
```

Where any `help=` text you read in Step 2 differs from the wording above, use the actual `cli.py` text — this document's wording is a starting draft, not the final source of truth.

- [ ] **Step 4: Update the version badge and tagline near the top of the file**

Run: `sed -n '1,18p' README.md` to see current state. Update the version badge (`https://img.shields.io/badge/version-0.10.0-blue`) to read `version-0.12.0-blue`, and update the `**v0.10.0:**` callout line (line 17) to summarize v0.12.0 instead — e.g.:

```markdown
**v0.12.0:** Measurement & Reliability — dispatch git-finalization (agents no longer need to remember to commit/push/PR), a 5th zero-cost `local` agent over on-device oMLX, fleet batch scheduling (`synlynk schedule`), and full cost-provenance tracking (every dollar shown is measured or flagged as an estimate). 1140 tests passing.
```

Also update the tests badge (`tests-623%20passing-brightgreen`) to `tests-1140%20passing-brightgreen` if it is still showing a stale count — verify the true current count first with `python3 -m pytest --collect-only -q | tail -1` before writing it.

- [ ] **Step 5: Self-verify — grep every command name in the new README table against `cli.py`**

Run:
```bash
grep -oE '`synlynk [a-z][a-z-]*' README.md | sed 's/`synlynk //' | sort -u
```
For each name printed, confirm it appears as a `add_parser("<name>"` (or nested `_sub.add_parser("<name>"`) in `synlynk/cli.py` via `grep -n '"<name>"' synlynk/cli.py`. Any orphan (a command in the README with no matching parser) is a bug — fix it before committing.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: refresh README command table for v0.12.0, organize by journey stage"
```

### Task 2: Light consistency check on `SYNLYNK_GUIDE.md`

**Files:**
- Read-only check: `SYNLYNK_GUIDE.md` (29 lines)
- Reference: `synlynk/cli.py`'s `init()` implementation (search `grep -n "def init\|def cmd_init" synlynk/*.py`)

- [ ] **Step 1: Read the file**

Run: `cat SYNLYNK_GUIDE.md`

This file documents this project's own AI-agent session protocol (referenced from `CLAUDE.md`'s "Session Protocol" section) — it is NOT a synlynk-CLI-usage doc and is not scaffolded into other repos by `synlynk init`. Do not rewrite it wholesale.

- [ ] **Step 2: Check for factual drift only**

Verify two things against current code:
1. The list of files it says `project-docs/` contains (roadmap.md, todo.md, memory.md, costs.md, devlogs/) still matches what `init()` actually scaffolds. Check via `grep -n "roadmap.md\|todo.md\|memory.md\|costs.md" synlynk/cli.py synlynk/*.py | grep -i init`.
2. Any reference to `.synlynk_config.json` mode values (`single`/`team` or `solo`/`team`) matches the current accepted values. Check via `grep -n "solo\|team\|single" synlynk/cli.py | grep -i mode`.

- [ ] **Step 3: Fix only if actually wrong**

If both checks pass (file list and mode values match), make **no edits** to `SYNLYNK_GUIDE.md` — do not commit anything for this task. If either is stale, make the minimal correcting edit (e.g., fix `single` to `solo` if that's what changed) and commit:

```bash
git add SYNLYNK_GUIDE.md
git commit -m "docs: fix stale detail in SYNLYNK_GUIDE.md"
```

- [ ] **Step 4: Report outcome**

State explicitly whether Task 2 made any changes or found the file already accurate — this is the expected/likely outcome per the design spec's Context section, not a failure to fix something.
