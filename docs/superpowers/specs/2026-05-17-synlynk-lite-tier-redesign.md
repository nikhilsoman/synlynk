# synlynk Lite Tier Redesign — Design Spec
**Date:** 2026-05-17  
**Author:** @nikhilsoman  
**Status:** Approved — ready for implementation planning  
**Version target:** v1.2.1-lite

---

## Problem Statement

The v1.2.0-lite implementation does not match the protocol defined in `SYNLYNK_GUIDE.md`. Specifically:

1. `init` templates (CLAUDE.md, GEMINI.md) are stubs — they don't embed the session protocol
2. `generate_context()` dumps all docs verbatim — no compaction, context grows unboundedly
3. Context injection is advisory — the AI must manually read `context.md`; synlynk doesn't ensure it's fresh
4. Flatline Sentinel prints to stdout only — the AI never sees it mid-session
5. Token extraction regex doesn't match real CLI output — Budget Pulse always shows $0.0000
6. `synlynk upgrade` is a stub — always reports "latest" regardless of actual version
7. No state visibility — developer can't tell if synlynk is actively watching or idle

---

## Architecture

### What stays the same
- Single-file Python CLI: `bin/synlynk.py`
- No external dependencies — stdlib only
- `project-docs/` maintained by AI; `.synlynk/` maintained by synlynk
- AI is responsible for doc discipline; synlynk scaffolds, aggregates, and enforces compaction

### New command surface
```
synlynk init                  # unchanged entry point; writes complete templates
synlynk watch start|stop|status  # new: background file watcher daemon
synlynk checkpoint            # new: archive done tasks, refresh context, emit telemetry
synlynk status [--json]       # new: human dashboard + machine-readable output
synlynk exec <cmd>            # simplified: removes fake token extraction
synlynk upgrade               # fixed: real GitHub release check
```

### Team/Enterprise guardrails
All decisions in this spec preserve clean upgrade paths to:
- **v1.3.0** LCP Daemon (JSON-RPC + MCP Server) — `watch` uses a swappable `Daemon` class
- **v1.4.0** Full Flatline Sentinel — `sentinel.md` format is fixed; only the response action changes
- **v1.5.0** S:H Matrix Telemetry — every event carries `user` field and `schema_version: 1`
- **v2.0.0** Pulse Sync / Team Tier — `synlynk status --json` output is stable and versioned; `config.json` reserves `org`, `team`, `sync_endpoint` keys

---

## Section 1: Template Fixes

### Problem
The `TEMPLATES` dict in `synlynk.py` writes minimal stubs. `SYNLYNK_GUIDE.md` has the correct protocol but it is never surfaced to the AI tools.

### Fix
Rewrite all four templates to embed the full session protocol. `SYNLYNK_GUIDE.md` remains the canonical human reference; the per-tool templates are curated implementations of it.

`synlynk init` skips existing template files by default (current behaviour retained). Add `synlynk init --force` to overwrite templates in existing projects — needed for upgrading template content after a `synlynk upgrade`.

### Template content (all tool templates)

**CLAUDE.md and GEMINI.md** (tool-native hooks, auto-read at session start):
```markdown
# synlynk Instructions

## Session Start (every session, no exceptions)
1. Run: `git config user.name` — this is your @username for all attribution
2. Run: `synlynk watch status` — if stopped, run `synlynk watch start`
3. Read: `.synlynk/context.md` — your full project state snapshot
4. Check `.synlynk/sentinel.md` for any active alerts
5. Greet with 3 rows:
   - Row 1: Last task YOU completed [by @username] — from your devlog entry
   - Row 2: Your next active task — from project-docs/todo.md
   - Row 3 (team mode): Last 1 entry per teammate from project-docs/devlogs/

## During the session
- Mark tasks `[x]` in project-docs/todo.md when complete — do NOT delete them
- Append decisions to project-docs/memory.md with [@username] attribution
- Run `synlynk checkpoint` at every task boundary
- In team mode: always `git pull` before editing any project-docs file
- Log costs in project-docs/costs.md after each significant AI operation

## At session end
- Append a summary entry to project-docs/devlogs/<username>.md
- Run `synlynk checkpoint` one final time
- Run `synlynk status` and include the output in your closing message
```

**AI_INSTRUCTIONS.md** (universal — for tools without a native hook):
Same protocol as above, prefixed with: "Apply the following as your system prompt or custom instructions before starting any session in this repository."

**.cursorrules** (Cursor — character-limited):
```
Read .synlynk/context.md at session start. Mark tasks [x] in project-docs/todo.md when done. Run `synlynk checkpoint` at task boundaries. Attribute all project-docs edits with [@username].
```

---

## Section 2: Context Compaction

### Problem
`generate_context()` reads all files in full. As the project grows, `context.md` grows unboundedly, increasing token cost and reducing signal-to-noise.

### Fix
Implement the "Active vs. Archive" model already defined in `project-docs/memory.md`.

### What `generate_context(scope="full")` includes

```
# synlynk Context Snapshot
Generated: <timestamp> | User: <username> | Mode: single|team

## ⚠️ Sentinel Alerts        ← from .synlynk/sentinel.md; section omitted if empty

## Active Tasks               ← todo.md lines matching `- [ ]` only
## Roadmap (active)           ← roadmap.md rows where Status is "In Progress" or
                                 targets the current release version
## Decisions                  ← project-docs/memory.md full (already curated)
## Recent Devlog              ← last 7 days of entries from devlogs/<username>.md
## Teammate Activity          ← (team mode) last 1 entry per teammate devlog
```

### What is excluded
- `[x]` completed task lines from todo.md
- Devlog entries older than 7 days
- `devlogs/archive/` directory entirely

### Scope parameter (future sub-agent routing)
```python
generate_context(scope="full")           # default
generate_context(scope="task:N")         # stub — logs warning, falls back to full
                                         # v1.3.0 implements scoped context slices
```

The `scope` parameter is wired into the function signature now. The `"task:N"` path is a documented no-op stub with a `# TODO(v1.3.0)` comment.

---

## Section 3: `synlynk watch`

### Command interface
```bash
synlynk watch start    # daemonize, write PID to .synlynk/watch.pid
synlynk watch stop     # kill PID, remove pidfile
synlynk watch status   # print: running/stopped + uptime + last trigger file
```

### Daemon behavior
- Polls `project-docs/` every **30 seconds** (default) using `os.path.getmtime`
- **3-second settle window (debounce):** on change detected, waits 3 seconds before regenerating context — handles burst writes where AI edits multiple files in quick succession
- On regeneration: calls `generate_context()`, emits telemetry event, calls `set_state("watching")`
- Daemonizes via double-fork (macOS/Linux); documented limitation on Windows
- Stdout/stderr → `.synlynk/watch.log`
- `watch_interval_seconds` configurable in `.synlynk/config.json` (default: 30)

### Daemon class (LCP upgrade path)
```python
class Daemon:
    def start(self): ...      # double-fork, write pidfile, enter poll loop
    def stop(self): ...       # read pidfile, kill, remove pidfile
    def status(self): ...     # check pidfile + PID liveness
    def on_change(self, filepath): ...  # override in LCP daemon (v1.3.0)
```
The LCP daemon subclasses `Daemon`, overrides `on_change()` to emit a JSON-RPC event. Command surface (`watch start/stop/status`) stays identical.

### Lifecycle guards
- `watch start` checks for existing pidfile, verifies PID is alive, cleans stale pidfiles automatically
- `watch stop` is idempotent — safe when already stopped

### AI instruction
> "At session start, run `synlynk watch status`. If stopped, run `synlynk watch start` before proceeding."

---

## Section 4: `synlynk checkpoint`

### What it does (in order)
1. Resolve `@username` from `git config user.name`
2. Scan `todo.md` for `[x]` lines — collect as "completed this checkpoint"
3. Append completed tasks to `devlogs/<username>.md` as a timestamped "Completed" block
4. Strip `[x]` lines from `todo.md` — active file stays clean
5. Scan `devlogs/<username>.md` — move entries older than 30 days to `devlogs/archive/YYYY-MM.md`
6. Call `generate_context(scope="full")`
7. Emit telemetry event (see schema below)
8. Call `set_state("watching")` (or `"stopped"` if watcher not running)
9. Print 3-line summary to stdout

### Output
```
✓ checkpoint [@nikhil] — 2 tasks archived, context refreshed
  Archived: "Implement synlynk watch" · "Fix token extraction"
  Budget: $1.24 used / $10.00 limit (12%)  ·  18 requests
```

Budget line reads from `costs.md` column 6 (`| Cost (USD) |`, zero-indexed) and `config.json` limits — not from stdout regex. Parser skips the header row and any row where column 6 is empty or non-numeric.

### Idempotency
Running checkpoint with no `[x]` tasks is a no-op. Safe to call multiple times per session.

### Telemetry event schema
```json
{
  "type": "checkpoint",
  "schema_version": 1,
  "timestamp": "2026-05-17 14:23:01",
  "user": "nikhilsoman",
  "completed_task_count": 2,
  "completed_task_ids": ["11", "12"],
  "devlog_entry_appended": true
}
```

`completed_task_ids` parsed from `<!-- id: N -->` markers already in the todo.md template. Used by S:H Matrix (v1.5.0) to correlate tasks to git commits.

---

## Section 5: `synlynk status`

### Human output (`synlynk status`)
```
─────────────────────────────────────────
 synlynk status · @nikhilsoman · team mode
─────────────────────────────────────────
 ACTIVE TASKS (3)
   [ ] Implement synlynk watch daemon         #11
   [ ] Fix generate_context compaction        #12
   [ ] Rewrite CLAUDE.md template             #13

 LAST CHECKPOINT
   @nikhilsoman · 2026-05-17 14:23 · 2 tasks archived

 SENTINEL
   ✓ No alerts

 BUDGET
   $1.24 / $10.00 (12%)  ·  18 requests / 100 limit

 WATCHER
   ● Running since 09:14  ·  last trigger 14:21 (devlogs/nikhil.md)

 TEAMMATES  (team mode only)
   @sara    · last active 2026-05-17 11:02
   @alex    · last active 2026-05-16 18:45
─────────────────────────────────────────
```

### Machine-readable output (`synlynk status --json`)
```json
{
  "schema_version": 1,
  "timestamp": "2026-05-17T14:30:00",
  "user": "nikhilsoman",
  "mode": "team",
  "active_tasks": [{ "id": "11", "text": "Implement synlynk watch daemon" }],
  "last_checkpoint": { "user": "nikhilsoman", "timestamp": "...", "tasks_archived": 2 },
  "sentinel": { "alerts": [] },
  "budget": { "used_usd": 1.24, "limit_usd": 10.00, "requests": 18, "limit_requests": 100 },
  "watcher": { "running": true, "started_at": "...", "last_trigger_file": "devlogs/nikhil.md" },
  "teammates": [{ "user": "sara", "last_active": "2026-05-17T11:02:00" }]
}
```

### Data sources (all local, no AI needed)
| Field | Source |
|---|---|
| Active tasks | `todo.md` `[ ]` lines |
| Last checkpoint | Last `checkpoint` event in `telemetry.json` |
| Budget | Sum of cost column in `costs.md` vs limits in `config.json` |
| Watcher | `.synlynk/state` file |
| Teammates | Most recent `## YYYY-MM-DD` heading in each `devlogs/<user>.md` |
| Sentinel | `.synlynk/sentinel.md` |

### Exit codes
- `0` — healthy
- `1` — sentinel active or budget exceeded

CI-composable: a pre-commit hook or CI step can gate on `synlynk status`.

### AI instruction
> "Run `synlynk status` at session end and include the output in your closing message."

---

## Section 6: Sentinel Fix

### Problem
Flatline alerts print to stdout and disappear. The AI never sees them mid-session.

### Fix
Write alerts to `.synlynk/sentinel.md` (append-only during session). `generate_context()` includes this file at the top of `context.md` — the AI sees any active alert on the next context read.

### sentinel.md format
```markdown
# Sentinel Alerts
- [2026-05-17 14:05] FLATLINE: `npm test` failed 3x in a row [@nikhilsoman]
```

### Alert lifecycle
- Written by `check_flatline()` on trigger
- `synlynk checkpoint` clears alerts older than 1 hour with no recurrence
- Full Tier (v1.4.0) adds SIGINT response — `sentinel.md` format stays identical

---

## Section 7: `synlynk upgrade` Fix

### Fix
Replace the stub with a real GitHub releases API check:
```
GET https://api.github.com/repos/nikhilsoman/synlynk/releases/latest
```
- Compare `tag_name` against `VERSION` constant
- If newer: download new `synlynk.py` to temp path, replace current binary, print changelog URL
- Uses `urllib.request` — stdlib only
- Fails gracefully with clear message if offline or rate-limited

---

## Section 8: Token Tracking Fix

### Problem
`extract_tokens()` regex patterns don't match real AI CLI output. Budget Pulse always shows $0.0000, eroding trust in the tool.

### Fix
- Remove `extract_tokens()` entirely
- AI is already instructed to write `costs.md` entries — this is the authoritative source
- `synlynk checkpoint` and `synlynk status` sum the cost column from `costs.md`
- `synlynk exec` retains timing and exit code telemetry but stops estimating cost
- If `costs.md` hasn't been updated in the current session, `exec` prints: `⚠ costs.md not updated this session — AI may have missed logging`

---

## Section 9: Terminal Title State Indicator

### State model
Three states written to `.synlynk/state` and reflected in the terminal title bar:

| State | Icon | Title | Triggered by |
|---|---|---|---|
| `watching` | `●` | `● synlynk: watching · <project>` | `watch start`, end of `checkpoint`/`exec` with watcher running |
| `active` | `⚡` | `⚡ synlynk: active · <project>` | Start of `exec`, `checkpoint`, watch context regen |
| `stopped` | `○` | `○ synlynk: stopped · <project>` | `watch stop`, watcher crash, post-`init` before first `watch start` |

### Implementation
```python
def set_state(state: str):
    icons = {"watching": "●", "active": "⚡", "stopped": "○"}
    with open(".synlynk/state", "w") as f:
        f.write(state)
    if sys.stdout.isatty():
        project = os.path.basename(os.getcwd())
        title = f"{icons[state]} synlynk: {state}  ·  {project}"
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()
```

- TTY check ensures ANSI escapes are skipped in CI/piped environments
- `.synlynk/state` is always written regardless of TTY — `synlynk status` reads it as the single source of truth for watcher state
- Works in iTerm2, Terminal.app, tmux, and any ANSI-compatible terminal

---

## `config.json` Schema (v1)

```json
{
  "schema_version": 1,
  "budget": {
    "limit_usd": 10.00,
    "limit_requests": 100
  },
  "watch_interval_seconds": 30,
  "org": null,
  "team": null,
  "sync_endpoint": null
}
```

`org`, `team`, `sync_endpoint` are reserved for Pulse Sync (v2.0.0). Null values are ignored by all lite-tier code.

---

## Telemetry Event Schema (v1)

All events share this base structure:
```json
{
  "type": "<event_type>",
  "schema_version": 1,
  "timestamp": "YYYY-MM-DD HH:MM:SS",
  "user": "<git_username>"
}
```

Event-specific fields added per type: `checkpoint` (above), `watch_trigger` (`changed_file`), `exec` (`command`, `duration`, `exit_code`), `sentinel` (`command`, `failure_count`).

Telemetry capped at 100 entries (existing behaviour retained).

---

## Files Changed

| File | Change |
|---|---|
| `bin/synlynk.py` | All changes — new commands, fixed functions, new `Daemon` class, `set_state()` |
| `.synlynk/config.json` | Schema v1 with new fields (generated by `init`) |
| `.synlynk/sentinel.md` | New file, written by `check_flatline()` |
| `.synlynk/state` | New file, written by `set_state()` |
| `devlogs/archive/` | New directory, written by `checkpoint` |

No new Python dependencies. No changes to `install.sh`.

---

## Out of Scope (this release)

- LCP Daemon / JSON-RPC (v1.3.0)
- Full Flatline Sentinel with SIGINT (v1.4.0)
- S:H Matrix git diff velocity (v1.5.0)
- Pulse Sync team aggregation (v2.0.0)
- Claude Code statusline integration (deferred — terminal title covers all tools)
- Windows support for daemon (documented limitation)
