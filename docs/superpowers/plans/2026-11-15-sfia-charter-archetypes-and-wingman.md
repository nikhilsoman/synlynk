# SFIA Charter Archetypes, Autonomous Coordination & Wingman Gateway Implementation Plan

**Date:** 2026-11-15  
**Author:** Agy (Home Conductor)  
**Spec Reference:** `docs/superpowers/specs/2026-11-15-sfia-charter-archetypes-and-wingman-design.md`  
**Master Tracking Reference:** Issue #5272 (Phase 1)  
**Governing Goals:** `goal-a222b393` (Agent Charter Framework), `goal-658aa384` (Agent Studio)  
**Target Release:** `v0.37.0` / Phase 1 Sweep

---

## 1. Goal & Architectural Overview

This plan implements Phase 1 of the Autonomous Operations & Release Lifecycle Sweep by:
1. Extending `synlynk/charter_schema.py` to support the 7th canonical archetype `chief-of-staff` in `VALID_ARCHETYPES`.
2. Adding machine-enforceable validation for `sfia_mapping`, `boundaries`, `evidence_contracts`, and `lifecycle_state_machine`.
3. Bundling the core SFIA skill taxonomy reference in `synlynk/sfia_taxonomy.json` (`PGMG`, `PROD`, `ARCH`, `PROG`, `TEST`, `ITOP`, `BAPM`).
4. Formalizing `.synlynk/charters/tpm.json` under the `orchestrator` archetype with SFIA PGMG Level 5 and the 7-stage autonomous milestone state machine.
5. Authoring the canonical Personal Edition default role `.synlynk/charters/wingman.json` under the `chief-of-staff` archetype with SFIA Level 2/3 composite skills and the Agent Studio graduation gate.
6. Establishing comprehensive TDD verification tests in `tests/test_charter_schema_archetypes.py` and `tests/test_wingman_charter.py`.

---

## 2. Tasks & Breakdown

### Task 1: Schema Extension for Archetypes & SFIA (`synlynk/charter_schema.py`)
- Add `"chief-of-staff"` to `VALID_ARCHETYPES`.
- Support optional frontmatter keys: `sfia_mapping`, `boundaries`, `evidence_contracts`, `lifecycle_state_machine`.
- For `chief-of-staff`, validate composite SFIA mapping structure (`composite_skills` list with skill, level, and role_slice).
- For specialist archetypes, validate single primary SFIA skill code (`sfia_code`, `sfia_level`).
- Validate that `boundaries` is a list of negative invariant constraints ("Never ...").

### Task 2: SFIA Taxonomy Bundle (`synlynk/sfia_taxonomy.json`)
- Bundle standard SFIA skills:
  - `PGMG`: Program Management (Level 4-6)
  - `PROD`: Product Management (Level 5-6)
  - `ARCH`: Solution Architecture (Level 5-6)
  - `PROG`: Software Development (Level 2-4)
  - `TEST`: Testing (Level 2-4)
  - `ITOP`: IT Infrastructure / Operations (Level 2-4)
  - `BAPM`: Business Analysis (Level 2-3)
- Export lookup helper in `synlynk/charters.py`: `get_sfia_skill(code: str) -> Optional[dict]`.

### Task 3: Formalize TPM Orchestrator Charter (`.synlynk/charters/tpm.json`)
- Update `tpm.json` frontmatter:
  - `primary_archetype: "orchestrator"`
  - `sfia_mapping: { sfia_code: "PGMG", sfia_level: 5, autonomy_level: "L2_GATED" }`
  - `boundaries`: Invariant rules (Never write code, never edit schemas directly, never merge own PRs).
  - `lifecycle_state_machine`: 7-stage closed loop (Intake & Mining -> Ambiguity Gate -> Package Proposal -> Human Gate -> Role Dispatch -> Cross-Harness Review -> Post-Merge Ceremony & Housekeeping).

### Task 4: Author Wingman Chief-of-Staff Charter (`.synlynk/charters/wingman.json`)
- Author `wingman.json`:
  - `primary_archetype: "chief-of-staff"`
  - `edition_tier: "personal_default"`
  - `sfia_mapping`: Composite skills across `BAPM` (Level 2), `PROG` (Level 3), `TEST` (Level 2), `ITOP` (Level 2).
  - `boundaries`: Never execute un-fenced Tier-3 changes unilaterally; never relax constitutional invariants (Law 0-3, GOVERNS).
  - `graduation_gate`: Explicit advice trigger to graduate to Agent Studio when complexity exceeds Tier 2.

### Task 5: Comprehensive Verification Tests
- Create `tests/test_charter_schema_archetypes.py`:
  - Test valid `chief-of-staff` and specialist archetypes.
  - Test validation failure when `boundaries` is missing or invalid.
  - Test SFIA mapping parsing and taxonomy validation.
- Create `tests/test_wingman_charter.py`:
  - Verify `.synlynk/charters/wingman.json` parses and passes constitutional schema validation.
  - Verify composite skill attributes and graduation gate rules.

---

## 3. Verification Commands
- `python3 -m pytest tests/test_charter_schema_archetypes.py tests/test_wingman_charter.py -v`
- `python3 bin/synlynk.py pr check`
