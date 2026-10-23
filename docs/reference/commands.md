# Command Reference

Generated from `synlynk/taxonomy.py`. Do not edit by hand — run `python3 scripts/generate_command_docs.py`.

Start with the [documentation hub](../README.md), the [10-minute quickstart](../quickstart.md), or a [task-oriented how-to](../how-to/README.md).

See [safe-caller-construction.md](safe-caller-construction.md) for guidance on building dispatch task text programmatically.

## Orientation gateway (always available)

- `governs` — visualize
- `preflight` — open
- `status` — visualize
- `watch` — visualize
- `viz` — visualize

## Tier 0 — First-Time Setup

- `home` (primary) — open
- `init` (primary) — open
- `start` (primary) — open
- `quickstart` (primary) — open
- `brainstorm` (primary) — goal
- `brief` (primary) — visualize
- `tool install` (secondary) — open
- `scan` (primary) — open
- `join` (primary) — open
- `migrate` (secondary) — sustain
- `configure agent` (secondary) — open
- `harness add` (secondary) — open
- `harness configure` (secondary) — open
- `harness list` (secondary) — open
- `config set` (secondary) — open
- `config nudges` (secondary) — open
- `whoami` (secondary) — open

## Tier 1 — Goal

- `pack` (primary) — execute
- `impact` (primary) — execute
- `mesh` (primary) — open
- `spike eval` (secondary) — sustain
- `backup create` (secondary) — sustain
- `backup verify` (secondary) — sustain
- `backup encrypt` (secondary) — sustain
- `backup package` (secondary) — sustain
- `backup verify-encrypted` (secondary) — sustain
- `state inventory` (secondary) — sustain
- `state promote` (secondary) — sustain
- `state quarantine` (secondary) — sustain
- `state restore` (secondary) — sustain
- `state register` (secondary) — sustain
- `decide` (primary) — goal
- `goal create` (primary) — goal
- `goal list` (primary) — goal
- `session open` (primary) — sustain
- `session status` (primary) — sustain
- `session checkpoint` (secondary) — sustain
- `session close` (secondary) — sustain
- `goal link` (primary) — goal
- `goal status` (primary) — goal
- `goal update` (primary) — goal
- `story create` (primary) — goal
- `story list` (primary) — goal
- `story ready` (secondary) — goal
- `story draft` (secondary) — goal
- `story done` (secondary) — goal
- `story reclaim` (secondary) — goal
- `story claim` (secondary) — goal
- `backlog capture` (secondary) — open
- `backlog list` (secondary) — open
- `backlog sync` (secondary) — open
- `backlog ingest` (secondary) — open
- `backlog triage` (primary) — open
- `backlog auto-promote` (secondary) — open
- `roadmap add` (secondary) — sustain
- `open` (primary) — open
- `launch` (primary) — open
- `roles` (secondary) — open
- `type create` (secondary) — execute
- `type seed` (secondary) — execute
- `type relabel` (secondary) — execute
- `connector add` (secondary) — execute
- `fleet list` (secondary) — open
- `fleet apply` (secondary) — open

## Tier 2 — Execute

- `swarm dispatch` (primary) — execute
- `swarm status` (secondary) — visualize
- `swarm destroy` (secondary) — execute
- `media generate` (secondary) — sustain
- `models list` (secondary) — sustain
- `models show` (secondary) — sustain
- `models discover` (secondary) — sustain
- `heal` (primary) — sustain
- `dispatch` (primary) — execute
- `backfill-capability-ratings` (secondary) — execute
- `charters adapt` (secondary) — sustain
- `jobs` (primary) — execute
- `jobs handoff` (secondary) — execute
- `jobs reap` (secondary) — execute
- `jobs reconcile` (secondary) — execute
- `jobs cleanup-resolve` (secondary) — execute
- `gc` (secondary) — sustain
- `schedule` (primary) — execute
- `tpm sweep` (primary) — execute
- `pm sweep` (primary) — execute
- `tpm wake` (primary) — execute
- `pm wake` (primary) — execute
- `governs sweep` (primary) — sustain
- `release` (primary) — release
- `marketing ceremony` (secondary) — release
- `marketing sync-pr` (secondary) — release
- `pr check` (primary) — release
- `provenance attest` (secondary) — sustain
- `gh` (primary) — execute
- `pr gate-status` (secondary) — release
- `policy check-merge` (secondary) — release
- `policy show` (secondary) — sustain
- `policy sync-branch-protection` (secondary) — sustain
- `policy gate-status` (secondary) — sustain
- `ops report` (primary) — sustain
- `doctor` (secondary) — sustain
- `probe` (secondary) — sustain
- `worktree audit` (secondary) — sustain
- `worktree clean` (secondary) — sustain
- `audit-docs` (secondary) — sustain
- `exec` (secondary) — execute
- `tui` (secondary) — execute
- `logs` (secondary) — execute
- `shell` (secondary) — execute
- `sentinel list` (secondary) — execute
- `sentinel clear` (secondary) — execute
- `cost log` (secondary) — sustain
- `cost true-up` (secondary) — sustain
- `cost billing` (secondary) — sustain
- `cost audit reconcile` (secondary) — sustain
- `cost audit import` (secondary) — sustain
- `cost audit report` (secondary) — sustain
- `cost audit correct` (secondary) — sustain
- `credit grant` (secondary) — sustain
- `quota` (secondary) — sustain
- `quota advisory` (secondary) — sustain
- `quota calibrate` (secondary) — sustain
- `quota federated` (secondary) — sustain
- `testbed` (secondary) — execute
- `capability sweep` (secondary) — sustain
- `capability report` (secondary) — sustain
- `capability backfill` (secondary) — sustain
- `capability export-pack` (secondary) — sustain
- `run` (primary) — execute
- `run --trio` (secondary) — execute
- `local doctor` (secondary) — sustain
- `local pilot status` (secondary) — sustain
- `local pilot review-start` (secondary) — sustain
- `local pilot record-review` (secondary) — sustain
- `local pilot resume` (secondary) — execute
- `upgrade` (secondary) — sustain
- `rollback` (secondary) — sustain
- `uninstall` (secondary) — sustain
- `relay status` (secondary) — visualize
- `relay send` (secondary) — execute
- `relay tail` (secondary) — visualize
- `relay hub init` (secondary) — sustain
- `relay hub connect` (secondary) — sustain
- `relay device add` (secondary) — sustain
- `relay device revoke` (secondary) — sustain
- `relay subscribe` (secondary) — sustain
- `relay unsubscribe` (secondary) — sustain
- `autonomy show` (primary) — sustain
- `autonomy set` (primary) — sustain
- `concierge synthesize` (primary) — goal
- `addon list` (secondary) — sustain
- `addon install` (primary) — sustain
- `gateway probe` (primary) — sustain
- `gateway dispatch` (primary) — execute

### Resolve aged cleanup uncertainty

Use `jobs cleanup-resolve` only when a job remains `cleanup_unverified` after
its persisted cleanup deadline and an operator has independently accepted the
risk that a descendant process may still be running:

```shell
synlynk jobs cleanup-resolve job-1234 \
  --accept-risk \
  --reason "host reboot independently confirmed"
```

The command rejects unknown jobs, missing acknowledgements, blank reasons, and
requests made before `cleanup_deadline_at` (normally 300 seconds after an
unverified cleanup). On success it appends the OS user, timestamp, and reason to
the lifecycle audit, sets `process_state` to `cleanup_overridden`, and releases
the job's capacity reservation atomically. This is an explicit risk override:
it does not claim `stopped_verified` and does not change the independent effect
state.

## Tier 3 — Team / Enterprise

- `workspace add-repo` (primary) — open
- `team status` (primary) — notify
- `sync` (primary) — sustain
- `score add` (secondary) — sustain
- `score list` (secondary) — sustain
- `score attest` (secondary) — sustain
- `board propose` (primary) — goal
- `board sign` (primary) — goal
- `board show` (secondary) — visualize

## Latent — Autopilot & Hooks Only

- `relay start` — execute
- `relay broadcast` — execute
- `checkpoint` — execute
- `daemon` — sustain
- `identity init` — sustain
- `identity list` — sustain
- `identity show` — open
- `identity whoami` — open
- `identity triplet` — open
- `relay peer list` — sustain
- `relay peer add` — sustain
- `events tail` — sustain
- `repair` — sustain
- `exit` — sustain
- `harness run` — execute
- `instructions status` — sustain
- `instructions diff` — sustain
- `instructions update` — sustain
- `instructions ack` — sustain
- `instructions register` — sustain
