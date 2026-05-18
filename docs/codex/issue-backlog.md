# Platform:Codex Issue Backlog

Create each issue with the label `Platform:Codex`.

## Milestone v0.3.0: Codex-Native Setup

### Issue 1: Generate Codex-native `AGENTS.md` during init

Labels: `Platform:Codex`

Summary:

Add `AGENTS.md` as a first-class Synlynk template so Codex CLI and Codex Desktop receive native project instructions.

Acceptance criteria:

- `synlynk init` creates `AGENTS.md`.
- `synlynk init --force` overwrites stale `AGENTS.md`.
- Existing `AGENTS.md` is preserved without `--force`.
- Tests cover create, skip, and overwrite behavior.

### Issue 2: Add `synlynk init --codex`

Labels: `Platform:Codex`

Summary:

Add an explicit Codex setup path that ensures Codex-native files exist and prints Codex-specific next steps.

Acceptance criteria:

- `synlynk init --codex` ensures `AGENTS.md`.
- Command is idempotent.
- It does not generate unverified `.codex/` config files.
- README documents the command.

### Issue 3: Document Codex CLI and Desktop baseline usage

Labels: `Platform:Codex`

Summary:

Add user documentation for Codex CLI interactive sessions and Codex Desktop App setup.

Acceptance criteria:

- `docs/codex/usage.md` exists.
- `docs/codex/desktop-app.md` exists.
- README links to Codex docs.
- Docs clarify that `AI_INSTRUCTIONS.md` is not the Codex-native instruction file.

## Milestone v0.4.0: Diagnostics and Reliability

### Issue 4: Implement `synlynk doctor --codex`

Labels: `Platform:Codex`

Summary:

Add diagnostics that validate whether the local repo is ready for Codex CLI/Desktop usage.

Acceptance criteria:

- Checks `codex` on PATH.
- Checks `codex --version`.
- Checks `AGENTS.md` exists and contains required Synlynk protocol terms.
- Checks context, costs, config, and watcher state.
- Supports `--json`.
- Tests cover success and failure paths.

### Issue 5: Add config, costs, context, and watcher validators

Labels: `Platform:Codex`

Summary:

Extract reusable validators used by `doctor`, `status`, and future migration commands.

Acceptance criteria:

- Invalid config values are reported.
- Malformed costs rows are reported.
- Stale or missing context is reported.
- Stale pidfiles are reported.
- Tests cover validators independently.

### Issue 6: Add fake-Codex subprocess smoke tests

Labels: `Platform:Codex`

Summary:

Add network-free subprocess tests that simulate Codex CLI behavior.

Acceptance criteria:

- Tests create a fake `codex` executable on a temporary PATH.
- Tests cover version success and failure.
- Tests cover JSONL output fixtures.
- Tests run in CI without real Codex.

## Milestone v0.5.0: Codex Non-Interactive Runner

### Issue 7: Implement `synlynk codex "<prompt>"`

Labels: `Platform:Codex`

Summary:

Add a Codex-specific command that runs `codex exec --json --cd <repo>` after refreshing Synlynk context.

Acceptance criteria:

- Generates context before execution.
- Preserves Codex exit code.
- Supports model/profile/sandbox/passthrough flags.
- Emits `codex_exec` telemetry.
- Tests mock command construction and exit codes.

### Issue 8: Add stdin prompt support for `synlynk codex`

Labels: `Platform:Codex`

Summary:

Allow prompts to be passed through stdin for automation and scripts.

Acceptance criteria:

- `synlynk codex -` reads stdin.
- Empty prompt exits with code `2`.
- Combined prompt/stdin behavior is documented and tested.

### Issue 9: Add Codex shortcut modes

Labels: `Platform:Codex`

Summary:

Add built-in prompts for common Codex workflows such as review, summarize, and fix-ci.

Acceptance criteria:

- `synlynk codex review` exists.
- `synlynk codex summarize` exists.
- `synlynk codex fix-ci` exists.
- Mutating behavior requires explicit `--write`.
- Tests cover generated prompts.

## Milestone v0.6.0: JSONL Parsing and Usage Ingestion

### Issue 10: Add tolerant Codex JSONL parser

Labels: `Platform:Codex`

Summary:

Parse Codex JSONL output without failing on malformed or unknown events.

Acceptance criteria:

- Extracts final message when present.
- Extracts usage when present.
- Counts tool calls, file changes, errors, malformed lines, and unknown events.
- Tests cover malformed and unknown events.

### Issue 11: Record Codex usage into `costs.md`

Labels: `Platform:Codex`

Summary:

Append Codex usage to `project-docs/costs.md` when structured usage data is available.

Acceptance criteria:

- Records token usage.
- Records dollar cost only when available.
- Does not invent cost values.
- Keeps `costs.md` parseable by `status`.
- Tests cover cost, token-only, and no-usage cases.

### Issue 12: Define and emit `codex_exec` telemetry events

Labels: `Platform:Codex`

Summary:

Store Codex execution metadata in `.synlynk/telemetry.json`.

Acceptance criteria:

- Event includes `schema_version`, `type`, `timestamp`, `user`, `command`, `duration`, `exit_code`, and parsed summary.
- Event is emitted on success and failure.
- Telemetry cap remains 100 entries.
- Tests cover event shape.

## Milestone v0.7.0: Codex Desktop App Helpers

### Issue 13: Add Codex Desktop App support guide

Labels: `Platform:Codex`

Summary:

Document recommended Codex Desktop App usage with Synlynk.

Acceptance criteria:

- Covers opening a repo, `AGENTS.md`, `synlynk status`, `checkpoint`, and limitations.
- Avoids unverified `.codex/` configuration claims.
- Linked from README.

### Issue 14: Add optional Codex Desktop deeplink helper

Labels: `Platform:Codex`

Summary:

Add an opt-in helper for opening Codex Desktop sessions with a repo path and prompt after verifying supported link format.

Acceptance criteria:

- Command is opt-in.
- Supports `--print-link`.
- Does not open GUI apps in CI.
- Tests cover URL encoding and unsupported platforms.

## Milestone v0.8.0: Third-Party IDE Support

### Issue 15: Document Codex usage from third-party IDEs

Labels: `Platform:Codex`

Summary:

Add guidance for using Codex and Synlynk from VS Code, Cursor, Windsurf, and generic IDE terminals.

Acceptance criteria:

- Covers PATH, cwd, git root, and task runner pitfalls.
- Recommends `synlynk doctor --codex`.
- Includes example terminal/task commands.

### Issue 16: Extend diagnostics for IDE environments

Labels: `Platform:Codex`

Summary:

Detect common third-party IDE integration problems.

Acceptance criteria:

- Checks cwd vs git root.
- Checks `codex` and `synlynk` visibility from current shell.
- Checks `AGENTS.md` is visible from cwd.
- Tests cover nested cwd and PATH mismatch.
