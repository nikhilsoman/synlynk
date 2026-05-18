# Native Codex Implementation Plan

## Phase 1: Codex-Native Instructions

### Task 1: Add `AGENTS.md` Template

Implementation:

- Add `AGENTS.md` to `TEMPLATES` in `bin/synlynk.py`.
- Include Codex-specific session protocol.
- Keep instructions daemon-tolerant: prefer explicit `synlynk status` and `synlynk checkpoint` over requiring `watch`.
- Add `AGENTS.md` to `synlynk init` root-level template handling.

Tests:

- `test_init_creates_agents_md`.
- `test_init_agents_md_contains_context_status_checkpoint`.
- `test_init_skips_existing_agents_md_without_force`.
- `test_init_force_overwrites_agents_md`.

Docs:

- Update README "Session protocol".
- Add `docs/codex/usage.md`.

### Task 2: Add `synlynk init --codex`

Implementation:

- Add `--codex` flag to `init`.
- Ensure `AGENTS.md` exists.
- Print Codex-specific next steps.
- Do not create `.codex/` files by default.

Tests:

- `init --codex` creates `AGENTS.md`.
- `init --codex` is idempotent.
- `init --codex` does not create `.codex/` unless a future explicit flag is added.

## Phase 2: Codex Diagnostics

### Task 3: Implement `synlynk doctor --codex`

Implementation:

- Add `doctor` command with `--json` and `--codex`.
- Use `shutil.which("codex")`.
- Run `codex --version` with timeout when present.
- Validate `AGENTS.md`.
- Validate `.synlynk/context.md`.
- Validate `project-docs/costs.md`.
- Validate config.
- Return exit code `1` for failures and `0` otherwise.

Tests:

- Missing Codex path.
- Present Codex path with successful version.
- Version command timeout/failure.
- Missing `AGENTS.md`.
- Weak `AGENTS.md` missing required protocol terms.
- JSON output schema.

### Task 4: Add Config and State Validators

Implementation:

- Add `validate_config`.
- Add `validate_costs_file`.
- Add `validate_context_freshness`.
- Add `validate_watcher_state`.
- Reuse validators from `doctor`, `status`, and future migration work.

Tests:

- Invalid config schema.
- Invalid budget values.
- Malformed costs row.
- Missing context file.
- Stale context after newer `project-docs` file.

## Phase 3: Codex CLI Runner

### Task 5: Add `synlynk codex` Command

Implementation:

- Add subcommand:

  ```bash
  synlynk codex [options] "<prompt>"
  ```

- Generate context before execution.
- Check budgets before execution.
- Run `codex exec --json --cd <repo>`.
- Stream output.
- Capture raw JSONL.
- Emit `codex_exec` telemetry.
- Return Codex exit code.

Options:

- `--model`.
- `--profile`.
- `--sandbox`.
- `--approval`.
- `--codex-arg` repeatable passthrough.
- `--output`.
- `--no-context-refresh`.

Tests:

- Command construction.
- Flag passthrough.
- Exit-code propagation.
- Telemetry emission.
- Missing `codex` executable.

### Task 6: Add Prompt Input Modes

Implementation:

- Support prompt argument.
- Support `-` for stdin.
- Support piped stdin append behavior compatible with Codex where practical.
- Reject empty prompt with exit code `2`.

Tests:

- Prompt argument.
- Stdin prompt.
- Empty prompt.
- Combined prompt and stdin behavior.

### Task 7: Add Codex Shortcut Commands

Implementation:

- Add shortcuts:
  - `synlynk codex review`.
  - `synlynk codex summarize`.
  - `synlynk codex fix-ci`.
- Keep write-capable modes explicit.
- Support `--write` for mutation-capable prompts.

Tests:

- Shortcut prompt generation.
- `fix-ci` without `--write` does not request mutation.
- `--write` passes appropriate sandbox/write intent.

## Phase 4: JSONL Parsing and Usage Ingestion

### Task 8: Add Tolerant Codex JSONL Parser

Implementation:

- Add `parse_codex_jsonl(lines)`.
- Tolerate malformed lines.
- Preserve unknown event counts.
- Extract:
  - final message,
  - usage,
  - tool calls,
  - file changes,
  - errors.

Tests:

- Known usage event.
- Missing usage.
- Malformed JSON.
- Unknown event.
- Error event.

### Task 9: Add Codex Cost Ingestion

Implementation:

- Add `append_cost_entry`.
- If Codex usage includes cost, record cost.
- If Codex usage includes tokens but no cost, record tokens with blank cost and note.
- Do not create fake dollar estimates.

Tests:

- Usage with cost.
- Usage without cost.
- No usage.
- Existing costs file preserved.

### Task 10: Add Codex Telemetry Schema

Implementation:

- Define `codex_exec` telemetry event.
- Include command, duration, exit code, usage summary, tool count, file change count, and error count.
- Keep telemetry capped at 100 events.

Tests:

- Success event.
- Failure event.
- Unknown JSONL event count stored.

## Phase 5: Codex Desktop App

### Task 11: Add Desktop Usage Documentation

Implementation:

- Add `docs/codex/desktop-app.md`.
- Document:
  - `AGENTS.md`,
  - opening a repo in Codex Desktop,
  - running `synlynk status`,
  - running `synlynk checkpoint`,
  - limitations around background watch daemons,
  - support checklist.

Tests:

- Documentation-only task; verify links and commands manually.

### Task 12: Add Optional Deeplink Helper

Implementation:

- Add `synlynk codex open`.
- Generate a Codex Desktop link only after supported format is verified.
- Provide `--print-link` mode.
- Do not auto-open GUI apps in CI.

Tests:

- Link encoding.
- No GUI invocation by default.
- Unsupported platform message.

## Phase 6: Third-Party IDE Support

### Task 13: Add IDE Usage Documentation

Implementation:

- Add `docs/codex/third-party-ides.md`.
- Cover:
  - VS Code integrated terminal.
  - Cursor terminal.
  - Windsurf terminal.
  - Generic task runners.
  - PATH and cwd pitfalls.
  - `synlynk doctor --codex` usage.

Tests:

- Documentation-only task; verify commands are shell-safe.

### Task 14: Add IDE Diagnostics

Implementation:

- Extend `doctor --codex` with environment checks:
  - cwd is git root or inside git repo,
  - `codex` on PATH from current shell,
  - `synlynk` on PATH,
  - `AGENTS.md` visible from cwd,
  - project-docs path resolvable.

Tests:

- Mock PATH mismatch.
- Nested cwd inside repo.
- Missing `synlynk` path.

## Phase 7: Release and Maintenance

### Task 15: Add Fake-Codex CI Fixtures

Implementation:

- Create a temporary fake `codex` executable in tests.
- Emit fixture JSONL.
- Verify `synlynk codex` subprocess behavior end to end.

Tests:

- Success fixture.
- Failure fixture.
- Malformed JSONL fixture.

### Task 16: Add Maintenance Playbook

Implementation:

- Keep `docs/codex/support-playbook.md` current.
- Add release validation checklist.
- Add troubleshooting table.
- Add compatibility review cadence.

Tests:

- Documentation-only task.
