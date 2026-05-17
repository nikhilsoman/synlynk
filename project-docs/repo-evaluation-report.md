# synlynk Repository Evaluation Report

Date: 2026-05-17

## Executive Assessment

synlynk has a coherent and useful product idea: a local, file-based coordination layer that gives multiple AI coding tools shared project state, task history, cost awareness, and safety signals. The strongest part of the repo is the product framing and the incremental "Lite first, daemon later" architecture. That direction is viable because it avoids external infrastructure, works with current AI CLIs, and gives users a simple mental model: keep `project-docs/` as human/AI-readable state and generate `.synlynk/context.md` as the machine-facing snapshot.

The current implementation is not yet as capable as the README claims. It is closer to an early prototype than a reliable v1.2-lite release. Core features such as context generation, telemetry logging, and Flatline Sentinel exist in partial form, but upgrade, budget tracking, command wrapping, and AI instruction enforcement need correction before this can be trusted as a developer workflow tool.

Overall viability: medium-high if the scope is narrowed to a local solo-developer context manager first. Viability drops sharply if the repo continues to present real-time hallucination detection, cross-tool cost accounting, auto-update, and team observability as already solved.

## Stated Goals

The repo presents synlynk as:

- A "Universal Context Switchboard" for stateless AI agents.
- A way to move between Claude, Gemini, Codex, Cursor, VS Code, and similar tools without losing project context.
- A lightweight local orchestration layer using `project-docs/` and `.synlynk/context.md`.
- A telemetry and cost pulse system for AI CLI usage.
- A future path toward daemon-based local coordination, MCP/JSON-RPC support, and team rollups.

These goals are directionally sound. The most valuable goal is not "quota hopping" by itself; it is continuity of context across tools. The repo should emphasize continuity, auditability, and reduced context reconstruction cost. "Quota hopping" is a catchy narrative, but it risks positioning the tool around provider limits instead of durable engineering value.

## Current Implementation Snapshot

Implemented:

- `synlynk init` creates `project-docs/`, `.synlynk/`, tool instruction files, and baseline templates.
- `synlynk exec <cmd>` regenerates context, runs a wrapped command, streams output, logs telemetry, estimates token/cost values from output, and checks for repeated failures.
- `generate_context()` compacts some state by including active tasks, active roadmap rows, memory, recent devlog entries, teammate activity in team mode, and sentinel alerts.
- Flatline Sentinel records an alert when the same command fails three times in a row.
- Basic config loading, mode detection, username detection, cost parsing helpers, and state-file writing exist.
- A pytest suite covers helper functions, context compaction, state writes, and sentinel behavior.

Not implemented or only stubbed:

- `synlynk watch start|stop|status`.
- `synlynk checkpoint`.
- `synlynk status` and `synlynk status --json`.
- Real `synlynk upgrade` behavior.
- `synlynk init --force`.
- A robust telemetry schema with event types, schema version, user attribution, and machine-readable status.
- Reliable cross-tool token/cost accounting.
- Exit-code propagation from wrapped commands.

## Critical Findings

1. README and roadmap overstate shipped functionality.

The README lists Flatline Sentinel, Budget & Cost Pulse, and frictionless telemetry as key v1.2.0-lite features, while the roadmap still marks Flatline Sentinel as planned and the implementation only partially supports it. `project-docs/todo.md` marks auto-update, Flatline Sentinel, budget alerts, and PATH setup complete, but `upgrade()` is a stub and install/version handling is inconsistent.

Correction: Split the README into "available now" and "planned" sections, then align roadmap and todo status with actual commands.

2. `synlynk upgrade` is non-functional.

`upgrade()` always sleeps and reports that the user is on the latest version. This directly contradicts the memory decision that auto-update must be seamless and the todo item marking it complete.

Correction: Either implement the GitHub releases check described in the spec or label `upgrade` experimental/unavailable.

3. `synlynk exec` likely masks child command failure.

`exec_command()` records the child `exit_code`, but `main()` does not call `sys.exit(exit_code)`. A failed wrapped command can therefore appear successful to the shell, CI, or scripts. This is a correctness bug for any CLI wrapper.

Correction: Return the child exit code from `exec_command()` and exit with it from `main()`.

4. Cost tracking is not trustworthy yet.

The implementation uses regex token extraction from command output plus hardcoded pricing. The design spec correctly says this should be removed because real CLI outputs vary and `costs.md` should be authoritative. There is also schema drift: the current repo's `project-docs/costs.md` has columns `Date | User | Requests | Tokens | Estimated Cost | Summary`, while the template and parser expect `Date | Type | Task/Command | Tokens | Requests | Cost | Notes`.

Correction: Choose one `costs.md` schema, migrate existing docs to it, and make `checkpoint`/`status` sum that source. Stop appending speculative cost entries from `exec`.

5. AI instruction templates are too weak for the stated protocol.

`SYNLYNK_GUIDE.md` defines a session-start protocol, maintenance rules, team behavior, and conflict checks. The generated `CLAUDE.md`, `GEMINI.md`, and `AI_INSTRUCTIONS.md` templates only say to read context and update docs. They do not enforce watch/checkpoint/status usage, attribution, team pull-before-edit behavior, or the 3-row start protocol.

Correction: Replace templates with the fuller protocol from the redesign spec and add `synlynk init --force` for existing projects.

6. The command surface promised by the spec is missing.

The spec describes `watch`, `checkpoint`, and `status`, but argparse only registers `init`, `upgrade`, and `exec`. Without `checkpoint` and `status`, synlynk cannot close the loop on context freshness, completed task archiving, budget visibility, sentinel visibility, or team summary.

Correction: Implement `status` before `watch`. `status` gives immediate user value and makes the system inspectable. Then add `checkpoint`, then `watch`.

7. The wrapper may degrade interactive CLI behavior.

`exec_command()` pipes stdout/stderr to capture output. This is useful for telemetry, but many AI CLIs change behavior when stdout is not a TTY. Interactive prompts, colors, terminal UI, progress rendering, and streaming behavior may degrade.

Correction: Decide whether `exec` is for non-interactive commands only, or implement a PTY-backed wrapper for interactive tools. For Lite, document the limitation clearly.

8. Repo hygiene needs attention.

The working tree includes generated artifacts such as `__pycache__`, `.pytest_cache`, `.venv`, `.synlynk/telemetry.json`, and `test_context_output/`. There is no root `.gitignore`. These files make review harder and increase the chance of publishing local state.

Correction: Add a root `.gitignore` and remove generated artifacts from version control if they are tracked.

## Utility Assessment

High utility:

- Context continuity across AI tools is a real developer pain point.
- Markdown-first state is easy to inspect, edit, diff, and recover.
- A local-only Lite tier reduces privacy concerns and setup friction.
- A status/checkpoint workflow could become a useful discipline layer for agentic coding sessions.

Medium utility:

- Flatline detection based on repeated command failures is useful, but should be framed as a heuristic safety signal, not true hallucination detection.
- Cost tracking is useful if manually logged or provider-sourced; speculative regex-based estimation is low confidence.

Low or risky utility:

- "Quota hopping" is a less defensible primary value proposition than "portable project context."
- Team observability is premature until the solo workflow is robust and the telemetry schema is stable.

## Recommended Enhancement Roadmap

P0 corrections before claiming v1.2-lite:

- Fix child exit-code propagation in `synlynk exec`.
- Align README, roadmap, todo, and spec with actual shipped behavior.
- Add root `.gitignore`.
- Resolve `costs.md` schema drift.
- Replace weak generated AI templates with full session protocol templates.
- Add CLI tests for `init`, `exec`, `upgrade`, and command failure behavior.
- Make `install.sh` and `bin/synlynk.py` report the same version.

P1 product-completeness work:

- Implement `synlynk status` with human and JSON output.
- Implement `synlynk checkpoint` to archive completed tasks, refresh context, and summarize budget.
- Convert telemetry entries to a versioned event schema.
- Remove speculative token extraction from `exec`.
- Add `synlynk init --force`.

P2 robustness and growth:

- Implement a polling `watch` command only after `status` and `checkpoint` are stable.
- Consider PTY support or document non-interactive limitations for wrapped AI CLIs.
- Add a migration command for old `project-docs` schemas.
- Add packaging metadata (`pyproject.toml`) or a clearer install/update contract.
- Add integration tests using temporary directories and subprocess calls.

## Suggested Positioning

Recommended positioning:

> synlynk is a local context and session ledger for AI-assisted development. It keeps project intent, active tasks, decisions, costs, and safety signals in a portable Markdown format so different AI tools can work from the same state.

Avoid leading with:

> Stop being locked into a single AI subscription.

That message may attract attention, but it understates the durable engineering benefit and may distract from the stronger product thesis: continuity, accountability, and project memory.

## Validation Performed

- Read repository documentation, roadmap, memory, todo, install script, implementation, specs, and tests.
- Ran syntax check: `python3 -m py_compile bin/synlynk.py` passed.
- Ran test suite with local venv: `.venv/bin/python -m pytest -q` passed with `21 passed`.

## Bottom Line

The repo has a viable and useful concept, and the Lite architecture is a sensible first step. The main issue is claim discipline: documentation, roadmap state, and code behavior are currently out of sync. The next best move is not to expand into MCP, team sync, or richer telemetry yet. First make the solo local loop dependable: truthful README, strong templates, reliable `exec`, inspectable `status`, idempotent `checkpoint`, and consistent cost/state schemas.
