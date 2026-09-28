<!-- synlynk:start version="0.23.0-dev" tool="grok" -->
# synlynk Grok Instructions

## Identity & Attribution
- **Engine:** grok-composer-2.5-fast
- **Commit trailer:** `Co-Authored-By: Grok <noreply@x.ai>`
- **Branch prefix:** `feat/grok/` or `fix/grok/`

## Branch Naming
- `feat/grok/<description>` — new functionality
- `fix/grok/<description>` — bug fixes
- `chore/<description>` — deps, docs, config

## Domain Ownership
| Domain | Owned by this agent | Notes |
|:---|:---|:---|
| TODO: fill domains for this agent | | |

## Shared synlynk Protocol

Load `AI_INSTRUCTIONS.md` for the full shared synlynk protocol, including the session lifecycle, worktree policy, live-issues SOP, document discipline, GitHub Projects workflow, and harness SOPs.

<!-- synlynk:end -->

<!-- synlynk:harness v2.1.275 verified:2026-09-23T18:58:15Z -->
# Harness Instructions (synlynk-managed — do not edit)

## Your Role
implement, test, canvas, js, infra

## PR Review Discipline
1. Assign a non-authoring agent to review the PR.
2. From within the PR's own checked-out worktree/branch, the reviewer must run `synlynk pr check` so it can auto-detect the PR via git/gh context.
3. The reviewer alone must merge the PR.
4. For a `BEHIND` or `DIRTY` PR, allow at most 2 `gh pr update-branch` → CI-wait cycles. If the PR is still `BEHIND` or `DIRTY` after the second cycle, stop retrying and report back for escalation.
5. If the reviewer is unavailable, escalate to Claude.

**GitHub identity note (#423):** qa APPROVE (`gh pr review --approve`) is the default whenever the reviewer identity differs from the PR author login (e.g. role App reviewing a human or sibling App PR). Dispatches under role App identities satisfy GitHub's non-author review requirement for real approvals. Route day-to-day reviews through `qa` and any feature/architecture-impacting review through `architect`. **Fallback (same-identity collision only):** post a formal COMMENT review with an explicit approve checklist (as on PR #417) only when the reviewer GitHub login equals the PR author login, where GitHub rejects self-approval. Do not tell sessions to skip `--approve` by default.

**Merge authority is enforced from `.synlynk/policy.json` (`merge_authority`)** — a reviewer must run `synlynk policy check-merge --role <role>` before `gh pr merge`; a non-zero exit means do not merge.

## Brainstorm-First Policy
1. Do not write code before an approved spec exists in `docs/superpowers/specs/`.
2. Run the brainstorm using the Architect/PM role via `synlynk dispatch` (or locally if running in Home Conductor mode).
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

**GitHub write routing (#426):** Route any task that requires GitHub write actions to **Codex by default, Claude/Agy as fallbacks** (PR #1271, verified live in job `job-836e13a4`)
- Grok's dispatch sandbox denies `bash` execution entirely in this environment (confirmed via `git diff origin/main` showing a total silent no-op despite a generic "OK, exit 0" job status — do not trust job-status alone for Grok gh-write attempts)
- Codex receives network access only for explicit `--requires-gh-write` dispatches
- Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically; it now also auto-implies the `run:shell` permission grant and fails closed with a `RuntimeError` if no role is resolvable via `--as-agent`, `--story`, or `--role` (#569)

This table is generated from `.synlynk/config.json` so it tracks the repo's own routing rather than synlynk's default fleet assumptions.

## Cost Visibility
1. Log estimated_cost in the job context header before dispatch.
2. Check `synlynk status` for current burn rate.
3. Confirm all work is captured via telemetry and manual/PM work is logged via `synlynk cost log`.
4. Append actual cost to `project-docs/costs.md`.

## Repo Hygiene
1. Do not commit directly to main or master.
2. Use the repo's documented task-scoped branch pattern; if none is recorded, follow the project's existing feature/fix/chore naming convention.
3. Co-Authored-By trailer is required: Claude (`Co-Authored-By: Claude Sonnet <noreply@anthropic.com>`), Agy (`Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`), Codex (`Co-Authored-By: Codex <noreply@openai.com>`), Grok (`Co-Authored-By: Grok <noreply@x.ai>`).
4. Use worktree per feature with `git worktree add`.
5. Run `git branch --show-current` before committing to verify branch.

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

## Headless Execution Contract
- Execution mode: pipe
- Non-interactive flag: --single
- Stdout flush: native
## Active Dispatch Flags
- Valid: --always-approve --permission-mode --output-format --model --single
- Invalid (do not use): --yes --dangerously-skip-permissions --print --non-interactive
## Network Dependencies
- Required: cli-chat-proxy.grok.com:443

<!-- /synlynk:harness -->
