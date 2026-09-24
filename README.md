<p align="center">
  <img src="docs/img/logo/lockup.svg" alt="synlynk — keep your AI tools in sync" height="80">
</p>

<p align="center"><strong>Keep your AI tools in sync with your project.</strong></p>
<p align="center"><a href="https://synlynk.com">synlynk.com</a></p>

<p align="center">
  <a href="https://github.com/nikhilsoman/synlynk"><img src="https://img.shields.io/badge/tests-3213%20collected-brightgreen" alt="Tests"></a>
  <a href="https://github.com/nikhilsoman/synlynk"><img src="https://img.shields.io/badge/version-0.22.0-blue" alt="Version"></a>
  <a href="https://github.com/nikhilsoman/synlynk"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://github.com/nikhilsoman/synlynk"><img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python"></a>
</p>

synlynk is a Python CLI that turns your terminal into a hybrid workgroup — one human, multiple AI harnesses, shared project state. It injects scoped project context into every dispatch, routes tasks to the best available harness using a live capability ledger, and tracks costs and hallucination loops. A shared `project-docs/` directory keeps every tool in sync: Claude Code, Codex, and AGY all read the same context, decisions, and progress.

**v0.22.0:** Frontier QA acceptance and multi-node soak testbed, cross-workspace Vizor background daemon, defensive worktree sandbox migration resilience, and concurrent schema state isolation, with 3213 tests collected.

## Documentation

| | | |
|:---:|:---:|:---:|
| [![Official Reference](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/site/src/assets/img/docs/synlynk-official-reference-thumb.png)](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-official-reference.pdf) | [![Command Reference](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/site/src/assets/img/docs/synlynk-command-reference-thumb.png)](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-command-reference.pdf) | [![Quick Start Guide](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/site/src/assets/img/docs/synlynk-quickstart-guide-thumb.png)](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-quickstart-guide.pdf) |
| **[Official Reference](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-official-reference.pdf)** | **[Command Reference](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-command-reference.pdf)** | **[Quick Start Guide](https://raw.githubusercontent.com/nikhilsoman/synlynk/main/docs/synlynk-quickstart-guide.pdf)** |
| 14-page full reference: architecture, all commands, agent profiles, relay, SQLite schema, changelog | 9-page command catalog: flags, options, usage scenarios | 5-page getting started: install, init, dispatch, invite |

## Install

**Recommended Method (via pipx):**
```bash
pipx install git+https://github.com/nikhilsoman/synlynk
```

**Run directly without installing (contributor / checkout mode):**
```bash
python3 bin/synlynk.py <command>
```

**Requirements:** Python 3.9+, stdlib only — no dependencies.

## Quick start

Get up and running in 60 seconds:

1. **Install synlynk globally:**
   ```bash
   pipx install git+https://github.com/nikhilsoman/synlynk
   ```

2. **Initialize your project:**
   Runs the interactive FTUE wizard to discover installed AI agent CLI tools, configure workspace topology, and bootstrap project state.
   ```bash
   synlynk init --wizard
   ```

3. **Analyze repository structure:**
   Scans the codebase to build and update the static source map.
   ```bash
   synlynk scan
   ```

4. **Migrate existing flat-file projects (optional):**
   If you have a project created using an older version of synlynk, migrate its `project-docs/` markdown files to `state.db`.
   ```bash
   synlynk migrate
   ```

5. **Dispatch a task to an agent in the background:**
   ```bash
   synlynk dispatch claude --task "refactor auth module"
   ```
   `--task` must be a non-empty string — `dispatch_agent()` fails closed on an empty or whitespace-only task before creating any job, worktree, or cost entry (see [#720](https://github.com/nikhilsoman/synlynk/issues/720))
   If `--task` is built from a shell variable in automation, don't interpolate it unchecked — an unset variable silently expands to an empty string
   Sanity-check what a dispatch would actually send with `--dry-run` first:
   ```bash
   synlynk dispatch claude --task "$TASK_VAR" --dry-run
   ```

   Every dispatched agent is also asked to echo a receipt marker
   (`SYNLYNK_TASK_RECEIVED: <task_sha256>`) as its literal first line of
   output, confirming it received the exact task text before doing any
   work. If a job's log is missing this marker (or prints it late, or with
   the wrong digest) and no corroborating git activity shows up in its
   worktree, Synlynk marks the job `task_delivery_failed` and skips
   auto-finalize/push for that worktree — the files stay in place for
   audit. If real work *did* land despite a missing/late marker, the job
   is not blocked; it's flagged with a non-blocking WARN note instead
   (see #720).

6. **Check running jobs:**
   ```bash
   synlynk jobs
   ```

7. **Tail a job's output:**
   ```bash
   synlynk logs --job <job-id>
   ```

## How it works

At the core of synlynk is a dual-storage model designed for agent speed and Git reliability:

- **`state.db` is the permanent source of truth** for all project state, including stories, roadmaps, memories, devlogs, and costs.
- **`project-docs/` flat files are write-through backups.** Every write to `state.db` automatically updates the corresponding markdown files in `project-docs/` (e.g., `todo.md`, `roadmap.md`, `memory.md`, `costs.md`). This ensures a human-readable, Git-trackable record of project state.
- **`generate_context()` resolves state dynamically.** Once a project is migrated, it reads directly from the SQLite database to compile the current active context. For non-migrated repositories, it falls back to reading raw flat files.
- **`synlynk exec <cmd>` manages context injection.** Before handing off to your AI tool, it compiles the active tasks and decisions, writes a compacted snapshot to `.synlynk/context.md` (active tasks only, no completed items), and checks cumulative spend limits in `.synlynk/config.json`. After the session ends, it detects flatline loops (3 consecutive failures of the same command) and writes alerts to `sentinel.md`.

The AI tool is instructed (via `CLAUDE.md` / `GEMINI.md`) to read `.synlynk/context.md` at session start. Cost tracking is fully automated: `state.db` records costs to the `cost_entries` table, which are written through to `project-docs/costs.md`.

## Commands

Commands are grouped by where you'll reach for them in a typical project lifecycle.

<!-- commands:start -->
<!-- commands:start -->

**Start here:**

- `synlynk home`
- `synlynk init`
- `synlynk start`
- `synlynk scan`
- `synlynk join`
- `synlynk status`
- `synlynk watch`
- `synlynk viz`

Full command reference: [docs/reference/commands.md](docs/reference/commands.md)

<!-- commands:end -->
<!-- commands:end -->
