# Synlynk Release Implementation Protocol & Governance Standard

**Document ID:** `docs/process/release-implementation-protocol.md`  
**Governing Standard:** Synlynk Multi-Harness Release Governance  
**Status:** Canonical Active Standard  
**Last Updated:** 2026-10-28  

---

## 1. Executive Summary & Purpose

This document establishes the canonical, repeatable execution protocol for all Synlynk releases. It defines the exact invariants, verification gates, attribution rules, and ceremony steps required for a Mode A Home Conductor or human operator to shepherd a release from milestone kickoff to final release tag and parent issue rollup.

The protocol is organized into **6 sequential phases**:
1. **Session Start & Pre-Flight Context Recovery**
2. **Design-First & Four-Point Attribution (Design → Plan → Build)**
3. **Worktree Isolation, TDD & Taxonomy Governance**
4. **PR Review Discipline & Merge Authority Verification**
5. **Release Cut, Version Authority & Documentation Sync**
6. **Post-Release Rollups, Telemetry & Workspace Housekeeping**

---

## Phase 1: Session Start & Pre-Flight Context Recovery

### 1.1 Inter-Task Status Rollup (PM Role / Interactive Session Boundary)
At session kickoff or major task transitions, the PM / Home Conductor produces an inter-task status banner anchoring the transition:
- **Last Completed Task:** Linked commit, PR, or tag with verified outcome.
- **Next Task:** Target story from `state.db` / `todo.md` with explicit story ID and milestone context.

### 1.2 Canonical State DB Integrity Verification
Verify canonical `state.db` access via `synlynk/state_registry.py`. Run recovery registration if running from a newly provisioned or isolated workspace:
```bash
SYNLYNK_ALLOW_REGISTRY_RECOVERY=1 synlynk state register --slug synlynk --path ~/.synlynk/workspaces/synlynk/state.db
```
*Fail-open invariant:* Database unavailability must log an advisory warning and never hard-crash CLI operations.

### 1.3 Lease & Active Checkout Audit
Run `synlynk doctor` and inspect `task_leases_integrity`. Immediately auto-reclaim any dead-PID or expired leases:
```bash
synlynk doctor --fix leases
```

### 1.4 Milestone Scope & Checkpoint Reconciliation
- Inspect `project-docs/roadmap.md` for the current daily release gate, parent epic, and governing goal.
- Run `synlynk checkpoint` to archive completed tasks and refresh context without polluting working tree diffs.

---

## Phase 2: Design-First & Four-Point Attribution (Design → Plan → Build)

### 2.1 Brainstorm-First Policy
No production code may be written before an approved design specification exists in `docs/superpowers/specs/`. Complex architectural decisions must explore user intent, system invariants, failure modes, and alternatives prior to planning.

### 2.2 Strict Four-Point Attribution Frontmatter
Every design spec (`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`) and implementation plan (`docs/superpowers/plans/YYYY-MM-DD-<topic>.md`) **must** begin with standard YAML frontmatter validated by `tests/test_four_point_attribution.py`:
```yaml
---
goal: goal-XXXXXXXX          # Governing goal ID from state.db
epic: "#XXXX"               # Parent release tracking issue (must be quoted)
milestone: v0.XX.X          # Exact target release version
arc: <arc-slug>             # Core functional arc (e.g. runtime, vizor, governance)
---
```
*Note:* Do not use loose Markdown bolding (e.g. `**Goal:** ...`) in place of YAML frontmatter delimiters (`---`).

### 2.3 Design → Plan → Build Strict Sequence
1. **Step A (Design Spec):** Document problem statement, root cause, architectural components, failure handling, and non-goals. Spec must be committed to the branch and approved by Nikhil.
2. **Step B (Implementation Plan):** Break the spec into bite-sized, verifiable tasks with explicit test criteria. Plan must be committed to the branch before dispatches begin.
3. **Step C (Build):** Implement code task-by-task following TDD.

### 2.4 Stale Backlog Audit & Explicit Non-Goals
Cross-check `state.db` and recent PRs to identify stories that are already satisfied (to prevent redundant re-implementation of previously shipped PRs). Explicitly list **Non-Goals** to keep release scope bounded to the daily gate.

---

## Phase 3: Worktree Isolation, TDD & Taxonomy Governance

### 3.1 Worktree Isolation Discipline
- Never commit directly to `main` or `master`.
- Feature and fix work must execute in a dedicated, isolated git worktree:
  ```bash
  git worktree add .worktrees/<branch-name> -b <branch-name>
  ```
- **Branch Naming Standard:**
  - `feat/<harness>/<description>` — new capability
  - `fix/<harness>/<description>` — bug fix / gate resolution
  - `chore/<harness>/<description>` — docs, dependencies, housekeeping
- **Mandatory Co-Author Attribution Trailer:**
  - All commits must include the executing harness's trailer:
    - Grok: `Co-Authored-By: Grok <noreply@x.ai>`
    - Agy: `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`
    - Claude: `Co-Authored-By: Claude Sonnet <noreply@anthropic.com>`
    - Codex: `Co-Authored-By: Codex <noreply@openai.com>`

### 3.2 Work-Start Claims & Lease Acquisition
- Interactive sessions claiming a story via `synlynk story update <id> --status in_progress` or workers executing `synlynk dispatch --story <id>` must acquire a rolling task lease in `task_leases`.
- If an active lease is held by another live process, work must fail with exit code 1 identifying the holder, unless `--override`/`--force` is explicitly supplied.
- Fail-open policy: DB locks or connection issues must emit advisory logs and never block CLI execution.

### 3.3 Test-Driven Development (TDD) Contract
- Write failing reproduction or contract verification tests in `tests/test_*.py` **before** writing production code.
- Run local sandboxed tests (`BypassSandbox: false`). Only elevate permissions for git lock operations, worktree creation, or network operations (`BypassSandbox: true`).
- Mock expensive external subprocesses (e.g. AST extraction, heavy model calls) in unit tests to prevent test execution inflation and CI timeouts.

### 3.4 Command Taxonomy & Documentation Synchronization Gate
- **Zero-Drift Taxonomy Rule:** Every command or subcommand registered in `synlynk/cli.py` **must** have a corresponding entry in `synlynk/taxonomy.py` (`COMMAND_TAXONOMY`).
- **Automated Docs Regeneration:** Whenever `synlynk/taxonomy.py` is touched, immediately run:
  ```bash
  python3 scripts/generate_command_docs.py
  ```
  This regenerates `docs/reference/commands.md` and updates the command index in `README.md`.
- Verified locally before opening PR via `pytest tests/test_taxonomy.py`.

---

## Phase 4: PR Review Discipline & Merge Authority Verification

### 4.1 Strict Non-Author Review Separation
The authoring harness must **never** approve or merge its own PR. Assign a non-authoring agent/role to conduct the review:
- Day-to-day verification & test review: Route to `qa` role (`claude` or `codex`).
- Feature, governance, or architecture-impacting review: Route to `architect` role.
- Dispatch review command example:
  ```bash
  synlynk dispatch claude --role qa --model-tier fast --story <story-id> --task "Review PR #XXXX"
  ```

### 4.2 Worktree-Context PR Validation (`synlynk pr check`)
The reviewer must execute verification from within the PR's checked-out worktree:
```bash
synlynk pr check
```
Checks performed automatically:
- All CI checks green across the matrix (Python 3.10 & 3.12).
- No active, unresolved sentinel alerts.
- GOVERNS linkage verified (no unlinked stories or goals).
- Model versions attested and devlog identity verified.

### 4.3 Approval Submission Protocol
- **Default:** Real approval via `gh pr review <pr> --approve` whenever reviewer GitHub login differs from PR author.
- **Same-Identity Collision Fallback:** If the reviewing session shares the author's GitHub identity (where GitHub API blocks self-approval), post a formal `COMMENT` review containing an explicit verified checklist:
  ```bash
  gh pr review <pr> --comment --body "### QA Review & Verification Checklist ... **Decision:** APPROVE"
  ```

### 4.4 Programmatic Merge Authority Gate
Before merging, the reviewer **must** verify authority via:
```bash
synlynk policy check-merge --role <role>
```
A non-zero exit code means merge is forbidden by `.synlynk/policy.json`. Do not bypass.

### 4.5 CI Freshness & Merge Execution
- Confirm all matrix checks pass via `gh pr checks <pr>`.
- If PR is `BEHIND`, allow up to 2 `gh pr update-branch` → CI-wait cycles. If still behind, escalate.
- Squash merge the PR:
  ```bash
  gh pr merge <pr> --squash --delete-branch
  ```
  *(Add `--admin` only when required to satisfy branch protection bypass for authorized unattended release operations).*

---

## Phase 5: Release Cut, Version Authority & Documentation Sync

### 5.1 Separation of Release Ceremony from Feature PRs
Feature and bugfix PRs must **not** bump `VERSION` or flip roadmap flags prematurely. The release ceremony executes on a dedicated release branch (`chore/release/vX.Y.Z`) or directly at the release milestone closeout once all candidate PRs are merged.

### 5.2 Version Authority & Synchronized Artifacts
- **`VERSION`:** Bump to exact semantic version (e.g. `0.26.5`).
- **`CHANGELOG.md`:** Add release block under Keep a Changelog standards:
  ```markdown
  ## [vX.Y.Z] - YYYY-MM-DD
  ### Added / Changed / Fixed / Verified
  - Explicit itemized list of capabilities, fixes, and revalidated issue numbers with PR links.
  ```
- **`README.md`:**
  - Update version badge to match `VERSION`.
  - Update test count badge to match exact output of `pytest --collect-only -q`.
  - Update hero/release summary paragraph.
- **`project-docs/roadmap.md`:**
  - Flip release header from `## vX.Y.Z — <Title> [planned]` to `[shipped]`.
  - Append shipped narrative citing merge PR, commit SHA, and closed/revalidated issues.

### 5.3 Automated Release Documentation Verification Gate
Before tagging, execute the release verification gate:
```bash
python3 bin/synlynk.py release --check-docs --role pm
```
All 6 verification checks must be green:
- `[x] version metadata`
- `[x] collected test count`
- `[x] hero/release summary`
- `[x] install instructions`
- `[x] command/documentation links`
- `[x] shipped vs planned commands`

### 5.4 Git Tagging & GitHub Release Publishing
- Ensure local `main` is cleanly fast-forwarded to `origin/main`:
  ```bash
  git checkout main && git pull --rebase
  ```
- Create annotated tag and push to remote:
  ```bash
  git tag -a vX.Y.Z -m "Release vX.Y.Z: <Release Title>"
  git push origin vX.Y.Z
  ```
- Publish GitHub Release:
  ```bash
  gh release create vX.Y.Z --title "vX.Y.Z — <Title>" --notes-file <notes.md>
  ```
- Trigger website docs-bundle synchronization if documentation assets/PDFs are tracked.

---

## Phase 6: Post-Release Rollups, Telemetry & Workspace Housekeeping

### 6.1 Ephemeral Worktree Pruning & Salvage Hygiene
- Remove task-scoped worktrees and local branches merged into `main`:
  ```bash
  git worktree remove .worktrees/<branch-name>
  git branch -d <branch-name>
  git worktree prune
  ```
- **Salvage-Before-Deletion Mandate:** If uncommitted investigations or test diffs exist in stale review worktrees, salvage them to `docs/archive/stale-worktree-salvage/` before pruning.

### 6.2 Post-Release Integrity & Health Verification Sweep
Immediately following worktree cleanup and before concluding the release, run the integrity sweep on `main`:
1. **Doctor Health Check:**
   ```bash
   synlynk doctor
   ```
   Confirm `task_leases_integrity`, `daemon_service`, and database schemas are healthy with zero blocking warnings.
2. **Lease Cleanliness:** Run `synlynk doctor --fix leases` to verify that no active or orphaned task leases were stranded by the release jobs.
3. **State & Doc Lock Check:** Run `synlynk checkpoint` on `main` to ensure `project-docs/todo.md` has archived all completed release stories and `memory.md` is locked.
4. **Working Tree Cleanliness:** Confirm `git status` shows clean working tree on `main` matching `origin/main`.

### 6.3 Conversational Status Rollup on Parent & Milestone Issues
Post the authoritative milestone synthesis comment directly to:
1. The **Milestone Release Issue** (e.g. `#2470`).
2. The **Parent Tracking Epic** (e.g. `#2458`).
Itemize intent, delivered architecture, test evidence, closing PRs, and carryovers.

### 6.4 Cost Logging & Token Provenance
Record PM and Conductor interactive session consumption into canonical telemetry:
```bash
synlynk cost log --harness <harness> --role pm --tokens-in <tokens-in> --tokens-out <tokens-out> --story-id <milestone-story-id> --note "vX.Y.Z release orchestration"
```
Confirm `synlynk status` burn rate reflects actual spend.

### 6.5 Inter-Task Handoff Generation
When handing off to the next Home Conductor, prepare the structured handoff prompt adhering to the inter-task boundary protocol established in Phase 1.
