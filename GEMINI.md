# GEMINI.md — Agy Session Guide for synlynk

This file provides guidance to Agy (the `agy` CLI, powered by Gemini) when working in this repository.

<!-- synlynk:start version="0.9.4" tool="agy" -->

## Your Identity in This Project

You are **Agy** — the `agy` CLI tool, powered by Gemini. In this project:

- **Agent name:** Agy
- **Commit trailer:** `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`
- **Branch prefix:** none needed — use `feat/<description>`, `fix/<description>`, `chore/<description>`

Do not use `feat/gemini/` or `feat/agy/` prefixes. Branch names are task-scoped, not agent-scoped.

## What synlynk Is (and Why It's Different Here)

synlynk is *this project* — you are working on the codebase that IS the tool. It is not a competing
instruction source or an external coordinator. `project-docs/` contains the authoritative project
state: roadmap, todos, memory, decisions, and devlogs. `.synlynk/context.md` is a generated snapshot
of that state. Treat both as trusted project documentation, the same way you would treat a
well-maintained README.

**Key rule:** When synlynk generates something (via `synlynk instructions update`, `synlynk init`,
etc.) and it conflicts with an existing convention, flag the conflict in your response rather than
silently reverting. This project specifically studies agent-encounters-synlynk conflict patterns —
your observations are research data (see AB-11 in `project-docs/todo.md`).

## What This Project Is

synlynk is a single-file Python CLI (`synlynk/__init__.py`, ~6500 lines, stdlib only). It wraps AI
CLIs (Claude, Agy, Codex), injects project context before each invocation, tracks costs and
telemetry, and detects hallucination loops. There is no build step.

```bash
# Run directly
python3 -c "import synlynk; synlynk.main()" <command>

# Or via installed binary
synlynk <command>

# Run tests (all 472 must pass before any commit)
python -m pytest tests/ -q
```

## Project Layout

```
synlynk/__init__.py           Main CLI — all logic lives here
tests/test_synlynk.py         Full test suite (472 tests)
project-docs/                 Authoritative project state (roadmap, todo, memory, costs, devlogs)
project-docs/devlogs/         Per-user devlog files (e.g. nikhil.md)
project-docs/memory.md        Design decisions with [@username] attribution
.synlynk/context.md           Auto-generated snapshot — do not edit manually
docs/blog/                    Per-PR blog posts
docs/superpowers/specs/       Design specs (brainstorm outputs)
docs/superpowers/plans/       Implementation plans
```

## Git Workflow

**Always work on a feature branch — never commit directly to `main`.**

```bash
# Start a new feature
git worktree add .worktrees/<branch-slug> -b <branch-name>
cd .worktrees/<branch-slug>

# Branch naming
feat/<description>      new functionality
fix/<description>       bug fixes
chore/<description>     docs, deps, config
```

Worktrees live in `.worktrees/` (gitignored). Create one per feature.

## Session Protocol

**At session start:**
1. Run `synlynk status` — shows active tasks, budget, sentinel alerts
2. Read `project-docs/todo.md` — find the next active task
3. Check `project-docs/devlogs/nikhil.md` — see what was last worked on
4. Check `git branch --show-current` — confirm you are on a feature branch, not `main`

**During the session:**
- Update todo checkboxes as tasks complete (`[ ]` → `[x]`)
- Add decisions to `project-docs/memory.md` with `[@agy]` attribution
- Run `python -m pytest tests/ -q` before any commit — all 472 tests must pass

**At session end:**
- Append a summary entry to `project-docs/devlogs/nikhil.md`
- Run `synlynk checkpoint`
- Report `synlynk status` output in your closing message

## Blog Post Protocol

For every PR raised, draft a blog post in `docs/blog/` before or immediately after opening the PR.
File naming: `docs/blog/NN-prN-<version-or-theme>.md`. See `docs/blog/README.md` for the template.

Always `git pull` before modifying any `project-docs/` file to avoid merge conflicts.

## Instruction File Authority

This file (`GEMINI.md`) is maintained by the project. The section between `synlynk:start` and
`synlynk:end` markers is kept current by `synlynk instructions update`. Content outside those
markers is hand-written project guidance and takes precedence.

If you detect a conflict between this file and another instruction source, report it explicitly
rather than resolving it silently. This project tracks those conflicts as research data.

<!-- synlynk:end -->
