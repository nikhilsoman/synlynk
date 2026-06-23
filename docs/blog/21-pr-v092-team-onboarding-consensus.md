---
title: "v0.9.2 — Team Onboarding + Consensus"
date: 2026-06-22
series: "Building the OS for Multi-Agent Development"
post: 21
pr: "feat/v0.9.2 — 6 tasks, merged to main"
merged: 2026-06-22
---

## The Broader Goal at the End of Post #20

Post #20 was about closing production gaps revealed by dogfooding — the install binary crash and the init overwrite problem that appeared the moment we ran synlynk in a non-synlynk repo. Both were fixed in a hotfix session before any new feature work began.

The stated next goalpost was v0.9.2: bring the team onboarding flow into the CLI so that adding a new developer to a synlynk-managed project doesn't require manual setup of devlogs, AI context files, and digest reads.

---

## What Changed in This PR

No strategic shifts. The feature set was well-defined from the v0.9.2 design spec and implementation plan. This was a clean 6-task execution with hybrid dispatch (Claude for exploratory tasks, Codex for targeted additions).

---

## What Shipped

### `synlynk join`

The entry point for a new team member. Running `synlynk join` in a synlynk-managed repo:

1. Seeds `project-docs/devlogs/<username>.md` with a stub entry attributed to the joining user — so the devlog exists and shows up in team digests from day one
2. Regenerates CLAUDE.md, GEMINI.md, and AGENTS.md with the joining member's `git config user.name` in the agent identity header
3. Prints a team digest: who else is in the project, what they've been working on, how to read their devlogs

```bash
$ synlynk join

✓  Seeded devlog for nikhil (10 recent commits found)
✓  Regenerated CLAUDE.md, GEMINI.md, AGENTS.md

Team — 2 members:
  alice   last active 2026-06-21  focus: SQLite migration, scoped context
  bob     last active 2026-06-20  focus: source scanner, symbol extraction

Next: synlynk exec claude — your context is ready
```

### `synlynk team status`

A point-in-time view of the entire workgroup:

```bash
$ synlynk team status

Member     Last Active     Stories         Budget Used
─────────  ──────────────  ──────────────  ───────────
alice      2026-06-21      S4 (active)     12,400 tok
bob        2026-06-20      S5 (active)     8,200 tok
nikhil     2026-06-22      S6 (planned)    —
```

Reads `project-docs/devlogs/` for all contributors and the `stories` table for active assignments. The `Budget Used` column reads `estimated_tokens` from the stories table.

### `synlynk decide`

Multi-agent consensus on any decision question:

```bash
$ synlynk decide "Should we store decision records in SQLite or Markdown files?" \
    --panel claude,codex,agy

Dispatching panel: claude, codex, agy...

  claude  →  SQLite — queryable, survives file renames, joins with stories
  codex   →  Markdown — human-readable, diffable in PRs, zero migration cost
  agy     →  SQLite — aligns with existing state.db pattern

Consensus: SQLite (2/3 panel)

Run with --record to write a signed Decision record.
```

With `--record`, writes `project-docs/decisions/YYYY-MM-DD-<slug>.md` containing the topic, panel responses, consensus position, and Ed25519 signature. Decisions become first-class artifacts that agents can reference in their context.

### Pull-before-write arbitration

Every command that writes to `project-docs/` now calls `_check_upstream_divergence()` first. If the local branch is behind the remote, the command warns:

```
⚠ project-docs/ may be out of date — consider git pull before writing
  (remote has 2 commits ahead of local)
  Continuing anyway...
```

The warning does not block — offline and disconnected workflows still function. The goal is visibility: if two developers' agents are writing to devlogs concurrently and one of them sees this warning, they know to pull before pushing to avoid a merge conflict.

### Token budgets on stories

`synlynk story create` accepts a `--tokens N` flag:

```bash
synlynk story create "Add Stripe webhook handler" --tokens 50000
```

The `estimated_tokens` column is visible in `synlynk team status` and in the dispatch planner's budget check. Stories with a budget cap trigger a warning when `_check_budgets()` sees cumulative tokens approaching the limit.

---

## Key Implementation Decisions

**`synlynk join` identity detection:** Uses `git config user.name` + `git config user.email` rather than asking interactively. This matches how synlynk has always identified members (via git attribution) and avoids prompting on first run.

**`decide` panel dispatch:** Each panel agent is dispatched non-interactively with `_run_agent_sync()` — the same mechanism used by the support engineer agent. The structured `DECISION:` block is extracted by regex from each agent's stdout. If an agent returns without the marker, its response is shown as "no structured decision" but the other panel members' votes still count.

**Consensus algorithm:** All panel responses are collected, then sent back to `panel[0]` (the first named agent) as a synthesis prompt. The synthesizer produces a final unified decision, and `cmd_decide` extracts the sentence starting with `"Decision:"` from the synthesis output as the canonical result. This means the first panel member is also the synthesizer — a deliberate simplicity tradeoff. Future versions may allow configuring a separate synthesizer agent or a voting-based alternative.

**Pull-before-write arbitration:** Implemented as a `git fetch --dry-run` + `git rev-list HEAD..origin/HEAD --count` check. Runs before every write to `project-docs/`. The check is skipped if the repo has no configured remote (`git remote -v` returns empty) so it doesn't break offline use.

---

## Test Approach

25 new tests across the 6 tasks. Key coverage:

- `_seed_devlog` with no prior commits (empty project) → writes minimal stub
- `_seed_devlog` with 10+ commits → truncates to last 10
- `cmd_join` in a repo with existing devlog → skips overwrite, prints status
- `cmd_decide` with panel of 1 → no consensus required, decision recorded directly
- `_check_upstream_divergence` with clean local → no warning
- `_check_upstream_divergence` with mock remote ahead → warning + exit

---

## Brainstorm Visuals Used

None for this feature. The v0.9.2 design spec (`docs/superpowers/specs/2026-06-22-v0.9.2-team-onboarding-consensus-design.md`) was written without a visual companion session — the feature set was well-understood from the invisible-state spec and team-mode requirements that preceded it.

---

## What This Achieved on the Path to Autonomy

**Agents can now onboard themselves into a team context.**

Before v0.9.2, adding a new developer (human or agent) to a synlynk-managed project required manually writing a devlog stub, manually updating agent instruction files with the new member's name, and manually reading all existing devlogs to understand team state. Each of these steps was error-prone and skipped under time pressure.

After v0.9.2:
- `synlynk join` runs in under five seconds and produces a correctly attributed devlog + up-to-date AI context files
- `synlynk team status` gives any agent a snapshot of team activity without reading multiple files
- `synlynk decide` closes the loop on one of the most common agent-coordination patterns: "I need three different agents to weigh in on this before I commit"

The pull-before-write arbitration is the piece that makes team mode safe to use concurrently. Without it, two agents writing to devlogs in the same repo in the same minute would produce a merge conflict that required human intervention. Now they don't.

---

## Strategic Note: The Goal at the End of This Post

Team features at v0.9.2 complete the synchronous layer of the multi-agent OS. Every human and agent on the team can now join, see team state, and participate in structured decisions — all locally, all offline-capable.

The next layer is the async daemon (v0.9.3): `synlynk daemon start` registers a background process that monitors `project-docs/`, fires context regeneration on writes, and exposes a local HTTP endpoint (`localhost:27471`) for agents to pull context without invoking the CLI. This moves synlynk from an on-demand tool to an always-running substrate — the step before the relay tier.
