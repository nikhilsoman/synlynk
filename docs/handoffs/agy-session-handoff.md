# Agy Session Handoff — synlynk repo

**Date:** 2026-06-24  
**Purpose:** Briefing for Agy to work in the synlynk repository, resolving conflicts observed in the
rxcc session.

---

## The Short Version

You are working *on* synlynk — the tool itself. Everything synlynk generates in this repo is your
own project's output, not an external coordinator's instructions. Read it as project documentation.

---

## Resolving the 6 Conflicts from the rxcc Session

### 1. Identity Mapping

**What Agy flagged:** synlynk maps `GEMINI.md` → agent `agy-2.x` but you identify as Gemini 2.5 Pro.

**Resolution:** In this repo, your identity is:

- **Name:** Agy (the CLI tool — not the model name)
- **Commit trailer:** `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`
- **What synlynk calls you internally:** `agy` (the CLI binary name)

The model version (`2.5 Pro`, `2.0 Flash`, etc.) is not used in commit trailers or branch names —
only the CLI tool name `Agy`. This matches how Claude Code is called `claude`, not `Claude Sonnet
4.6`.

### 2. Commit Trailer Format

**What Agy flagged:** `Co-Authored-By: AGY <noreply@antigravity.dev>` vs your preference for
`Co-Authored-By: Gemini 2.5 Pro <noreply@google.com>`.

**Resolution:** Use exactly:

```
Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>
```

This is the project standard for Agy-assisted commits. It names the CLI tool with the model family
in parentheses.

### 3. Branch Naming

**What Agy flagged:** synlynk suggesting `feat/agy/` prefixes vs your preference for `feat/gemini/`
or no agent prefix.

**Resolution:** No agent prefix on any branch. Branches are task-scoped:

```
feat/<description>    fix/<description>    chore/<description>
```

Examples: `feat/v0.9.5-health-pulse`, `fix/sentinel-rearm-logic`. Never `feat/agy/` or
`feat/gemini/`.

### 4. Git Workflow (Worktrees)

**What Agy flagged:** synlynk instructions recommend worktree-first workflow vs your standard
checkout preference.

**Resolution:** The worktree-first workflow is the project standard here. Every feature gets its own
worktree under `.worktrees/`:

```bash
git worktree add .worktrees/feat-health-pulse -b feat/v0.9.5-health-pulse
cd .worktrees/feat-health-pulse
```

This is particularly important in this project because Claude Code sessions run concurrently and
share the SQLite state DB. Worktrees prevent branch collisions. Follow it as a project requirement,
not a synlynk imposition.

### 5. Docs Location

**What Agy flagged (in rxcc):** `docs/` at root vs `project-docs/` for devlogs and decisions.

**Resolution for synlynk repo:** The correct layout is:

| Content | Location |
|---|---|
| Roadmap, todo, memory, costs | `project-docs/` |
| Devlog | `project-docs/devlogs/nikhil.md` |
| Design specs | `docs/superpowers/specs/` |
| Implementation plans | `docs/superpowers/plans/` |
| Blog posts | `docs/blog/` |
| Handoff docs (this file) | `docs/handoffs/` |

`project-docs/` is for live project state. `docs/` is for artifacts and reference material.

### 6. Session Greeting Format

**What Agy flagged:** synlynk expects a 3-row greeting; you prefer a 2-row format.

**Resolution:** The greeting format is not enforced. What matters is that at session start you:

1. Run `synlynk status` (or read `project-docs/todo.md` directly)
2. Confirm you are on a feature branch, not `main`
3. Read the last entry in `project-docs/devlogs/nikhil.md`

Format your opener however you prefer — the content matters, not the row count.

---

## The One Rule That Caused the Revert

In the rxcc session, `synlynk instructions update` overwrote your instruction block because the file
had no `<!-- synlynk:start -->` / `<!-- synlynk:end -->` markers. Synlynk interpreted the entire
file as fair game and replaced it.

**This is a synlynk bug** (tracked as AB-12 in `project-docs/todo.md`). The correct behaviour is
that `synlynk instructions update` should refuse to write to a file without markers unless `--merge`
is explicitly passed.

**In this repo:** `GEMINI.md` now has proper markers. The synlynk-managed section (between
`<!-- synlynk:start -->` and `<!-- synlynk:end -->`) will be refreshed by `synlynk instructions
update`. Content outside the markers is yours to edit freely and will not be touched.

**In other repos (rxcc, etc.):** Until AB-12 ships, do not run `synlynk instructions update` on a
file without markers. Add the markers manually first, or pass `--no-update-instructions`.

---

## What to Do When You Detect a Conflict

The old pattern (rxcc session) was: detect conflict → revert silently. The new pattern for this
project:

1. **Flag it explicitly** — "I found a conflict between X and Y. Here's what each says."
2. **State your interpretation** — "I'm treating X as authoritative because..."
3. **Ask if that's correct** — one message, one question
4. **Proceed once confirmed**

Your conflict detection instincts are valuable research data for this project. Don't suppress them —
surface them.

---

## Quick Reference

| Item | Value |
|---|---|
| Your name | Agy |
| Commit trailer | `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>` |
| Branch format | `feat/<desc>`, `fix/<desc>`, `chore/<desc>` |
| Worktrees | `.worktrees/<branch-slug>` |
| Project state | `project-docs/` |
| Tests | `python -m pytest tests/ -q` (472 tests, all must pass) |
| On conflict | Flag → state interpretation → ask → proceed |
| On missing markers | Do not run `synlynk instructions update` |

---

## Context You Would Want

- **Current version:** v0.9.4 (shipped June 2026)
- **Next release:** v0.9.5 Health Pulse (spec at `docs/superpowers/specs/2026-06-24-health-pulse-design.md`)
- **Your conflict patterns:** tracked as AB-11/12/13 in `project-docs/todo.md` — the data from the rxcc session is already captured there
- **This is your first session in the synlynk repo:** the rxcc conflict happened in a different repo where synlynk is a dependency; here you are working on synlynk itself
