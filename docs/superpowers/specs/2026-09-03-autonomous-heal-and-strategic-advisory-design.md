# Design Spec: Autonomous Remediation Loop (synlynk heal) & Strategic Advisory (synlynk decide --audit)

**Date:** 2026-09-03  
**Status:** In Review  
**Authors:** [@nikhilsoman], [@agy], [@codex], [@claude]  
**Relates to:** `goal-6ebfe9b5`, `goal-adb60ccc`, `goal-005ea87d`  

---

## 1. Objective & Scope

Establish two high-leverage capabilities:
1. **`synlynk heal`**: A 1-click closed-loop command executing:
   $$\text{Diagnose (Scan)} \longrightarrow \text{Story in state.db} \longrightarrow \text{Swarm Worker} \longrightarrow \text{QA Verify} \longrightarrow \text{Auto-Merge}$$
2. **`synlynk decide --audit`**: Multi-agent executive consulting panel synthesizing Code Health, Modularity, Technical Debt Hotspots, and AI-Readiness into an **Executive Strategic Recommendation Brief**.

---

## 2. Architecture & Components

```
 ┌──────────────────────────────────────────────────────────────────┐
 │                      AUTONOMOUS CONTROL ENGINE                   │
 └────────────────────────────────┬─────────────────────────────────┘
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
 ┌───────────────────────────────┐ ┌───────────────────────────────┐
 │ 1-Click Remediation (heal)    │ │ Strategic Advisory (decide)   │
 ├───────────────────────────────┤ ├───────────────────────────────┤
 │ • Scan repository gaps        │ │ • Multi-harness consensus     │
 │ • Form stories in state.db    │ │ • Preserves dissent & nuance  │
 │ • Fan-out fix to swarm worker │ │ • Emits Executive Brief in    │
 │ • QA test gate & auto-merge   │ │   project-docs/decisions/     │
 └───────────────────────────────┘ └───────────────────────────────┘
```

### A. The 1-Click Remediation Subsystem (`synlynk/heal.py`)
- CLI command: `synlynk heal [--auto-merge] [--batch-size N]`
- Executes the full pipeline without requiring manual step-by-step invocations:
  1. Invokes `run_workspace_scan()` to capture actionable diagnostics.
  2. Synthesizes `ready` stories with acceptance criteria via `synlynk/backlog.py`.
  3. Dispatches swarm jobs via `synlynk/swarm.py` to local or ephemeral cloud runners.
  4. Runs verification test matrix via QA gate.
  5. Resolves table conflicts with `synlynk/rebase.py` and completes merges.

### B. Strategic Advisory Audit (`synlynk decide --audit`)
- Convenes the multi-harness advisory board (Claude, Agy, Codex, Grok).
- Evaluates repository architecture along 5 dimensions:
  1. *Structural Modularity & Coupling*
  2. *Test Matrix & Regression Vulnerability*
  3. *AI-Native Development Readiness*
  4. *Technical Debt & Stale Dependencies*
  5. *Execution Cost & Token Efficiency*
- Generates structured Markdown Decision Record in `project-docs/decisions/YYYY-MM-DD-executive-architecture-audit.md`.

---

## 3. Test & Verification Plan
- Unit tests in `tests/test_heal.py` and `tests/test_decide_audit.py`.
