# Generalized Domain Framework & Tri-Graph Architecture (Domain Pack v2.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 1 & Phase 2 of Domain Pack Framework v2.0 and the Tri-Graph Architecture (`.synlynk/domaingraph.json`), establishing stack fingerprinting, typed schema models, reference packs (Mobile/Android & Software Generic), and sub-1.5k prompt context injection for `goal-4459c851` under roadmap arc `v0.40.0`.

**Architecture:** A typed schema metamodel (`synlynk/domain_pack_schema.py`) defines the `Industry -> Domain -> Function -> Workflow -> Task -> Role | Domain -> Stack -> Tools + Competencies` hierarchy. The scanner (`synlynk/scan.py` & `synlynk/repo_classifier.py`) is extended to detect mobile/cloud manifest signatures. A pack loader (`synlynk/domain_pack_loader.py`) validates and caches JSON packs. The Tri-Graph compiler (`synlynk/domaingraph.py`) computes bidirectional cross-indexes (`code_to_domain`, `doc_to_domain`, `domain_to_code`, `domain_to_doc`) persisted to `.synlynk/domaingraph.json` with lazy mtime freshness checking. Finally, `synlynk/pack.py` queries `domaingraph.json` to inject a surgical, strictly capped (≤1,500 tokens) prompt prior on dispatch.

**Tech Stack:** Python 3 stdlib only (`json`, `dataclasses`, `pathlib`, `typing`, `hashlib`), `pytest` for TDD testing. Zero new external dependencies.

---

## File Structure

| Action | File | Responsibility |
|---|---|---|
| **Create** | `synlynk/domain_pack_schema.py` | Typed dataclass schema definitions (`DomainPackV2`, `StackDefinition`, `TaskDefinition`, `CompetencyDefinition`) with validation |
| **Create** | `tests/test_domain_pack_schema.py` | Unit tests for schema validation, required fields, and token size boundaries |
| **Modify** | `synlynk/scan.py` | Extend manifest scanner to detect `build.gradle.kts`, `Package.swift`, `Podfile`, `Cargo.toml`, `fly.toml`, etc. |
| **Modify** | `synlynk/repo_classifier.py` | Map detected manifest signatures to candidate domain pack IDs |
| **Create** | `tests/test_domain_pack_fingerprint.py` | Test manifest detection across multi-language projects |
| **Create** | `synlynk/packs/mobile_applications.json` | Reference Android/Kotlin & iOS/Swift domain pack v2.0 |
| **Create** | `synlynk/packs/software_generic.json` | Baseline SWE pack porting existing heuristics to serve as regression oracle |
| **Create** | `synlynk/domain_pack_loader.py` | Sideloading, caching, and validation of local/global domain packs |
| **Create** | `tests/test_domain_pack_loader.py` | Tests for pack loading, caching in `.synlynk/packs/`, and fallbacks |
| **Create** | `synlynk/domaingraph.py` | Tri-Graph compiler generating `.synlynk/domaingraph.json` with bidirectional reverse indexes |
| **Create** | `tests/test_domaingraph.py` | Tests for cross-index queries (`code_to_domain`, `domain_to_code`, `domain_to_doc`) and lazy mtime freshness |
| **Modify** | `synlynk/pack.py` | Extract active Task slice and inject sub-1.5k stack prior into dispatch context |
| **Create** | `tests/test_pack_domain_slice.py` | Characterization tests verifying injected prompt token ceiling (≤1,500 tokens) |
| **Modify** | `synlynk/cli.py` & `synlynk/taxonomy.py` | Add `domain` CLI verb surface (`synlynk domain list`, `synlynk domain inspect`) |
| **Create** | `tests/test_cli_domain.py` | Subprocess smoke tests for `synlynk domain` CLI |

---

## Phase 1: Metamodel Schema & Fingerprinting Core

### Task 1: Domain Pack v2.0 Typed Dataclass Schema & Validator

**Files:**
- Create: `synlynk/domain_pack_schema.py`
- Create: `tests/test_domain_pack_schema.py`

- [ ] **Step 1: Write failing tests for DomainPackV2 schema**
  - Verify serialization and deserialization of `DomainPackV2` JSON dicts.
  - Verify validation errors when required fields (`industry`, `domain`, `version`, `stacks`, `functions`) are missing or malformed.
  - Verify enforcement of `schema_version == "2.0"`.

- [ ] **Step 2: Implement `synlynk/domain_pack_schema.py`**
  - Define `TaskDefinition`, `WorkflowDefinition`, `FunctionDefinition`, `CompetencyDefinition`, `StackDefinition`, and `DomainPackV2`.
  - Implement `validate_pack_dict(data: dict) -> DomainPackV2`.
  - Implement helper `estimate_pack_tokens(pack: DomainPackV2) -> int`.

- [ ] **Step 3: Run pytest to verify Task 1**
  - Command: `python3 -m pytest tests/test_domain_pack_schema.py`

---

### Task 2: Stack Fingerprint Scanning Extensions

**Files:**
- Modify: `synlynk/scan.py`
- Modify: `synlynk/repo_classifier.py`
- Create: `tests/test_domain_pack_fingerprint.py`

- [ ] **Step 1: Write failing tests for mobile and cloud manifest detection**
  - Test identification of Android projects via `build.gradle.kts` / `settings.gradle.kts` / `libs.versions.toml`.
  - Test identification of iOS projects via `Package.swift` / `Podfile` / `*.xcodeproj`.
  - Test identification of Cloud/Infra projects via `fly.toml` / `main.tf` / `helmfile.yaml`.

- [ ] **Step 2: Update `synlynk/scan.py` and `synlynk/repo_classifier.py`**
  - Add `_EXTENDED_MANIFEST_SIGNATURES` mapping manifest files to technical stack IDs.
  - Update `scan_project_signatures(repo_path)` to return matching stack markers without altering existing Python/JS detection.

- [ ] **Step 3: Run pytest to verify Task 2**
  - Command: `python3 -m pytest tests/test_domain_pack_fingerprint.py`

---

### Task 3: Reference Domain Pack Authoring & Loader

**Files:**
- Create: `synlynk/packs/mobile_applications.json`
- Create: `synlynk/domain_pack_loader.py`
- Create: `tests/test_domain_pack_loader.py`

- [ ] **Step 1: Author reference `mobile_applications.json`**
  - Include `client_engineering` function with `feature_screen_delivery` workflow.
  - Include `android_kotlin` stack with Compose state hoisting competencies and anti-patterns.
  - Bind `./gradlew test` and `./gradlew connectedAndroidTest` to `qa` verification.

- [ ] **Step 2: Implement `synlynk/domain_pack_loader.py`**
  - `load_builtin_pack(domain_id: str) -> Optional[DomainPackV2]`
  - `load_workspace_pack(workspace_root: str) -> Optional[DomainPackV2]`
  - Resolution precedence: Workspace override (`.synlynk/packs/`) -> Cached pack (`~/.synlynk/cache/packs/`) -> Built-in pack.

- [ ] **Step 3: Run pytest to verify Task 3**
  - Command: `python3 -m pytest tests/test_domain_pack_loader.py`

---

### Task 4: Port Existing SWE Heuristics as Pack #1 (Regression Oracle)

**Files:**
- Create: `synlynk/packs/software_generic.json`
- Create: `tests/test_domain_pack_swe_oracle.py`

- [ ] **Step 1: Author `synlynk/packs/software_generic.json`**
  - Port existing Synlynk software lifecycle heuristics (`cli-plumbing`, `refactor`, `test`, `implement`) into standard Domain Pack v2.0 format.

- [ ] **Step 2: Write characterization tests**
  - Verify that `software_generic.json` validates under `DomainPackV2` and produces identical toolbindings to legacy `domain_packs.py`.

- [ ] **Step 3: Run pytest to verify Task 4**
  - Command: `python3 -m pytest tests/test_domain_pack_swe_oracle.py`

---

## Phase 2: Tri-Graph Compiler & Prompt Packager

### Task 5: Tri-Graph Compilation & Cross-Indexing (`domaingraph.py`)

**Files:**
- Create: `synlynk/domaingraph.py`
- Create: `tests/test_domaingraph.py`

- [ ] **Step 1: Write failing tests for Tri-Graph compilation**
  - Verify generation of `.synlynk/domaingraph.json` containing `code_to_domain_index`, `doc_to_domain_index`, `domain_to_code_index`, and `domain_to_doc_index`.
  - Verify lazy mtime staleness check (KD4): only recompile if manifest or pack file mtime changed.

- [ ] **Step 2: Implement `synlynk/domaingraph.py`**
  - `compile_domain_graph(workspace_root: str, pack: DomainPackV2) -> dict`
  - `query_code_domain(graph: dict, file_path: str) -> Optional[dict]`
  - `query_domain_tools(graph: dict, task_id: str) -> List[str]`

- [ ] **Step 3: Run pytest to verify Task 5**
  - Command: `python3 -m pytest tests/test_domaingraph.py`

---

### Task 6: Prompt Sub-Slice Injection with Hard Token Ceiling (≤1,500 Tokens)

**Files:**
- Modify: `synlynk/pack.py`
- Create: `tests/test_pack_domain_slice.py`

- [ ] **Step 1: Write characterization tests for prompt context extraction**
  - Assert that extracted domain slice for a given task never exceeds 1,500 tokens (KD6).
  - Verify that injected content includes task guidance, recommended tools, competencies, and anti-patterns.

- [ ] **Step 2: Update `synlynk/pack.py`**
  - Hook `extract_domain_context_slice(domaingraph, task_id, story_title)` into prompt assembly.
  - Fail-safe fallback: if no domain graph exists or query misses, return empty string with zero disruption.

- [ ] **Step 3: Run pytest to verify Task 6**
  - Command: `python3 -m pytest tests/test_pack_domain_slice.py`

---

### Task 7: CLI Query Commands (`synlynk domain`)

**Files:**
- Modify: `synlynk/cli.py`
- Modify: `synlynk/taxonomy.py`
- Create: `tests/test_cli_domain.py`

- [ ] **Step 1: Register `domain` in `COMMAND_TAXONOMY`**
  - Tier: Standard (`COMMAND_TAXONOMY["domain"] = {"tier": "standard", ...}`).

- [ ] **Step 2: Implement CLI dispatch commands in `cli.py`**
  - `synlynk domain list`: list active and available packs.
  - `synlynk domain inspect <domain_id>`: display functions, workflows, and stacks.

- [ ] **Step 3: Run pytest to verify Task 7**
  - Command: `python3 -m pytest tests/test_cli_domain.py`

---

## Phase 3: Empirical Release Gate & Verification

### Task 8: Controlled A/B Evaluation Suite (With vs. Without Pack)

**Files:**
- Create: `tests/test_domain_pack_ab_benchmark.py`

- [ ] **Step 1: Author benchmark test harness**
  - Run 5 simulated dispatches with domain pack injection and 5 without.
  - Verify that with-pack dispatches produce zero anti-pattern violations and correct test runner flags.
  - Record metric assertions for `pr_review_cycles` and `total_cost_usd`.

- [ ] **Step 2: Execute benchmark and confirm release gate**

---

### Task 9: Atomic Roadmap Arc Placement (`v0.40.0`)

- [ ] **Step 1: Execute `synlynk roadmap add`**
  - Command: `python3 bin/synlynk.py roadmap add --version v0.40.0 --title "Domain-Graph Engine & Tri-Graph Architecture" --status in_progress --phase-title "Phase 1 - Tri-Graph Core & Sideloading" --goal-id goal-4459c851 --priority 0`
- [ ] **Step 2: Run `synlynk roadmap check` to verify zero drift**
