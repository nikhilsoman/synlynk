<!-- generated - source of truth is state.db -->
---
decision_id: dec-8b3c1d42
topic: "Final Sprint Master Plan: Deep Repo Backlog & Tech-Debt Sweep, Worktree/Branch Hygiene, Packaging Hermeticity, and Autonomous GitHub Observability Protocol for Developer Preview v0.29.0"
date: 2026-11-07
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Review and approve the comprehensive housekeeping, debt remediation, and execution plan for the final sprint prior to the Developer Preview release (v0.29.0). Address the deep sweep of 135 accumulated worktrees, root file clutter, test suite hermeticity, standalone packaging, and the unified 10-stage onboarding flow, executed fully autonomously with GitHub as the sole operator review surface.

## Panel Inputs

### claude
[model=claude-3-7-sonnet; role=architect/pm]

**Analysis & Perspective: Autonomous Sprint Governance & Risk Elimination**

The findings of this deep sweep confirm that Synlynk has been operating under severe operational debt. Accumulating 135 worktrees is not merely a disk hygiene issue—it is the direct architectural cause of the recurring LIVE-16 and LIVE-30 crash-loops, as python interpreters and daemons resolve modules through deleted or stale worktree paths.

For this final sprint to succeed autonomously with GitHub as the operator's primary surface:
1. **GitHub Issue as the Single Control Plane:** Issue #5163 must be structured as the Master Epic, linking 4 concrete child tracking issues:
   - Issue A: Repo & Worktree Hygiene (pruning 135 worktrees, sweeping orphan dispatch branches, cleaning root docs).
   - Issue B: Hermetic Packaging & Test Green (standalone wheel/pipx, virtualizing doctor paths, 100% test pass on main).
   - Issue C: Unified Genesis Onboarding Engine (10-stage flow, Sovereign Key generation, Fenced Companion).
   - Issue D: Developer Preview Packaging & Release Gate (v0.29.0 tag, release notes, and Hacker News collateral).
2. **Automated Status Rollups:** After each child PR merges, the agent must post a structured, long-form conversational status rollup as a comment directly on #5163, giving Nikhil complete visibility on GitHub without needing to open a terminal.
3. **Zero Direct-to-Main Commits:** Every task must execute in an isolated branch/worktree, pass TDD verification, and go through a non-authoring cross-harness QA review before squash-merging.

**Position:** Approve the plan. Require that Issue #5163 and its child tickets serve as the exclusive, transparent audit trail on GitHub.

### agy
[model=gemini-3.8-flash; role=frontend/onboarding]

**Analysis & Perspective: The Clean-Canvas Release Experience**

From a product and onboarding standpoint, shipping a developer preview with 85+ dead `worktrees/job-*` folders and operational files (`synlynk_costs.md`, `.bak` databases, legacy shard cleanup reports) at the repository root destroys credibility. An open-source evaluator inspecting the repo on GitHub will immediately judge the project by its root cleanliness and documentation coherence.

The hygiene sprint must:
1. **Curate the Repository Root:** Keep the root strictly canonical (`README.md`, `LICENSE`, `pyproject.toml`, `VERSION`, `CHANGELOG.md`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `GROK.md`). Everything else moves to `project-docs/` or `docs/archive/`.
2. **Execute the Unified Genesis Onboarding:** Implement the 10-stage flow from spec `2026-11-07-unified-onboarding-and-fenced-companion-design.md`. Ensure the operator experience starts with the Synlynk Invariants, generates their Sovereign Key, and awakens the Fenced Companion cleanly.
3. **GitHub Review Surface Ergonomics:** Ensure PR descriptions feature formatted markdown summaries, before/after diff tables, and direct links to generated artifacts.

**Position:** Strongly approve. Purging root clutter and delivering the unified Genesis onboarding transforms Synlynk from an internal laboratory into a cohesive, production-grade product.

### codex
[model=codex-cli-0.163.0; role=core-systems/cli-plumbing]

**Analysis & Perspective: Mechanical Hygiene & Hermetic Packaging Protocol**

The mechanical root cause of instability across past releases is the interplay between editable installs (`pip install -e .`) and short-lived git worktrees. When Worktree Hygiene prunes a worktree, any background process holding a reference to that worktree dies on `ModuleNotFoundError`.

To execute the hygiene sweep safely:
1. **Worktree Pruning Protocol:**
   - Scan all 135 worktrees.
   - For every worktree whose branch is merged into `main` or whose PR is closed, run `git worktree remove --force`.
   - Prune git metadata via `git worktree prune`.
   - Sweep matching local `dispatch/*` and `review/*` branches.
2. **Hermetic Wheel Packaging:**
   - Modify `synlynk/vizor_daemon.py` and `synlynk/dispatch.py` so they do not rely on dynamic git root rev-parse calls.
   - Package Synlynk as a standalone wheel and generate a self-contained entry point (`pipx` compatible) with isolated dependencies.
3. **Doctor Test Virtualization:**
   - In `tests/test_agent_quota_tracking.py` and `synlynk/doctor.py`, mock `resolve_github_apps_dir` and workspace state paths to a temporary sandbox directory so running `pytest` never attempts to read `~/.synlynk` or fail on permission barriers.

**Position:** Approve. This eliminates the technical debt that produced LIVE-16, LIVE-28, and LIVE-30 once and for all.

### grok
[model=grok-1.0.70; role=infra/capability-routing]

**Analysis & Perspective: Fleet Telemetry & Sovereign Key Infrastructure**

This final sprint cements the operational transition to Paradigm 2a while laying the cryptographic bedrock for Paradigm 2b:

1. **Sovereign Key Infrastructure:**
   - Integrate `synlynk/crypto.py` to generate `Ed25519` keypairs with 12-word BIP-39 mnemonic phrases.
   - Anchor all policy updates and milestone approvals to this sovereign signature.
2. **Fenced Companion & Statusline:**
   - Deploy `synlynk/companion.py` as a strictly read-only, non-mutating observer that renders ambient statusline updates and monitors spend against budget ceilings.
3. **Observability via GitHub:**
   - The autonomous fleet will post telemetry rollups (tokens burned, quality scores, test execution proofs) directly into GitHub issue comments, satisfying Nikhil's requirement for zero-touch oversight.

**Position:** Approve. This establishes a clean, auditable boundary between sovereign biological direction and synthetic execution.

## Synthesis
The panel unanimously approves the **Final Sprint Master Plan**. 

The sprint is organized into three sequential phases executed via autonomous dispatch and tracked on GitHub:
1. **Phase A: Deep Repo & Worktree Housekeeping**
   - Safe removal of 135 stale worktrees and orphan dispatch branches.
   - Elimination of root clutter (`synlynk_costs.md`, `.bak` files, migration reports).
2. **Phase B: Core Engine Hermeticity & Test Green**
   - Standalone wheel packaging and `pipx` launcher (permanent LIVE-30 fix).
   - Test suite hermeticity fix for `synlynk/doctor.py` and quota tracking (100% green `pytest` on `main`).
3. **Phase C: Unified Genesis Onboarding & Sovereign Key**
   - Implement the 10-stage Genesis flow (`synlynk new` and `synlynk onboard`).
   - Implement Ed25519 Sovereign Key generator + 12-word recovery phrase.
   - Implement Domain Archetype recommender and Fenced Companion statusline.
4. **Phase D: Developer Preview Gate Closeout**
   - Update `VERSION` to `v0.29.0`, generate clean release notes, and update master tracking issue #5163.

## Decision
Execute the Final Sprint Master Plan immediately under the governance of parent issue #5163, with GitHub as the sole observability and approval surface.

> Signatures: see 2026-11-07-final-sprint-backlog-sweep-hygiene-and-dev-preview-readiness.json
