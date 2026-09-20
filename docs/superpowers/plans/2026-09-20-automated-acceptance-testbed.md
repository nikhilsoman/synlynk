# Frontier QA Testbed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `synlynk testbed`, an automated, multi-node acceptance and soak testing engine using ephemeral OrbStack VMs and Docker containers, owned by the QA Agent charter and integrated as an attested cryptographic release gate.

**Architecture:** A dual-backend driver abstraction (`OrbDriver` / `DockerDriver`) orchestrates isolated Linux nodes with bridge networking, injects pinned Synlynk versions (via git checkout or local wheel builds), applies headless BYOK synthetic identities (`<@user, role, harness>`), runs distributed acceptance/soak scenarios, validates SQLite `state.db` invariants directly across nodes, and generates signed Ed25519 attestation receipts.

**Tech Stack:** Python 3.10+ (stdlib `subprocess`, `sqlite3`, `pathlib`, `json`, `dataclasses`), OrbStack (`orbctl`), Docker, Pytest.

**Spec:** [`docs/superpowers/specs/2026-09-20-automated-acceptance-testbed-design.md`](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-09-20-automated-acceptance-testbed-design.md)

---

## Global Constraints
- **Zero Host Pollution:** Ephemeral VMs/containers must be cleanly dismantled after execution; no leftover processes or ports on host.
- **Client Stdlib Purity:** No heavy external dependencies added to core client distribution.
- **Diagram Standard:** All ASCII diagrams ≤ 56 columns wide.
- **Test-Driven Development:** Write unit tests first before implementing each module.
- **Attestation Cryptography:** Receipts must carry verifiable signatures and invariant validation metadata.

---

### Task 1: Testbed Driver & Subprocess Execution Layer (TB-1)

**Files:**
- Create: `synlynk/testbed/__init__.py`
- Create: `synlynk/testbed/driver.py`
- Create: `tests/test_testbed_driver.py`

**Interfaces:**
- Produces: `TestbedDriver`, `NodeHandle`, `ExecResult`, `OrbDriver`, `DockerDriver`

- [ ] **Step 1: Write unit tests for `TestbedDriver` protocol, `OrbDriver`, and `DockerDriver` mock executions**
- [ ] **Step 2: Implement `NodeHandle`, `ExecResult`, and `TestbedDriver` base protocol in `synlynk/testbed/driver.py`**
- [ ] **Step 3: Implement `OrbDriver` wrapping `orbctl` with golden image fallback and fault injection (`kill`, `partition`)**
- [ ] **Step 4: Implement `DockerDriver` for CI environments**
- [ ] **Step 5: Run tests and verify 100% pass**

---

### Task 2: Version Resolver & Wheel Packaging Engine (TB-2)

**Files:**
- Create: `synlynk/testbed/installer.py`
- Create: `tests/test_testbed_installer.py`

**Interfaces:**
- Consumes: `TestbedDriver`, `NodeHandle`
- Produces: `TargetResolver`, `install_target_on_node(driver, node, target_ref)`

- [ ] **Step 1: Write unit tests for version resolution (`staging`, `unstable`, `commit:<sha>`, `local`)**
- [ ] **Step 2: Implement `build_local_wheel()` to package workspace into temporary `.whl`**
- [ ] **Step 3: Implement remote installation logic via driver file copy and pip install**
- [ ] **Step 4: Run tests and verify clean resolution**

---

### Task 3: Synthetic Credential Vault & 3-Tier Identity Attribution (TB-3)

**Files:**
- Create: `synlynk/testbed/identities.py`
- Create: `tests/test_testbed_identities.py`

**Interfaces:**
- Consumes: `NodeHandle`
- Produces: `SyntheticIdentity`, `provision_node_identity(driver, node, identity)`

- [ ] **Step 1: Write unit tests for synthetic 3-tier identity injection**
- [ ] **Step 2: Implement `SyntheticIdentity` dataclass and standard identities (`@alice`, `@bob`, `@charlie`)**
- [ ] **Step 3: Implement environment variable export (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) and Git identity configuration**
- [ ] **Step 4: Run tests and verify identity isolation**

---

### Task 4: Multi-Node Acceptance Scenarios & SQLite Invariant Asserter (TB-4)

**Files:**
- Create: `synlynk/testbed/scenarios.py`
- Create: `synlynk/testbed/invariants.py`
- Create: `tests/test_testbed_scenarios.py`

**Interfaces:**
- Consumes: `TestbedDriver`, `TargetResolver`, `SyntheticIdentity`
- Produces: `run_scenario(name, driver, nodes)`, `assert_invariants(driver, nodes)`

- [ ] **Step 1: Write unit tests for invariant assertions (mutual exclusion, zero orphan leases, relay checksums)**
- [ ] **Step 2: Implement `InvariantAsserter` reading remote `state.db` SQLite tables directly**
- [ ] **Step 3: Implement core scenarios: `brownfield_init`, `p2p_mesh`, `task_lease_recovery`**
- [ ] **Step 4: Run tests and verify invariant detection**

---

### Task 5: CLI Integration, QA Living Charter & Release Gate Hook (TB-5)

**Files:**
- Create: `synlynk/testbed/cli.py`
- Modify: `synlynk/cli.py`
- Modify: `synlynk/charters.py`
- Modify: `synlynk/policy.py`
- Create: `tests/test_testbed_cli.py`

**Interfaces:**
- Produces: `synlynk testbed run/matrix/soak/status/clean`, QA attestation receipt generation, release gate verification

- [ ] **Step 1: Write unit tests for `synlynk testbed` CLI commands and QA receipt verification**
- [ ] **Step 2: Implement `synlynk/testbed/cli.py` with full argument parsing and JSON output**
- [ ] **Step 3: Register `TOOL_ROLE_SKILLS["testbed"]` for `qa` in `synlynk/charters.py`**
- [ ] **Step 4: Hook receipt verification into `synlynk/policy.py`**
- [ ] **Step 5: Run complete test suite and verify end-to-end**
