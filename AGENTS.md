<!-- synlynk:start version="0.13.0" tool="codex" -->
# synlynk Codex Instructions

## Identity & Attribution
- **Engine:** OpenAI Codex CLI (`codex exec`)
- **Commit trailer:** `Co-Authored-By: Codex <noreply@openai.com>`
- **Branch prefix:** prefer `feat/` / `fix/` task-scoped names when authoring

## Role
Implementer / tests / refactor / CLI plumbing. Builder-only for fleet claims until GH-write and package-install matrix cells are Proven (see fleet operability design).

## Headless contract
- Invoked via `codex exec` with workspace sandbox flags from synlynk dispatch.
- Prefer non-interactive completion; write commits with the Co-Authored-By trailer above.
- Do not assume GitHub write works headless — route PR review/merge to agents with `can_gh_write` unless role tokens are provisioned.

## Git Worktree-First Policy
Never commit directly to `main`/`master`. Use the job worktree provided by dispatch.

## Repo Hygiene
1. Task-scoped branches only.
2. Co-Authored-By trailer required on commits.
3. Run tests for touched areas before claiming done.
4. Do not rewrite unrelated files.

## Cost Visibility
Log estimated cost when dispatching further work; prefer minimal context mode for mechanical tasks.

<!-- synlynk:end -->
