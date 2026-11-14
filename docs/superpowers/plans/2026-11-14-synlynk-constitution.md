# Synlynk Constitution & Charter Governance Implementation Plan (v0.34.0)

**Date:** 2026-11-14  
**Author:** Agy (Home Conductor)  
**Spec Reference:** `docs/superpowers/specs/2026-11-13-synlynk-constitution-charter-governance-design.md`  
**Master Roadmap Reference:** Issue #5247 (Phase 1 / Track 2)  
**Target Release:** `v0.34.0`

---

## 1. Goal & Architectural Overview

This plan operationalizes the Synlynk Constitution design spec by:
1. Promoting Asimov Laws 0–3 and the Intent-Based Engineering invariant into canonical code-level data structures and API queries (`synlynk/constitution.py`).
2. Generalizing the high-stakes session bearings block (`synlynk/bearings.py`) sourced from constitutional laws.
3. Implementing the constitutional citation drift-gate (`check_constitution_gate`) supporting `observe` and `enforce` modes via `.synlynk/policy.json`.
4. Extending Sentinel alerts and RCA schema definitions to record `constitution_law` citations on incidents.
5. Updating docs, test suites, and releasing `v0.34.0`.

---

## 2. Tasks & Breakdown

### Task 1: Canonical Constitution Laws Module (`synlynk/constitution.py`)
- Define `ConstitutionLaw` dataclass (`id`, `number`, `name`, `summary`, `tier`, `enforcement_mechanism`).
- Instantiate canonical registry `CONSTITUTION_LAWS`:
  - `law-0`: Secrets & System Integrity (Tier 3 - Injected / pattern check)
  - `law-1`: Human Sovereignty & App Identity (Tier 3 - Injected / token attribution)
  - `law-2`: Evidence Over Assertions (Tier 3 - Injected / direct verification)
  - `law-3`: Metered Self-Preservation (Tier 2 - Cited / budget circuit breaker)
  - `intent-invariant`: Intent-Based Engineering (Tier 2 - Cited / GOVERNS goal linkage)
- Provide lookup and validation functions:
  - `get_law(law_id: str) -> Optional[ConstitutionLaw]`
  - `list_laws() -> List[ConstitutionLaw]`
  - `validate_citation_tag(tag: str) -> bool`
- **Tests:** `tests/test_constitution.py` (validate registry invariants, lookup, schema).

### Task 2: Bearings Block Generator (`synlynk/bearings.py`)
- Create `generate_bearings_block()` synthesizing Tier 3 laws into the standard session card:
  - Law 0 / Secrets protection
  - Law 1 / Human Sovereignty & App Identity attribution (`dispatch --as-agent <role>`)
  - Law 2 / Evidence Over Assertions (Direct evidence, never self-reported assertions)
  - Operational mechanics: `tpm wake`/`tpm sweep`, PR review discipline.
- Integrate bearings injection helper for context compilers.
- **Tests:** `tests/test_bearings.py` (verify deterministic text, formatting, and constitutional law coverage).

### Task 3: Citation Tagging & Drift Gate (`synlynk/constitution_gate.py`)
- Implement `check_constitution_gate(repo_path, policy)`:
  - Scans touched instruction files (`CLAUDE.md`, `GEMINI.md`, `AI_INSTRUCTIONS.md`) and role charters for `<!-- constitution: <law-id> -->` tags.
  - Detects orphaned clauses (instructions missing constitution citations).
  - Detects orphaned laws (laws with zero citations across the instruction set).
  - Reads `constitution_authority.require_citation_mode` from `.synlynk/policy.json` (`observe` vs `enforce`).
  - Returns structured `(passed, warnings, errors)`.
- **Tests:** `tests/test_constitution_gate.py` (test observe/enforce modes, detection of orphaned laws and clauses).

### Task 4: Sentinel & RCA Schema Integration
- Extend Sentinel alert parsing and formatting in `synlynk/sentinel.py` to record `constitution_law: <id>`.
- Update RCA document validation to check for `constitution_law` annotation in root-cause sections.
- **Tests:** `tests/test_constitution_sentinel_rca.py`.

### Task 5: Version Bump, Documentation & Quality Gate
- Bump `VERSION` to `0.34.0`.
- Update `CHANGELOG.md` with `[v0.34.0]` release notes.
- Update `README.md` version badge and release summary.
- Run full pytest verification suite.
- Open PR, dispatch QA review, and merge.

---

## 3. Verification Commands
- `pytest tests/test_constitution.py tests/test_bearings.py tests/test_constitution_gate.py tests/test_constitution_sentinel_rca.py -v`
- `python3 bin/synlynk.py release --check-docs --pr-mode`
- Full test matrix in CI.
