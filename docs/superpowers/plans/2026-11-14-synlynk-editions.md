# Synlynk Editions: Core / Opt-in / Hosted Boundary & Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Synlynk Editions classification engine, config surface, doctor verification check, CLI management surface, and comprehensive module inventory for **v0.33.0** (`story-8684a183` under `goal-ecffdaaf`), formalizing the boundaries of Core, Personal, Team, and Enterprise editions.

**Architecture:**
- **Classification Engine (`synlynk/editions.py`)**: Registry-based capability classification by marginal cost bearer (Core, Opt-in, Hosted). Provides ordinal check `check_edition(config, capability_name)` and membership check `check_hosted(config, capability_name)`.
- **Config Surface (`.synlynk/config.json`)**: Additive, soft advisory keys `edition` (default `"personal"`) and `hosted` (default `[]`). Reuses existing config loading patterns without schema migration overhead.
- **Passive Health Check (`synlynk/doctor.py`)**: `_hc_editions_config()` warns on unrecognized edition values or unknown hosted capability keys.
- **CLI Management (`synlynk edition {show,set}`)**: CLI surface in `synlynk/cli.py` and `synlynk/taxonomy.py` allowing operators to inspect and update tier settings with automatic default hosted key preset bundling.
- **Inventory Artifacts (`docs/strategy/editions-inventory.*`)**: Human-readable markdown and machine-readable JSON classifying Synlynk modules against the cost-bearer test.

**Tech Stack:** Python 3.12+, dataclasses, JSON schema validation, pytest, Synlynk CLI & Doctor subsystems.

**Spec:** [`docs/superpowers/specs/2026-11-13-synlynk-editions-boundary-and-opt-in-gating-design.md`](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-11-13-synlynk-editions-boundary-and-opt-in-gating-design.md) (Committed on `main` at `4f32e919`).

---

## Global Constraints

- **Additive & Backwards-Compatible:** Existing installations with absent `edition` or `hosted` keys in `.synlynk/config.json` MUST continue to function identically with zero disruption (defaulting to `"personal"` and `[]`).
- **No False Enforcement:** Soft advisory model only. No artificial license keys, hardware dongles, or DRM checks ahead of Platform Vision Phase 1.
- **Fail-Closed on Typos:** `check_edition` and `check_hosted` must raise `KeyError` on unknown capability names to prevent silent pass bugs.
- **Zero Sunk Cost / Independence:** Zero dependencies on Approach C or Constitution code; pure additive registry code that can be deployed standalone.

---

### Task 1: Classification Engine & Gating Primitives Substrate

**Files:**
- Create: `synlynk/editions.py`
- Test: `tests/test_editions.py`

**Interfaces:**
- `EDITION_ORDER = ("personal", "team", "enterprise")`
- `Capability(name, category, min_edition=None, hosted_key=None, note="")`
- `CAPABILITIES: dict[str, Capability]`
- `DEFAULT_HOSTED_BY_EDITION: dict[str, list[str]]`
- `check_edition(config: dict, capability_name: str) -> tuple[bool, str]`
- `check_hosted(config: dict, capability_name: str) -> tuple[bool, str]`

- [ ] **Step 1: Write failing tests for classification engine**
  Create `tests/test_editions.py` asserting:
  1. `check_edition` returns `(True, "")` for `core` and `opt_in` capabilities regardless of configured edition.
  2. `check_edition` correctly computes ordinal rank for `min_edition`: `personal` < `team` < `enterprise`.
  3. `check_edition` raises `KeyError` when given an unrecognized capability name.
  4. `check_hosted` verifies presence of `hosted_key` in `config.get("hosted", [])`.
  5. `check_hosted` raises `ValueError` if called on a non-hosted capability.
  6. `check_hosted` raises `KeyError` on unrecognized capability name.
  7. Registry structural invariant: every capability with `category == "hosted"` has a non-empty `hosted_key`; every `core` and `opt_in` capability has `min_edition is None`.

- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_editions.py` and confirm failure (`ModuleNotFoundError: No module named 'synlynk.editions'`).

- [ ] **Step 3: Implement `synlynk/editions.py`**
  1. Define `EDITION_ORDER` tuple and `Capability` frozen dataclass.
  2. Seed initial `CAPABILITIES` with the worked examples from spec Section 3 and Section 5:
     - Core: `capability_tracking`, `local_pilot`, `quota_tracking`, `swarm_local`
     - Opt-in: `github_app_auth`, `relay_local`
     - Hosted: `hosted_relay`, `audit_retention`, `sso`, `rbac`, `data_residency`, `swarm_cloud_provisioning`
  3. Define `DEFAULT_HOSTED_BY_EDITION = {"personal": [], "team": ["hosted_relay"], "enterprise": ["hosted_relay", "audit_retention", "sso", "rbac", "data_residency"]}`.
  4. Implement `check_edition()` and `check_hosted()`.

- [ ] **Step 4: Run test and ensure pass**
  Run `pytest tests/test_editions.py` and confirm all tests pass.

- [ ] **Step 5: Commit changes**
  Commit: `feat(editions): implement classification engine and gating primitives`

---

### Task 2: Doctor Health Check & Config Validation

**Files:**
- Modify: `synlynk/doctor.py`
- Test: `tests/test_doctor_editions.py`

**Interfaces:**
- `_hc_editions_config(config: dict = None) -> HealthCheckResult`
- Registered in `HEALTH_CHECKS`

- [ ] **Step 1: Write failing tests for doctor health check**
  Create `tests/test_doctor_editions.py` asserting:
  1. `_hc_editions_config` returns OK when config is empty or missing `edition`/`hosted` (defaults applied).
  2. `_hc_editions_config` returns OK when `edition` is in `EDITION_ORDER` and all `hosted` entries match known `hosted_key`s.
  3. `_hc_editions_config` returns WARNING when `edition` is unrecognized (e.g., `"pro"` or `"ultimate"`).
  4. `_hc_editions_config` returns WARNING when `hosted` contains unknown keys.

- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_doctor_editions.py` and confirm failure.

- [ ] **Step 3: Implement `_hc_editions_config` in `synlynk/doctor.py`**
  1. Import `EDITION_ORDER` and `CAPABILITIES` from `synlynk.editions`.
  2. Read `.synlynk/config.json` via standard loader.
  3. Check `edition` against `EDITION_ORDER`; flag unrecognized tier as WARNING.
  4. Check each entry in `hosted` against known hosted keys from `CAPABILITIES`; flag unrecognized entries as WARNING.
  5. Register check in `HEALTH_CHECKS` list.

- [ ] **Step 4: Run test and ensure pass**
  Run `pytest tests/test_doctor_editions.py` and confirm all tests pass.

- [ ] **Step 5: Commit changes**
  Commit: `feat(doctor): add _hc_editions_config health check for edition and hosted keys`

---

### Task 3: Full Module Inventory & JSON Artifact Generator

**Files:**
- Create: `docs/strategy/editions-inventory.md`
- Create: `docs/strategy/editions-inventory.json`
- Create: `synlynk/tools/generate_editions_inventory.py` (or JIT generator script)
- Test: `tests/test_editions_inventory_schema.py`

**Interfaces:**
- Walk all `synlynk/*.py` modules.
- Emit human-readable markdown breakdown by category.
- Emit structured JSON array matching `Capability` dataclass schema.

- [ ] **Step 1: Write schema validation test**
  Create `tests/test_editions_inventory_schema.py` asserting:
  1. `docs/strategy/editions-inventory.json` exists and is valid JSON.
  2. Every entry matches `{"name": str, "category": "core"|"opt_in"|"hosted", "min_edition": str|null, "hosted_key": str|null, "note": str}`.
  3. All entries in `editions.py:CAPABILITIES` exist in the JSON inventory.

- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_editions_inventory_schema.py` and confirm failure.

- [ ] **Step 3: Generate inventory artifacts**
  1. Categorize modules across Core (~85%), Opt-in (~10%), and Hosted (~5%).
  2. Write `docs/strategy/editions-inventory.json`.
  3. Render `docs/strategy/editions-inventory.md` with table summaries and cost-bearer rationales.
  4. Wire `CAPABILITIES` in `synlynk/editions.py` to ingest or synchronize with `editions-inventory.json`.

- [ ] **Step 4: Run test and ensure pass**
  Run `pytest tests/test_editions_inventory_schema.py` and confirm passes.

- [ ] **Step 5: Commit changes**
  Commit: `docs(editions): generate comprehensive module inventory and schema artifacts`

---

### Task 4: CLI Surface (`synlynk edition {show,set}`)

**Files:**
- Modify: `synlynk/cli.py`
- Modify: `synlynk/taxonomy.py`
- Modify: `docs/reference/commands.md`
- Test: `tests/test_cli_edition.py`

**Interfaces:**
- `synlynk edition show`
- `synlynk edition set <tier>`

- [ ] **Step 1: Write failing CLI tests**
  Create `tests/test_cli_edition.py` asserting:
  1. `synlynk edition show` outputs current edition (defaulting to `personal`) and hosted keys.
  2. `synlynk edition set team` updates `.synlynk/config.json` with `"edition": "team"` and adds `"hosted_relay"`.
  3. `synlynk edition set invalid_tier` exits with code 2 and error message.
  4. Setting an edition preserves existing custom `hosted` keys (additive behavior).

- [ ] **Step 2: Run test to confirm failure**
  Run `pytest tests/test_cli_edition.py` and confirm failure.

- [ ] **Step 3: Implement CLI commands**
  1. Register `edition` subcommand in `synlynk/taxonomy.py` under Tier 1 Management.
  2. Implement subparser and `cmd_edition()` in `synlynk/cli.py`.
  3. Wire config read/write to `.synlynk/config.json`.
  4. Regenerate `docs/reference/commands.md` via `python3 bin/synlynk.py docs --regen` (or taxonomy sync).

- [ ] **Step 4: Run test and ensure pass**
  Run `pytest tests/test_cli_edition.py tests/test_docs_sync.py` and confirm all tests pass.

- [ ] **Step 5: Commit changes**
  Commit: `feat(cli): add synlynk edition show and set subcommands`

---

### Task 5: Integration Verification, Version Bump & Release v0.33.0 Prep

**Files:**
- Modify: `VERSION`
- Modify: `CHANGELOG.md`
- Modify: `project-docs/roadmap.md`

- [ ] **Step 1: Run comprehensive verification**
  Run `pytest tests/test_editions*.py tests/test_cli_edition.py tests/test_doctor_editions*.py tests/test_docs_sync.py` and confirm 100% green.

- [ ] **Step 2: Update version metadata**
  1. Bump `VERSION` to `0.33.0`.
  2. Add `[v0.33.0]` section in `CHANGELOG.md` documenting Track 1 Editions Registry.
  3. Update `project-docs/roadmap.md` marking v0.33.0 Track 1 as implemented.

- [ ] **Step 3: Commit and cut PR**
  Commit changes, push to branch `feat/v0.33.0-editions-registry`, and create PR for cross-harness QA verification.
