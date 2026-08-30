# Design Spec: Claude Baseline Role Alignment & Permission Handling

- **Topic:** Claude Harness Fleet Parity & Role Alignment
- **Author:** Agy (Gemini)
- **Status:** Approved / In Implementation
- **Target Release:** v0.18.1 / Fleet Parity
- **Goal:** goal-005ea87d
- **Story:** story-1a500214
- **Issue:** #1284
- **Related Issues:** #1140 (LIVE-6), #423

---

## 1. Problem Statement & Background

Our comprehensive fleet harness audit (`docs/harness-parity-reference.md`) identified a standing contradiction between Claude's programmatic capabilities and project SOP:

1. **Role Contradiction:**
   `synlynk/_constants.py:67` declares Claude's baseline roles as `["architect", "builder"]`. However, `CLAUDE.md`, `docs/harness-capability-baseline.md`, and project governance strictly designate Claude as PM, deployer, and reviewer (`pm / deploy / brainstorm only`), role-locking Claude out of code implementation. This contradiction leads to capability score drift and improper task auto-routing.
2. **Credential Risk Isolation (LIVE-6 / #1140):**
   When Claude Code runs in auto-mode, Anthropic's local risk classifier denies actions referencing sensitive `.pem` files or privileged GitHub App credentials (`Blocked by classifier`). Clarifying credential paths and baseline declarations prevents unexpected classifier denials.

---

## 2. Proposed Architecture & Changes

### Layer 1: Baseline Roles & Constants (`synlynk/_constants.py`)
- Update `HARNESS_CAPABILITY_BASELINES["claude"]["roles"]` from `["architect", "builder"]` to `["architect", "pm"]`.
- Ensure `can_gh_write: True` is preserved (used for PM/deploy and PR review flows).

### Layer 2: Tests & Documentation Reconciliations
- Update `tests/test_constants.py` and related test fixtures asserting Claude's roles to expect `["architect", "pm"]`.
- Update `docs/harness-capability-baseline.md` to reflect that Claude's baseline is formally aligned with its PM/architect operational scope.
