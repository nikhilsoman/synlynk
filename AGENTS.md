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

<!-- synlynk:harness vsop-repair verified:2026-08-29T07:09:44Z -->
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

**GitHub write routing (#426):** Route any task that requires GitHub write actions to **claude by default, Agy as fallback** (live-verified 2026-08-23; see `docs/superpowers/specs/2026-08-23-gh-write-identity-hardening-design.md`)
- Grok's dispatch sandbox denies `bash` execution entirely in this environment (confirmed via `git diff origin/main` showing a total silent no-op despite a generic "OK, exit 0" job status — do not trust job-status alone for Grok gh-write attempts)
- Codex's `workspace-write` sandbox blocks network egress to `api.github.com` by design
- Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically; it now also auto-implies the `run:shell` permission grant and fails closed with a `RuntimeError` if no role is resolvable via `--as-agent`, `--story`, or `--role` (#569)

This table is generated from `.synlynk/config.json` so it tracks the repo's own routing rather than synlynk's default fleet assumptions.

## Herdr Workspace Protocol
1. At a task/session boundary, finish housekeeping (project docs, memory, cost log) before running `/clear`.
2. File a ticket — with an appropriate label (e.g. `tech-debt` for a gap surfaced mid-task, out of current scope) — for anything left open beyond the current story/goal/session, rather than letting it go untracked.
3. Launch each new session in a new Herdr tab + new pane, within the same workspace (Herdr workspace = synlynk workspace).
- Never reuse another session's pane.
4. Name each pane and tab with the synlynk session_id / job-ID / agent name so panes are identifiable at a glance.
5. When working in person via Herdr, run interactive-shell sessions for each of the 4 core harnesses (Claude, Codex, Agy, Grok) as needed — synlynk aims to be harness-agnostic, giving each harness equal "home" (interactive) and "away" (headless dispatch) airtime while cycling through implementation work across target workspaces.
- (Local harness — Ornith+Aider+oMLX — is a future extension, not yet wired up.)
6. Any new harness interactive session also gets its own new tab within the same workspace.
7. Begin every Claude session with `/rc`.
- **Precondition for all Herdr commands:** check `test "${HERDR_ENV:-}" = 1` before issuing any `herdr` command; if unset, this agent is not running inside Herdr and must not attempt to control a Herdr session from outside it.
- Herdr is Apache-2.0 licensed (no NOTICE file) — free to reference/use without royalty or attribution beyond standard license retention.
- Full CLI reference: https://github.com/herdrdev/herdr/blob/v0.8.2/skills/herdr/SKILL.md

<!-- /synlynk:harness -->
