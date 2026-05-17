# Codex Preferred Roadmap for synlynk

This roadmap assumes synlynk should first become an excellent local session ledger and context compiler for one developer using multiple AI tools, then grow into team workflows after the solo loop is dependable.

## Product Direction

synlynk's durable value is project continuity: active tasks, decisions, devlogs, costs, safety signals, and generated context should remain usable across Claude, Gemini, Codex, Cursor, and other tools. The CLI wrapper is useful, but the product should not depend on wrapping every AI interaction. The stronger product is a local, inspectable source of truth that AI tools can read and update consistently.

## 0.3: Usability and Trust

### Add `synlynk doctor`

- Users need a single command that explains whether synlynk is correctly installed and configured.
- It should check PATH setup, Python version, git username, `.synlynk/config.json`, template presence, watcher state, context freshness, malformed cost rows, and stale telemetry.
- This reduces support burden because bug reports can include `synlynk doctor --json` output.
- It turns silent setup drift into actionable diagnostics.

### Add Context Size and Token Estimates to `status`

- Context growth is the central risk in a context compiler; users need visibility before large snapshots become expensive or noisy.
- `synlynk status` should show `.synlynk/context.md` file size, approximate token count, and the largest contributing sections.
- This makes compaction decisions measurable instead of subjective.
- It gives future scoped-context work a clear baseline for improvement.

### Add `synlynk cost add`

- Manual cost tracking is currently correct in principle but too easy to forget or format incorrectly.
- A command such as `synlynk cost add --tool claude --in 1000 --out 500 --usd 0.03 --note "..."`
  would enforce the expected `costs.md` schema.
- Structured cost entry improves `status`, budget warnings, and future team rollups.
- It keeps the Lite tier dependency-free while avoiding unreliable automatic token scraping.

### Add Shell Completions

- Completion support makes the CLI feel mature and reduces command friction.
- `synlynk completion zsh|bash|fish` is low risk because it does not change core data behavior.
- It helps users discover subcommands such as `checkpoint`, `status`, `watch`, and future task/cost commands.
- It is especially useful as the command surface expands.

### Add Config Validation and Clearer Errors

- A malformed config should produce a precise error instead of silently falling back to defaults.
- Validation should catch invalid budget values, invalid watcher intervals, unsupported modes, and unknown schema versions.
- Clear errors protect users from thinking synlynk is enforcing policies that it has actually ignored.
- This is also the first step toward safe migrations.

## 0.4: Context Intelligence

### Implement Scoped Context Generation

- Full-project context is useful at session start, but subagents and focused tasks need smaller, more relevant snapshots.
- `synlynk context --task 12`, `--file path`, and `--changed` should produce targeted context files.
- Scoped context reduces token cost and lowers the chance that irrelevant historical details steer an AI tool.
- This is the most important enhancement for practical multi-agent workflows.

### Add Git-Aware Context Sections

- The current project state is not only in `project-docs`; it is also in the branch, dirty files, recent commits, and staged changes.
- Context should optionally include branch name, changed files, last few commits, and uncommitted status.
- This helps AI tools understand what is actively being worked on without scanning the whole repo.
- It also improves handoff quality when switching tools mid-task.

### Add Context Budgets Per Section

- Each context section should have a rough token budget and truncation policy.
- Active tasks and sentinel alerts should have priority over old devlogs or broad memory entries.
- Budgeting makes context generation predictable and prevents one noisy section from crowding out higher-signal data.
- It creates a foundation for user-tunable context profiles later.

### Add `synlynk context --preview`

- Users should be able to inspect what would be sent to an AI tool before relying on it.
- Preview mode can show included sections, excluded sections, estimated tokens, and output path.
- This makes context generation transparent and debuggable.
- It also gives users confidence that sensitive or irrelevant material is not being included accidentally.

### Add Stale-Context Detection

- If `project-docs/` changes after `.synlynk/context.md` was generated, the user should know.
- `status` and `doctor` should flag stale context and recommend `synlynk checkpoint` or `synlynk context`.
- This avoids sessions starting from outdated state.
- It provides value even when users do not run the watcher daemon.

## 0.5: Workflow Layer

### Improve Checkpoint Summaries

- `checkpoint` is the natural moment to reinforce the user's workflow discipline.
- It should summarize archived tasks, missing cost logs, stale context, sentinel alerts, and the likely next task.
- Better summaries make the command worth running even when no tasks were completed.
- This strengthens synlynk as a session boundary tool, not just a file mutator.

### Add `synlynk next`

- Users and AI agents often need a simple answer to "what should happen next?"
- `synlynk next` can read `todo.md`, roadmap priority, blocked tasks, and recent devlogs to suggest the next active task.
- It should not make autonomous product decisions; it should surface the highest-signal candidate from existing docs.
- This makes session startup faster and less dependent on manual reading.

### Add Task Commands

- Routine task edits should not require hand-editing Markdown.
- Commands such as `synlynk task add`, `synlynk task done`, and `synlynk task list` can preserve IDs, attribution, and formatting.
- Structured task commands reduce malformed todo entries and improve checkpoint reliability.
- Markdown should remain editable, but the CLI should handle common workflows safely.

### Add Devlog Commands

- Devlogs are central to continuity, but manual entries are easy to skip.
- `synlynk devlog add` can standardize timestamps, attribution, task references, and session summaries.
- Better devlog structure improves context generation and teammate summaries later.
- It also makes session history easier to audit.

### Make Routine Use Possible Without Manual Markdown Edits

- Markdown should remain the source of truth, but common actions should have safe CLI paths.
- A user should be able to initialize, add tasks, mark tasks done, log costs, checkpoint, and inspect status through commands.
- This lowers the adoption barrier for users who like the concept but do not want to manage doc formatting.
- It also makes automation and testing more reliable.

## 0.6: Team Foundations

### Add an Append-Only Event Log

- Team workflows need a durable canonical record that is safer than concurrent Markdown editing.
- A JSONL event log can record task creation, completion, decisions, costs, checkpoints, and devlog entries.
- Markdown files can become generated views while remaining human-readable.
- This reduces merge conflicts and creates a clean path to sync features.

### Regenerate Markdown Views from Events

- Generated views let synlynk keep the user-friendly Markdown interface while improving data integrity.
- Rebuilding `todo.md`, `memory.md`, and devlogs from events can normalize formatting and IDs.
- It makes migrations and conflict resolution easier.
- It also allows future UI or sync layers to use the same canonical data.

### Add Attribution Validation

- Team mode depends on knowing who made which decision, completed which task, and incurred which cost.
- Validation should flag missing `[@username]` tags, unknown users, and entries that conflict with the configured mode.
- This keeps team summaries and rollups trustworthy.
- It also creates a clear contract for AI agents writing project docs.

### Add Conflict Detection

- Before writing shared docs, synlynk should detect whether files changed since the last read/checkpoint.
- In Git-backed projects, it can warn about upstream changes or dirty project-doc files before mutation.
- Conflict detection prevents accidental overwrites by multiple AI tools or collaborators.
- It is a prerequisite for credible team sync.

### Add Local Team Rollups

- Before building a hosted sync service, synlynk should produce useful team summaries from local docs.
- Rollups can show active users, recent completed tasks, open blockers, current budget, and sentinel alerts.
- This validates the team use case without adding infrastructure.
- It also clarifies which data model is actually needed for enterprise features.

## 1.0: Stable Local Product

### Freeze CLI and Schema Contracts

- A 1.0 release should promise stable command names, config schema, telemetry event shapes, and Markdown conventions.
- Stability matters because users will put synlynk into shell aliases, AI instructions, and team workflows.
- Breaking changes after 1.0 should require migrations and changelog callouts.
- This makes the product safe to recommend and automate.

### Add Migrations

- Users should be able to upgrade old project-docs and `.synlynk/config.json` files safely.
- `synlynk migrate` can detect schema versions, preview changes, and apply updates.
- Migrations prevent abandoned projects from becoming incompatible with new versions.
- They also reduce pressure to keep legacy parsing paths forever.

### Add Package Manager Distribution

- `curl | bash` is convenient but not enough for a polished developer tool.
- Support `pipx`, Homebrew, or another standard install path so users can install, upgrade, and uninstall cleanly.
- Package distribution improves trust and makes CI/devcontainer usage easier.
- It also reduces version drift between installer output and CLI behavior.

### Harden Daemon Lifecycle

- The watcher should handle stale pidfiles, crashes, project moves, log rotation, and repeated start/stop cycles reliably.
- It should expose enough status detail for `doctor` to diagnose daemon problems.
- Daemon reliability matters because stale context undermines the entire product.
- The daemon should remain optional so synlynk still works in simple/manual mode.

### Maintain a Full macOS/Linux Test Matrix

- `watch` depends on Unix daemon behavior, so platform coverage matters.
- CI should exercise normal CLI flows through subprocess calls, not just imported Python functions.
- Tests should cover init, exec failure propagation, checkpoint mutation, status JSON, upgrade network errors, and watcher lifecycle where feasible.
- This protects the single-file architecture from becoming brittle as features accumulate.

## Strategic Rule

Do not move into hosted team sync, enterprise policy, or MCP/LCP infrastructure until the local solo workflow is dependable. The product should earn trust first as a precise local ledger and context compiler, then use that stable data model as the foundation for collaboration.
