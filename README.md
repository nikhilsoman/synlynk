# synlynk

**Universal context switchboard for AI-native development.**

synlynk is a single-file Python CLI that wraps AI tools (Claude Code, Gemini CLI, etc.) with automatic project context injection, cost tracking, and hallucination detection — so you can switch between tools and accounts without losing project state.

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

# Check for updates
synlynk upgrade
```

## How it works

`synlynk exec <cmd>` does four things before handing off to your AI tool:

1. Reads `project-docs/memory.md`, `roadmap.md`, and `todo.md`
2. Writes a compacted snapshot to `.synlynk/context.md`
3. Checks your cost/request budget against limits in `.synlynk/config.json`
4. Detects flatline loops — 3 consecutive failures of the same command trigger a sentinel alert

## Commands

| Command | Description |
| --- | --- |
| `synlynk init` | Bootstrap `project-docs/` and AI instruction files in the current repo |
| `synlynk exec <cmd>` | Run any AI CLI with context injection and telemetry |
| `synlynk upgrade` | Check GitHub releases for a newer version |
| `synlynk --version` | Print current version |

## Project layout

```
project-docs/
  roadmap.md        # Feature priorities and status
  todo.md           # Active tasks ([ ] / [x] checkboxes with <!-- id: N --> comments)
  memory.md         # Persistent decisions and conventions
  costs.md          # Per-session cost log (manually maintained)
  devlogs/          # Per-user session notes

.synlynk/
  context.md        # Auto-generated snapshot (overwritten each exec)
  config.json       # Budget limits and settings
  telemetry.json    # Rolling log of last 100 exec events
```

## Configuration

`.synlynk/config.json` is created by `synlynk init` with these defaults:

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

## Session protocol

`synlynk init` writes `CLAUDE.md`, `GEMINI.md`, and `AI_INSTRUCTIONS.md` to your repo root. These instruct each AI tool to read `.synlynk/context.md` at the start of every session, keep `project-docs/` updated, and log costs.

## Cost estimation

Costs are logged to `project-docs/costs.md` by the AI agent during sessions. The telemetry tracks exec count, duration, and exit code. Budget warnings fire at 80% of configured limits.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
