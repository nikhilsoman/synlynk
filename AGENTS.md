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

<!-- synlynk:harness vsop-repair verified:2026-08-09T18:03:36Z -->
# Harness Instructions (synlynk-managed — do not edit)

## PR Review Discipline
1. Assign a non-authoring agent to review the PR.
2. From within the PR's own checked-out worktree/branch, the reviewer must run `synlynk pr check` so it can auto-detect the PR via git/gh context.
3. The reviewer alone must merge the PR.
4. If the reviewer is unavailable, escalate to Claude.

**GitHub identity caveat (#423):** The non-authoring reviewer rule is a *process control* enforced by dispatch discipline, **not** a GitHub-enforced mechanism. All dispatched agents share one GitHub identity (`gh` under the repo owner), so GitHub cannot verify a different reviewer and `gh pr review --approve` fails with "Can not approve your own pull request" on every dispatch-authored PR. **Sanctioned fallback:** post a formal COMMENT review with an explicit approve checklist (as on PR #417) instead of `gh pr review --approve`.

## Brainstorm-First Policy
1. Do not write code before an approved spec exists in `docs/superpowers/specs/`.
2. Run the brainstorm using Claude via `synlynk dispatch`.
3. Spec is approved only when committed to the branch and Nikhil signs off.

## Design → Plan → Build Sequence
1. Design: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
2. Plan: `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
3. Build: Code implementation
- Spec not committed = do not write plan.
- Plan not committed = do not dispatch tasks.

## Capability-Based Task Allocation

**Note:** "Harness" below means the execution backend (Claude/Agy/Grok/Codex) that runs a 
task, not the Agent (role) doing the work
- See `docs/glossary-agent-vs-harness.md`

| Role | Harness | Tasks |
| :--- | :--- | :--- |
| pm / review / deploy / brainstorm | Claude | pm, review, deploy, brainstorm |
| implement / test / css / templates / content / subpages | Agy | implement, test, css, templates, content, subpages |
| implement / test / canvas / js / infra | Grok | implement, test, canvas, js, infra |
| implement / test / refactor / cli-plumbing | Codex | implement, test, refactor, cli-plumbing |
Do not start a task outside your role column without explicit approval from Claude.

**GitHub write routing (#426):** Route any task that requires GitHub write actions to **Grok by default**. Agy headless can complete `gh pr review`, `gh pr comment`, and `gh pr merge` writes when the machine-local `~/.gemini/antigravity-cli/settings.json` already contains scoped `command(gh pr review)`, `command(gh pr comment)`, and `command(gh pr merge)` allow-rules; that precondition is operator-confirmed, not reliably verifiable mid-task. Codex's `workspace-write` sandbox blocks network egress to `api.github.com` by design. Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically, but do not treat it as a hard identity guarantee yet: the token-stripping fallback does not prevent `gh` from using a locally logged-in personal keyring identity when no role-scoped GitHub App token is available (#569).

This table is generated from `.synlynk/config.json` so it tracks the repo's own routing rather than synlynk's default fleet assumptions.

<!-- /synlynk:harness -->
