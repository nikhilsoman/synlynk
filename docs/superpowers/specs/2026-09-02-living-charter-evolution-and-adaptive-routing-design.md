# Design Spec: Living Charter Evolution & Capability-Gated Adaptive Routing Engine

**Date:** 2026-09-02  
**Status:** In Review  
**Issue:** [#1342](https://github.com/nikhilsoman/synlynk/issues/1342)  
**Authors:** [@nikhilsoman], [@agy], [@codex], [@claude]  
**Relates to:** `goal-adb60ccc`, `goal-a222b393`, #1199  

---

## 1. Objective & Scope

Establish an empirical feedback loop between **verified job telemetry**, **Bayesian capability scoring**, and **dynamic fleet routing**. 

When actual production execution proves that a model or harness excels or degrades at a specific task domain (e.g. Codex on CLI plumbing, Agy on large-scale refactors, Grok on infra/canvas), the capability router automatically adjusts dispatch weights and generates living charter update PRs for team sign-off.

---

## 2. Architectural Design

```
                     ┌────────────────────────────────────────────────────────┐
                     │          VERIFIED EXECUTION & QA MERGE RECEIPTS        │
                     └──────────────────────────┬─────────────────────────────┘
                                                │
                                                ▼
                     ┌────────────────────────────────────────────────────────┐
                     │         Bayesian Capability Calibrator (state.db)      │
                     │  - First-pass pass rate (%)                            │
                     │  - Rework / review cycle frequency                     │
                     │  - Token efficiency & cost per successful diff         │
                     └──────────────────────────┬─────────────────────────────┘
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
     ┌───────────────────────┐                                     ┌───────────────────────┐
     │  Adaptive Dispatcher  │                                     │  Living Charter Sync  │
     │  - Bayesian Weighting │                                     │  - synlynk charters   │
     │  - Expected Value Eq  │                                     │    adapt (Draft PRs)  │
     └───────────────────────┘                                     └───────────────────────┘
```

### A. Bayesian Capability Ledger (`capability_ledger` in `state.db`)
- Tracks performance tuple `(model_id, harness, task_domain)`:
  - `prior_alpha`, `prior_beta` (Beta distribution for success probability)
  - `recency_half_life`: Decays stale priors every 30 days to account for model upgrades
  - `token_productivity_ratio`: `output_tokens_accepted / total_tokens_spent`

### B. Expected Value Dispatch Formula
$$\text{Expected Value} = \frac{E[\text{Success} \mid \text{model, domain}] \times \text{Task Criticality}}{\text{Amortized Cost}(\text{model}) + \alpha \cdot \text{P95 Latency}}$$

### C. Living Charter Auto-Proposal Generator (`synlynk charters adapt`)
- When empirical success rates for an agent/harness pair diverge from static markdown charters by $>25\%$:
  - Automatically drafts a PR updating `docs/charters/corpus-references.md` and `.synlynk/roles.yaml`.
  - Attaches verifiable empirical charts and cost comparisons to the PR description.

---

## 3. Test & Verification Plan
- Unit tests in `tests/test_capability_ledger.py` validating Beta prior updates, decay functions, and adaptive routing decisions.
