# Native Codex Integration Implementation Plan

## Goal

Make Codex a first-class synlynk integration instead of relying on generic AI instructions. The implementation should support Codex CLI and Codex Desktop users through native instruction files, diagnostics, and a reliable non-interactive `codex exec --json` workflow.

## Constraints

- Preserve the single-file CLI architecture in `bin/synlynk.py`.
- Keep runtime dependencies to the Python standard library.
- Keep existing generic `synlynk exec <cmd>` behavior.
- Do not invent or write unstable `.codex/` app config formats until the local app contract is verified.
- Prefer additive changes with tests for each phase.

## Phase 1: Add Codex-Native Instructions

### Task 1.1: Add `AGENTS.md` Template

Files:

- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`
- Update: `README.md`
- Update: `CHANGELOG.md`

Implementation:

- Add `AGENTS.md` to the `TEMPLATES` dict.
- Use a Codex-specific instruction body rather than only copying `AI_INSTRUCTIONS.md`.
- Keep the document concise and action-oriented.
- Include these required instructions:
  - Read `.synlynk/context.md` at session start.
  - Run `synlynk status` before substantial work.
  - Run `synlynk checkpoint` at task boundaries and before final response.
  - Update `project-docs/todo.md`, `memory.md`, `costs.md`, and `devlogs/<username>.md` when relevant.
  - Treat `.synlynk/sentinel.md` alerts as blocking until acknowledged.
  - Prefer `synlynk status` and `synlynk checkpoint` over assuming the watcher daemon is running.

Acceptance criteria:

- `synlynk init` creates `AGENTS.md`.
- `synlynk init --force` overwrites stale `AGENTS.md`.
- Existing projects are not overwritten without `--force`.
- README documents `AGENTS.md` as the Codex-native instruction file.

Tests:

- Add `test_init_creates_agents_md`.
- Add `test_init_agents_md_contains_codex_protocol`.
- Add `test_init_force_overwrites_agents_md`.
- Add `test_init_skips_existing_agents_md_without_force`.

### Task 1.2: Add Root-Level Codex Documentation

Files:

- Update: `README.md`
- Optional create: `docs/codex-usage.md`

Implementation:

- Add a "Using with Codex" section.
- Document two paths:
  - Interactive: open Codex in the repo and rely on `AGENTS.md`.
  - Non-interactive: use future `synlynk codex` command once implemented.
- Clarify that `AI_INSTRUCTIONS.md` is universal fallback material, not the native Codex entry point.

Acceptance criteria:

- README names `AGENTS.md`.
- README no longer implies Codex will automatically read `AI_INSTRUCTIONS.md`.

## Phase 2: Add Codex Diagnostics

### Task 2.1: Implement `synlynk doctor`

Files:

- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`
- Update: `README.md`
- Update: `CHANGELOG.md`

Implementation:

- Add command:

  ```bash
  synlynk doctor [--json] [--codex]
  ```

- General checks:
  - Python version.
  - Git repository presence.
  - Git username availability.
  - `project-docs/` exists.
  - `.synlynk/config.json` exists and parses.
  - `.synlynk/context.md` exists.
  - `project-docs/costs.md` parses.
  - Watcher pidfile state is healthy or absent.

- Codex checks when `--codex` is provided:
  - `codex` exists on PATH using `shutil.which("codex")`.
  - `codex --version` succeeds with timeout.
  - `AGENTS.md` exists.
  - `AGENTS.md` mentions `.synlynk/context.md`, `synlynk status`, and `synlynk checkpoint`.
  - Optional `.codex/` directory is reported but not required.

- Human output should group checks by `OK`, `WARN`, and `FAIL`.
- JSON output should include stable fields:

  ```json
  {
    "schema_version": 1,
    "ok": true,
    "checks": [
      {"id": "codex.path", "status": "ok", "message": "..."}
    ]
  }
  ```

Exit codes:

- `0`: no failures.
- `1`: one or more failures.
- Warnings should not fail the command.

Acceptance criteria:

- `synlynk doctor --codex` gives a clear answer about Codex readiness.
- It does not require network.
- It does not modify files.

Tests:

- Mock `shutil.which` and `subprocess.run`.
- Test Codex missing from PATH.
- Test Codex present and version succeeds.
- Test `AGENTS.md` missing produces failure.
- Test JSON output is valid and stable.

### Task 2.2: Add Config Validation Helper

Files:

- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

Implementation:

- Add `validate_config(config: dict) -> list[dict]` or Python 3.8-compatible equivalent.
- Validate:
  - `schema_version == 1`.
  - `budget.limit_usd` is a non-negative number.
  - `budget.limit_requests` is a positive integer.
  - `watch_interval_seconds` is a positive integer.
  - `org`, `team`, and `sync_endpoint` are either `None` or strings.

Acceptance criteria:

- `doctor` uses validation.
- Existing `load_config()` behavior remains backward compatible.

Tests:

- Valid config returns no failures.
- Invalid budget, interval, and schema version are reported.

## Phase 3: Add `synlynk codex` Command

### Task 3.1: Implement Basic Non-Interactive Wrapper

Files:

- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`
- Update: `README.md`
- Update: `CHANGELOG.md`

Command:

```bash
synlynk codex "<prompt>"
```

Implementation:

- Add argparse subcommand `codex`.
- Before running Codex:
  - Call `generate_context()`.
  - Call `check_budgets()`.
  - Set state to `active`.
- Run:

  ```bash
  codex exec --json --cd <current_repo> <prompt>
  ```

- Use `subprocess.Popen` with `stdout=PIPE`, `stderr=STDOUT`, `text=True`.
- Stream human-readable summaries to the terminal where possible.
- Capture raw JSONL lines for parsing.
- Return Codex child exit code through `sys.exit`.

Options:

- `--model MODEL`: pass through as `--model`.
- `--profile PROFILE`: pass through as `--profile`.
- `--sandbox MODE`: pass through as `--sandbox`.
- `--codex-arg ARG`: repeatable raw passthrough for advanced flags.
- `--output FILE`: write final message if parsed.
- `--no-checkpoint`: skip final checkpoint suggestion or auto-checkpoint behavior.

Acceptance criteria:

- `synlynk codex "summarize repo"` invokes `codex exec --json`.
- `synlynk codex` returns the child exit code.
- It writes an `exec_codex` telemetry event.
- It does not require Codex Desktop.

Tests:

- Mock `subprocess.Popen`.
- Assert generated command includes `codex exec --json --cd`.
- Assert model/profile/sandbox flags pass through.
- Assert non-zero Codex exit returns non-zero.
- Assert telemetry event includes `type: "codex_exec"`.

### Task 3.2: Add Prompt Handling from stdin

Files:

- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

Implementation:

- Allow:

  ```bash
  synlynk codex -
  ```

  to read prompt from stdin.

- If both argument prompt and piped stdin are present, append stdin as a `<stdin>` block or reject with a clear error. Prefer matching Codex behavior if practical.

Acceptance criteria:

- Users can pipe prompts into synlynk.
- Empty prompt returns a clear error with exit code `2`.

Tests:

- Mock stdin and verify prompt construction.
- Test empty prompt behavior.

### Task 3.3: Add Codex Shortcut Modes

Files:

- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`
- Update: `README.md`

Commands:

```bash
synlynk codex review
synlynk codex summarize
synlynk codex fix-ci
```

Implementation:

- Add subcommands or `--mode` choices.
- Suggested prompts:
  - `review`: "Review this repository for correctness issues, regressions, and missing tests. Prioritize findings."
  - `summarize`: "Summarize current project state using .synlynk/context.md and repository files."
  - `fix-ci`: "Inspect failing tests or CI logs available locally and propose or implement fixes."
- For mutation-capable modes, require explicit `--write` or use Codex sandbox options only when requested.

Acceptance criteria:

- Shortcuts produce predictable prompts.
- Mutating modes do not silently run with broad write capability.

Tests:

- Assert shortcut prompt content.
- Assert `fix-ci` without `--write` stays non-mutating or asks for explicit write mode.

## Phase 4: Parse Codex JSONL Events

### Task 4.1: Create Event Parser

Files:

- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

Implementation:

- Add `parse_codex_jsonl(lines: list[str]) -> dict`.
- Parser should tolerate unknown event types.
- Extract if present:
  - Final assistant message.
  - Usage/token data.
  - Tool command executions.
  - File edits or patch summaries.
  - Error events.
- Preserve raw unknown events count for diagnostics.

Acceptance criteria:

- Parser never crashes on malformed JSONL.
- Parser returns stable keys even when usage data is missing.

Tests:

- Valid JSONL with usage.
- Valid JSONL without usage.
- Malformed lines.
- Unknown event types.
- Error event.

### Task 4.2: Record Codex Usage into Costs

Files:

- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

Implementation:

- Add helper `append_cost_entry(...)`.
- If Codex JSONL includes usage data:
  - Append a row to `project-docs/costs.md`.
  - Include date, type `codex`, task/prompt summary, input/output tokens, request count, cost if available, and notes.
- If cost is not available but tokens are:
  - Record tokens and leave cost blank or `0.0000` only if documented.
  - Prefer blank cost plus note: `tokens captured; cost unavailable`.

Acceptance criteria:

- Costs file remains parseable.
- Status budget remains accurate.
- Missing usage does not create fake cost entries.

Tests:

- Append cost with cost.
- Append token-only cost entry.
- No usage means no cost row unless explicitly requested.
- Existing costs header is preserved.

### Task 4.3: Record Codex Telemetry

Files:

- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`

Implementation:

- Add telemetry event:

  ```json
  {
    "type": "codex_exec",
    "schema_version": 1,
    "timestamp": "...",
    "user": "...",
    "command": "codex exec --json ...",
    "duration": 1.23,
    "exit_code": 0,
    "usage": {...},
    "tool_call_count": 3,
    "file_change_count": 2
  }
  ```

Acceptance criteria:

- Event is capped by existing telemetry cap.
- `status --json` can continue reading telemetry without breaking.

Tests:

- Telemetry event is emitted on success.
- Telemetry event is emitted on Codex failure.

## Phase 5: Codex Desktop Helpers

### Task 5.1: Add `synlynk init --codex`

Files:

- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`
- Update: `README.md`

Implementation:

- `synlynk init --codex` should:
  - Ensure `AGENTS.md` exists.
  - Print Codex-specific next steps.
  - Run or suggest `synlynk doctor --codex`.
- Do not write `.codex/` files until a verified config schema is adopted.

Acceptance criteria:

- Existing `init` behavior remains unchanged unless `--codex` is provided.
- `--codex` is safe and idempotent.

Tests:

- `init --codex` creates `AGENTS.md`.
- `init --codex` does not create unverified `.codex` config by default.

### Task 5.2: Add Deeplink Helper

Files:

- Modify: `bin/synlynk.py`
- Modify: `tests/test_synlynk.py`
- Update: `README.md`

Command:

```bash
synlynk codex open "<prompt>"
```

Implementation:

- Generate a Codex app link using the current repo path and encoded prompt only after confirming the current supported link format.
- If link format is unavailable or unstable, implement `--print-link` as experimental and clearly label it.
- Do not auto-open GUI apps in tests.

Acceptance criteria:

- Command is opt-in.
- Link generation is deterministic.
- Unsupported platforms receive a clear message.

Tests:

- Encodes path and prompt correctly.
- Does not invoke GUI by default in tests.

## Phase 6: Documentation and Reliability Hardening

### Task 6.1: Add End-to-End Smoke Tests

Files:

- Modify: `.github/workflows/test.yml`
- Modify: `tests/test_synlynk.py` or add `tests/test_cli_smoke.py`

Implementation:

- Add subprocess tests for:
  - `synlynk init` in a temp repo.
  - `synlynk init --force`.
  - `synlynk status --json`.
  - `synlynk doctor --json`.
  - `synlynk exec` exit-code propagation.
- For Codex command, use a fake `codex` executable in a temp PATH that emits JSONL.

Acceptance criteria:

- Tests do not require real Codex installation.
- CI remains network-free.

### Task 6.2: Update Generated Docs and Release Notes

Files:

- Update: `README.md`
- Update: `CHANGELOG.md`
- Update: `docs/codex-integration-proposals.md`
- Update: `docs/codex-synlynk-preferred-roadmap.md` if roadmap changes

Implementation:

- Document:
  - Codex interactive setup.
  - `AGENTS.md` behavior.
  - `synlynk doctor --codex`.
  - `synlynk codex` non-interactive workflow.
  - Known limitations.

Acceptance criteria:

- Docs clearly distinguish Codex CLI, Codex Desktop, and generic AI CLI behavior.
- No docs claim automatic cost capture unless implemented through JSONL parsing.

## Suggested Release Slices

### v0.3.0: Codex-Native Instructions and Diagnostics

- `AGENTS.md` template.
- README Codex section.
- `synlynk doctor --codex`.
- Config validation.
- Tests for init and doctor.

### v0.4.0: Codex Non-Interactive Runner

- `synlynk codex "<prompt>"`.
- JSONL parsing.
- Codex telemetry events.
- Cost ingestion when usage data exists.
- Fake-Codex smoke tests.

### v0.5.0: Codex Desktop Ergonomics

- `synlynk init --codex`.
- Optional app deeplink helper after verification.
- Codex shortcut modes.
- Better docs and project setup checks.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Codex JSONL event schema changes | Parser must tolerate unknown events and missing fields. Add fixture-based tests. |
| Codex Desktop config format changes | Do not write `.codex/` config until verified. Keep Desktop integration to `AGENTS.md`, diagnostics, and optional links first. |
| Users expect automatic cost dollars | Record tokens separately when cost is unavailable. Never invent cost values. |
| Watch daemon unreliable in sandboxed Codex sessions | Instructions should prefer `status` and explicit context refresh over requiring watch. |
| Single-file CLI becomes hard to maintain | Keep helpers small, add tests per helper, and consider splitting only after 1.0 or when complexity forces it. |

## Definition of Done

- `synlynk init` creates Codex-native `AGENTS.md`.
- `synlynk doctor --codex` accurately reports Codex readiness without network access.
- `synlynk codex "<prompt>"` runs `codex exec --json`, preserves exit codes, and records telemetry.
- Codex usage/cost data is ingested only when available from structured output.
- README clearly documents Codex CLI and Codex Desktop usage.
- CI includes fake-Codex subprocess tests.
