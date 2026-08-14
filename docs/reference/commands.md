# Command Reference

Generated from `synlynk/taxonomy.py`. Do not edit by hand — run `python3 scripts/generate_command_docs.py`.

See [safe-caller-construction.md](safe-caller-construction.md) for guidance on building dispatch task text programmatically.

## Orientation gateway (always available)

- `status` — visualize
- `watch` — visualize
- `viz` — visualize

## Tier 0 — First-Time Setup

- `init` (primary) — open
- `start` (primary) — open
- `scan` (primary) — open
- `join` (primary) — open
- `migrate` (secondary) — sustain
- `configure agent` (secondary) — open
- `agent add` (secondary) — open
- `agent configure` (secondary) — open
- `agent list` (secondary) — open
- `config set` (secondary) — open
- `config nudges` (secondary) — open

## Tier 1 — Goal

- `decide` (primary) — goal
- `goal create` (primary) — goal
- `goal list` (primary) — goal
- `session open` (primary) — sustain
- `session status` (primary) — sustain
- `session checkpoint` (secondary) — sustain
- `session close` (secondary) — sustain
- `goal link` (primary) — goal
- `goal status` (primary) — goal
- `story create` (primary) — goal
- `story list` (primary) — goal
- `story ready` (secondary) — goal
- `story draft` (secondary) — goal
- `story done` (secondary) — goal
- `roadmap add` (secondary) — sustain
- `open` (primary) — open
- `launch` (primary) — open
- `roles` (secondary) — open

## Tier 2 — Execute

- `dispatch` (primary) — execute
- `backfill-capability-ratings` (secondary) — execute
- `jobs` (primary) — execute
- `jobs handoff` (secondary) — execute
- `jobs reap` (secondary) — execute
- `schedule` (primary) — execute
- `release` (primary) — release
- `pr check` (primary) — release
- `ops report` (primary) — sustain
- `doctor` (secondary) — sustain
- `probe` (secondary) — sustain
- `worktree audit` (secondary) — sustain
- `worktree clean` (secondary) — sustain
- `exec` (secondary) — execute
- `tui` (secondary) — execute
- `logs` (secondary) — execute
- `shell` (secondary) — execute
- `sentinel list` (secondary) — execute
- `sentinel clear` (secondary) — execute
- `cost log` (secondary) — sustain
- `credit grant` (secondary) — sustain
- `quota` (secondary) — sustain
- `capability sweep` (secondary) — sustain
- `run --trio` (secondary) — execute
- `local doctor` (secondary) — sustain
- `upgrade` (secondary) — sustain
- `rollback` (secondary) — sustain

## Tier 3 — Team / Enterprise

- `team status` (primary) — notify
- `sync` (primary) — sustain
- `score add` (secondary) — sustain
- `score list` (secondary) — sustain
- `score attest` (secondary) — sustain

## Latent — Autopilot & Hooks Only

- `relay start` — execute
- `relay broadcast` — execute
- `checkpoint` — execute
- `daemon` — sustain
- `identity init` — sustain
- `identity list` — sustain
- `events tail` — sustain
- `repair` — sustain
- `exit` — sustain
- `agent run` — execute
- `instructions status` — sustain
- `instructions diff` — sustain
- `instructions update` — sustain
- `instructions ack` — sustain
