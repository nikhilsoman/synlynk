---
title: "PR #TBD — v0.10.0: synlynk migrate — state.db Source of Truth"
date: 2026-07-01
series: "Building the OS for Multi-Agent Development"
post: 36
pr: "#TBD"
merged: status: open
---

# PR #TBD — v0.10.0: synlynk migrate — state.db Source of Truth

## The Broader Goal at the End of the Previous PR

At the close of BS-17 (which introduced `synlynk scan` and `synlynk init --wizard`), synlynk successfully simplified the onboarding process and provided a guided, interactive First-Time User Experience (FTUE). However, a fundamental architectural bottleneck persisted: the repository's active state (the `project-docs/` directory containing `todo.md`, `memory.md`, `costs.md`, etc.) remained tracked directly in Git. When multiple agents and humans worked concurrently, they frequently generated annoying merge conflicts on these markdown files, disrupting the parallel development flow. The broader goal was clear: project state needed to move out of Git and into a structured database (`state.db`) as the permanent, single source of truth, while keeping a reliable local backup format.

## Strategic Shifts in This PR

BS-18 marks a major architectural shift rather than a feature release: transitioning `project-docs/` out of Git tracking. To achieve this safely without sacrificing visibility or resilience, we implemented three key mechanisms:
1. **Database as Source of Truth:** Every read and write query targets `state.db` directly. For instance, context generation now reads from the database.
2. **Immediate Local Write-Through:** To keep the state human-readable and accessible, any database change is immediately written to `.synlynk/project-docs/` as a local markdown backup.
3. **Zero-Dependency Disaster Recovery (DR) Sync:** Instead of building complex cloud authentication protocols, we introduced a path mirror configuration. Users can direct synlynk to mirror backup files to a local folder synced by existing desktop cloud clients (like iCloud, Google Drive, OneDrive). The operating system handles the network traffic, avoiding new dependencies or OAuth flows.

## What This PR Shipped

### The `synlynk migrate` Subcommand

This PR introduces the `synlynk migrate` CLI command to perform the 8-step atomic migration flow:
1. **Import:** Reads the flat markdown files in `project-docs/` and imports them into `state.db`.
2. **Copy:** Copies the markdown files to `.synlynk/project-docs/` as the initial local backup.
3. **DR Mirror:** Mirrors the files to the user's disaster recovery (DR) folder (if configured).
4. **Git Untrack:** Executes `git rm --cached -r project-docs/` to stop tracking active state files in Git.
5. **Gitignore:** Adds `project-docs/` to the repository's `.gitignore`.
6. **Sentinel:** Writes a `.synlynk/.synlynk_migrated` sentinel file marking the project as migrated.
7. **Stage:** Stages `.gitignore` and `.synlynk/.synlynk_migrated` for commit.
8. **Commit:** Commits the migration changes with a standardized message.

#### CLI Flags Shipped:
* `--dry-run`: Parses the flat files and prints what would be imported without writing to the database or modifying Git.
* `--recover`: Re-imports all project docs from the backup folder `.synlynk/project-docs/` back into `state.db`.
* `--setup-dr`: Sets the local path for the zero-dependency disaster recovery mirror in the workspace configuration.

### Technical Implementation

* **Database Schemas:** Added 5 new database tables to store project state: `memory_entries`, `roadmap_arcs`, `roadmap_phases`, `cost_entries`, and `devlog_entries`.
* **Flat-File Parsers:** Wrote 5 robust parsers in `synlynk/__init__.py`:
  * `_parse_memory_md`: Section-by-section parser keying on section headers and tracking authors via `[@username]`.
  * `_parse_roadmap_md`: Roadmap structure extraction separating version arcs (shipped, planned) and phase rows.
  * `_parse_costs_md`: Reads token records from the markdown table.
  * `_parse_devlog_file`: Parses individual developer journals to extract log entries.
  * `_parse_todo_metadata`: Matches checkboxes and metadata comments (e.g., gh_issue/story IDs) to sync stories.
* **Write-Through Hooks:** Configured `state.db` updates to trigger immediate write-throughs to flat files under `.synlynk/project-docs/` for:
  * `_generate_todo_md` (ToDo updates)
  * `cmd_memory_add` (Memory writes)
  * `cmd_devlog_append` (Devlog appends)
  * `update_costs` (Token cost logs)
* **Context Generation Routing:** Refactored `generate_context()` so that it dynamically routes to `_generate_context_from_db()` once the migration sentinel is detected, eliminating reading from raw Git-tracked markdown files.

### Testing and E2E Verification

To verify the migration lifecycle, we added a comprehensive end-to-end integration test (`test_full_migration_end_to_end` in [test_migrate.py](file:///Users/nikhilsoman/dev/synlynk/tests/test_migrate.py)) that validates:
1. **Dry-Run Isolation:** Ensuring `--dry-run` leaves the database empty.
2. **Atomic Migration:** Confirming database tables are correctly populated and the sentinel file is written.
3. **Write-Through Integrity:** Verifying that `cmd_memory_add` and `cmd_devlog_append` write to the database *and* immediately output to the backup directory.
4. **Context Integrity:** Ensuring `generate_context` reads directly from the database post-migration.
5. **Full Recovery:** Dropping memory entries, running `--recover`, and asserting that the database successfully re-imports all 3 entries (2 original + 1 written-through).

The full test suite containing 616 tests passes successfully.

## Brainstorm Visuals Used

No visual mockups or UI brainstorm files were created for this PR, as the architectural shift was a design-first discussion focused purely on CLI mechanics, data modeling, and file persistence.

## What This Achieved on the Path to Autonomy

1. **Conflict-Free Agent Collaboration:** Multi-agent squads can now execute tasks, update costs, and log devlogs simultaneously. They write to a single transactional SQLite database rather than trying to concurrently edit the same markdown files, eliminating git merge conflicts.
2. **Durable Local Fallbacks:** If a database corruption ever occurs, the `.synlynk/project-docs/` backup acts as a persistent human-readable snapshot that can be easily recovered using `synlynk migrate --recover`.
3. **Zero-Configuration Backup:** By mirroring to iCloud/Google Drive paths, team members get automated backup/sync without synlynk having to manage cloud credentials, token refreshes, or network request code.

## Strategic Note: The Goal at the End of This PR

With the onboarding experience, repository scanning, and state database migrations fully complete, the last remaining **Phase 0 P0 priority** before the first named `v0.10.0` release is **packaging**.

The next milestone is to wrap synlynk into a proper Python package (`pyproject.toml` definition + `pipx install` support). This ensures that developers can install and upgrade synlynk as a standalone global CLI utility, making it ready for daily production use.
