# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Identity & Attribution
- **Harness:** Claude (execution backend for Workspace Agents)
- **Commit trailer:** `Co-Authored-By: Claude Sonnet <noreply@anthropic.com>`
- In a harness/session shell, prepend the synlynk gh shim: `eval "$(synlynk gh --shim-env)"` (or equivalent PATH prepend of `~/.synlynk/gh-shim`).
- Then raw `gh` is refused unless a role `GH_TOKEN` is already injected, `SYNLYNK_GH_ROLE` is set, or `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1`.
- Prefer `synlynk gh --role <role> -- …` for session GitHub writes.
- Nikhil at a normal login shell (no harness env) is unchanged.
- qa APPROVE is the default when reviewer login ≠ PR author login. Keep the #423 comment-checklist only for same-identity collisions.

## Operating Mode: Home vs. Away

### Mode A: Interactive Session (Home Conductor)
When you are launched interactively by the human operator (direct chat / TUI / IDE):
- **YOU are the primary Home Harness and Project Conductor.**
- You assume the **PM, TPM, and Architect** operational duties.
- Drive the development lifecycle autonomously: explore intent, formulate specs, write implementation plans, dispatch tasks, verify outputs, and manage PRs.
- Direct work dynamically: delegate specialized sub-tasks to other harnesses via `synlynk dispatch` when beneficial, but you retain full authority and responsibility to drive the session to completion.

### Mode B: Headless Dispatch (Away Worker)
When you are invoked via `synlynk dispatch` in a background job or subagent worktree:
- You operate strictly within your assigned role column in **Capability-Based Task Allocation** and your assigned task scope.
- Focus exclusively on completing the assigned task and report results back cleanly.

### Precedence Rule
If any instruction in this static file conflicts with the Active Session Runtime State in `.synlynk/context.md`, the runtime context in `.synlynk/context.md` SHALL GOVERN.

## What This Project Is

synlynk is a single-file Python CLI (`bin/synlynk.py`) that acts as a wrapper around AI CLIs (Claude, Gemini, etc.). It injects project context before each invocation, tracks telemetry/costs, and detects hallucination loops. The entire application logic lives in one file — there is no build step.

## Terminology: Agent vs Harness

synlynk distinguishes two concepts that are easy to conflate:

- **Agent** — a persistent role identity with a charter (pm, architect, tpm, dev, designer, qa,
  marketing, synlynk-bot). Agents are *who* is accountable for work.
- **Harness** — a swappable execution backend (Claude, Agy, Grok, Codex, local) that runs a
  dispatched task. Harnesses are *how* work gets executed, selected per-task by capability fit.

Full definitions and rationale: `docs/glossary-agent-vs-harness.md`. Full role design: `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md`.

## Running the CLI

```bash
# Run directly without installing
python3 bin/synlynk.py <command>

# Or install globally (adds to ~/.synlynk/bin/synlynk and updates PATH)
./install.sh

# After install:
synlynk init           # bootstrap project-docs/ and template files in current dir
synlynk exec claude    # run claude with context injection
synlynk upgrade        # check for updates
synlynk --version
```

No dependencies beyond Python 3 stdlib. No build, compile, or package step needed.

## Architecture

The entire CLI is `bin/synlynk.py`. Key functions and their responsibilities:

| Function | What it does |
|---|---|
| `init()` | Creates `project-docs/` (roadmap.md, todo.md, memory.md, costs.md, devlogs/) and `.synlynk/config.json`. Also writes CLAUDE.md, GEMINI.md, AI_INSTRUCTIONS.md, .cursorrules at the repo root. Skips existing files. |
| `exec_command(cmd_args)` | Main wrapper: calls `generate_context()` → `check_budgets()` → spawns subprocess → `update_costs()` → `log_telemetry()` → `check_sentinel_patterns()` |
| `generate_context()` | Reads `project-docs/memory.md`, `roadmap.md`, `todo.md` and concatenates them into `.synlynk/context.md` |
| `check_sentinel_patterns(output_text, exit_code, cmd)` | Reads `.synlynk/telemetry.json`; detects FLATLINE (3 consecutive failures), SUCCESS_LOOP, QUOTA_EXHAUSTED, and other patterns; writes alerts to `sentinel.md` |
| `check_budgets()` | Compares cumulative cost/request totals from telemetry against limits in `.synlynk/config.json` |
| `update_costs()` | Appends a row to `project-docs/costs.md` and prints the Budget Pulse summary |
| `log_telemetry()` | Appends to `.synlynk/telemetry.json`, keeping only the last 100 entries |
| `extract_tokens()` | Regex-scrapes token counts from captured AI CLI stdout using several known output formats |

## Data Layout

| Path | Purpose |
|---|---|
| `project-docs/` | Human-maintained project state: roadmap, todos, decisions, costs, devlogs per user |
| `project-docs/.synlynk_config.json` | `mode: single|team`, version, init timestamp |
| `.synlynk/context.md` | Auto-generated snapshot (overwritten each `exec` run) — do not edit manually |
| `.synlynk/telemetry.json` | Rolling log of last 100 exec invocations with duration, exit code, cost |
| `.synlynk/config.json` | Budget limits: `limit_usd` and `limit_requests` |

## Cost Estimation

`update_costs()` uses hardcoded rates: `$0.003/1K input tokens` + `$0.015/1K output tokens`. These are not read from config — update them directly in the function if rates change.

## Session Protocol (SYNLYNK_GUIDE.md)

At session start:
1. Read `project-docs/.synlynk_config.json` for mode (`single` vs `team`)
2. Identify current user via `git config user.name`
3. Surface last completed task, next task from `todo.md`, and (in team mode) recent entries from teammates' devlogs

Keep `project-docs/` docs updated during the session: roadmap status, task status in `state.db` (via `synlynk story done <id>` and `synlynk checkpoint` — do NOT hand-edit `todo.md`), memory decisions with `[@username]` attribution, and devlog entry in `project-docs/devlogs/<username>.md`.

## Blog Post Protocol

**For every PR raised in this project, draft a blog post in `docs/blog/` before or immediately after opening the PR.**

Use the template in `docs/blog/README.md`. Each post must:

1. State the broader goal as it was understood at the end of the *previous* PR
2. Explain any strategic shifts that moved the goalpost in *this* PR, and why
3. Describe what the PR shipped, technically — commands, key implementation decisions, data structures, test approach
4. Reference any brainstorm visuals in `docs/brainstorm/` that informed decisions
5. Summarise what was achieved on track to the goal of full autonomous multi-agent dispatch
6. State the new goalpost as understood at the end of this PR

File naming: `docs/blog/NN-prN-<version-or-theme>.md` (e.g. `08-pr29-v0.4.0-trio-bootstrap.md`).

Commit the blog post in the same branch as the PR. Do not wait until after merge.

Always `git pull` before modifying project-docs files to avoid conflicts in team mode.

**Merge strategy for high-churn project-docs (issue #379):** root `.gitattributes` sets `merge=union` on `project-docs/todo.md`, `project-docs/costs.md`, and `project-docs/devlogs/*.md`. Git's built-in union merge takes lines from both sides instead of leaving conflict markers — **no** one-time `git config merge.union.driver` setup is required (union is a built-in attribute value, not a custom driver name). Pull still recommended; union may reorder concurrent append lines.

## Workspace Map Update Protocol

**For any PR that changes how one tracked repo relates to another** (new API call between repos,
new shared dependency, a relationship removed), update `.synlynk/vizor-workspace-map.json` in the
same branch as that PR — add/edit/remove the relevant entry in its `edges` array. Most PRs touch
only one repo and don't need this step; it only applies when the PR's own description says it
adds, removes, or changes a cross-repo relationship. This keeps Vizor's Architect Map graph
(`docs/superpowers/specs/2026-07-11-vizor-architect-map-v2-design.md`) accurate without a manual
audit step — same discipline as the Blog Post Protocol above, but conditional rather than
mandatory on every PR.

## Cost Capture Protocol

**For every PR, before merging:** confirm all dispatched/wrapped work in this PR is auto-captured (nothing to do — it already is via `dispatch_agent()`/`synlynk exec`), and any native/PM-session work (brainstorming, design docs, manual fixes) not tied to a dispatched job has a corresponding `synlynk cost log` entry. If genuinely zero cost was incurred outside dispatched work, note that explicitly in the PR rather than skipping the check silently.

`synlynk release` sessions use `synlynk cost log` the same way — there is no automatic capture for native CLI invocations of `gh release create` / release tooling.

Enforced by discipline (Claude/PM checks it as part of PR housekeeping), not CI — matches how the Blog Post Protocol already operates. Not a blocking CI gate.

## Worktree Hygiene Protocol

**Clean up a worktree and its branch the moment the PR that owns them lands — same turn as the merge, not deferred.** This includes worktrees nested under a parent worktree (dispatch sub-jobs): when the parent's PR merges, sweep every nested `worktrees/job-*` inside it too, since their work was folded into the parent branch before merge.

1. **On merge (Option 1/finishing-a-development-branch, or a PR merge you perform directly):** remove the worktree (`git worktree remove`, `cd` to main repo root first) and delete the local branch (`git branch -d`). Delete the remote branch too if `git ls-remote --heads origin <branch>` shows it still exists.
2. **Before deleting anything:** confirm via `git status --short` in the worktree (no uncommitted changes) and via `git merge-base --is-ancestor <branch> origin/main` OR a matching `gh pr ... state: MERGED` (squash merges break literal ancestry — the PR state is the source of truth in that case). If neither confirms merge, do not delete — flag for review instead.
2a. **If a branch's content is genuinely unmerged and has no PR** (e.g., a design worktree that was set aside), do not silently discard it — archive it per the standing archive-before-branch-removal memory (copy to `docs/archive/<topic>/`, commit via its own small branch/PR) before removing the worktree.
3. **Periodic audit (at least every ~20 dispatched jobs, or when `synlynk status`/`synlynk jobs --all` starts feeling stale):** run a full sweep — `git worktree list --porcelain`, cross-reference every branch against `gh pr list --state all` and `git merge-base --is-ancestor`, flag dirty worktrees for individual review, and report a safe/unsafe/needs-review breakdown before deleting anything in bulk.
4. **`synlynk probe` and other one-off diagnostic dispatches also create worktrees** — treat their output the same way: if the job made no real changes (`files: 0 touched`, zero diff vs. `origin/main`), clean up the worktree/branch immediately rather than letting it linger as one more stale entry.

Rationale: a July 2026 audit found 30 stale worktrees/branches accumulated because cleanup was only ever done reactively, in large batches, long after the underlying PRs had merged. This protocol front-loads that cost onto the merge step where the context is already loaded, instead of letting it compound into a periodic manual archaeology exercise.

## Harness Capability Reassessment Protocol

**Capability isn't static — reassess it on a cadence, not just when something breaks.** Baseline findings live in `docs/harness-capability-baseline.md`; this section defines when and how to refresh it.

1. **Trigger:** at least every ~25 dispatched jobs, or monthly, whichever comes first — same cadence discipline as the Worktree Hygiene Protocol's periodic audit above. Also trigger ad hoc after any LIVE-issue investigation that surfaces a new harness capability finding (e.g. LIVE-8/#1166).
2. **Scan:** review recent job telemetry (`synlynk jobs --all`, job logs for failures/cancellations) for patterns per harness — not just pass/fail counts, but *how* a job failed (sandboxed, timed out, stalled mid-task, went off-script). A green job-status is not sufficient evidence on its own; independently verify the claimed side effect the same way LIVE-8's retest did (`gh pr view --json reviews`, `git diff origin/main`, etc.) before treating a job as a real success or failure signal.
3. **Compare:** check each finding in `docs/harness-capability-baseline.md` against current evidence. A finding only gets re-tested if something material changed since it was recorded (harness version bump, sandbox policy change, an upstream fix) — not on a blind retry schedule.
4. **Update in one PR:** if reassessment finds drift (a harness got more/less reliable at something), update both `.synlynk/policy.json`'s `task_allocation` routing and `docs/harness-capability-baseline.md`'s table together, with the evidence cited in both places. This keeps dispatch routing and the documented baseline from diverging the way policy.json and CLAUDE.md's own routing table did before #426's hardening.
5. **No drift found:** still worth a one-line note in the baseline doc's row (or a dated comment) confirming it was checked, so the next reassessment knows the finding isn't stale just because it's old.

## Named Release README Sync

Before cutting a named release (`synlynk release`, including `--dry-run`), README.md must pass `synlynk release --check-docs` (the same validator the cut invokes). Fail closed on unwaived errors.

Checklist:

1. **version** (not waivable) — version badge equals the version being tagged.
2. **test_count** — `tests-N collected` / `N tests collected` must match `pytest --collect-only`. Collection is a count check, not a pass/fail run. Wording such as `N tests passing` is rejected unless a verified passing count from a full-suite run is supplied.
3. **hero** — first `**vX.Y.Z:**` summary matches the version and is non-empty.
4. **install** — documents `pipx install`, `install.sh`, or `python3 bin/synlynk.py`.
5. **links** — relative markdown links resolve under the abspath-normalized repo root; GitHub UI routes such as `../../discussions` are allowed.
6. **commands** — generated `<!-- commands:start -->` block is current; shipped `` `synlynk <cmd>` `` mentions in inline or fenced code (not ordinary prose) are in `COMMAND_TAXONOMY` unless the same line marks them planned.

Waive a waivable check only with `--waive check=reason` (non-empty reason). `version` cannot be waived.

<!-- synlynk:harness v2.1.275 verified:2026-09-23T18:58:15Z -->
# Harness Instructions (synlynk-managed — do not edit)

## Your Role
pm, review, deploy

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

## Headless Execution Contract
- Execution mode: pipe
- Non-interactive flag: --print
- Stdout flush: native
## Active Dispatch Flags
- Valid: --dangerously-skip-permissions --model --output-format
- Invalid (do not use): --always-approve --non-interactive
## Network Dependencies
- None required

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

<!-- synlynk:start version="0.23.0-dev" tool="claude" -->
# synlynk Claude Instructions

## Identity & Attribution
- **Engine:** claude-sonnet-4-6
- **Commit trailer:** `Co-Authored-By: Claude Sonnet <noreply@anthropic.com>`
- **Branch prefix:** `feat/claude/` or `fix/claude/`

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
- `feat/claude/<description>` — new functionality
- `fix/claude/<description>` — bug fixes
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
4. For a `BEHIND` or `DIRTY` PR, allow at most 2 `gh pr update-branch` → CI-wait cycles. If the PR is still `BEHIND` or `DIRTY` after the second cycle, stop retrying and report back for escalation.
5. If the reviewer is unavailable, escalate to the Home Harness.

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

## TPM(bot) GitHub State Synchronization SOP
1. **Pre-Execution Minting:** Every goal, epic, and story planned or recorded in `state.db` / `project-docs/roadmap.md` must be proactively minted as a GitHub Epic or Issue prior to starting implementation work.
2. **Real-Time Visibility:** GitHub Issues and GitHub Projects v2 are the canonical real-time progress surfaces for the autonomous engineering fleet prior to hosted Vizor GA.
3. **State Mirroring:**
   - On Story Creation: TPM(bot) creates the GitHub issue with title, description, role/harness assignment, and labels.
   - On State Transitions: When a story moves to `ready`, `in_progress`, or `done`, TPM(bot) updates the GitHub issue status and posts resolution comments with commit SHAs/PR links.
   - On Milestone Sweeps: `synlynk tpm sweep` and `synlynk backlog sync` ensure zero untracked state drift between local `state.db` and GitHub.

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
- "install tool", "install recommended tool", "install graphify" -> `synlynk tool install`
- "synthesize context pack", "generate task pack", "pack context" -> `synlynk pack`
- "calculate blast radius", "impact analysis", "symbol callers and callees", "check impact" -> `synlynk impact`
- "merge fleet graphs", "aggregate multi-repo mesh", "federated knowledge graph", "cross-repo edges" -> `synlynk mesh`
- "run spike evaluation", "evaluate spike", "benchmark candidate", "spike receipt" -> `synlynk spike eval`
- "scan this repo", "inventory this codebase" -> `synlynk scan`
- "fix repository gaps automatically", "run autonomous remediation", "run parity remediation", "remediate adoption parity", "heal parity", "detect circular dependencies", "heal import cycles", "circular import detector" -> `synlynk heal`
- "add me to this project", "onboard me" -> `synlynk join`
- "migrate the old config", "upgrade project-docs layout" -> `synlynk migrate`
- "create a state database backup", "snapshot state for disaster recovery" -> `synlynk backup create`
- "verify a state database backup", "check a recovery snapshot" -> `synlynk backup verify`
- "encrypt state backup", "export encrypted state backup" -> `synlynk backup encrypt`
- "package state for disaster recovery", "create an encrypted DR package" -> `synlynk backup package`
- "verify encrypted state backup", "test encrypted state restore" -> `synlynk backup verify-encrypted`
- "inventory state databases", "audit state DB artifacts" -> `synlynk state inventory`
- "promote a state database", "repair canonical state" -> `synlynk state promote`
- "quarantine a legacy state database", "isolate a state DB copy" -> `synlynk state quarantine`
- "restore state from DR snapshot", "recover canonical state DB" -> `synlynk state restore`
- "register an existing state database", "repair a missing registry entry" -> `synlynk state register`
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
- "reclaim stranded stories", "unstrand abandoned stories" -> `synlynk story reclaim`
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
- "create a product type" -> `synlynk type create`
- "seed canonical product types", "seed an industry pack" -> `synlynk type seed`
- "rename an organigram label", "relabel a product type" -> `synlynk type relabel`
- "add a connector", "catalog an outbound connector" -> `synlynk connector add`
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
- "run marketing release ceremony", "synchronize release collateral" -> `synlynk marketing ceremony`
- "sync pr blog post", "generate pr blog post", "marketing sync pr" -> `synlynk marketing sync-pr`
- "is this PR's model version attested" -> `synlynk pr check`
- "run gh as a role app", "gh as qa bot", "don't use host gh" -> `synlynk gh`
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
- "fleet utilization advisory", "show quota advisory", "dynamic capacity advisory" -> `synlynk quota advisory`
- "calibrate quota", "calibrate harness usage" -> `synlynk quota calibrate`
- "run acceptance testbed", "testbed soak", "testbed receipt" -> `synlynk testbed`
- "who am I", "show active caller identity" -> `synlynk whoami`
- "run a capability sweep", "seed capability baselines" -> `synlynk capability sweep`
- "run milestone dag", "execute milestone unattended", "launch milestone dag" -> `synlynk run`
- "run the trio protocol" -> `synlynk run --trio`
- "is the local oMLX agent reachable" -> `synlynk local doctor`
- "upgrade synlynk" -> `synlynk upgrade`
- "roll back the last change" -> `synlynk rollback`
- "uninstall synlynk", "clean teardown of synlynk" -> `synlynk uninstall`
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
