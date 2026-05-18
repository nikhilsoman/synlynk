# Codex Support Playbook

## Support Scope

This playbook covers Synlynk support for:

- Codex CLI interactive sessions.
- Codex CLI non-interactive `codex exec --json`.
- Codex Desktop App local project usage.
- Codex launched through third-party IDE terminals or tasks.

## First Response Checklist

Ask users for:

- `synlynk --version`.
- `codex --version`.
- `synlynk doctor --codex --json`.
- Operating system.
- Shell or IDE used.
- Whether they are using Codex CLI, Desktop App, or an IDE integration.
- Current repo root and command run.

## Common Failure Modes

| Symptom | Likely Cause | Action |
| --- | --- | --- |
| Codex ignores Synlynk instructions | Missing or stale `AGENTS.md` | Run `synlynk init --codex` or `synlynk init --force`. |
| Codex starts with old project state | Stale `.synlynk/context.md` | Run `synlynk checkpoint` or refresh context. |
| Desktop App does not see project docs | Opened wrong folder or subfolder | Open repository root and run `synlynk doctor --codex`. |
| IDE terminal cannot find Codex | PATH mismatch in IDE shell | Check `codex --version` in same terminal. |
| Costs stay at zero | Usage not logged or unavailable | Use `synlynk cost add` once implemented; do not invent cost values. |
| Watcher behaves inconsistently | Daemon/sandbox mismatch | Use explicit status/checkpoint workflow instead of relying on watch. |

## Reliability Rules

- Prefer native Codex instructions through `AGENTS.md`.
- Keep `AGENTS.md` short and stable.
- Treat `AI_INSTRUCTIONS.md` as fallback documentation, not the Codex integration point.
- Avoid generating `.codex/` files until the supported app config format is verified.
- Never silently ignore Codex child exit codes.
- Never fabricate token or cost data.

## Release Validation Checklist

Before releasing Codex integration changes:

- `python -m py_compile bin/synlynk.py`.
- `pytest tests/`.
- Fake-Codex subprocess tests pass.
- `synlynk init --codex` creates expected files.
- `synlynk doctor --codex --json` is parseable.
- `synlynk codex` preserves exit codes.
- README and `docs/codex/` are updated.
- Changelog includes Codex changes.

## Maintenance Cadence

- Review `Platform:Codex` issues weekly during active development.
- Revalidate Codex CLI JSONL fixtures after Codex CLI updates.
- Revisit Desktop App docs when app config or deeplink behavior changes.
- Keep third-party IDE docs focused on portable terminal behavior unless an IDE has a stable Codex integration contract.
