# Developer Preview (v0.29.0) Final Sprint Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the consolidated final sprint to stabilize, package, and launch Synlynk Developer Preview (`v0.29.0`)—retiring all accumulated technical debt (135 worktrees, root clutter, LIVE-30 import crashes, test isolation failures) and delivering the Unified Genesis Onboarding flow with the full Companion v2.1 ambient co-pilot.

**Observability & Governance Contract:** This plan executes autonomously under the governance of GitHub Parent Issue **#5163**. All progress, telemetry rollups, and PR review checkpoints are reported directly to GitHub issue comments.

---

## File Structure & Impact Matrix

| Subsystem / Area | File Targets | Responsibility |
|:---|:---|:---|
| **Housekeeping & Worktrees** | `worktrees/job-*`, `.worktrees/*`, `.claude/worktrees/*` | Safe audit against merged PRs and bulk pruning of dead worktrees and orphan dispatch branches. |
| **Root Hygiene** | `synlynk_costs.md`, `state.db.pre-migration-*.bak`, `legacy_*.txt` | Relocate internal logs to `project-docs/archive/` and reconciliation notes to `docs/archive/`. |
| **Core Packaging (LIVE-30)** | `synlynk/vizor_daemon.py`, `synlynk/dispatch.py`, `pyproject.toml` | Build hermetic wheel & standalone `pipx` launcher, removing ambient worktree git `rev-parse` dependencies. |
| **Test Suite Hermeticity** | `synlynk/doctor.py`, `tests/test_agent_quota_tracking.py` | Virtualize `~/.synlynk/` workspace paths under test runners for 100% green `pytest` on clean checkouts. |
| **Sovereign Crypto** | `synlynk/crypto.py`, `tests/test_crypto.py` | `Ed25519` keypair generator, GPG key import, and BIP-39 12-word recovery phrase generator. |
| **Domain Taxonomy** | `synlynk/taxonomy.py`, `tests/test_taxonomy_archetypes.py` | Workspace domain taxonomy (Web, Mobile, AI/ML, Backend, Systems) & Fleet Archetype recommender. |
| **Fencing Seam** | `synlynk/fencing.py`, `tests/test_fencing_hint_contributors.py` | Generic `_HINT_CONTRIBUTORS` seam calling registered feature callbacks without feature-level circular imports. |
| **Companion v2.1 Engine** | `synlynk/companion.py`, `tests/test_companion.py` | 4-part message anatomy (`[Signal]`, `[Context]`, `[Nudge]`, `[Deep Links]`), relationship ladder, OSC 8 hyperlinks. |
| **Genesis Onboarding** | `synlynk/greenfield/`, `synlynk/wizard.py` | Unified 10-stage Genesis flow (`synlynk new` and `synlynk onboard`) weaving Invariants, Sovereign Key, & Companion. |
| **Release Gate** | `VERSION`, `CHANGELOG.md`, `README.md` | Version bump to `v0.29.0`, synchronized collateral, and Hacker News launch draft. |

---

## Phase A: Deep Repo & Worktree Housekeeping

### Task A1: Safe Worktree & Branch Pruning
- [ ] **Step A1.1: Audit Worktree Status against Merged PRs**
  Run an automated audit script matching each of the 135 worktree paths against merged git branches and GitHub PR states (`gh pr list --state merged`). Flag active or uncommitted worktrees; mark all merged/stale dispatch worktrees for removal.
- [ ] **Step A1.2: Remove Dead Worktrees & Prune Git Metadata**
  Safely execute `git worktree remove --force <path>` for all verified stale dispatch worktrees in `worktrees/job-*` and `.worktrees/`. Follow with `git worktree prune`.
- [ ] **Step A1.3: Prune Stale Local Dispatch & Review Branches**
  Delete orphan local branches (`dispatch/*`, `review/*`) whose PRs have already been squash-merged into `main`.

### Task A2: Repository Root Curation
- [ ] **Step A2.1: Relocate Internal Cost & Burn Tracking**
  Move [`synlynk_costs.md`](file:///Users/nikhilsoman/dev/synlynk/synlynk_costs.md) into `project-docs/archive/costs-pre-v0290.md`.
- [ ] **Step A2.2: Relocate Legacy Reconciliation Reports**
  Move `legacy_shard_cleanup_report.txt`, `positioning-messaging-reconciliation.md`, `union-merge-conflict-reconciliation.md`, and `data-model-design.md` into `docs/archive/reconciliations/`.
- [ ] **Step A2.3: Purge Binary Backups & Enforce Gitignore**
  Remove `state.db.pre-migration-20260928T182556.450435Z.bak` from the working tree. Update `.gitignore` to ensure `*.bak`, `*.db*.bak`, and local `.env.*` files are unconditionally ignored.
- [ ] **Step A2.4: Verify Root Cleanliness**
  Verify that `ls` at the repository root contains only canonical product files (`README.md`, `LICENSE`, `VERSION`, `CHANGELOG.md`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `GROK.md`, `pyproject.toml`).

---

## Phase B: Core Engine Hermeticity & Green Test Suite

### Task B1: Standalone Wheel & Packaging Hermeticity (LIVE-30 True Fix)
- [ ] **Step B1.1: Write Failing Regression Test for Worktree-Independent Import**
  Create `tests/test_standalone_import_isolation.py` verifying that `vizor_daemon._service_environment()` and `dispatch._build_subprocess_env()` resolve against an immutable, non-worktree interpreter path when run outside git repos.
- [ ] **Step B1.2: Refactor `_synlynk_import_root()`**
  In `synlynk/vizor_daemon.py`, replace the ephemeral `git rev-parse --git-common-dir` lookup with resolution against the installed package venv/wheel directory, falling back to durable main root.
- [ ] **Step B1.3: Package Hermetic Entrypoint (`pipx` compatible)**
  Verify `python3 -m build` generates a clean wheel and test installation via `pipx install dist/*.whl --force`.

### Task B2: Doctor Test Virtualization for 100% Green Suite
- [ ] **Step B2.1: Reproduce `PermissionError` under Sandbox**
  Run `pytest tests/test_agent_quota_tracking.py -k "test_synlynk_doctor"` and confirm failure on unmocked `apps_dir` paths.
- [ ] **Step B2.2: Virtualize Host Paths in `synlynk/doctor.py`**
  In `_hc_identity_file_perms()`, wrap `resolve_github_apps_dir()` with an environment variable override (`SYNLYNK_TEST_APPS_DIR`) or ensure it gracefully handles sandboxed permission errors.
- [ ] **Step B2.3: Run Full Suite Verification**
  Execute `pytest -q` across the entire repository and confirm 100% green exit code (0 failures).

---

## Phase C: Genesis Onboarding & Companion v2.1 Integration

### Task C1: Sovereign Key & Cryptographic Recovery Engine
- [ ] **Step C1.1: Write Failing Tests for Sovereign Key Generation**
  Create `tests/test_crypto_sovereign_identity.py` testing `generate_sovereign_keypair()`, BIP-39 12-word mnemonic phrase derivation, and message signing/verification.
- [ ] **Step C1.2: Implement `synlynk/crypto.py`**
  Implement `Ed25519` keypair generation using standard library / cryptography, with mnemonic export and signature verification.
- [ ] **Step C1.3: Wire Key Generation into Onboarding**
  Add Sovereign Key generation to Stage 5 of the Genesis onboarding protocol.

### Task C2: Domain Taxonomy & Fleet Archetype Recommender
- [ ] **Step C2.1: Write Tests for Archetype Recommendation**
  Create `tests/test_taxonomy_archetypes.py` verifying that selecting domains (`mobile`, `ai_ml`, `backend`, `fullstack`) returns specialized agent archetype sets.
- [ ] **Step C2.2: Implement Recommender in `synlynk/taxonomy.py`**
  Map domains and organizational hierarchy positions to default fleet configurations.

### Task C3: Generic Hint-Contributor Seam in `synlynk/fencing.py`
- [ ] **Step C3.1: Write Failing Tests for Hint Contributor Registry**
  Create `tests/test_fencing_hint_contributors.py` asserting that registered callbacks modify `data.hints` and that `fencing.py` names no feature modules directly.
- [ ] **Step C3.2: Implement `_HINT_CONTRIBUTORS` Seam**
  Add `_HINT_CONTRIBUTORS: list` and `register_hint_contributor()` in `synlynk/fencing.py`, calling registered contributors in `render_task_fence()`.

### Task C4: Companion v2.1 Engine Implementation
- [ ] **Step C4.1: Write Tests for Companion v2.1 Message Anatomy & Pinning**
  Create `tests/test_companion_v21.py` testing 4-part message formatting (`[Signal]`, `[Context]`, `[Nudge]`, `[Deep Links]`), OSC 8 virtual hyperlinks, and per-command stage/segment pinning.
- [ ] **Step C4.2: Implement `synlynk/companion.py`**
  Implement the full Companion v2.1 engine per spec `docs/superpowers/specs/2026-10-31-companion-v2-design.md`, including template lookup, domain vocabulary substitution, and the 6 relationship ladder stages.
- [ ] **Step C4.3: Wire Companion into Genesis Onboarding (Stage 8)**
  Connect Companion v2.1 to `synlynk new` and `synlynk onboard` as the ambient Fenced Companion presence.

---

## Phase D: Developer Preview Gate Closeout (v0.29.0)

### Task D1: License & Packaging Finalization
- [ ] **Step D1.1: Update LICENSE to Apache 2.0**
  Update [`LICENSE`](file:///Users/nikhilsoman/dev/synlynk/LICENSE) from plain MIT to Apache 2.0, providing explicit patent protection and trademark reservation.
- [ ] **Step D1.2: Bump Version to `0.29.0`**
  Update `VERSION` to `0.29.0` and synchronize `pyproject.toml` and documentation assets.

### Task D2: Verification & Public Collateral Gate
- [ ] **Step D2.1: Run 15-Minute Greenfield FTUE Dry-Run**
  Execute `synlynk new` on a clean temporary directory, verifying all 10 stages from Invariants briefing to First-Win verification skeleton.
- [ ] **Step D2.2: Closeout Status Rollup on Issue #5163**
  Post the comprehensive conversational status rollup comment on GitHub Issue #5163 with full test logs, token costs, and commit SHAs.
- [ ] **Step D2.3: Generate Hacker News Announcement Draft**
  Author `docs/blog/v0.29.0-hacker-news-announcement.md` positioning Synlynk as *"The Full-Stack Builder Harness"*.
