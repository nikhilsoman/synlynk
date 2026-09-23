<!-- synlynk:start version="0.21.0-dev" tool="universal" -->
# synlynk Universal AI Instructions

Apply the following as your system prompt or custom instructions before starting any session in this repository.

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
