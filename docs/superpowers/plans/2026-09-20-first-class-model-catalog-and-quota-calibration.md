# First-Class Model Catalog & Rolling Quota Calibration Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a data-driven, declarative First-Class Model Catalog (`.synlynk/models.json`) and an empirical Rolling Quota Calibration Engine with multi-track support (Google AI Pro Gemini, Claude, GPT OSS) and public fleet utilization advisories.

**Architecture:** Model definitions, pricing rate cards, and dispatch tiers (`fast`, `pro`, `reasoning`) are loaded dynamically from `.synlynk/models.json` with stdlib-only fallback. Multi-track subscription quotas are isolated in `harness_quotas` (`track` column). A calibration loop periodically parses CLI `/usage` reports, correlates delta executed tokens against delta reported percentages, computes exact 5H and 1W capacity ceilings, and surfaces dynamic surge vs off-peak window advisories (`synlynk quota advisory`).

**Tech Stack:** Python 3.10+ (stdlib `json`, `sqlite3`, `dataclasses`, `time`, `re`), Pytest.

**Spec:** [`docs/superpowers/specs/2026-09-20-first-class-model-catalog-and-quota-calibration-design.md`](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-09-20-first-class-model-catalog-and-quota-calibration-design.md)

---

## Global Constraints
- **Zero-Network Stdlib Purity:** Model catalog loading and quota calibration must not require external network dependencies or third-party packages.
- **Strict Authority Boundary:** Model metadata constrains cognitive suitability, but never grants execution authority or shell permissions.
- **Diagram Standard:** All ASCII diagrams ≤ 56 columns wide.
- **Test-Driven Development:** Write failing tests first before implementing each subsystem.

---

### Task 1: First-Class Model Catalog Schema & Declarative Loader (MC-1)

**Files:**
- Create: `.synlynk/models.json`
- Modify: `synlynk/models.py`
- Modify: `synlynk/dispatch.py`
- Create: `tests/test_models_catalog.py`

**Interfaces:**
- Produces: `load_model_catalog(repo_path: Optional[str]) -> dict`, `resolve_catalog_tier(tier: str, harness: str) -> str`

- [ ] **Step 1: Write unit tests for JSON model catalog loading and fallback resolution**
- [ ] **Step 2: Create declarative default `.synlynk/models.json` with 2026 SOTA models and rate cards**
- [ ] **Step 3: Update `synlynk/models.py` to load from `.synlynk/models.json` with builtin fallback**
- [ ] **Step 4: Update `synlynk/dispatch.py` to query model catalog dynamically for tier resolution**
- [ ] **Step 5: Run tests and verify 100% pass**

---

### Task 2: Multi-Track Quota Schema & Dual-Read Cost Engine (MC-2)

**Files:**
- Modify: `synlynk/db.py`
- Modify: `synlynk/costs.py`
- Modify: `synlynk/quota.py`
- Create: `tests/test_multitrack_quota.py`

**Interfaces:**
- Produces: Multi-track `harness_quotas` table with `track` column (`gemini`, `claude_proxy`, `gpt_oss`, `default`)

- [ ] **Step 1: Write unit tests for multi-track quota reads/writes and dual-read cost updates**
- [ ] **Step 2: Add migration for `track` column in `harness_quotas` table in `synlynk/db.py`**
- [ ] **Step 3: Update `synlynk/costs.py` to attribute multi-track subscription costs**
- [ ] **Step 4: Run tests and verify backward compatibility**

---

### Task 3: Rolling `/usage` CLI Calibration Engine (MC-3)

**Files:**
- Modify: `synlynk/quota.py`
- Create: `tests/test_quota_calibration.py`

**Interfaces:**
- Produces: `parse_cli_usage_output(harness: str, text: str) -> dict`, `calibrate_quota_window(...)`

- [ ] **Step 1: Write unit tests for `/usage` parsing across Claude, Antigravity, and Codex CLI outputs**
- [ ] **Step 2: Implement delta mathematical calibration formula correlating tokens to percentage deltas**
- [ ] **Step 3: Implement dynamic runway calculation (hours/days remaining) based on rolling burn rates**
- [ ] **Step 4: Run tests and verify calibration accuracy**

---

### Task 4: Empirical Time-of-Day Dynamic Allocation & Advisory Service (MC-4)

**Files:**
- Create: `synlynk/advisory.py`
- Modify: `synlynk/quota.py`
- Create: `tests/test_advisory.py`

**Interfaces:**
- Produces: `get_utilization_advisory() -> dict`, `detect_offpeak_expanded_windows() -> list`

- [ ] **Step 1: Write unit tests for surge throttle and off-peak expanded capacity detection**
- [ ] **Step 2: Implement `synlynk/advisory.py` computing regional time-block capacity factors**
- [ ] **Step 3: Implement advisory formatter for CLI and public JSON export**
- [ ] **Step 4: Run tests and verify advisory outputs**

---

### Task 5: CLI Integration & Verification Suite (MC-5)

**Files:**
- Modify: `synlynk/cli.py`
- Modify: `synlynk/quota.py`
- Create: `tests/test_quota_cli.py`

**Interfaces:**
- Produces: `synlynk quota advisory`, `synlynk quota calibrate`, `synlynk quota --json`

- [ ] **Step 1: Write CLI integration tests for `synlynk quota advisory` and `synlynk quota calibrate`**
- [ ] **Step 2: Wire CLI subcommands in `synlynk/cli.py`**
- [ ] **Step 3: Run entire test suite across all subsystems and verify 100% pass**
