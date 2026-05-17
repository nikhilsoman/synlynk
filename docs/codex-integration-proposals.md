# Codex Integration Proposals

## Validation Summary

Current Codex integration is weak but easy to improve.

| Integration Point | Current Status | Validation |
| --- | ---: | --- |
| Codex CLI executable | Present locally | `codex --version` returns `codex-cli 0.130.0`. |
| `synlynk exec codex` | Works generically | It can launch Codex and log duration/exit because `synlynk exec <cmd>` is generic. |
| Codex-native instructions | Missing | No `AGENTS.md`, `AGENTS.override.md`, or `.codex/` config exists. |
| `AI_INSTRUCTIONS.md` for Codex | Not reliable | Codex reads `AGENTS.md` / `AGENTS.override.md` by default; other filenames are ignored unless configured as fallbacks. |
| Codex desktop app | Not integrated | No `.codex` project config, local environment setup, or app actions are present. |
| Codex non-interactive mode | Not integrated | No wrapper around `codex exec --json`, so synlynk cannot capture Codex usage events or final output reliably. |
| Cost tracking from Codex | Manual only | Codex `exec --json` can emit structured events, but synlynk does not parse them yet. |

## Most Important Fix

Add first-class `AGENTS.md` generation.

Codex reads `AGENTS.md` before work and builds an instruction chain from global and project files. It does not automatically read this repo's `AI_INSTRUCTIONS.md` unless the user configures fallback filenames. Today, Codex CLI/Desktop users may never see synlynk's session protocol.

Recommended change:

- Add `AGENTS.md` to `TEMPLATES`.
- Keep it concise enough for Codex project-doc limits.
- Include:
  - Read `.synlynk/context.md` at session start.
  - Run `synlynk status` before and after substantial work.
  - Run `synlynk checkpoint` at task boundaries.
  - Update `project-docs/todo.md`, `memory.md`, `costs.md`, and devlogs.
  - Do not assume `watch` is running; check it.
- Add tests asserting `synlynk init` creates `AGENTS.md`.

## Codex CLI Improvements

1. Add a Codex-specific command path:

   ```bash
   synlynk codex "<prompt>"
   ```

   Internally:

   - Refresh context before execution.
   - Run `codex exec --json --cd <repo> "<prompt>"`.
   - Parse JSONL events.
   - Record usage into `project-docs/costs.md` when usage data is available.
   - Record file changes, command executions, duration, and exit code into telemetry where available.

2. Support automation shortcuts:

   ```bash
   synlynk codex review
   synlynk codex summarize
   synlynk codex fix-ci
   ```

   Use mutation-capable sandbox settings only when mutation is intended.

3. Add Codex argument passthrough:

   ```bash
   synlynk codex --codex-args "--model gpt-5.4 --sandbox workspace-write" "<prompt>"
   ```

   Users need access to Codex-native model, sandbox, profile, approval, and JSON controls. synlynk should not hide those controls.

## Codex Desktop App Improvements

1. Add `synlynk init --codex`.

   - Create `AGENTS.md`.
   - Optionally create `.codex/` starter files only when the app configuration format is stable and verified.
   - Avoid guessing app config schema.

2. Add recommended Codex app actions:

   - `synlynk status`
   - `synlynk checkpoint`
   - `synlynk watch status`
   - `pytest tests/`

   These map well to local project actions that Codex Desktop can expose or run.

3. Add a deeplink helper:

   - Codex app supports opening new sessions with repo path and prompt metadata.
   - A future command could print or open a generated Codex app link for the current repo and task.
   - This is useful for opening a Codex Desktop thread already pointed at the repository.

## Reliability Recommendations

- Treat Codex as first-class, not as a generic AI CLI. `CLAUDE.md`, `GEMINI.md`, `.cursorrules`, and `AI_INSTRUCTIONS.md` are not enough. Add `AGENTS.md`.
- Do not require the watcher daemon in Codex instructions. Codex may run in sandboxes, worktrees, or app-managed environments where background daemons are not reliable. Prefer: run `synlynk status`; refresh context/checkpoint if stale.
- Add `synlynk doctor --codex`.
- Check:
  - `codex` on PATH.
  - `codex --version`.
  - `AGENTS.md` exists.
  - `.synlynk/context.md` exists and is fresh.
  - `.codex/` local environment config if present.
  - Git repository exists.
  - `project-docs/costs.md` is parseable.
- Add subprocess integration tests for Codex behavior.
- Keep app-server integration later. Codex app-server is powerful but heavier than synlynk needs now. First build reliable `AGENTS.md` and `codex exec --json` support.

## Recommended Sequence

1. Add `AGENTS.md` template and tests.
2. Add `synlynk doctor --codex`.
3. Add `synlynk codex` wrapper for non-interactive `codex exec --json`.
4. Add JSONL event parsing and telemetry/cost ingestion.
5. Add optional Codex Desktop helpers after the Codex-native local file contract is stable.
