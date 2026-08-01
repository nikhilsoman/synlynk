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

<!-- synlynk:harness vsop-repair verified:2026-07-30T07:33:24Z -->
# Harness Instructions (synlynk-managed — do not edit)

## Your Role
pm, review, deploy
## PR Review Discipline
1. Assign a non-authoring agent to review the PR.
2. The reviewer must run `synlynk pr check <pr#>`.
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
| Role | Agent | Tasks |
| :--- | :--- | :--- |
| pm / review / deploy / brainstorm | Claude | pm, review, deploy, brainstorm |
| implement / test / css / templates / content / subpages | Agy | implement, test, css, templates, content, subpages |
| implement / test / canvas / js / infra | Grok | implement, test, canvas, js, infra |
| implement / test / refactor / cli-plumbing | Codex | implement, test, refactor, cli-plumbing |
Do not start a task outside your role column without explicit approval from Claude.

**GitHub write routing (#426):** Route any task that requires GitHub write actions to **Grok by default**. Agy headless can complete `gh pr review`, `gh pr comment`, and `gh pr merge` writes when the machine-local `~/.gemini/antigravity-cli/settings.json` already contains scoped `command(gh pr review)`, `command(gh pr comment)`, and `command(gh pr merge)` allow-rules; that precondition is operator-confirmed, not reliably verifiable mid-task. Codex's `workspace-write` sandbox blocks network egress to `api.github.com` by design. Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically, but do not treat it as a hard identity guarantee yet: the token-stripping fallback does not prevent `gh` from using a locally logged-in personal keyring identity when no role-scoped GitHub App token is available (#569).

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

<!-- /synlynk:harness -->
