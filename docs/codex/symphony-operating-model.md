# OpenAI/Codex Symphony Operating Model

This model treats Synlynk's Codex integration as a coordinated product surface rather than a single CLI feature. The "Symphony" is the set of parts that must stay in tune: instructions, local state, CLI execution, desktop workflows, IDE shells, telemetry, tests, and support.

## 1. Score: Product Intent and Contracts

The score defines what all integrations must follow.

- Codex reads native instructions from `AGENTS.md`.
- Synlynk remains the local project memory and session ledger.
- `.synlynk/context.md` is generated state, not hand-authored truth.
- `project-docs/` is the human-readable source of product state.
- Codex CLI/Desktop integrations must not require background daemons.
- Cost records must be based on structured usage data or explicit user/agent entries.

Required artifacts:

- Codex support roadmap.
- Implementation plan.
- GitHub issue backlog.
- Test plan and release gates.
- Support playbook.

## 2. Parts: Integration Surfaces

Each surface has its own responsibilities.

### Codex CLI Interactive

- Reads `AGENTS.md`.
- Uses `synlynk status` and `synlynk checkpoint` during sessions.
- Relies on the user or Codex agent to follow the session protocol.
- Does not require `synlynk exec codex`, though generic wrapping should still work.

### Codex CLI Non-Interactive

- Uses `codex exec --json`.
- Synlynk captures JSONL events, exit code, duration, and usage when present.
- Suitable for repeatable review, summarize, and automation commands.
- Must preserve Codex-native flags such as model, sandbox, approval, and profile.

### Codex Desktop App

- Uses `AGENTS.md` and local project files.
- May expose documented local actions such as `synlynk status`, `checkpoint`, and tests.
- Should not depend on speculative `.codex/` config until verified.
- Desktop helpers should be optional and reversible.

### Third-Party IDEs

- Often invoke Codex CLI through embedded terminals or task runners.
- Should rely on `AGENTS.md`, `synlynk doctor --codex`, and explicit commands.
- Must not assume IDE-specific context loading behavior.
- Should keep project state portable across IDEs.

## 3. Conductor: Synlynk CLI

Synlynk coordinates the surfaces through commands.

- `synlynk init --codex`: creates Codex-native setup.
- `synlynk doctor --codex`: validates readiness.
- `synlynk codex`: runs non-interactive Codex workflows.
- `synlynk status`: reports local state.
- `synlynk checkpoint`: archives task progress and refreshes context.
- `synlynk context`: future scoped-context generation.

The conductor must keep exit codes, telemetry, costs, and generated context consistent.

## 4. Rehearsal: Quality Gates

Every Codex integration release must pass:

- Unit tests for templates, diagnostics, parsing, telemetry, and costs.
- Subprocess tests with a fake `codex` binary.
- Python 3.8 compatibility checks.
- No network dependency in tests.
- Manual smoke test with real `codex --version` when available.
- Documentation review to avoid overclaiming Desktop App behavior.

## 5. Performance: Release Slices

Release work in small slices:

1. Native instructions and docs.
2. Diagnostics and validation.
3. Non-interactive runner.
4. JSONL usage parsing and cost ingestion.
5. Desktop helpers.
6. Third-party IDE hardening.

Each slice must leave the product usable and truthfully documented.

## 6. Tuning: Support and Maintenance

The Codex owner monitors:

- Codex CLI help and behavior changes.
- Codex Desktop App local project behavior.
- JSONL event schema drift.
- User issues tagged `Platform:Codex`.
- Flaky watcher behavior in Codex-managed environments.
- Misleading cost, token, or status output.

Maintenance cadence:

- Review Codex issues weekly while active development is ongoing.
- Revalidate `codex exec --json` fixtures every Codex CLI minor release.
- Keep `AGENTS.md` concise and backwards-compatible.
- Prefer new diagnostics over hidden assumptions.
