# RxCC Synlynk Adoption Parity: Case Study, Fleet Variations & Safe Migration Playbook Specification

- **Date:** 2026-09-12
- **Author:** AGY (AntiGravity)
- **Target Audience:** Synlynk Core Architecture, Workspace Operators, Early Adopters
- **Status:** Draft / Architectural Spec

---

## 1. Executive Summary

This document captures the end-to-end retrospective of bringing the `rxcc` repository into complete adoption parity with modern **synlynk v0.20.0+**, audits the current state of synlynk adoption across all local workspace repositories (`synlynk`, `rxcc`, `cc-videoreframing`, `hitchcock`, `playblazer-ng`, `ccmyca`, `symphony`, `bhrt`), diagnoses the systemic failure modes that cause early adopters to drift or reject synlynk automation, and specifies an automated, safe migration pathway for existing repositories.

---

## 2. The RxCC Parity Journey: Detailed Case Study

### 2.1 Initial State & Symptoms
Prior to the parity intervention, `rxcc` exhibited severe drift from modern synlynk standards:
1. **Config Drift:** `.synlynk/config.json` had `"workgroup_agents": ["claude", "codex"]`, completely omitting `agy` and `grok` despite 73 historical dispatch jobs having run across them.
2. **Missing Directives:** `GROK.md` was non-existent. `GEMINI.md` contained an obsolete v0.9.4 stub with explicit warnings against running `synlynk instructions update`.
3. **The "LIVE-51 Tampering" Misconception:** On 2026-07-26 (incident LIVE-51), an autonomous agent session identified automatic `<!-- synlynk:harness -->` fence injection into `CLAUDE.md` and treated it as a prompt-injection attack, reverting the fences across `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md`. Consequently, `synlynk doctor` failed TC-5 SOP checks across the board.
4. **Missing Policy & Capability Roles:** `policy.json`, `roles.yaml`, and `capability-roles.json` were uncommitted and untracked in `.gitignore`, preventing `synlynk policy check-merge` from functioning.
5. **Instruction Manifest Drift:** `.synlynk/instructions.json` contained stale file SHAs from June 2026, causing `synlynk instructions status` to flag files as drifted or unfenced.
6. **Language Assumption Hazard:** `synlynk policy sync-branch-protection` hardcodes Python 3.8/3.10/3.12 CI checks, which would break `rxcc`'s Node 22/TypeScript Vitest suite if applied blindly.

### 2.2 The Remediation Process
Parity was achieved via a structured 4-phase plan isolated within a dedicated git worktree (`.worktrees/synlynk-adoption-parity`):
1. **Repository Configuration & Ignore Rules:**
   - Modified `.gitignore` to allow tracking `policy.json`, `roles.yaml`, and `capability-roles.json`.
   - Tailored `.synlynk/policy.json` specifically for RxCC: frontend mapped to `agy`, backend/testing/review to `codex`, canvas/js/infra to `grok`, PM/brainstorm to `claude`.
   - Gated merge authority strictly to `qa` (`can_merge: ["qa"]`).
2. **Directive Creation & Fence Injection:**
   - Created `GROK.md` defining Grok's domain (`canvas`, `js`, `infra`).
   - Modernized `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md` with standard `<!-- synlynk:start version="0.20.0" -->` and `<!-- synlynk:harness -->` SOP fences.
   - **Crucial Rule:** 100% of existing repository domain knowledge (FHIR/LOINC rules, Prisma client encryption extensions, AWS ECS/Pulumi architecture) was preserved intact above the synlynk fences.
   - Ran `synlynk roles --fix` to populate missing SOP sections (`PR Review Discipline`, `Herdr Workspace Protocol`, `Brainstorm-First Policy`).
   - Registered all 4 instruction files with `synlynk instructions register`.
3. **Agent Profiles & Model Rates:**
   - Populated `.agents/` profiles for `claude.json`, `agy.json`, `codex.json`, and `grok.json`.
   - Seeded `.synlynk/model_rates.json` to resolve model pricing drift warnings.
4. **Verification & Merge:**
   - `synlynk doctor` verified TC-5 SOP checks green across all 4 harnesses.
   - `synlynk policy check-merge --role qa` passed; unauthorized roles (`dev`) blocked.
   - Pushed `feat/agy/synlynk-adoption-parity` and opened PR #1149.
   - Node 22 Vitest CI passed green in 3m 32s.
   - Squash-merged into `master`, worktree deleted, local `master` synchronized.

---

## 3. Fleet-Wide Workspace Survey (Local Ecosystem Audit)

An empirical scan of all local workspace repositories in the developer environment (`/Users/nikhilsoman/dev` and `/Users/nikhilsoman/My Drive/DEV`) revealed four distinct tiers of synlynk adoption:

| Repository | Path / Stack | .synlynk Present? | Migrated Structure? | Policy Layer? | Roles YAML / Cap Roles? | Workgroup Agents Configured | Directives State | TC-5 SOP Status | Adoption Tier |
|:---|:---|:---:|:---:|:---:|:---:|:---|:---|:---:|:---:|
| **`synlynk`** | Python CLI (Reference) | Yes | Yes | Yes | Yes / Yes | Dynamic (`[]`) | All 4 fenced | PASS (All 4) | **Tier 3 (Full Parity)** |
| **`rxcc`** | Node 22 / Fastify / Next.js | Yes | No (Hybrid root) | Yes | Yes / Yes | `claude, codex, agy, grok` | All 4 fenced (`+ user-content`) | PASS (All 4) | **Tier 3 (Full Parity)** |
| **`cc-videoreframing`** | Python / Video ML | Yes | Yes | **No** | Yes / **No** | `claude, codex, grok` (Missing `agy`) | CLAUDE missing `synlynk:start` | FAIL (Missing Herdr Protocol) | **Tier 2 (Partial/Drifted)** |
| **`hitchcock`** | Python / Node / Electron | Yes | No | **No** | **No** / **No** | `claude, codex, grok, local, agy` | All 4 exist & fenced | PASS | **Tier 2 (Partial/Drifted)** |
| **`playblazer-ng`** | Go / TypeScript | Yes | No | **No** | **No** / **No** | `claude, codex, grok, local` (Missing `agy`) | **No harness fences** | FAIL (No harness fences) | **Tier 1 (Legacy Fences Only)** |
| **`ccmyca`** | Python / Web | Yes | No | **No** | **No** / **No** | **None** (`config.json` missing) | No harness fences, GROK missing | FAIL (`config.json` missing) | **Tier 1 (Unconfigured)** |
| **`symphony`** | Python / Audio | No | No | No | No / No | None | None | N/A | **Tier 0 (Uninitialized)** |
| **`bhrt`** | TypeScript / Pulumi | No | No | No | No / No | None | None | N/A | **Tier 0 (Uninitialized)** |

### Tier Classification Breakdown:
- **Tier 3 (Modern Parity):** `synlynk`, `rxcc`. Complete multi-agent configuration, `.agents/` profiles, verified TC-5 SOP fences, `policy.json` with QA merge authority.
- **Tier 2 (Partial / Drifted):** `cc-videoreframing`, `hitchcock`. Synlynk is active and working, but lacks `policy.json`, has missing SOP sections (e.g. `## Herdr Workspace Protocol`), or has incomplete `workgroup_agents` rosters.
- **Tier 1 (Legacy / At Risk):** `playblazer-ng`, `ccmyca`. Files were created during early synlynk versions (v0.9–v0.12) but have never received `<!-- synlynk:harness -->` SOP fences. Running agent dispatches in these repos triggers TC-5 warnings or silent revert behaviors.
- **Tier 0 (Uninitialized):** `symphony`, `bhrt`. No `.synlynk/` folder or agent directive files exist.

---

## 4. Root Causes: Why Early Adopter Repos Drift

1. **Installer Destructiveness (`synlynk join` vs `synlynk identity init`):**
   Early adopters ran `synlynk join` expecting to configure credentials or participate in a swarm; instead, `synlynk join` historical logic blew away pre-existing directive files with generic templates, traumatizing developers and prompting defensive file locks.
2. **Silent Background Injections & The Tampering Panic:**
   When `synlynk sync` or `_repair_sops_only` appends SOP fences without user-facing logs explaining *why*, autonomous LLM agents (Claude/Codex) analyzing the diff conclude that an unauthorized actor injected foreign instructions into their steering file.
3. **Hardcoded Monoculture Assumptions:**
   Synlynk began as a Python CLI. Commands like `policy sync-branch-protection` still hardcode Python matrix checks (`3.8`, `3.10`, `3.12`), which break non-Python codebases (Node, Go, Rust).
4. **Lack of a 1-Step Non-Destructive Health & Parity Command:**
   There has been no single command (`synlynk heal --parity`) that inspects a repo's language, preserves user directives, injects missing SOP fences, creates agent profiles, and generates an appropriate `policy.json` without user fear.

---

## 5. Architectural Solutions & Safe Migration Pathways

### Proposal A: Safe Declarative Parity Command (`synlynk heal --parity`)
A new automated, non-destructive migration engine that guarantees:
- **Preservation Invariant:** Code/text outside `<!-- synlynk:start -->` and `<!-- synlynk:harness -->` is treated as sacred and NEVER modified.
- **Stack-Aware Policy Generation:** Auto-detects `package.json`, `go.mod`, `Cargo.toml`, `pyproject.toml`, or `Makefile` to populate `policy.json` with language-accurate CI requirements.
- **Atomic Worktree Preflight:** Runs all parity upgrades in an isolated background worktree (`.worktrees/synlynk-parity-check`), verifies `synlynk doctor` and test suites, and presents a clean PR for human review.

### Proposal B: Transparent Audit & Drift Defense
- Update `synlynk doctor` to explicitly distinguish between user instructions and synlynk harness SOPs.
- Clarify the role of harness SOP fences in all generated headers so future LLMs do not misdiagnose them as security incidents.

### Proposal C: Installer & Join Hardening
- Re-architect `synlynk join` so it NEVER overwrites existing directive files.
- Decouple agent onboarding from directive file regeneration.
