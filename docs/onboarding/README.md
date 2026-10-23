# Synlynk Onboarding Guide

Welcome to Synlynk — the neutral control plane that routes coding tasks across AI vendors and local models, then proves the result. This guide gets a new collaborator from zero to first dispatch.

## Prerequisites

- **Python 3.10+** — `python3 --version`
- **Git** — `git --version`
- **`pipx` or `uv`** — isolated install (either works; `pipx` is the default recommendation):
  ```bash
  brew install pipx && pipx ensurepath   # macOS
  # Linux: pip install --user pipx && pipx ensurepath
  ```

## 1. Install Synlynk

```bash
# From PyPI (isolated, recommended)
pipx install git+https://github.com/nikhilsoman/synlynk

# One-liner installer (verifies Python, handles fallback)
curl -fsSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | bash

# Contributor / checkout mode — no install needed
python3 bin/synlynk.py --version
```

Verify:

```bash
synlynk --version
synlynk doctor          # health check
```

Requirements: Python 3.10+, stdlib only — zero required external dependencies.

## 2. Clone the Project

```bash
git clone https://github.com/nikhilsoman/synlynk.git
cd synlynk
```

## 3. Configure Git Identity (required)

Synlynk identifies you via `git config user.name` / `user.email`. Without it, `join` will fail.

```bash
git config user.name "Your Name"
git config user.email "you@example.com"
git config user.name && git config user.email   # verify
```

## 4. Join the Project

Ask the project owner for an invite token, then run from the repository root:

```bash
synlynk join --invite "<paste-invite-here>"
```

What this does:

- Runs `synlynk scan` to build the static source map
- Generates `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `AI_INSTRUCTIONS.md` at the repo root
- Seeds `project-docs/devlogs/<your-username>.md`
- Sets `project-docs/.synlynk_config.json` → `mode: team`
- Writes the shared context used by every execution backend

If no invite flow is configured for the workspace, the owner may have you join via an ad-hoc invite or direct config — ask in that case.

Verify:

```bash
synlynk status              # should show workspace_id and team digest
synlynk team status         # members, in-progress stories, top TODO
synlynk status --json       # machine-readable
cat .synlynk/context.md | head -n 80
ls project-docs/devlogs/
synlynk identity whoami     # 3-tier identity attribution
```

## 5. Run the Relay (stay in sync)

### Local relay (default — no hub needed, events stay on this machine)

```bash
synlynk relay start --daemon    # background
synlynk relay status            # health
synlynk relay tail              # stream events live
```

### Personal hosted relay (only when bridging *your own* machines through a self-hosted NATS hub)

On the hub host (once, by admin):

```bash
synlynk relay hub init --workspace-id personal --config-dir ~/.synlynk/relay
synlynk relay device add desktop --workspace-id personal --config-dir ~/.synlynk/relay
synlynk relay device add laptop --workspace-id personal --config-dir ~/.synlynk/relay
nats-server -c ~/.synlynk/relay/nats.conf
```

On each device — copy the printed `.creds` via a secure channel, `chmod 0600`:

```bash
synlynk relay start --hub --credential-file /path/to/laptop.creds \
  --workspace-id personal --hub-url nats://<hub-host>:4222
# Hub bridging is foreground-only; --hub --daemon is rejected.
```

Subscribe filters (restart bridge after changing):

```bash
synlynk relay subscribe 'job.>'
synlynk relay subscribe 'sentinel.>'
```

See [Personal hosted relay](../personal-hosted-relay.md) for full details, limits, and verification steps.

### P2P mesh (alternative to hub)

```bash
synlynk relay peer list
synlynk relay peer add --help
```

## 6. Daily Workflow

```bash
git pull                        # always pull before touching project-docs
synlynk jobs                    # running jobs
synlynk jobs --all              # including completed / failed
synlynk status                  # workspace health, goals, burn rate
synlynk watch                   # live HUD
```

## How Work Is Assigned

Synlynk uses **GitHub Issues + Synlynk dispatches** together:

1. **Owner creates a GitHub Issue** — labelled, assigned to you. For a multi-task epic, a parent tracking Issue holds Intent / Context / Associated Tickets & PRs, with child Issues per task.

2. **Owner dispatches it via Synlynk** — creates an isolated worktree + job + cost entry:

   ```bash
   # Auto-routed by capability policy
   synlynk dispatch --task "Implement X — verify with pytest tests/test_x.py -v" --issue 1234

   # Explicit harness + role (recommended for onboarding)
   synlynk dispatch codex --as-agent dev --task "Implement X — verify with ..." --issue 1234

   # Dry-run first to sanity-check what would be sent (no job/worktree created)
   synlynk dispatch --task "$TASK_VAR" --dry-run
   ```

   Dispatch injects `.synlynk/context.md` into the agent session automatically.

3. **You work in the isolated worktree** (e.g. `../synlynk-worktrees/job-xxxx`), push a branch, open a PR. Branch naming: `feat/<id>-<slug>` or `fix/<slug>`. Never commit directly to `main` — the pre-commit hook blocks it; use a linked worktree (`git worktree add ../feat+<name> feat/<agent-prefix>/<name>`).

4. **Review gate** — a non-authoring agent reviews the PR *from within the PR's worktree*:

   ```bash
   synlynk pr check                    # auto-detects PR via git/gh context
   synlynk policy check-merge --role qa   # must pass before merge
   ```

   The reviewer alone merges; the author never self-merges (`merge_authority` enforced via `.synlynk/policy.json`).

5. **Tracking & reassignment:**

   ```bash
   synlynk jobs --stalled            # jobs awaiting handoff
   synlynk jobs handoff <job-id>     # move a stalled job to another harness
   synlynk story list                 # stories from state.db
   synlynk story claim <story-id>    # interactive claim
   synlynk goal status               # goal rollup
   ```

6. **Source of truth** — `state.db` (SQLite WAL) + `.synlynk/` is canonical; `project-docs/todo.md`, `roadmap.md`, `costs.md`, `memory.md` are write-through backups. Do not hand-edit `todo.md` — use `synlynk story create/done` and `synlynk checkpoint` instead. Costs are auto-captured per dispatch; for manual/PM work run `synlynk cost log --pr <n> --harness <harness>`.

## Quick Reference

| Command | Purpose |
|---|---|
| `synlynk quickstart` | 10-minute guided setup → first dispatch |
| `synlynk init --wizard` | Interactive FTUE wizard |
| `synlynk scan` | Build / update static source map |
| `synlynk dispatch --task "..." --issue N` | Dispatch a task |
| `synlynk jobs` / `synlynk jobs --all` | Inspect jobs |
| `synlynk logs --job <id>` | Tail a job's output |
| `synlynk status` / `synlynk team status` | Workspace & team health |
| `synlynk doctor` | Diagnostic health checks |
| `synlynk relay start --daemon` | Start local relay |
| `synlynk relay status` / `synlynk relay tail` | Relay health / event stream |

Further reading: [10-minute quickstart](../quickstart.md) · [Task-oriented how-tos](../how-to/README.md) · [Command reference](../reference/commands.md) · [Agent vs harness glossary](../glossary-agent-vs-harness.md)
