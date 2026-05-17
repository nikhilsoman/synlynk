# synlynk

**Keep your AI tools in sync with your project.**

synlynk is a single-file Python CLI that injects project context into AI tool sessions, tracks costs, and detects hallucination loops. It maintains a shared `project-docs/` directory that every AI tool reads at session start — so switching between Claude Code, Gemini CLI, or Cursor doesn't lose your task state, decisions, or progress.

## Install

```bash
curl -sSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | bash
```

Or run directly without installing:

```bash
python3 bin/synlynk.py <command>
```

**Requirements:** Python 3.8+, stdlib only — no dependencies.

## Quick start

```bash
# Initialize synlynk in your repo
synlynk init

# Run an AI CLI with context automatically injected
synlynk exec claude
synlynk exec gemini

# Archive completed tasks and refresh context
synlynk checkpoint

# Show project state
synlynk status
```

## How it works

`synlynk exec <cmd>` does four things before handing off to your AI tool:

1. Reads `project-docs/memory.md`, `roadmap.md`, and `todo.md`
2. Writes a compacted snapshot to `.synlynk/context.md` — active tasks only, no completed items
3. Checks cumulative spend and request count against limits in `.synlynk/config.json`
4. After the session ends: detects flatline loops (3 consecutive failures of the same command) and writes alerts to `sentinel.md`

The AI tool is instructed (via `CLAUDE.md` / `GEMINI.md`) to read `context.md` at session start and to log costs manually to `project-docs/costs.md`. synlynk does not capture token usage automatically — cost tracking depends on the AI agent following the session protocol.

## Commands

| Command | Description |
| --- | --- |
| `synlynk init [--force]` | Bootstrap `project-docs/` and AI instruction files |
| `synlynk exec <cmd>` | Run any AI CLI with context injection and telemetry |
| `synlynk watch start\|stop\|status` | Background daemon that regenerates `context.md` when files change (Unix only) |
| `synlynk checkpoint` | Archive completed `[x]` tasks to devlog, refresh context, emit telemetry |
| `synlynk status [--json]` | Dashboard: active tasks, budget, sentinel alerts, watcher state |
| `synlynk upgrade` | Check GitHub releases for a newer version |
| `synlynk --version` | Print current version |

> **Note:** `synlynk watch` uses `os.fork()` and requires macOS or Linux.

## Project layout

```
project-docs/
  roadmap.md        # Feature priorities and status
  todo.md           # Active tasks ([ ] / [x] checkboxes with <!-- id: N --> comments)
  memory.md         # Persistent decisions and conventions
  costs.md          # Per-session cost log (maintained by the AI agent)
  devlogs/          # Per-user session notes (appended by checkpoint)

.synlynk/
  context.md        # Auto-generated snapshot (overwritten each exec/watch cycle)
  config.json       # Budget limits and settings
  telemetry.json    # Rolling log of last 100 exec/checkpoint/watch events
  state             # Current state: watching | active | stopped
  sentinel.md       # Flatline alerts
  watch.pid         # Watcher daemon PID (present only while running)
  watch.log         # Watcher daemon stdout/stderr
```

## Configuration

`.synlynk/config.json` (created by `synlynk init`):

```json
{
  "schema_version": 1,
  "budget": { "limit_usd": 10.0, "limit_requests": 100 },
  "watch_interval_seconds": 30,
  "org": null,
  "team": null,
  "sync_endpoint": null
}
```

`org`, `team`, and `sync_endpoint` are reserved for a future team sync feature and have no effect in the current version.

## Session protocol

`synlynk init` writes `CLAUDE.md`, `GEMINI.md`, and `AI_INSTRUCTIONS.md` to your repo root. At session start, the AI tool is instructed to:

1. Run `synlynk watch status` — start the watcher if stopped
2. Read `.synlynk/context.md` for full project state
3. Check `.synlynk/sentinel.md` for any active alerts
4. Report: last completed task, next active task, and (in team mode) recent teammate activity

At session end: append a devlog entry and run `synlynk checkpoint`.

## Budget tracking

synlynk warns at 80% of configured cost and request limits. Spend is read from `project-docs/costs.md`, which the AI agent is expected to update after each significant operation. The `exec` telemetry records duration and exit code but does not capture token counts automatically.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

---

## Roadmap

synlynk is early-stage and community feedback will shape its direction. Below is the broad vision across three horizons.

### Solo edition (current focus)

The goal is to make a single developer with multiple AI tools feel like they have one consistent co-pilot across all of them — no repeated context-setting, no lost state between sessions or quota resets.

Near-term priorities:
- Automatic token/cost capture from AI CLI output (removing the manual step)
- Scoped context slices — inject only the tasks and decisions relevant to the current file or feature, not the whole project
- Shell integration improvements — seamless alias setup, tab completion

### Team edition (next)

Extend synlynk to shared projects where multiple developers are using AI tools concurrently. The core challenge is keeping `project-docs/` consistent without merge conflicts while each developer's AI tool writes decisions, devlog entries, and task completions.

Areas of interest:
- Lightweight sync mechanism for `project-docs/` across team members (pull-before-write, conflict detection)
- Shared telemetry aggregation — team-wide cost and usage visibility
- Attribution enforcement — decisions and task completions tagged to the right developer

### Enterprise edition (future)

For organisations running AI tools across many teams, repositories, and accounts.

Areas of interest:
- Org-level budget and policy enforcement
- Centralised audit log of AI operations across repos
- SSO and role-based access to shared project state
- Self-hosted sync endpoint

---

**We're looking for community input on what to build next.** See the [Discussions](../../discussions) tab to vote on feature direction and share use cases.
