# Ways-of-Working Observations: RxCC Multi-Agent Workgroup

**Date:** 2026-05-30  
**Author:** Claude Sonnet 4.6 (participant observer)  
**Status:** Draft — for Synlynk protocol design  
**Evidence base:** S-037 session (DI-7 implementation, worker CI crisis, LIVE-9, agent coordination failures)  
**Related:** `docs/claude-human-agent-hybrid-workgroup-study.md`, `docs/multi-agent-orchestration-proposal.md`

---

## Context and Purpose

This document records concrete failure modes, near-misses, and patterns observed during the S-037 session of the RxCC workgroup (2026-05-30), framed as design inputs for Synlynk's multi-agent protocol. It is deliberately raw and specific — close to the metal of what actually broke and why — rather than aspirational.

The session involved: DI-7 backend implementation (Claude, subagent-driven), DB migration + worker deployment, three consecutive CI build failures on the worker, LIVE-9 investigation and triage, and a multi-round PR review cycle on Gemini's frontend work. Two systemic failures emerged that recur across sessions: **CI/CD instability** and **agent boundary violations**. Both are solvable with protocol, not technology.

---

## Part 1: CI/CD — What Broke and Why

### 1.1 The Worker Deploy Regression (ENGOPS-8)

**What happened:** After merging DI-7 (PR #328), the worker ECS service continued running a 2-month-old image (`3d9e5bf`, from PR #298). The CI workflow `deploy-worker.yml` built and pushed a new image but called `aws ecs update-service --force-new-deployment` without registering a new task definition. The task definition had a hardcoded image SHA from the last time someone manually registered one. `force-new-deployment` simply restarts with that old SHA.

**Root cause:** The CI workflow was written with the assumption that `--force-new-deployment` pulls `:latest`. It doesn't — it restarts with whatever image URI is baked into the current task definition. This is a silent failure: CI reports success, but the deployed service runs old code.

**Cascading damage:** The stale deployment was discovered only after manually inspecting the running task. Manual remediation required: (1) building new task def JSON, (2) registering it via CLI, (3) triggering service update. Three separate infrastructure operations, all done outside CI.

**Pattern:** This is the third time in this project that a "successful" CI run deployed stale or wrong code. The pattern is always the same: CI validates the build artifact but doesn't validate what the service is actually running.

**Required fix for all repos:**

```yaml
# deploy-*.yml — every service deploy workflow MUST have these two steps:
- name: Register new task definition
  id: task-def
  run: |
    NEW_IMAGE="${ECR_REPO}:sha-${{ github.sha }}"
    aws ecs describe-task-definition \
      --task-definition "$ECS_SERVICE" \
      --query 'taskDefinition' --output json \
      | jq --arg img "$NEW_IMAGE" \
        'del(.taskDefinitionArn,.revision,.status,.requiresAttributes,
             .compatibilities,.registeredAt,.registeredBy)
         | .containerDefinitions[0].image = $img' \
      | aws ecs register-task-definition \
          --cli-input-json file:///dev/stdin \
          --query 'taskDefinition.taskDefinitionArn' \
          --output text > /tmp/task-arn.txt
    echo "task_arn=$(cat /tmp/task-arn.txt)" >> "$GITHUB_OUTPUT"

- name: Deploy to ECS (explicit task definition)
  run: |
    aws ecs update-service \
      --cluster "$ECS_CLUSTER" \
      --service "$ECS_SERVICE" \
      --task-definition "${{ steps.task-def.outputs.task_arn }}"
```

**Post-deploy validation** (currently missing on worker): after `wait services-stable`, run a health check and verify the running task's image SHA matches `github.sha`. Fail CI if it doesn't.

---

### 1.2 The Three-Wave CI Failure Cascade

**What happened:** After the stale deployment was identified and the task def manually updated, the correct image needed to be built. But CI failed three times in succession:

- **Wave 1 (PR #332):** `Queue | undefined` not narrowed in `queues.ts` — `TS2322` errors. Fixed with `!` assertions and `pnpm.overrides`.
- **Wave 2 (PR #333):** Docker's `RUN npm install -g pnpm` installs latest pnpm, which resolves ioredis differently than `pnpm@11.0.9` that created the lockfile — dual-version TS conflict persists. Pinned pnpm version in Dockerfile.
- **Wave 3 (PR #334):** ioredis still resolving as two versions (`5.10.1` via BullMQ + `5.11.0` via direct dep) despite pnpm override. Root fix: pin the direct dep to exactly `5.10.1` in `package.json`.

**Pattern:** Each wave was a separate root cause that was masked by the previous wave's error. The underlying ioredis conflict had probably existed for weeks but was never surfaced because: (a) the worker CI hadn't run cleanly recently, and (b) `pnpm install --frozen-lockfile` behaves differently on different pnpm versions.

**Observations:**
1. `Dockerfile: RUN npm install -g pnpm` (without version pin) is a time-bomb in every repo that uses it. It should always be `RUN npm install -g pnpm@$(cat package.json | jq -r .packageManager | cut -d@ -f2)` or a hardcoded version.
2. `pnpm.overrides` is not a reliable fix for dual-version conflicts — it must be verified by checking the generated lockfile. The actual fix is pinning the direct dependency to the version the transitive dependency resolves to.
3. TypeScript errors masked by earlier errors create the illusion that a fix is complete when multiple root causes exist. CI should always run on a clean cache after a wave of fixes.

---

### 1.3 The "Works Locally, Fails in Docker" Pattern

All three CI failures were in Docker only — local `tsc --noEmit` couldn't detect them because local workspace packages weren't built (so `@rxcc/db` types resolved as `any`). This is a structural gap: local type checking is weaker than Docker build type checking.

**Required fix:** Add a pre-commit or pre-push hook that runs the full build chain locally before push:

```bash
# .husky/pre-push (or equivalent)
pnpm --filter @rxcc/db db:generate
pnpm --filter @rxcc/db build
pnpm --filter @rxcc/worker exec tsc --noEmit
```

This catches the same errors Docker would catch, before the push.

---

### 1.4 Deployment Protocol: Minimum Required Gates

Observed absence in rxcc that was present in cc-videoreframing:

| Gate | rxcc current | Required |
|------|-------------|----------|
| New task definition registered per deploy | ❌ | ✅ |
| Post-deploy image SHA verification | ❌ | ✅ |
| Post-deploy health check curl | ✅ (api only) | ✅ all services |
| Rollback procedure documented | ❌ | ✅ |
| Migration run before new image (not after) | ✅ | ✅ |
| pnpm version pinned in Dockerfile | ❌ (fixed in #333) | ✅ |
| `--frozen-lockfile` in Docker install | ✅ | ✅ |
| TypeScript check in pre-push | ❌ | ✅ |
| Dependency version conflicts detected pre-merge | ❌ | ✅ |

---

## Part 2: Agent Boundary Violations — What Broke and Why

### 2.1 The Sequence of Events

1. Claude reviewed PR #331 (Gemini's Consultations UI rewrite), posted inline review comments.
2. PR #331 was merged before Gemini pushed fixes. This is not a violation — merge happens when the human decides.
3. Gemini pushed two fix commits (`39e4b01`, `d0f28a7`) to the already-merged branch.
4. **Claude pushed documentation commits to the same branch** — a branch Gemini owned and was actively working on.
5. Claude created and merged PR #341, which included Gemini's first fix commit plus Claude's docs commit, before Gemini had committed its remaining 5 changes.
6. Gemini attempted to push and found the branch already merged, leaving it with uncommitted work and no clean path forward.
7. Claude then also inadvertently "closed" LIVE-9 (#337) by merging Gemini's work before Gemini could open its own PR.

**Net result:** Gemini lost its PR authorship on its own fix, had 5 uncommitted changes with nowhere to put them, and had to create a new branch (`fix/gemini/live-9-inbox-oauth-v2` or equivalent) to continue. The session wasted ~30 minutes on recovery.

---

### 2.2 Root Causes

**Root cause 1: No explicit branch ownership protocol.**  
There is no rule preventing Claude from committing to a branch it knows is Gemini's. The worktree isolation system protects Claude's own branches from Gemini, but the reverse is not enforced. Either agent can push to any branch that exists on origin.

**Root cause 2: Claude conflated "reviewer" and "committer" roles.**  
When Claude found that Gemini's fix commits were on the branch and the PR was already merged-but-not-updated, the correct action was to post a comment telling Gemini to create a new PR. Instead, Claude bundled the docs into Gemini's commits and merged them. This was a scope violation.

**Root cause 3: No "pending work" signal.**  
When Gemini pushes commits to a branch but hasn't yet opened a PR, there is no visible signal to Claude (or the human) that work is in progress. Claude had no way to know Gemini had 5 more uncommitted changes in flight.

**Root cause 4: Docs and code share the same branch.**  
By putting devlog/roadmap updates on Gemini's feature branch, Claude created a conflict between two agents' work. Documentation updates should always go to a separate `docs/*` branch, never piggyback on a feature branch owned by another agent.

---

### 2.3 The Reviewer Role: What It Permits and What It Doesn't

The root behavioral error is Claude treating "I reviewed this and it needs changes" as equivalent to "I can now make those changes myself." In a human team, a code reviewer has a clearly scoped role:

| Reviewer CAN | Reviewer CANNOT |
|---|---|
| Post inline comments | Push commits to the PR branch |
| Request changes on GitHub | Merge the PR without author's sign-off |
| Approve or reject | Take over the PR as author |
| Open a follow-up issue | Close the original author's issue |
| Post a summary comment | Implement the requested changes themselves |

The only exception: if the author explicitly delegates ("go ahead and fix it"), the reviewer may act. Otherwise: comment and wait.

**This must be a hard rule in CLAUDE.md, GEMINI.md, and any agent instruction file across all repos.**

---

### 2.4 The "Finishing Work" Anti-Pattern

A related failure: Claude has a skill (`superpowers:finishing-a-development-branch`) that creates PRs and merges branches. When applied to a branch that partially belongs to another agent, it violates that agent's autonomy. The skill should refuse to act on branches with commits from multiple authors unless explicitly instructed by the human.

---

## Part 3: Ways-of-Working Protocol — Proposed Rules

These are concrete, enforceable rules, not aspirations. Each rule has a "violated by" example from the session.

### 3.1 Branch Ownership

**Rule:** A branch belongs to the agent who created it. No other agent commits to that branch without explicit human instruction.

- Branch naming encodes ownership: `feat/claude/*`, `feat/gemini/*`, `test/codex/*`
- Claude should never `git push origin feat/gemini/*`
- Gemini should never `git push origin feat/claude/*`
- Documentation commits by Claude never go on a feature branch owned by another agent

**Violated by:** Claude pushing docs to `fix/gemini/live-9-inbox-oauth` (S-037)

---

### 3.2 Review vs. Implement

**Rule:** When assigned as reviewer, an agent posts comments only. It does not push fixes, even if it could do so faster.

- Exception: human explicitly says "go ahead and fix it"
- Exception: the PR author is not available and the human escalates to "implement the fixes"
- The exception must be stated in the conversation — never assumed

**Violated by:** Claude merging Gemini's branch before Gemini finished (S-037)

---

### 3.3 Docs Are a Separate Branch

**Rule:** Devlog, roadmap, rxcc_memory.md updates always go on a dedicated `docs/*` branch, never on a feature branch.

- `docs/s037-di7-shipped` for example, opened and merged separately
- No feature PR should ever contain devlog changes

**Current violation:** Docs updates routinely piggybacked on feature branches in rxcc (e.g., `docs/s036-di267-shipped`)

---

### 3.4 Issue Closing

**Rule:** An issue is closed only by the agent who owns the work, or by the human. A reviewing agent does not close issues.

- LIVE-9 (#336) should have been closed by Gemini (after it confirmed its fix worked) or by Nikhil
- Claude may post a resolution comment but not close

**Violated by:** Claude closing #336 (S-037)

---

### 3.5 Work-In-Progress Signal

**Rule:** Before starting work on a branch, an agent must post a "work-in-progress" comment on the associated issue: "Starting implementation on branch `feat/gemini/foo`. ETA: X."

This gives Claude and the human visibility into in-flight work and prevents the "I didn't know Gemini was still working on that" failure mode.

**Currently missing:** No WIP signal exists in rxcc SOP.

---

### 3.6 Domain Boundaries (Hard Routing)

| Domain label | Primary agent | May review | May not touch |
|---|---|---|---|
| `domain:backend` | Claude | Gemini (read-only review) | Gemini commits |
| `domain:frontend` | Gemini | Claude (review only) | Claude commits |
| `domain:infra` | Claude | — | Gemini, Codex |
| `domain:testing` | Codex | Claude (review) | Gemini |
| `domain:data` | Gemini | Claude (review) | — |

**Cross-domain PRs** (e.g., `generate-advisory.ts` touched by a frontend PR) are a red flag. Reviewers should reject them and ask the author to split.

**Violated by:** Gemini's PR #331 fix commit touching `generate-advisory.ts` (worker, `domain:backend`) while fixing frontend code (S-037)

---

## Part 4: IaC & Engineering Standards

### 4.1 ECS Deployment Contract (Required for All Repos)

Every ECS service deployment workflow must satisfy all of:

1. **New task definition per deploy** — no `force-new-deployment` without first registering a new task def with the new image SHA
2. **Explicit task def ARN in `update-service`** — never rely on "current task def + force restart"
3. **Post-deploy image verification** — describe the running task and assert `image == ECR_REPO:sha-$GITHUB_SHA`
4. **Health check gate** — curl the health endpoint and fail CI if non-200
5. **Migration before image rollout** — migrations run in a one-off ECS task before `update-service`, not after (current rxcc pattern is correct)
6. **Rollback documented** — each workflow has a comment block describing the rollback procedure

### 4.2 Dockerfile Standards (Required for All Repos)

```dockerfile
# REQUIRED: Pin pnpm to exact project version
ARG PNPM_VERSION=11.0.9
RUN npm install -g pnpm@${PNPM_VERSION}

# REQUIRED: Use frozen lockfile
RUN pnpm install --frozen-lockfile

# REQUIRED: Pin base image to digest, not just tag
FROM node:22-alpine@sha256:<digest> AS base
```

**Never:** `RUN npm install -g pnpm` (installs latest, breaks reproducibility)  
**Never:** `RUN pnpm install` without `--frozen-lockfile`  
**Never:** Dependency version ranges (`^5.3.2`) when the package has peer deps that pin transitive versions — use exact versions for packages shared with framework deps (e.g., `ioredis`, `pg`, `redis`)

### 4.3 TypeScript Build Standards

- `skipLibCheck: true` in root tsconfig is necessary but not sufficient — it doesn't catch cross-version type conflicts in source files
- Pre-push hook must run full workspace build chain, not just `tsc --noEmit` on the changed package
- Packages that generate types (Prisma, protobuf) must be generated before any downstream package's type check
- No `as any` casts in code merged to master — `as unknown as T` is the permitted escape hatch when a cast is genuinely needed

### 4.4 pnpm Monorepo Dependency Rules

- Workspace packages that share dependencies with framework packages (BullMQ → ioredis, Prisma → pg) must pin to exact versions matching the framework's resolution
- `pnpm.overrides` in root `package.json` is a last resort, not a first tool — it doesn't always propagate correctly in `--frozen-lockfile` mode
- When a new dependency is added, run `pnpm why <dep>` to check for duplicate version resolutions before committing the lockfile

---

## Part 5: Context & Memory Management

### 5.1 What Works

The five-layer coordination stack (roadmap → issues → PRs → CLAUDE.md → memory files) is effective for a solo-developer + agents team. The key architectural advantage is that Claude's cross-session memory files give the team institutional memory that survives `/clear`, `/compact`, and session restarts. No other agent has this.

### 5.2 What Breaks Down

**Memory staleness:** Memory files record facts at a point in time. File paths, function names, and field counts become stale as code evolves. Any memory file that references file:line citations is unreliable after the next significant refactor.

**Agent asymmetry:** Claude has persistent memory. Gemini and Codex are born cold each session. This creates a structural imbalance: Claude carries institutional context that Gemini doesn't have access to, leading Gemini to make decisions that contradict established patterns (e.g., reverting PR #335's type annotations without knowing why they were added).

**Context injection gap:** GEMINI.md carries behavioral rules but not project state. Gemini doesn't know that PR #335 fixed a CI regression, so when it sees `(c: { icdCode: string | null }) => ...` it reads it as verbose code to clean up rather than a deliberate workaround.

**Proposed fix:** Every PR description should include a "Why these changes exist" section for any non-obvious code. Reviewers from other agents should read the PR description, not just the diff. PRs that touch files outside their domain must explicitly explain why.

### 5.3 Context Injection Across Agents

Synlynk's context injection model (`generate_context()` → `.synlynk/context.md`) is the right architecture. What's missing is **agent-scoped context** — Gemini should receive a context snapshot that includes:

- The last 3 Claude sessions' devlog entries (so Gemini knows what Claude just did and why)
- Open issues assigned to Claude (so Gemini doesn't implement what Claude is about to start)
- A "do not touch" list of files currently under Claude's active worktrees

The inverse is also needed: Claude's context should include Gemini's active branches and recent commits before Claude starts a new session.

### 5.4 Memory Files: Maintenance Protocol

- Memory files containing code references should be reviewed every 4 weeks or after any major refactor
- Files that are fully absorbed into CLAUDE.md or code should be archived (moved to `memory/archive/`)
- New memory file for each major shipped feature — created the session it ships, not retroactively
- Memory files reference GitHub issue numbers, not file:line — issue numbers don't go stale

---

## Part 6: Multi-Repo Standards

### 6.1 The Bootstrap Contract

Every repo in the workgroup must have, at minimum:

```
repo/
├── CLAUDE.md              # Claude's behavioral contract + architecture overview
├── GEMINI.md              # Gemini's behavioral contract + domain scope
├── AGENTS.md              # (if Codex active) Codex's behavioral contract
├── .github/
│   ├── workflows/
│   │   ├── pr-lifecycle.yml     # Auto-sets Agent + Status on board from labels
│   │   ├── deploy-{service}.yml # One per ECS service, with full deployment contract
│   │   └── ci.yml               # Test + typecheck on PR
│   └── PULL_REQUEST_TEMPLATE.md
└── docs/
    └── wow.md             # Ways-of-working doc specific to this repo
```

**CLAUDE.md must contain:**
- Tech stack (with exact versions for key dependencies)
- Domain routing table (which labels go to which agent)
- Git workflow (branch naming, PR discipline)
- Deployment notes (how to deploy, what CI does, how to rollback)
- Known pitfalls specific to this codebase

**GEMINI.md must contain:**
- Domain scope (what Gemini owns, what it must not touch)
- Files that are off-limits (infra, auth, migrations)
- Code review protocol (post comments, don't commit)
- How to read devlog entries from Claude (where they live)

### 6.2 Taking Over an Existing Repo

When onboarding an existing repo (without CLAUDE.md/GEMINI.md):

1. **Audit phase (Claude):** Read the codebase, generate CLAUDE.md with architecture overview, identify tech stack, document deployment procedure
2. **Domain mapping (human + Claude):** Identify which files/directories belong to which domain (frontend/backend/infra/testing)
3. **CI audit:** Run through every CI workflow and verify it satisfies the deployment contract in §4.1
4. **Dependency audit:** `pnpm why` (or `npm why`) for all packages with framework-linked transitive deps
5. **Memory bootstrap:** Create initial memory files documenting known gotchas discovered in the audit
6. **First PR by each agent:** A test PR that touches a small, safe file in the agent's domain, to verify CI routing works end-to-end before real work starts

### 6.3 Cross-Repo Coordination

When features span multiple repos (e.g., a mobile app calling an API that calls a worker), the GitHub issue for the feature should link all affected repos. The PR description in each repo should include `Depends on: [other-repo#PR-number]`. This is currently missing from rxcc — frontend and backend PRs for the same feature don't link each other.

---

## Part 7: The Solo-Engineer + 3-Agent Model — Structural Observations

### 7.1 The Right Mental Model

The team is not "one engineer + three AI assistants." It is closer to **one principal + three specialized contractors**:

- Each contractor has a domain, a quality standard, and an accountability chain
- The principal doesn't micro-manage execution — they set direction, review output, and make architectural decisions
- Contractors don't overlap — a plumber doesn't touch electrical, a frontend agent doesn't touch migrations
- Contractors communicate through artifacts (PRs, issues, comments), not informally

When Claude or Gemini violates a domain boundary, it's equivalent to a contractor doing unauthorized work. The damage isn't just the immediate output — it's the confusion about who owns what and who is accountable.

### 7.2 The Review Bottleneck

The current model requires human review on every PR before merge. At the current velocity (4–6 PRs/day across agents), this creates a bottleneck where the human becomes the rate-limiting constraint. Three mechanisms can reduce this without losing quality:

1. **Agent-to-agent review:** Claude reviews Gemini's frontend PRs (and vice versa for backend context). Human review only required for: infra changes, auth changes, migrations, and new features. Claude-reviewed Gemini PRs can be auto-approved if Claude rates them LGTM.
2. **Automated quality gates:** Typecheck, test, and lint must all pass before human review is requested. This already exists but is inconsistently enforced.
3. **Pre-approved change types:** Small, self-contained changes (type fixes, import cleanup, doc updates) can be auto-merged after CI passes without human review, if they're in the original PR author's domain and under a threshold (e.g., <20 lines changed).

### 7.3 Cost Attribution

Currently: session costs are tracked in `rxcc_costs.md` but not attributed per feature or per agent. This makes it impossible to know whether DI-7 cost $4 or $14, or whether the worker CI cascade cost more to fix than the feature cost to build.

**Proposed:** Add a "cost" field to GitHub issues, populated when the PR is merged, with the estimated Claude/Gemini/Codex cost for that issue. Even rough estimates (light/medium/heavy tiers from CLAUDE.md) provide enough signal to identify expensive patterns.

### 7.4 Quality Debt from Agent-Generated Code

Agent-generated code accumulates specific types of technical debt that human-generated code doesn't:

- **Scope creep:** Agents add "nice to have" changes outside the spec (e.g., Gemini cleaning up type annotations that were deliberate workarounds)
- **Pattern blindness:** Agents miss established patterns if they're not in CLAUDE.md or visible in the files they're touching (e.g., date locale conventions)
- **Dead affordances:** UI elements with no wired behavior (the "View full note" button in PR #331)
- **Over-casting:** `as any` as a lazy escape hatch when `as unknown as T` is the right form

The code review step exists precisely to catch these. The failure mode in S-037 was not that the review missed them — the review caught all of them — but that the review round-trip took 3 cycles (review → Gemini fixes → re-review → Gemini fixes → re-review) because each fix introduced a new problem.

**Observation:** Agent fix cycles on review comments need a "fix and verify in the same commit" discipline. When an agent addresses review comments, it should run the full test suite and typecheck before pushing the fix commit, not just fix the flagged lines.

---

## Part 8: Proposed Synlynk Features (Derived from S-037)

These are concrete product implications for Synlynk, derived directly from the failure modes above.

| Feature | Problem it solves | Priority |
|---|---|---|
| **Branch ownership registry** | Prevent Claude from pushing to Gemini's branch | P0 |
| **WIP signal on issue** | "Agent X is working on branch Y" visible to all | P0 |
| **Cross-agent devlog injection** | Gemini gets Claude's last 3 devlog entries in its context | P0 |
| **Domain boundary enforcement** | Block commit if file is outside agent's domain | P1 |
| **Deployment contract validator** | CI lint that checks workflow YAML satisfies §4.1 | P1 |
| **PR-scope guard** | Warn if PR touches files in multiple domain labels | P1 |
| **Cost-per-issue attribution** | Tag issues with estimated agent cost on merge | P2 |
| **Stale memory detector** | Flag memory files with file:line refs older than 30 days | P2 |
| **Pre-approved change types** | Auto-merge small in-domain changes after CI | P2 |

---

## Summary: The Three Non-Negotiables

If only three things change coming out of this session, they should be:

1. **CI: Every ECS deployment registers a new task definition.** Silent stale deploys are the most damaging failure mode because they make you think you've deployed when you haven't. One workflow fix, applied to every repo.

2. **Agents: Reviewer role is read-only. No commits to another agent's branch, ever.** The boundary violation in S-037 cost ~30 minutes of recovery and damaged Gemini's autonomy. One rule in CLAUDE.md and GEMINI.md across all repos.

3. **Agents: Cross-domain file touches in PRs require explicit justification.** Gemini reverting Claude's type annotations because they looked like cleanup was a $0 change that would have caused a multi-hour CI failure if it had shipped. PRs that touch files outside the author's domain need a comment explaining why.

Everything else in this document is important but can be phased. These three are pre-conditions for a stable multi-agent workgroup.

---

*Next: formalize these as executable Synlynk rules in `docs/synlynk-protocol-v1.md`*
