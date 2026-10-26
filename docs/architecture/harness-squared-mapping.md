# Google Research Harness² Architecture Mapping for Synlynk

**Reference:** Google Research, *Empirical Foundations of Self-Improving Agent Architectures* (arXiv:2610.14224)  
**Synlynk Release Alignment:** v0.26.1 (Milestone #16, Release Epic #2469, Parent Epic #2458)  
**Author:** Agy (Home Conductor)  
**Date:** 2026-10-29  

---

## 1. Executive Summary

Google Research’s **Harness²** formalizes autonomous AI agent execution, verification, and recursive self-improvement around an 8-component architecture:

$$\mathcal{H}^2 = \langle H_{cfg}, A_{rt}, E_{sbx}, T_{spec}, C_{asm}, V_{har}, M_{eng}, T_{trk} \rangle$$

Furthermore, Harness² defines the **Dual-Recursion (Propose-Probe-Compose)** paradigm, where system mutations (code, prompt templates, tool definitions, charters) are iteratively proposed, tested against adversarial verification probes in isolated sandboxes, and composed into the authoritative substrate without regression.

This document formally maps Synlynk's subsystems, files, and contracts to the Harness² 8-component specification and formalizes how Synlynk implements dual-recursive self-improvement.

---

## 2. The 8-Component Mapping

| Harness² Component | Mathematical Notation | Synlynk Subsystem / Implementation | Primary Modules & Files |
| :--- | :---: | :--- | :--- |
| **1. Harness Config** | $H_{cfg}$ | Global and workspace policies, harness billing, role authority boundaries, and execution models. | `.synlynk/config.json`<br>`.synlynk/policy.json`<br>`synlynk/config.py`<br>`synlynk/policy.py` |
| **2. Agent Runtime** | $A_{rt}$ | Execution adapters that invoke and stream outputs from heterogeneous agent harnesses (`claude`, `agy`, `codex`, `grok`). | `synlynk/dispatch.py`<br>`synlynk/jobs.py`<br>`synlynk/circuit_breaker.py` |
| **3. Environment Sandbox** | $E_{sbx}$ | Isolated git worktrees, ephemeral ports, macOS fork guards, and sandboxed process environments. | `synlynk/worktree.py`<br>`synlynk/daemon.py`<br>`.worktrees/`<br>`tests/conftest.py` |
| **4. Task Spec** | $T_{spec}$ | Governed goals, epics, stories, and task prompts defining input requirements, deliverables, and budgets. | `state.db` (stories/goals)<br>`project-docs/todo.md`<br>GitHub Issues / PRs |
| **5. Context Assembly** | $C_{asm}$ | Token-bounded context packers, agent charter injectors, AST scanners, and memory recall. | `synlynk/context.py`<br>`synlynk/charter_injection.py`<br>`synlynk/scan.py`<br>`project-docs/memory.md` |
| **6. Verification Harness** | $V_{har}$ | Multi-tier validation contracts, test suites, invariant oracles, and QA merge gates. | `synlynk/selftest.py`<br>`synlynk pr check`<br>`synlynk policy check-merge`<br>`pytest` test suites |
| **7. Mutation Engine** | $M_{eng}$ | Atomic git branch manipulation, commit authoring, charter adaptation, and code editing operations. | `synlynk/charters.py` (`adapt`)<br>`git worktree` / `git cherry-pick`<br>`synlynk/roadmap.py` |
| **8. Telemetry Tracker** | $T_{trk}$ | Granular cost attribution, token ledger, sentinel fault monitors, and empirical capability calibration. | `synlynk/costs.py`<br>`synlynk/sentinel.py`<br>`synlynk/capability_sweep.py`<br>`project-docs/costs.md` |

---

## 3. Subsystem Deep-Dive

### 1. $H_{cfg}$ — Harness Configuration & Policy
Synlynk enforces declarative operational governance:
- **Merge Authority (`.synlynk/policy.json`):** Defines which roles (`architect`, `qa`, `pm`) possess authorization to approve or merge pull requests.
- **Billing & Subscriptions (`synlynk/costs.py`):** Calibrates monthly subscription amortization ($90/mo base across Claude, Codex, Agy, Grok) and un-amortized API overage tracking.
- **Charter Schemas (`synlynk/charter_schema.py`):** Canonicalizes allowed tools, escalation triggers, and bound superpowers.

### 2. $A_{rt}$ — Heterogeneous Agent Runtime
Synlynk decouples agent identity from harness backend:
- Headless execution pipes dispatches asynchronously to the four frontier harnesses with unbuffered stdout streaming and PID tracking.
- Circuit breakers monitor token velocity and dollar burn rate, enforcing clean-exit semantics on process termination.

### 3. $E_{sbx}$ — Environment Sandboxing
Every mutating task operates under strict isolation:
- **Worktree Isolation:** Changes occur exclusively in `.worktrees/<branch-name>`, keeping `origin/main` immutable.
- **Daemon Process Isolation:** Ephemeral port hunting ladders (`[33333, 44444, 55555, 22222, 11111]`) prevent socket conflicts.
- **macOS Fork-Safety:** `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` and absolute canonical PEM resolution protect background workers against multi-threaded crashes.

### 4. $T_{spec}$ — Task Specification & Contracts
Synlynk uses the GOVERNS lifecycle:
- High-level intents anchor in Goals (`goal-<hex>`) and Epics (`#<issue>`).
- Epics decompose into transactional Stories in `state.db` with explicit acceptance criteria and designated role assignments.

### 5. $C_{asm}$ — Context Assembly
Context packing balances token economy with model grounding:
- Charters from `.synlynk/agents/` are dynamically parsed, injecting role mandates, escalation boundaries, and bound superpowers instructions directly into task prompt headers.
- Worktrees are pruned from AST scans to eliminate token explosion and CPU thrashing.

### 6. $V_{har}$ — Verification Harness & Non-Author Oracles
Synlynk enforces non-negotiable verification gates before code transitions state:
- **Invariant 1:** The authoring harness cannot review or merge its own PR.
- **QA Verification (`synlynk pr check`):** Confirms model attribution, branch freshness, and clean regression test execution.
- **Post-Flight Attestation:** Headless dispatches with bound TDD skills must provide test modification receipts before review dispatch.

### 7. $M_{eng}$ — Mutation Engine
Code, configurations, and governance documents mutate via transactional primitives:
- `synlynk charters adapt` compares operational performance against baseline charters, proposing adjustments to `behavioral_weights` and `autonomous_authorities`.
- Multi-branch git operations stage mutations in isolated worktrees before submitting pull requests.

### 8. $T_{trk}$ — Telemetry & Empirical Calibration
All execution produces immutable telemetry:
- Every turn records input tokens, output tokens, dollar cost, duration, and model ID in `state.db` and `project-docs/costs.md`.
- `synlynk/sentinel.py` captures operational faults with automated 30-day TTL compaction and deduplication rollups.
- `synlynk/capability_sweep.py` benchmarks real-world model quality ($n \ge 5$ threshold) across SFIA software disciplines (`PROG`, `TEST`, `REQM`), driving dynamic EV-based dispatch routing.

---

## 4. Dual-Recursion: Propose-Probe-Compose in Synlynk

Harness² formalizes recursive self-improvement through three decoupled stages:

```
┌────────────────────────────────────────────────────────────────────────┐
│               HARNESS² DUAL-RECURSION WORKFLOW IN SYNLNYK              │
├────────────────────┬────────────────────┬──────────────────────────────┤
│ 1. PROPOSE         │ 2. PROBE           │ 3. COMPOSE                   │
├────────────────────┼────────────────────┼──────────────────────────────┤
│ • Agent analyzes   │ • Isolated scratch │ • Successful mutation        │
│   telemetry/faults │   worktree created │   merged to authoritative    │
│ • Drafts candidate │ • Executes smoke,  │   branch                     │
│   code, charter,   │   regression, &    │ • Telemetry baseline updated │
│   or prompt patch  │   adversarial test │ • Rollback snapshot pruned   │
└────────────────────┴────────────────────┴──────────────────────────────┘
```

1. **Propose:**
   - The **Maintainer Agent** consumes grouped alerts from `synlynk/sentinel.py`, analyzes stack traces, and generates a minimal reproduction test and candidate fix patch.
   - Or, the **Living Charter Engine** detects frequent escalation pauses and proposes expanding an agent's `autonomous_authorities`.
2. **Probe:**
   - Synlynk spins up an ephemeral scratch worktree (`.worktrees/probe-<id>`).
   - The verification harness executes the reproduction test to prove the bug exists on `main`, applies the candidate mutation, and runs the full test suite (`pytest`) to verify that no prior invariants are broken.
3. **Compose:**
   - Upon green probe verification, the mutation is committed, pushed to a feature branch, and opened as a pull request.
   - Following non-author review approval, the fix merges into `origin/main`, and `state.db` updates the system health baseline.

---

## 5. Architectural Alignment for v0.26.1 and Beyond

Integrating the Harness² model establishes the theoretical framework for:
- **v0.26.1:** Unifying Charter Schemas, enforcing Superpowers skill contracts, and activating the Maintainer triage loop.
- **v0.26.2:** Fully automating the Maintainer *Probe* cycle with ephemeral scratch worktree execution.
- **v0.27.0+ (Epic #2547):** Autonomous Recursive Self-Improvement (RSI) across agent prompts, routing policies, and harness adapters.
