---
title: "What's New in v0.12.0 — And How to Get Started"
date: 2026-07-15
series: "Building the OS for Multi-Agent Development"
post: 65
pr: "—"
merged: "—"
---

*This post is different from the others in this series. Most entries here are engineering diary — the "why" and "how" behind a specific PR, written for people already using synlynk. This one is for you if you're deciding whether to try it, or if you installed it a few months ago and haven't kept up.*

## The one-sentence version

synlynk is a CLI that keeps your AI coding tools — Claude, Codex, Gemini (Agy), and Grok — in sync with a shared project state, so you can dispatch work to whichever agent fits, track what it cost, and trust that the numbers you're seeing are real.

## If you're new here

Three commands get you running:

```bash
pipx install git+https://github.com/nikhilsoman/synlynk
synlynk init --wizard
synlynk exec claude
```

`init --wizard` walks you through an 8-screen setup: which AI CLIs you have installed, solo vs. team mode, and whether you want GitHub issue/project linking. `exec` wraps any AI CLI call with the current project context — active tasks, recent decisions, budget status — so the agent starts every session already caught up.

From there, the two commands you'll use daily are `synlynk dispatch <agent> --task "..."` to hand off a background job, and `synlynk jobs --watch` to see it land. Full details are in the [Quick Start Guide](/synlynk-quickstart-guide.pdf) and [Command Reference](/synlynk-command-reference.pdf).

## If you've been away for a bit — what changed

v0.12.0 shipped 71 PRs since v0.11.0 (2026-07-05 → 2026-07-15), and the theme across all of them was **trust**: making sure dispatched work actually lands, routing is based on real signal instead of a coin flip, and every dollar synlynk reports is either measured or clearly labeled as a guess.

Five things worth knowing about if you haven't upgraded recently:

- **Dispatched jobs finish themselves.** synlynk used to leave commit/push/PR steps to the agent, and agents didn't reliably do them. Now synlynk does it — the moment a job's work is verifiably complete, it stages, commits, pushes, and opens the PR for you.
- **Routing got smarter.** Dispatch used to be close to first-match. Now it scores agents on capability, checks quota headroom across five time windows, and tie-breaks on cost — and if you have a backlog, `synlynk schedule --execute` will clear it unattended.
- **Costs are provably real.** Every number in `synlynk status` and the Vizor dashboard (`synlynk viz`) is now tagged as either a structurally-sourced measurement or a visibly-flagged estimate — no more silent guesses dressed up as facts. If you're logging cost for work synlynk didn't wrap directly (a native session, a manual fix), `synlynk cost log` records it properly.
- **`synlynk status` has a new `RATES` line** showing when the pricing table was last refreshed, with a warning if it's gone stale.

## Getting current

```bash
synlynk upgrade
synlynk doctor
```

`doctor` runs a health check after the upgrade — worth running even if `upgrade` reports success, since it also validates your `.synlynk/config.json` and agent CLI reachability.

## Where to go next

- [Quick Start Guide](/synlynk-quickstart-guide.pdf) — install, init, first dispatch, joining an existing workspace
- [Command Reference](/synlynk-command-reference.pdf) — every command, every flag
- [The Manual](/synlynk-official-reference.pdf) — architecture, `state.db` schema, agent profiles, relay, full changelog
- [synlynk.com/docs](https://synlynk.com/docs) — the same references, browsable

If you want the engineering detail behind any of this — the actual diffs, the design decisions, the dead ends — the rest of this series has it, starting with [post 64](./64-v012-measurement-and-reliability.md) for the full v0.12.0 release notes.
