<!-- synlynk:start version="0.9.4" tool="grok" -->
# synlynk Grok Instructions

## Identity & Attribution
- **Engine:** grok-composer-2.5-fast
- **Commit trailer:** `Co-Authored-By: Grok <noreply@x.ai>`
- **Branch prefix:** `feat/grok/` or `fix/grok/`

## Domain Ownership
| Domain | Owned by this agent | Notes |
|:---|:---|:---|
| TODO: fill domains for this agent | | |

## Git Worktree-First Policy
Never commit directly to `main`/`master`. Create a dedicated worktree for every feature or fix:
```
git worktree add ../feat+<name> feat/<agent-prefix>/<name>
git branch --show-current   # confirm before every commit
```
Delete the worktree only after its branch is merged.

## Branch Naming
- `feat/grok/<description>` — new functionality
- `fix/grok/<description>` — bug fixes
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
- Update task status in project-docs/todo.md — do NOT delete tasks:
  `[ ]` active · `[x]` done · `[-]` deferred · `[~]` superseded · `[>]` absorbed
- Append decisions to project-docs/memory.md with [@username] attribution
- Run `synlynk checkpoint` at every task boundary
- In team mode: always `git pull` before editing any project-docs file
- Log costs in project-docs/costs.md after each significant AI operation

## At session end
- Append a summary entry to project-docs/devlogs/<username>.md
- Run `synlynk checkpoint` one final time
- Run `synlynk status` and include the output in your closing message

<!-- synlynk:end -->
