# GitHub-Managed Repos with Agentic Workers
### A Programme Management Playbook for Small Teams Using AI Agents as First-Class Contributors

**Version:** 1.0  
**Date:** 2026-05-21  
**Author:** Nikhil Soman / RxCC.me  
**Licence:** CC BY 4.0 — share freely with attribution

---

## Abstract

This document describes a complete programme management model for small software teams (2–10 humans) that use GitHub as their single source of truth and AI agents (Claude, Gemini, Codex, or any CLI-based agent) as first-class contributors alongside humans.

The model solves three problems that existing PM guidance ignores:

1. **Attribution without new accounts** — AI agents commit under a human's GitHub handle. You need agent identity to be visible in git history, PRs, and project boards without creating fake GitHub accounts or losing traceability.

2. **Task routing without a coordinator** — Multiple agents have different capability profiles. Issues need to flow to the right agent automatically, with humans retaining control over what gets deployed.

3. **PM tooling that agents can use natively** — Jira, Linear, and Asana are designed for humans. AI agents interact with GitHub natively via `gh` CLI and REST API. Adding a separate PM tool creates a coordination gap that breaks agentic workflows.

The result is a model where a human writes a spec, an issue is created, a label routes it to the right agent, the agent opens a PR, CI validates it, and a human approves the deploy — all within a single GitHub workflow that both humans and agents can drive.

---

## Who This Is For

- **Team size:** 1–10 human contributors, any number of AI agents
- **Repository:** Private or public GitHub repo, any language
- **Agent tooling:** Any CLI-based agent with filesystem + shell access (Claude Code, Gemini CLI, OpenAI Codex CLI, Cursor, Aider, etc.)
- **Stage:** Pre-launch through early growth — before a dedicated PM or Scrum Master joins
- **Plan:** GitHub Free works for ~80% of this model; upgrade trigger is clearly defined

This model is **not** appropriate for:
- Teams of 15+ where sprint velocity and burndown charts are actively managed by a PM
- Enterprises requiring audit trails, SSO, or Jira integration for compliance
- Fully autonomous agent pipelines with no human in the loop on deploys

---

## Part 1 — Decision Framework

Before adopting this model, work through five decisions. Each has a clear recommendation with the tradeoffs stated.

---

### Decision 1: GitHub-only vs GitHub + external PM tool

**Three options:**

**A. GitHub exclusively (recommended)**  
Issues + Projects v2 + Actions + branch protection. One tool for code, tracking, CI, and deploy gates. AI agents interact via `gh` CLI and REST API — no integration glue needed.  
*Cost:* Free → $4/user/month (Team)  
*Tradeoff:* Sprint velocity reporting is thin compared to Jira. Fine before you have a dedicated PM.

**B. GitHub + Jira**  
Jira owns epics/sprints/burndown; GitHub owns code. Branch naming links PRs into the Jira Development Panel.  
*Cost:* Jira Standard ~$8/user/month on top of GitHub  
*Tradeoff:* Two systems to maintain. Agents can read Jira issues via API but it requires custom integration; branch-naming is the only reliable sync. Breaks down when agents need to update ticket state autonomously.

**C. GitHub + Linear**  
Linear is more developer-friendly than Jira with a fast native GitHub sync.  
*Cost:* Linear ~$8/user/month  
*Tradeoff:* Still two systems. Linear free tier caps at 250 issues. Agent interaction is second-class — there is no Linear CLI.

**Choose A if:** Agents are contributors, not just helpers. The key test: can your agent open an issue, check out a branch, implement, push, and close the issue without leaving GitHub? If yes, stay in GitHub.

---

### Decision 2: GitHub Free vs Team

GitHub Free covers the majority of this model. Here is what each plan provides:

| Feature | Free | Team ($4/user/mo) |
|---|---|---|
| Issues, PRs, Projects v2 | ✅ | ✅ |
| Branch protection + required PR reviews | ✅ | ✅ |
| GitHub Actions (private repos) | 2,000 min/month | 3,000 min/month |
| CODEOWNERS enforcement | Advisory | Enforced |
| Environment protection rules (deploy gates) | ❌ | ✅ |
| Scheduled Slack/Teams reminders | ❌ | ✅ |
| Audit log (full actor history) | ❌ | ✅ |

**Start on Free. Upgrade when your CI/CD pipeline ships.**

The feature that makes Team worth it is **Environment protection rules** — the ability to require a specific human to approve a GitHub Actions job before it deploys to production. Without it, the deploy gate is a `github.actor` check in the YAML, which works but can be bypassed by editing the file. Once a CI/CD pipeline exists, upgrade on the same day it merges.

**Upgrade triggers (in order of likelihood):**
1. CI/CD pipeline ships → need deploy gate enforcement → **upgrade now**
2. Actions minutes approach 1,500/month → buffer running thin → upgrade
3. Team grows to 5+ and PR review reminders via Slack become needed → upgrade
4. First external (non-core-team) contributor → audit log needed → upgrade

---

### Decision 3: Agent capability model

Not all agents are equal. Assign work based on observed capability, not vendor marketing. The table below reflects the consensus from teams using these agents in production on real codebases as of 2026. Reassess every 3–6 months — the field is moving fast.

| Capability | Claude (Code/Opus) | Gemini (CLI/2.5 Pro) | Codex (CLI) |
|---|---|---|---|
| Architecture & system design | ●●●●● | ●●●○○ | ●●○○○ |
| Backend / API / TypeScript / Go | ●●●●● | ●●●○○ | ●●●●○ |
| Frontend / React components | ●●●●○ | ●●●●● | ●●●○○ |
| Visual design reasoning | ●●○○○ | ●●●●○ | ●●○○○ |
| Unit + pure-function test generation | ●●●○○ | ●●●○○ | ●●●●● |
| Integration + async test design | ●●●●○ | ●●○○○ | ●●●○○ |
| Multi-file refactoring | ●●●●● | ●●●○○ | ●●●○○ |
| Infrastructure / deploy operations | ●●●●● | ●●○○○ | ●●○○○ |
| Spec / plan writing | ●●●●● | ●●●○○ | ●●○○○ |
| Agentic reliability (long multi-step tasks) | ●●●●○ | ●●●○○ | ●●●○○ |

**Three practical rules from this table:**

1. **Don't let Codex design tests** — it generates tests well when given existing code and a clear spec, but it doesn't design test strategies. Complex async/integration tests need Claude.
2. **Don't use Claude for visual iteration** — Claude can write component code but cannot evaluate "does this look right" without screenshot feedback. Gemini with multimodal vision can. For UI polish and animation, Gemini is faster.
3. **Keep infra and deploys on Claude or humans** — Infrastructure changes require system-level judgment (when to abort, when to roll back, what a cascading failure means). Codex and Gemini do not have the reasoning depth for this yet.

---

### Decision 4: Task boundary ownership

Map your codebase domains to primary agents. This is your **routing table** — every issue gets one domain label, and that label routes to a primary agent via automation.

The boundaries below are a recommended starting point. Adjust based on your stack.

| Domain | Primary Agent | Fallback | Notes |
|---|---|---|---|
| Architecture, specs, plans | Claude | — | `domain:design` issues |
| Backend API, data layer | Claude | — | `domain:backend` |
| Infrastructure, deploy, migrations | Claude | Human only | `domain:infra` — deploy always human-approved |
| PR review + merge gate | Claude | Human | Claude reviews code; human approves infra PRs |
| Frontend web components | Gemini | Claude | `domain:frontend` |
| Visual polish, animations | Gemini | — | |
| Unit / pure-function tests | Codex | — | `domain:testing` (mechanical generation) |
| Integration / API tests | Claude | Codex | Complex async / DB-touching tests |
| Mobile (React Native, Flutter) | Claude | Gemini | Reassess once mobile work starts |

**How to adapt:** If you don't use Gemini, route frontend to Claude. If you don't use Codex, route testing to Claude. The model works with a single agent — routing is just a nudge, not a hard constraint.

---

### Decision 5: Human control surface

Define the three decisions that only humans make, regardless of how autonomous agents become:

1. **Merge to production branch** — A human clicks merge (or approves the environment gate) for anything going to `main`/`master`. Agents open PRs; humans close them.
2. **Deploy to production** — Either a manual trigger or a required reviewer approval in GitHub Actions. Not automated on push until the team is confident in the CI/CD suite.
3. **Spec approval** — Agents can brainstorm and draft specs, but a human approves the design before implementation begins. This is the highest-leverage decision point.

Everything else — writing code, writing tests, opening PRs, updating issue status, running migrations in staging — can be delegated to agents.

---

## Part 2 — The Model

### 2.1 Label Taxonomy

Three orthogonal axes. Every issue gets exactly one label from each axis (type, domain, priority). Agent and status labels are applied automatically.

#### Type — what kind of work
```
type:feature    — New functionality
type:fix        — Bug or regression
type:chore      — Deps, config, docs, infra
type:spec       — Design doc or implementation plan
type:test       — Test suite additions
type:security   — Security or compliance work
```

#### Domain — what codebase area it touches
```
domain:backend   — API, workers, database, migrations
domain:frontend  — Web UI, components, client-side
domain:infra     — Cloud infrastructure, CI/CD, deploy
domain:mobile    — Native apps (iOS, Android)
domain:testing   — Test suites, test infrastructure
domain:design    — Specs, UX, visual design
```

#### Priority — when it needs to ship
```
priority:p0  — Blocks launch / critical path
priority:p1  — Important, target this cycle
priority:p2  — Valuable, backlog
priority:p3  — Nice-to-have, no ETA
```

#### Agent attribution — applied automatically by CI
```
agent:claude    — PR authored by Claude
agent:gemini    — PR authored by Gemini
agent:codex     — PR authored by Codex
agent:human     — Authored by a human
```

#### Status — lifecycle signals
```
status:blocked      — Cannot proceed, waiting on dependency
status:in-review    — PR open, awaiting review
status:needs-spec   — Needs design doc before implementation
status:stale        — No activity in 14 days (auto-applied)
```

---

### 2.2 Milestones

Map milestones to your project's natural launch gates — not time-boxed sprints. Time-boxed sprints are appropriate once you have a PM and a stable velocity; before that, gate-based milestones align with how early-stage software actually ships.

**Recommended starting milestones for an early-stage product:**
```
Private Beta   — Minimum set of features to invite real users
Public Launch  — All compliance, security, and UX gates cleared
Backlog        — Unprioritised / P2–P3 items with no ETA
```

Add more milestones as the product evolves (e.g., `v2.0`, `Enterprise Track`, `Mobile`). Keep milestones at the launch-gate level, not the sprint level — GitHub Issues are not a sprint board.

---

### 2.3 Issue Templates

Four templates cover the lifecycle of a software project. All use GitHub's form YAML format, which emits structured data (dropdowns, checkboxes) that GitHub Actions can parse automatically to apply labels.

**`feature.yml`** — For new functionality requests. Requires: priority, domain, description, acceptance criteria.  
**`bug.yml`** — For broken behaviour. Requires: priority, domain, reproduction steps, expected behaviour.  
**`chore.yml`** — For maintenance work. Requires: priority, domain, description.  
**`spec.yml`** — For design or planning work. Sets `type:spec` + `status:needs-spec` automatically.

All templates include a `Priority` dropdown (`P0/P1/P2/P3`) and a `Domain` dropdown. A GitHub Actions workflow reads these fields from the issue body and applies the corresponding `priority:*` and `domain:*` labels automatically — no manual labelling needed.

Disable blank issues (`config.yml: blank_issues_enabled: false`) to enforce template usage.

---

### 2.4 PR Template

Every PR body should answer four questions: **what** changed, **which issue** it closes, **how** to verify it, and **who** (human or agent) authored it.

```markdown
## Summary

## Roadmap item
Closes #

## Domain
<!-- backend / frontend / infra / testing / design -->

## Test plan
- [ ]
- [ ]

## Agent / author
<!-- Claude Sonnet 4.6 / Gemini 2.5 Pro / Codex / Human -->

## Migration / deploy notes
<!-- Write "None" if not applicable -->
```

The `Closes #NNN` line auto-closes the issue and moves the project board card to Done on merge. This is the mechanism that keeps the board current without manual updates.

---

### 2.5 Agent Identity and Attribution

**The problem:** All AI agents in a team typically run under the same GitHub user account. A commit from Claude and a commit from Gemini look identical in `git log`.

**Three-layer solution:**

**Layer 1 — `git user.name` per session**  
Each agent session configures its own display name:
```bash
# In Claude session
git config user.name "Your Name (Claude)"

# In Gemini session  
git config user.name "Your Name (Gemini)"

# In Codex session
git config user.name "Your Name (Codex)"
```
This appears in `git log`, `git blame`, and on GitHub commit pages. It is the canonical signal visible in git history forever.

**Layer 2 — Co-authored-by trailer**  
Append to every agent commit message:
```
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
Co-Authored-By: Gemini 2.5 Pro <noreply@google.com>
Co-Authored-By: Codex <noreply@openai.com>
```
GitHub renders these as co-author avatars in the commit view and PR contributors panel. Visible without reading the commit body.

**Layer 3 — Branch naming prefix**  
```
feat/claude/short-description
feat/gemini/short-description
test/codex/short-description
fix/claude/short-description
```
The agent segment (`/claude/`, `/gemini/`, `/codex/`) is machine-readable. A GitHub Actions workflow reads `github.head_ref` on PR open and applies the corresponding `agent:*` label automatically.

Together these three layers give you: git history attribution (Layer 1), GitHub UI attribution (Layer 2), and automated board categorisation (Layer 3) — with zero manual overhead.

---

### 2.6 GitHub Actions Automation

Four lightweight workflows handle all automation. All run on the GitHub-hosted `ubuntu-latest` runner. All fit within the 2,000 minute/month free tier for a team of up to 10 contributors doing 20–30 PRs/month.

---

#### Workflow 1: Agent attribution on PR open

**File:** `.github/workflows/agent-label.yml`  
**Trigger:** `pull_request` opened / synchronised  
**Action:** Read branch name → match agent segment → apply `agent:*` label → post attribution comment

```yaml
name: Agent attribution label
on:
  pull_request:
    types: [opened, synchronize, reopened]
permissions:
  pull-requests: write
  issues: write
jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/github-script@v7
        with:
          script: |
            const branch = context.payload.pull_request.head.ref;
            const pr = context.payload.pull_request.number;
            const agentMap = {
              claude: { label: 'agent:claude', name: 'Claude' },
              gemini: { label: 'agent:gemini', name: 'Gemini' },
              codex:  { label: 'agent:codex',  name: 'Codex' },
            };
            let matched = null;
            for (const [key, val] of Object.entries(agentMap)) {
              if (branch.includes(`/${key}/`)) { matched = val; break; }
            }
            const label = matched ? matched.label : 'agent:human';
            await github.rest.issues.addLabels({
              ...context.repo, issue_number: pr, labels: [label],
            });
            if (matched) {
              await github.rest.issues.createComment({
                ...context.repo, issue_number: pr,
                body: `🤖 **Agent:** ${matched.name} · branch \`${branch}\``,
              });
            }
```

---

#### Workflow 2: Priority and domain labels from issue form

**File:** `.github/workflows/issue-label.yml`  
**Trigger:** `issues` opened  
**Action:** Parse `### Priority` and `### Domain` sections from issue body → apply `priority:*` and `domain:*` labels

```yaml
name: Issue auto-label from form
on:
  issues:
    types: [opened]
permissions:
  issues: write
jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/github-script@v7
        with:
          script: |
            const body = context.payload.issue.body ?? '';
            const issueNumber = context.payload.issue.number;
            function extract(body, heading) {
              const re = new RegExp(`###\\s+${heading}\\s*\\n+([^\\n#]+)`);
              const m = body.match(re);
              return m ? m[1].trim() : null;
            }
            const priority = extract(body, 'Priority');
            const domain   = extract(body, 'Domain');
            const labels   = [];
            if (priority && ['P0','P1','P2','P3'].includes(priority))
              labels.push(`priority:${priority.toLowerCase()}`);
            if (domain && ['backend','frontend','infra','mobile','testing','design'].includes(domain))
              labels.push(`domain:${domain}`);
            if (labels.length > 0)
              await github.rest.issues.addLabels({
                ...context.repo, issue_number: issueNumber, labels,
              });
```

---

#### Workflow 3: Agent routing suggestion on domain label

**File:** `.github/workflows/domain-route.yml`  
**Trigger:** `issues` labelled (when `domain:*` label applied)  
**Action:** Post a comment with the recommended agent, branch convention, and co-authored-by trailer

```yaml
name: Agent routing suggestion
on:
  issues:
    types: [labeled]
permissions:
  issues: write
jobs:
  route:
    runs-on: ubuntu-latest
    if: startsWith(github.event.label.name, 'domain:')
    steps:
      - uses: actions/github-script@v7
        with:
          script: |
            const domain = context.payload.label.name.replace('domain:', '');
            const issueNumber = context.payload.issue.number;
            const ROUTING = {
              backend:  { agent: 'Claude',  coAuthor: 'Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>', prefix: 'feat/claude' },
              frontend: { agent: 'Gemini',  coAuthor: 'Co-Authored-By: Gemini 2.5 Pro <noreply@google.com>',      prefix: 'feat/gemini' },
              infra:    { agent: 'Claude',  coAuthor: 'Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>', prefix: 'feat/claude',
                          note: '⚠️ Infra PRs require human approval before merge.' },
              mobile:   { agent: 'Claude',  coAuthor: 'Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>', prefix: 'feat/claude' },
              testing:  { agent: 'Codex',   coAuthor: 'Co-Authored-By: Codex <noreply@openai.com>',               prefix: 'test/codex' },
              design:   { agent: 'Claude',  coAuthor: 'Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>', prefix: 'feat/claude' },
            };
            const r = ROUTING[domain];
            if (!r) return;
            const slug = context.payload.issue.title
              .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40);
            const body = [
              `🤖 **Suggested agent:** ${r.agent} (\`domain:${domain}\`)`,
              `**Branch:** \`${r.prefix}/${slug}\``,
              `**Commit trailer:** \`${r.coAuthor}\``,
              r.note ?? '',
            ].filter(Boolean).join('\n');
            await github.rest.issues.createComment({
              ...context.repo, issue_number: issueNumber, body,
            });
```

**To adapt:** Edit the `ROUTING` object to change which agent handles which domain. If you only use Claude, route all domains to Claude. If you add a new agent (e.g., Cursor), add it here.

---

#### Workflow 4: Stale issue cleanup

**File:** `.github/workflows/stale.yml`  
**Trigger:** Daily cron (09:00 UTC)  
**Action:** Label issues inactive for 14 days as `status:stale`; close after 30 days. Exempt P0, blocked, and in-review issues.

```yaml
name: Stale issue cleanup
on:
  schedule:
    - cron: '0 9 * * *'
  workflow_dispatch:
permissions:
  issues: write
jobs:
  stale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/stale@v9
        with:
          repo-token: ${{ secrets.GITHUB_TOKEN }}
          days-before-stale: 14
          days-before-close: 30
          stale-issue-label: status:stale
          stale-issue-message: >
            No activity for 14 days — marked stale. Will close in 16 days
            unless there is new activity. Remove `status:stale` to reset.
          close-issue-message: Closing after 30 days of inactivity. Reopen if still relevant.
          exempt-issue-labels: 'priority:p0,status:blocked,status:in-review'
          days-before-pr-stale: -1
          days-before-pr-close: -1
```

---

### 2.7 Branch Protection

Configure on `main`/`master` immediately. On GitHub Free, required reviews are available and should be enabled from day one.

```bash
gh api repos/{ORG}/{REPO}/branches/main/protection \
  -X PUT \
  --input - <<'EOF'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
```

After upgrading to Team, add your production Environment in Actions settings and add required reviewers (the humans authorised to approve deploys). This replaces the `github.actor` check in the YAML.

---

### 2.8 CODEOWNERS

CODEOWNERS documents which humans (or teams) should review changes to specific paths. On Team plan, GitHub enforces this at the PR level. On Free plan, it is advisory — but worth having so the expectation is clear and documented.

```
# Infra and deploy — human review required
infra/                       @your-handle @other-human
.github/workflows/           @your-handle @other-human

# Backend — Claude-primary, human review
apps/api/                    @your-handle
apps/worker/                 @your-handle

# Frontend — Gemini-primary, human review
apps/web/src/components/     @your-handle
apps/web/src/app/            @your-handle

# Test suites — Codex-primary, human review
tests/                       @your-handle
```

Replace `@your-handle` with the GitHub username(s) who should approve each area. In a 2-person team, both humans likely approve everything — CODEOWNERS still documents the expectation for when agents submit PRs.

---

### 2.9 Projects v2 Board

One board per product, at the organisation level. Link it to all relevant repos.

**Required custom fields:**
- `Sprint` (Iteration, 2-week cycles)
- `Effort` (Number — story points, optional but useful once team has velocity data)
- `Agent` (Single select: Claude / Gemini / Codex / Human / Unassigned)

**Views to create:**

| View | Type | Grouped by | Purpose |
|---|---|---|---|
| **Kanban** | Board | Status | Day-to-day work tracking |
| **Roadmap** | Roadmap | Milestone | Launch gate visibility |
| **By Agent** | Board | Agent field | See what each agent is working on |
| **Sprint** | Board | Status | Current iteration scope |
| **Backlog** | Table | Priority label | Prioritisation and grooming |

The Projects v2 board is the only item in this model that cannot be configured via API without additional OAuth scopes. Create it manually via the GitHub UI.

---

## Part 3 — The Agentic Workflow in Practice

This section describes how a feature moves from idea to deployed code in this model. The workflow is the same whether the agent is Claude, Gemini, or Codex — the routing is what differs.

### Step 1: Issue creation

A human (or an agent acting on behalf of a human) creates an issue using a template. The template form captures priority and domain. On submit:

- GitHub Actions applies `priority:pN` and `domain:X` labels automatically
- The `domain:X` label triggers the routing workflow, which posts the suggested agent + branch name as a comment
- The human assigns the issue if desired (optional — agents can self-assign by reading the routing comment)

**Example:**  
Issue: `[FEAT] Add consultation specialties endpoint`  
Template: Feature | Priority: P0 | Domain: backend  
Auto-labels applied: `type:feature`, `priority:p0`, `domain:backend`  
Routing comment: `🤖 Suggested agent: Claude · branch feat/claude/consultation-specialties-endpoint`

---

### Step 2: Agent picks up the issue

The agent (running in a terminal session or an automated trigger) does the following:

```bash
# Set identity for this session
git config user.name "Your Name (Claude)"

# Create branch matching the routing suggestion
git checkout -b feat/claude/consultation-specialties-endpoint

# Do the work: implement, test, commit
git commit -m "feat(api): add consultation specialties endpoint

Closes #42

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

# Open PR
gh pr create \
  --title "feat(api): add consultation specialties endpoint" \
  --body "..."
```

The PR body uses the PR template. The `Closes #42` line links the PR to the issue.

---

### Step 3: CI validates

On PR open:
1. The agent-label workflow applies `agent:claude` and posts the attribution comment
2. If a CI build workflow exists (`ci.yml`), it runs tsc / tests / lint
3. The PR is ready for human review

---

### Step 4: Human reviews and merges

The human (or Claude acting as reviewer) reads the diff and approves. For `domain:infra` PRs, a human must approve — Claude can review but not merge infra changes alone.

On merge:
1. GitHub closes the linked issue (`Closes #42`)
2. The Projects board card moves to Done
3. If a deploy workflow exists, it triggers (with the deploy gate check)

---

### Step 5: Deploy gate

**Pre-Team plan (github.actor check):**
```yaml
- name: Deploy
  if: github.ref == 'refs/heads/main' && (github.actor == 'human1' || github.actor == 'human2')
  run: ./scripts/deploy.sh
```

**Post-Team plan (Environment protection):**  
The Actions job is gated by the `production` environment, which requires approval from a designated human before the deploy step runs. No YAML change needed — GitHub blocks the job at the environment approval step.

---

## Part 4 — Implementation Recipe

Steps to set up this model in any GitHub repository from scratch. Estimated time: **3–4 hours** for an experienced engineer.

### Phase A: Repository configuration (1 hour)

1. Add dev dependencies: `@octokit/rest` and `tsx` (or equivalent for your language)
2. Write and run a label setup script that creates the full taxonomy and deletes GitHub's default labels
3. Create milestones matching your project's launch gates
4. Create `.github/ISSUE_TEMPLATE/` with the four template files
5. Create `.github/pull_request_template.md`
6. Create `.github/CODEOWNERS` with your directory structure
7. Configure branch protection via `gh api`

### Phase B: GitHub Actions workflows (1 hour)

8. Create `.github/workflows/agent-label.yml` (Workflow 1)
9. Create `.github/workflows/issue-label.yml` (Workflow 2)
10. Create `.github/workflows/domain-route.yml` (Workflow 3)
11. Create `.github/workflows/stale.yml` (Workflow 4)

Smoke test each workflow: create a test issue, verify labels and comment appear. Create a test PR from a `test/claude/smoke-test` branch, verify `agent:claude` label.

### Phase C: Issue migration (1–2 hours)

12. Write a migration script that reads your existing backlog (spreadsheet, Notion, Trello, local markdown) and creates GitHub Issues via the API with correct labels and milestones
13. Dry-run the script and review output before executing
14. Execute live; verify a sample in the GitHub UI
15. Archive the old backlog with a note pointing to GitHub Issues

### Phase D: Projects board (30 minutes)

16. Create the Projects v2 board via GitHub UI
17. Add the repository to the board
18. Add custom fields (Sprint, Effort, Agent)
19. Create the five views (Kanban, Roadmap, By Agent, Sprint, Backlog)
20. Import open issues into the board

### Phase E: Team onboarding

21. Document the branch naming convention in your CONTRIBUTING.md or README
22. Document the `git config user.name` convention for each agent in your agent session notes or CLAUDE.md / AGENTS.md equivalent
23. Share the routing table with all contributors — agents and humans

---

## Part 5 — Adaptation Guide

### Single-agent teams

If you use only one agent, remove the routing complexity. Set all `domain:*` routes to that agent. Remove the `agent:gemini` and `agent:codex` labels. Keep the attribution workflow — it still catches human vs agent attribution.

### No agents yet (future-proofing)

Add the label taxonomy and workflow infrastructure now, before agents join. The overhead is near-zero, and retrofitting attribution into a live codebase is painful. Use `agent:human` as the default until agents contribute.

### Monorepos with multiple apps

Add sub-domain labels: `domain:web`, `domain:api`, `domain:worker`, `domain:mobile`. Update the routing table in `domain-route.yml`. Update CODEOWNERS with the specific app paths.

### Different agent stacks

The `ROUTING` object in `domain-route.yml` is your adapter. Add, remove, or change entries to match your team:
```javascript
const ROUTING = {
  backend: { agent: 'Cursor', prefix: 'feat/cursor', coAuthor: '...' },
  // etc.
};
```

### Adding CI/CD (ENGOPS-1 equivalent)

When you add a CI pipeline, extend it to:
1. Run on PR open: type-check + test
2. Run on merge to main: build + push artifact + deploy to staging
3. Add a manual deploy-to-production step gated by the `production` environment (Team plan)

The deploy step should check `github.actor` (Free) or use environment protection (Team) to restrict who can approve production deploys.

---

## Part 6 — Common Pitfalls

**"The routing comment fires but the agent ignores it"**  
Agents must be instructed to read issue comments before starting work. Add a step to your agent session instructions: "Read all comments on the issue before creating a branch."

**"Two agents opened PRs for the same issue"**  
Add a self-assignment step: when an agent picks up an issue, it assigns itself via `gh issue edit NNN --add-assignee @me`. Other agents check the assignee before starting.

**"Agent commits are not getting the co-authored-by trailer"**  
For Claude Code: add `Co-Authored-By: ...` to the CLAUDE.md instructions. For other agents: add it to the session prompt or a project-level config file (`AGENTS.md`, `GEMINI.md`).

**"Stale workflow is closing things it shouldn't"**  
Add your critical labels to `exempt-issue-labels`. Common additions: `priority:p1`, `type:security`, any milestone-specific labels.

**"The branch protection rule blocks hotfixes"**  
Add a bypass rule for specific users in the branch protection settings (Team plan). On Free, nikhilsoman's own pushes can bypass if `enforce_admins: false`.

**"Projects board is out of sync with issues"**  
Use the `Closes #NNN` syntax in every PR body. If an issue was closed manually, move the board card manually. The auto-close hook only fires on PR merge with the `Closes` keyword.

---

## Appendix — Label Colour Reference

Colours chosen for accessibility and visual distinction across both light and dark GitHub themes.

| Group | Colour hex | Appearance |
|---|---|---|
| Priority P0 | `b60205` | Red — urgent |
| Priority P1 | `e4a700` | Amber — important |
| Priority P2 | `cfd3d7` | Grey — normal |
| Priority P3 | `ffffff` | White — low |
| Domain: backend | `1d76db` | Blue |
| Domain: frontend | `0052cc` | Dark blue |
| Domain: infra | `5319e7` | Purple |
| Domain: mobile | `006b75` | Teal |
| Domain: testing | `0e8a16` | Green |
| Domain: design | `e99695` | Rose |
| Agent: Claude | `d2a8ff` | Lavender |
| Agent: Gemini | `a8f0d2` | Mint |
| Agent: Codex | `ffa8a8` | Salmon |
| Agent: Human | `ffd700` | Gold |
| Type: feature | `0075ca` | Blue |
| Type: fix | `d73a4a` | Red |
| Type: chore | `e4e669` | Yellow |
| Type: spec | `8250df` | Purple |
| Type: test | `0e8a16` | Green |
| Type: security | `b60205` | Red |
| Status: blocked | `b60205` | Red |
| Status: in-review | `e4a700` | Amber |
| Status: needs-spec | `8250df` | Purple |
| Status: stale | `cfd3d7` | Grey |

---

*This document describes the programme management model developed for RxCC.me (2026). It is intended as a reusable recipe for any small team running GitHub-managed repos with AI agent contributors. Contributions and adaptations welcome.*
