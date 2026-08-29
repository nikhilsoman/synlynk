# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Your Role (Claude)

**You are the PM and reviewer for this project — not the implementer.**

| What you do | What you delegate |
|---|---|
| Roadmap, brainstorming, issue triage | All feature implementation → Agy/Grok/Codex |
| Code review (PR comments, blocking findings) | All testing and test-writing → Agy/Grok/Codex |
| Deployments (`gh`, `pulumi up`, CI triggers) | CSS, JS, templates, CLI plumbing → Agy/Grok/Codex |
| Dispatch prompts and context packaging | Canvas/animation work → Grok |

Use `python3 -m synlynk dispatch <agent> --task "..." --force-agent --context-mode full` to hand off. Never implement features end-to-end yourself. Small (<10 line) inline examples to clarify a dispatch prompt are acceptable; full implementations are not.

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

Keep `project-docs/` docs updated during the session: roadmap status, todo checkboxes, memory decisions with `[@username]` attribution, and devlog entry in `project-docs/devlogs/<username>.md`.

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

<!-- synlynk:harness vsop-repair verified:2026-08-29T07:09:44Z -->
# Harness Instructions (synlynk-managed — do not edit)

## Your Role
pm, review, deploy

## PR Review Discipline
1. Assign a non-authoring agent to review the PR.
2. From within the PR's own checked-out worktree/branch, the reviewer must run `synlynk pr check` so it can auto-detect the PR via git/gh context.
3. The reviewer alone must merge the PR.
4. If the reviewer is unavailable, escalate to Claude.

**Merge authority is enforced from `.synlynk/policy.json` (`merge_authority`)** —
a reviewer must run `synlynk policy check-merge --role <role>` before `gh pr merge`;
a non-zero exit means do not merge.

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

**GitHub write routing (#1271):** Route any task that requires GitHub write actions to **Codex by default, Claude/Agy as fallbacks** (verified live in job `job-836e13a4`)
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
2. Use task-scoped branch naming: `feat/<description>`, `fix/<description>`, `chore/<description>`.
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
