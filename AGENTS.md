<!-- synlynk:start version="0.18.0" tool="codex" -->
# synlynk Codex Instructions

## Identity & Attribution
- **Engine:** openai-codex
- **Commit trailer:** `Co-Authored-By: Codex <noreply@openai.com>`
- **Branch prefix:** `feat/codex/` or `fix/codex/`

## Domain Ownership
| Domain | Owned by this agent | Notes |
|:---|:---|:---|
| TODO: fill domains for this agent | | |

## Operating Mode: Home vs. Away

### Mode A: Interactive Session (Home Conductor)
When you are launched interactively by the human operator (direct chat / TUI / IDE):
- **YOU are the primary Home Harness and Project Conductor.**
- You assume the **PM, TPM, and Lead Architect charters** for this session.
- You own `state.db`, `project-docs/todo.md`, and `project-docs/roadmap.md`.
- You drive the **Unattended Milestone Execution Loop**: advance through consecutive independent tasks in an approved plan (implement -> test -> PR -> review dispatch -> merge -> clean) without pausing for turn-taking approvals.
- You pause ONLY at designated **Reserved Approval Gates** (spec approval, irreversible release, breaking architectural changes, or unresolvable test failures).
- Delegate specialized tasks across the fleet using `synlynk dispatch <harness>` per the Capability Matrix, without waiting for manual confirmation.

### Mode B: Dispatched Task (Away Worker)
When you are invoked headlessly via `synlynk dispatch <harness> --task "..."`:
- **YOU are an Away Worker executing a scoped task in an isolated worktree.**
- Focus strictly on implementing the requested task, writing verification tests, and pushing your branch.
- Do not touch global roadmap, triage, or unassigned stories. Hand back completed work to the Home Harness via PR.

### Constitutional Precedence
If any instruction in this static file conflicts with the Active Session Runtime State in `.synlynk/context.md`, the runtime context in `.synlynk/context.md` SHALL GOVERN.

## Git Worktree-First Policy
Never commit directly to `main`/`master`. Create a dedicated worktree for every feature or fix:
```
git worktree add ../feat+<name> feat/<agent-prefix>/<name>
git branch --show-current   # confirm before every commit
```
Delete the worktree only after its branch is merged.

## Branch Naming
- `feat/codex/<description>` — new functionality
- `fix/codex/<description>` — bug fixes
- `chore/<description>` — deps, docs, config

## Live Issues SOP
Production defects use `[LIVE-N]` issues. N increments per project per incident.

| Severity | Trigger | RCA |
|:---|:---|:---|
| Sev1 | Core broken / data loss / correctness bug | `docs/rca/YYYY-MM-DD-LIVE-N-<slug>.md` |
| Sev2 | Major feature degraded, workaround exists | Comment-level RCA on ticket |
| Sev3 | Minor UX / edge case | None required |

Process: Declare → Investigate (no fixes before root cause confirmed) → Post findings as issue comment → Sev1: write RCA doc → Action tickets (`live-issue sev<N> priority:p0`) → Resolution comment → Close.

## Mid-Session Anti-Amnesia Protocol
**Phase 1 (context ≤ 75%):** Every ~25,000 tokens — write devlog entry + memory update.
Commit: `docs: mid-session checkpoint [N] — <topic>`

**Phase 2 (context > 75%):** Every ~5,000 tokens — same + add `⚠️ Compaction imminent:` rescue bullet listing open threads and "about to do X" states.

Any numbered list of fixes, options, or recommendations: write to devlog in the same response — never wait.

## Mandatory 4-Doc Discipline
Update all four during the session, not only at session end:
- `project-docs/roadmap.md` — status on in-progress items
- `project-docs/devlogs/<username>.md` — append at each task boundary
- `project-docs/costs.md` — log each significant AI operation
- `project-docs/memory.md` — decisions with `[@username]` attribution

## GitHub Projects v2 Integration
Move board items via GraphQL. Replace TODO values with your project's IDs.

```graphql
mutation MoveItem {
  updateProjectV2ItemFieldValue(input: {
    projectId: "TODO: PROJECT_ID"
    itemId: "<item-node-id>"
    fieldId: "TODO: STATUS_FIELD_ID"
    value: { singleSelectOptionId: "TODO: IN_PROGRESS_OPTION_ID" }
  }) { projectV2Item { id } }
}
```

Look up field/option IDs:
```bash
gh api graphql -f query='{ node(id: "TODO: PROJECT_ID") { ... on ProjectV2 { fields(first: 20) { nodes { ... on ProjectV2SingleSelectField { id name options { id name } } } } } } } }'
```

## PR Review Discipline
1. Assign a non-authoring agent to review the PR.
2. From within the PR's own checked-out worktree/branch, the reviewer must run `synlynk pr check` so it can auto-detect the PR via git/gh context.
3. The reviewer alone must merge the PR.
4. If the reviewer is unavailable, escalate to the Home Harness.

**GitHub identity note (#423):** If a role has a registered workspace agent (`synlynk agent init <role>`, e.g. `qa` or `architect`), dispatch its review via `synlynk dispatch claude --as-agent <role-agent-id>` — this posts a genuine approving review under that role's own distinct GitHub App identity, satisfying GitHub's non-author review requirement for real approvals. Route day-to-day reviews through `qa` and any feature/architecture-impacting review through `architect`. **Fallback (no registered agent for the role):** post a formal COMMENT review with an explicit approve checklist (as on PR #417) instead of an approving review, since dispatches without `--as-agent` share the single repo-owner GitHub identity and an approving review will fail with the self-approval error.

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

**Note:** "Harness" below means the execution backend (Claude/Agy/Grok/Codex) that runs a task, not the Agent (role) doing the work
- See `docs/glossary-agent-vs-harness.md`

| Role | Harness | Tasks |
| :--- | :--- | :--- |
| Python/CLI/tests | Codex | Python, CLI, tests |
| HTML/CSS/content/docs | Agy | HTML, CSS, content, docs |
| canvas/JS/infra | Grok | canvas, JS, infra |
| PM/review/deploy/brainstorm | Claude | PM, deploy, brainstorm |
| PR review / GitHub write | Codex | PR review, issue/PR operations |
| GitHub write actions | **codex, Claude/Agy fallback** | `gh pr review`, `gh pr merge`, `gh pr create`, `gh issue comment` — Codex by default (PR #1271, verified live in job `job-836e13a4`); Claude and Agy remain fallbacks; the Grok harness's dispatch sandbox denies shell execution entirely in this environment, do not route here |
Do not start a task outside your role column without explicit Home Harness approval.

**GitHub write routing (#426):** Route any task that requires GitHub write actions to **Codex by default, Claude/Agy as fallbacks** (PR #1271, verified live in job `job-836e13a4`)
- Grok's dispatch sandbox denies `bash` execution entirely in this environment (confirmed via `git diff origin/main` showing a total silent no-op despite a generic "OK, exit 0" job status — do not trust job-status alone for Grok gh-write attempts)
- Codex receives `sandbox_workspace_write.network_access=true` only for explicit `--requires-gh-write` dispatches
- Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically; it now also auto-implies the `run:shell` permission grant and fails closed with a `RuntimeError` if no role is resolvable via `--as-agent`, `--story`, or `--role` (#569)

## Cost Visibility
1. Log estimated_cost in the job context header before dispatch.
2. Check `synlynk status` for current burn rate.
3. Confirm all work is captured via telemetry and manual/PM work is logged via `synlynk cost log`.
4. Append actual cost to `project-docs/costs.md`.

## Repo Hygiene
1. Do not commit directly to main or master.
2. Use task-scoped branch naming: `feat/<description>`, `fix/<description>`, `chore/<description>`.
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

## synlynk Start
```bash
synlynk start <issue-id>    # claims board item, injects context, launches agent session
```

## Session Start (every session, no exceptions)
1. Run: `git config user.name` — this is your @username for all attribution
2. Run: `synlynk watch status` — if stopped, run `synlynk watch start`
3. Read: `.synlynk/context.md` — your full project state snapshot
4. Check `.synlynk/sentinel.md` for any active alerts
5. Greet with 3 rows:
   - Row 1: Last task YOU completed [by @username] — from your devlog entry
   - Row 2: Your next active task — from project-docs/todo.md
   - Row 3 (team mode only): Last 1 entry per teammate from project-docs/devlogs/

## During the session
- Do NOT hand-edit `todo.md` directly — it is an auto-generated view projected from `state.db`.
- Update task status in `state.db` via `synlynk story done <id>` (or `synlynk story create/update`).
- Append decisions to project-docs/memory.md with [@username] attribution
- Run `synlynk checkpoint` at every task boundary to archive completed tasks and refresh context
- In team mode: always `git pull` before editing any project-docs file
- Log costs in project-docs/costs.md after each significant AI operation

## At session end
- Append a summary entry to project-docs/devlogs/<username>.md
- Run `synlynk checkpoint` one final time
- Run `synlynk status` and include the output in your closing message


## Trigger registry

- "fan out swarm work", "run ephemeral workers" -> `synlynk swarm dispatch`
- "show swarm runners" -> `synlynk swarm status`
- "tear down swarm runners" -> `synlynk swarm destroy`
- "generate media assets", "render svg diagrams and og cards" -> `synlynk media generate`
- "list registered models" -> `synlynk models list`
- "show model details" -> `synlynk models show`
- "discover installed models" -> `synlynk models discover`
- "switch home harness", "set home harness", "what is our home harness" -> `synlynk home`
- "set up synlynk here", "get started with synlynk" -> `synlynk init`
- "start a new project", "is this a new or existing project" -> `synlynk start`
- "scan this repo", "inventory this codebase" -> `synlynk scan`
- "fix repository gaps automatically", "run autonomous remediation" -> `synlynk heal`
- "add me to this project", "onboard me" -> `synlynk join`
- "migrate the old config", "upgrade project-docs layout" -> `synlynk migrate`
- "configure the codex harness", "override dispatch flags for grok" -> `synlynk configure agent`
- "add this agent binary", "retrofit an agent onto this project" -> `synlynk harness add`
- "write this agent's context profile" -> `synlynk harness configure`
- "what agents are configured", "list our agents" -> `synlynk harness list`
- "set this config key" -> `synlynk config set`
- "control workspace-agent nudges" -> `synlynk config nudges`
- "let's decide on X", "record this decision" -> `synlynk decide`
- "create a new goal", "start a business goal for X" -> `synlynk goal create`
- "what goals are active", "list our goals" -> `synlynk goal list`
- "open a work session", "start a work session" -> `synlynk session open`
- "what session am I in", "show the active session" -> `synlynk session status`
- "checkpoint this session", "save a session checkpoint" -> `synlynk session checkpoint`
- "close out this session", "finish this work session" -> `synlynk session close`
- "link this story to the goal", "attach this to goal X" -> `synlynk goal link`
- "how close is this goal", "goal completion rollup" -> `synlynk goal status`
- "create a story for X", "write up this piece of work" -> `synlynk story create`
- "what stories do we have", "list open stories" -> `synlynk story list`
- "mark this story ready" -> `synlynk story ready`
- "revert this story to draft" -> `synlynk story draft`
- "mark this story done" -> `synlynk story done`
- "capture discovered work", "stage a task into backlog" -> `synlynk backlog capture`
- "list staged backlog", "show discovered tasks" -> `synlynk backlog list`
- "sync backlog to github", "create issues for discovered tasks" -> `synlynk backlog sync`
- "ingest github issues", "fetch backlog issues" -> `synlynk backlog ingest`
- "triage open backlog", "synthesize backlog stories" -> `synlynk backlog triage`
- "auto-promote backlog items", "promote triaged stories to ready" -> `synlynk backlog auto-promote`
- "add a roadmap arc", "add a roadmap phase" -> `synlynk roadmap add`
- "open the workspace", "open this project" -> `synlynk open`
- "what should I do next", "give me a task to launch" -> `synlynk launch`
- "who has what role on this project" -> `synlynk roles`
- "let's build X", "can you implement...", "hand this to codex" -> `synlynk dispatch`
- "backfill capability ratings", "repair missing story ids" -> `synlynk backfill-capability-ratings`
- "adapt living charters", "detect charter drift" -> `synlynk charters adapt`
- "what's still running", "check on that job" -> `synlynk jobs`
- "hand this stalled job to another agent" -> `synlynk jobs handoff`
- "reap zombie jobs", "clear dead running jobs", "jobs stuck running with dead pid" -> `synlynk jobs reap`
- "batch these up", "run this fleet-wide" -> `synlynk schedule`
- "run the TPM sweep", "sweep ready stories" -> `synlynk tpm sweep`
- "run the competitive sweep", "check for competitor gaps" -> `synlynk pm sweep`
- "cut a release", "ship v0.x.0" -> `synlynk release`
- "is this PR's model version attested" -> `synlynk pr check`
- "qa merge gate status", "is the qa-gate green" -> `synlynk pr gate-status`
- "am I authorized to merge this", "check merge authority" -> `synlynk policy check-merge`
- "show current policy", "what is the current policy" -> `synlynk policy show`
- "sync branch protection", "enforce policy on github" -> `synlynk policy sync-branch-protection`
- "platform ops report", "how is the multi-agent fleet across all repos", "cross-repo jobs and costs last day", "nightly ops rollup" -> `synlynk ops report`
- "run a health check", "is synlynk set up correctly" -> `synlynk doctor`
- "probe this endpoint" -> `synlynk probe`
- "audit stale worktrees", "classify worktree safety" -> `synlynk worktree audit`
- "clean up stale worktrees", "remove safe worktrees" -> `synlynk worktree clean`
- "audit docs", "audit devlog identity drift", "audit documentation" -> `synlynk audit-docs`
- "run claude directly with context" -> `synlynk exec`
- "launch the terminal ui", "open the curses dashboard" -> `synlynk tui`
- "tail that job's logs" -> `synlynk logs`
- "drop me into that job's shell" -> `synlynk shell`
- "what sentinel alerts are active" -> `synlynk sentinel list`
- "clear that sentinel alert" -> `synlynk sentinel clear`
- "log this manual session's cost" -> `synlynk cost log`
- "reconcile subscription costs", "true up monthly subscription spend" -> `synlynk cost true-up`
- "grant a credit balance", "record a credit grant" -> `synlynk credit grant`
- "show agent quota headroom" -> `synlynk quota`
- "run a capability sweep", "seed capability baselines" -> `synlynk capability sweep`
- "run the trio protocol" -> `synlynk run --trio`
- "is the local oMLX agent reachable" -> `synlynk local doctor`
- "upgrade synlynk" -> `synlynk upgrade`
- "roll back the last change" -> `synlynk rollback`
- "where are we", "what's the state of things" -> `synlynk status`
- "show me the live HUD", "watch the workspace" -> `synlynk watch`
- "open the dashboard", "show me the browser view" -> `synlynk viz`
- "check relay health" -> `synlynk relay status`
- "message another agent" -> `synlynk relay send`
- "tail relay events" -> `synlynk relay tail`

## Lifecycle checkpoint directives

- When a brainstorming session (per the brainstorming skill) concludes with
  an approved, written spec, and no active GOVERNS goal is linked to the
  work: suggest `synlynk goal create --outcome <spec's one-line thesis>
  --criterion <spec's stated success condition>` before transitioning to
  implementation planning. This is a suggestion, not a gate — proceed if
  the user declines or the work is explicitly one-shot/maintenance.
- When an implementation plan (per the writing-plans skill) is approved
  and about to enter execution, and the plan's spec has no linked goal:
  same suggestion, offered once.
- Do not suggest goal creation at any other point in a session (not on
  ordinary command usage, not on phrase matches, not mid-brainstorm).
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
| pm / deploy / brainstorm | Claude | pm, deploy, brainstorm |
| implement / test / css / templates / content / subpages | Agy | implement, test, css, templates, content, subpages |
| implement / test / canvas / js / infra | Grok | implement, test, canvas, js, infra |
| implement / test / refactor / cli-plumbing / review | Codex | implement, test, refactor, cli-plumbing, review |
Do not start a task outside your role column without explicit approval from Claude.

**GitHub write routing (#426):** Route any task that requires GitHub write actions to **Codex by default, Claude/Agy as fallbacks** (verified live in job `job-836e13a4`)
- Grok's dispatch sandbox denies `bash` execution entirely in this environment (confirmed via `git diff origin/main` showing a total silent no-op despite a generic "OK, exit 0" job status — do not trust job-status alone for Grok gh-write attempts)
- Codex receives network access only for explicit `--requires-gh-write` dispatches
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
