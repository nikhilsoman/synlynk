# Autonomous Workspace Agent Roles & GitHub-Centric Approval Network — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish an always-on, role-by-role autonomous execution network across workspace agents (PM, Architect, TPM, Dev, Designer, QA, Maintainer), driven by GitHub issue state changes (issue closed = approved) and task boundary fence notifications.

**Architecture:** A multi-agent state machine orchestrated by daemon ticks: PM sweeps active goals in `state.db` lacking specs, authors brainstorming agendas, files GitHub issues assigned to `@nikhilsoman`, and surfaces notices. Closing the issue deterministically triggers the Architect to draft design specs and file approval tickets. Closing the spec ticket triggers plan authoring and TPM task decomposition into ready stories. Ready stories execute autonomously through leased worktrees, effect verification, QA non-author review, and auto-merge.

**Tech Stack:** Python 3.12–3.14 (zero runtime dependencies, standard library only: `sqlite3`, `subprocess`, `json`, `pathlib`, `unittest/pytest`), GitHub CLI (`gh`), Git worktrees.

**Spec:** `docs/superpowers/specs/2026-11-02-autonomous-workspace-agent-roles-github-approvals-design.md`

## Global Constraints

- Zero third-party runtime dependencies (stdlib only).
- All Git writes and branch creations must operate within leased worktrees.
- PR merge authority is restricted strictly to the `qa` role (`can_merge: ["qa"]` in `.synlynk/policy.json`).
- Approval trigger is deterministically gated on GitHub issue state (`state == "CLOSED"`). Issue comments are extracted for context/directives.
- Co-Authored-By trailer is required on all commits: `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`.

---

### Task 1: PM Goal Sweeper & Brainstorm Agenda Generator

**Files:**
- Create: `synlynk/pm_sweep.py`
- Test: `tests/test_pm_sweep.py`

**Interfaces:**
- Consumes: `synlynk.db._get_db`, `goals` table schema.
- Produces:
  - `sweep_active_goals(conn=None, repo_path=None) -> list[dict]`
  - `generate_brainstorm_agenda(goal: dict, repo_path: str) -> str`
  - `raise_brainstorm_agenda_issue(goal: dict, agenda_path: str, repo_path: str) -> str`

- [ ] **Step 1: Write the failing test**
  Create `tests/test_pm_sweep.py` with test cases:
  1. `test_sweep_active_goals_detects_unspecced_goals`: Seeds an active goal without matching spec in `docs/superpowers/specs/`, verifies it is returned.
  2. `test_sweep_active_goals_skips_specced_goals`: Seeds a goal with an existing spec file, verifies it is omitted.
  3. `test_generate_brainstorm_agenda`: Verifies markdown agenda structure with Intent, Context, Trade-offs, and Instructions.

- [ ] **Step 2: Run test to confirm failure**
  ```bash
  pytest tests/test_pm_sweep.py
  ```

- [ ] **Step 3: Implement `synlynk/pm_sweep.py`**
  Implement scanning of `goals` table, check against `docs/superpowers/specs/`, generate agenda markdown files in `docs/brainstorm/`, and invoke `gh issue create` via `synlynk.gh_role` or subprocess with `--assignee @nikhilsoman --label brainstorm-agenda,pm-intake`.

- [ ] **Step 4: Run test to confirm passing**
  ```bash
  pytest tests/test_pm_sweep.py
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add synlynk/pm_sweep.py tests/test_pm_sweep.py
  git commit -m "feat(pm): goal sweeper and brainstorm agenda generator"
  ```

---

### Task 2: GitHub State-Driven Approval Oracle

**Files:**
- Modify: `synlynk/approval_gate.py`
- Test: `tests/test_approval_gate_oracle.py`

**Interfaces:**
- Consumes: `approval_tickets` table, GitHub CLI (`gh`).
- Produces:
  - `check_github_issue_status(issue_ref: str, repo_path=None) -> dict`: Returns `{"state": "OPEN"|"CLOSED", "closed_at": str, "comments": list[str]}`.
  - `poll_approval_tickets(conn=None, repo_path=None) -> list[dict]`: Scans `approval_tickets WHERE status='open'`, resolves tickets whose GitHub issues are closed, extracts comment feedback into `resolution_context`.

- [ ] **Step 1: Write the failing test**
  Create `tests/test_approval_gate_oracle.py` mocking `subprocess.run` on `gh issue view`, testing:
  1. Open issue remains `open`.
  2. Closed issue transitions ticket to `resolved` and extracts operator comments.
  3. Closed issue with label `wontfix` transitions ticket to `cancelled`.

- [ ] **Step 2: Run test to confirm failure**
  ```bash
  pytest tests/test_approval_gate_oracle.py
  ```

- [ ] **Step 3: Implement oracle functions in `synlynk/approval_gate.py`**
  Implement `check_github_issue_status` and `poll_approval_tickets`. Ensure deterministic parsing of `gh issue view <num> --json state,comments,labels,closedAt`.

- [ ] **Step 4: Run test to confirm passing**
  ```bash
  pytest tests/test_approval_gate_oracle.py
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add synlynk/approval_gate.py tests/test_approval_gate_oracle.py
  git commit -m "feat(gate): deterministic github issue state approval oracle"
  ```

---

### Task 3: Dual-Surfacing Notifications (Task Boundary Fence & Vizor Inbox)

**Files:**
- Create: `synlynk/inbox_notifier.py`
- Test: `tests/test_inbox_notifier.py`

**Interfaces:**
- Consumes: `.synlynk/viz-inbox.json`, terminal stdout.
- Produces:
  - `emit_boundary_fence_notice(title: str, issue_url: str, doc_path: str) -> None`: Prints high-visibility box/fence in interactive session.
  - `record_vizor_inbox_item(category: str, title: str, link: str, metadata: dict) -> None`: Appends structured JSON notification item for Vizor Tasks Inbox.

- [ ] **Step 1: Write the failing test**
  Create `tests/test_inbox_notifier.py` testing notice formatting and json persistence.

- [ ] **Step 2: Run test to confirm failure**
  ```bash
  pytest tests/test_inbox_notifier.py
  ```

- [ ] **Step 3: Implement `synlynk/inbox_notifier.py`**
  Write fence formatting logic and thread-safe atomic JSON file writing to `.synlynk/viz-inbox.json`.

- [ ] **Step 4: Run test to confirm passing**
  ```bash
  pytest tests/test_inbox_notifier.py
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add synlynk/inbox_notifier.py tests/test_inbox_notifier.py
  git commit -m "feat(notify): task boundary fence notice and vizor inbox logger"
  ```

---

### Task 4: Architect Spec & Plan Handoff Engine

**Files:**
- Create: `synlynk/architect_handoff.py`
- Test: `tests/test_architect_handoff.py`

**Interfaces:**
- Consumes: Resolved brainstorm tickets, `synlynk.dispatch.dispatch_agent`.
- Produces:
  - `trigger_architect_spec(ticket: dict, repo_path=None) -> str`: Launches Architect to draft design doc incorporating human feedback.
  - `raise_spec_approval_issue(spec_path: str, topic: str, repo_path=None) -> str`: Files `[Spec Review]` issue on GitHub assigned to `@nikhilsoman`.
  - `trigger_architect_plan(spec_ticket: dict, repo_path=None) -> str`: Launches Architect to produce plan upon spec issue closure.

- [ ] **Step 1: Write the failing test**
  Create `tests/test_architect_handoff.py` testing handoff dispatch and payload injection.

- [ ] **Step 2: Run test to confirm failure**
  ```bash
  pytest tests/test_architect_handoff.py
  ```

- [ ] **Step 3: Implement `synlynk/architect_handoff.py`**
  Implement prompt context formatting, dispatch invocation with role `architect`, and creation of the spec review issue.

- [ ] **Step 4: Run test to confirm passing**
  ```bash
  pytest tests/test_architect_handoff.py
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add synlynk/architect_handoff.py tests/test_architect_handoff.py
  git commit -m "feat(architect): spec and plan handoff state machine"
  ```

---

### Task 5: TPM Plan Decomposition & Scoped Ready Stories

**Files:**
- Modify: `synlynk/tpm_sweep.py`
- Test: `tests/test_tpm_plan_decomposition.py`

**Interfaces:**
- Consumes: `docs/superpowers/plans/*.md`.
- Produces:
  - `decompose_plan_to_stories(plan_path: str, goal_id: str, phase: str, conn=None) -> list[str]`: Parses plan tasks, writes stories with `role='dev'|'designer'|'qa'` and `readiness='ready'`.

- [ ] **Step 1: Write the failing test**
  Create `tests/test_tpm_plan_decomposition.py` verifying parsing of markdown tasks and creation of state.db story rows.

- [ ] **Step 2: Run test to confirm failure**
  ```bash
  pytest tests/test_tpm_plan_decomposition.py
  ```

- [ ] **Step 3: Implement plan decomposition in `synlynk/tpm_sweep.py`**
  Parse checkbox tasks, assign appropriate role from task tags or file patterns, and insert rows into `stories` table.

- [ ] **Step 4: Run test to confirm passing**
  ```bash
  pytest tests/test_tpm_plan_decomposition.py
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add synlynk/tpm_sweep.py tests/test_tpm_plan_decomposition.py
  git commit -m "feat(tpm): plan decomposition into scoped ready stories"
  ```

---

### Task 6: Autonomous Worker Dispatch, QA Auto-Merge & Daemon Cadence Wiring

**Files:**
- Modify: `synlynk/tpm_sweep.py`
- Modify: `synlynk/daemon.py`
- Test: `tests/test_autonomous_sdlc_loop.py`

**Interfaces:**
- Consumes: All components from Tasks 1–5.
- Produces:
  - Autonomous pipeline tick in `synlynk/daemon.py`:
    `PM Sweep -> GitHub Approval Poll -> Architect Handoff -> TPM Decomposition -> Dev/Designer Build -> QA Review/Merge -> Maintainer Hygiene`.

- [ ] **Step 1: Write the failing end-to-end simulation test**
  Create `tests/test_autonomous_sdlc_loop.py` simulating full lifecycle from an unspecced goal to a merged PR.

- [ ] **Step 2: Run test to confirm failure**
  ```bash
  pytest tests/test_autonomous_sdlc_loop.py
  ```

- [ ] **Step 3: Wire autonomous stages into `synlynk/daemon.py` and `synlynk/tpm_sweep.py`**
  Connect the full pipeline loop into `_run_autonomous_loop_tick()` in `daemon.py`.

- [ ] **Step 4: Run test to confirm passing**
  ```bash
  pytest tests/test_autonomous_sdlc_loop.py
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add synlynk/daemon.py synlynk/tpm_sweep.py tests/test_autonomous_sdlc_loop.py
  git commit -m "feat(daemon): wire full autonomous sdlc loop with github approval gates"
  ```
