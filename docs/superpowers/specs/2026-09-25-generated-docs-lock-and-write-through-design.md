# Design Spec: Generated 4-doc lock, worktree identity, and generator write-through

- **Governing Goal:** `goal-6733bbf1` — state.db is the sole mutation point for `project-docs/`
- **Date:** 2026-09-25
- **Status:** Approved (operator sign-off: implement A+D then B)
- **Incident:** git-tracked `project-docs/roadmap.md` on `main` was replaced by a brownfield/init skeleton titled from a worktree folder (`feat+vizor-governs-board-and-gantt-ia`)

## Problem

After migrate, `_generate_roadmap_md()` writes `.synlynk/project-docs/roadmap.md`. Git-tracked `project-docs/roadmap.md` is not updated (`dr_sync_path` unset). `init()` / `_write_informed_skeleton()` / `init --brownfield` (`_bootstrap_4docs`) write raw markdown to `project-docs/` using `os.path.basename(cwd)`, which is the worktree folder name. `_detect_hand_edit()` only watches the migrated path, so the git file is overwritten silently.

## Approach (locked)

### A — Fail-closed on a migrated ledger

If `.synlynk/.synlynk_migrated` is present (resolved via git-common-dir / `_is_migrated()`):

- `_write_informed_skeleton`, `_bootstrap_4docs`, and `_llm_enrich` must not write `roadmap.md` / `todo.md` / `memory.md` / `costs.md`.
- `--force` is not enough. An explicit `--replace-generated-docs` is required to bypass the lock.
- Unmigrated repos keep today's bootstrap (raw skeleton / brownfield templates).
- On a locked brownfield run, ingest via `state.db` (`roadmap add` / `memory add` / `story create` / `devlog append`) and regenerate.

### D — Worktree identity

Never use the worktree directory basename as the product name.

Resolution order:

1. README H1 (unchanged, when present)
2. `identity_slug` from this repo or the git-common-dir root `.synlynk/config.json`
3. git-common-dir repository directory name
4. cwd basename (last resort)

`synlynk/scan.py` `_static_scan` and `synlynk/coldstart.py` `run_brownfield_init` share this helper.

### B — Single generator write path

All four generators (`_generate_roadmap_md`, `_generate_todo_md`, `_write_memory_md`, `_generate_costs_md`) write through one helper:

- unmigrated: `_docs_dir()` only (today)
- migrated: `.synlynk/project-docs/<file>` **and** git-tracked `_docs_dir()/<file>`
- then existing `_dr_sync` if configured

Raw `open(..., "w")` on those four filenames outside the generators is forbidden after migrate (enforced by A). Unmigrated bootstrap remains the only raw-write path.

## Tests

- Migrated + `skip_existing=False` / `force=True`: skeleton and brownfield do not replace a generated `roadmap.md`
- `--replace-generated-docs` on migrated: writes are allowed (generator path)
- Worktree named `feat+vizor-governs-board-and-gantt-ia` with root `identity_slug=synlynk` and no README H1: scan/brownfield name is `synlynk`
- Migrated `_generate_roadmap_md()` writes the generated header to both `.synlynk/project-docs/roadmap.md` and `project-docs/roadmap.md`
- Existing unmigrated brownfield / skeleton tests stay green

## Out of scope

- Extending `_detect_hand_edit` to the git-tracked copy (follow-up)
- Changing brownfield's first-run template for unmigrated repos
- Auto-setting `dr_sync_path`
