# v0.12.0 Docs Refresh — Plan 4: New Reader-Facing Blog Post Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one new reader-facing "what's new in v0.12.0 + how to get started" blog post, distinct in tone from the existing engineering-diary PR posts (including post 64, which is release-notes-style for that same version).

**Architecture:** Single new markdown file in `docs/blog/`, following the series' existing frontmatter/index conventions from `docs/blog/README.md`. No code changes.

**Tech Stack:** Markdown only.

---

This plan is one of 4 independent, parallel-dispatchable plans derived from `docs/superpowers/specs/2026-07-15-v0.12.0-docs-onboarding-refresh-design.md`. It touches only `docs/blog/65-whats-new-v012-getting-started.md` and `docs/blog/README.md`'s index table — disjoint from the other 3 plans' files.

### Task 1: Confirm the next free post number

**Files:**
- Read-only check: `docs/blog/`

- [ ] **Step 1: List current posts and confirm 65 is free**

Run: `ls docs/blog/*.md | sort`

As of this plan's authoring, the highest numbered post is `64-v012-measurement-and-reliability.md`, so `65` is the next free number. **Re-verify this at execution time** — if a post numbered 65 (or higher, with a gap at 65) already exists by the time this task runs, use the actual next free number instead and adjust the filename and all references below accordingly (per this project's prior-session precedent of numbering collisions during parallel work).

### Task 2: Write the new blog post

**Files:**
- Create: `docs/blog/65-whats-new-v012-getting-started.md` (filename number per Task 1's result)

- [ ] **Step 1: Cross-check command names used in the post against `synlynk/cli.py`**

Run: `grep -n 'add_parser(' synlynk/cli.py` before writing, to confirm exact command names (`schedule`, `cost log`, `status`, `viz`, `upgrade`, `doctor`, `init`) referenced below still exist under those exact names.

**Scope note:** the `local` (on-device oMLX) agent has shipped in code but is intentionally excluded from this post — it's being trialed before a public announcement. Do not mention `local` or `local doctor` anywhere in the post below; the agent roster referenced in this post is Claude, Codex, Agy, and Grok only.

- [ ] **Step 2: Write the file**

Create `docs/blog/65-whats-new-v012-getting-started.md` with this content:

```markdown
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
```

- [ ] **Step 3: Add the post to `docs/blog/README.md`'s Series Index table**

**Files:**
- Modify: `docs/blog/README.md:66` (immediately after the row for post 62, before the blank line that precedes `## Per-PR Post Template`)

Read current state: `sed -n '60,68p' docs/blog/README.md`

Insert a new row (adjust the post number if Task 1 found a different free number) directly after the existing row for post 62 (`62-pr258-vizor-cost-flagging.md`) and before the blank line at line 67-68:

```markdown
| [65](./65-whats-new-v012-getting-started.md) | What's New in v0.12.0 — And How to Get Started | — | 2026-07-15 |
```

Note rows 63 and 64 are missing from the current index table (they exist as files but were never indexed — this is a pre-existing gap, not something this task needs to fix; only add the new row for post 65 unless fixing the 63/64 gap is a 1-line addition you can make alongside it without expanding scope. If you do add 63/64 while you're in the file, use titles matching their actual `title:` frontmatter fields, read via `grep -A2 "^title:" docs/blog/63-pr259-status-rates-updated-at.md docs/blog/62-pr258-vizor-cost-flagging.md` — do not guess).

- [ ] **Step 4: Self-verify — spot-check every command name against `cli.py`**

Run:
```bash
grep -oE 'synlynk [a-z][a-z-]*' docs/blog/65-whats-new-v012-getting-started.md | sed 's/synlynk //' | sort -u
```
For each name, confirm a matching `add_parser("<name>"` in `synlynk/cli.py` via `grep -n '"<name>"' synlynk/cli.py`. Fix any orphan before committing.

- [ ] **Step 5: Confirm no numbering collision one more time**

Run: `ls docs/blog/65-*.md 2>/dev/null | wc -l` — expected: `1` (just the file you created). If more than 1, another process created a conflicting post 65 during this task's execution — rename to the next free number and update both the post's own `post:` frontmatter field and the README.md index row before committing.

- [ ] **Step 6: Commit**

```bash
git add docs/blog/65-whats-new-v012-getting-started.md docs/blog/README.md
git commit -m "docs: add reader-facing what's-new/getting-started post for v0.12.0"
```
