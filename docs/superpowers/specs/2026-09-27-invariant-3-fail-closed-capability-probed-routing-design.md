# Invariant 3: Fail-Closed Capability-Probed Routing Prior to Dispatch — Design Spec

**Document ID:** `spec-20260927-invariant-3-fail-closed-capability-probed-routing`  
**Goal ID:** `goal-5be4eb8b` (*v1.0.0 Dev Preview Mandatory Architectural Invariants*)  
**Epic:** [#1805](https://github.com/nikhilsoman/synlynk/issues/1805)  
**Tracking Story:** `story-9e0b2e71`  
**Tracking Issue:** [#1810](https://github.com/nikhilsoman/synlynk/issues/1810)  
**Decision Record:** `dec-20260927-round-1` in `project-docs/decisions/2026-09-27-round-1-deep-architectural-review.md`  
**Author:** Agy (Gemini)  
**Status:** Approved  

---

## 1. Thesis & Motivation

In heterogeneous multi-agent fleet execution, agent harnesses run inside differing execution sandboxes with distinct capabilities and constraints:
- **Grok:** Headless dispatch sandbox denies `bash` / shell execution in certain environments, returning exit code 0 despite silent no-ops when tasks demand shell executions or git mutations.
- **Codex:** Confined to `workspace-write` by default and requires explicit network grants (`network_access=True`) for external HTTP / remote GitHub write operations.
- **Agy / Claude:** Full workspace write, shell execution, and network egress capabilities, subject to CLI tool allow-rules.
- **Local (Aider/oMLX):** Air-gapped local model execution without remote GitHub API write authority.

Previously, dispatch routing relied on post-facto failure detection (e.g. failing during execution or discovering zero-diff completions afterwards) or ambient operator memory.

**Invariant 3 enforces:**
$$\text{DispatchAllowed}(\text{Harness}, \text{Task}) \iff \forall c \in \text{RequiredCaps}(\text{Task}),\; \text{HarnessHasCap}(\text{Harness}, c) \land c \notin \text{Revokes}$$

If a candidate harness lacks any required capability for a task:
1. If `--force-agent` is set: **Fail closed immediately** with `IncompatibleHarnessCapabilityError` rather than spending tokens on a doomed execution.
2. If `--force-agent` is not set: **Autonomously reroute** to the highest-ranking authorized harness in the fallback chain that satisfies all required capabilities.
3. If no harness in the fleet satisfies the requirements: **Fail closed immediately** with `NoCapableHarnessError` and trigger a Sentinel alert.

---

## 2. Capability Taxonomy & Inference

### 2.1 Standard Capability Constants
```python
CAP_SHELL = "run:shell"              # Execute shell/bash subprocesses (tests, linters, builds, git)
CAP_WORKSPACE_WRITE = "write:workspace" # Modify/create files in worktree
CAP_GH_WRITE = "write:github"        # Create/review/merge PRs, post issue comments
CAP_NET = "net:external"             # Outbound network HTTP/API access
```

### 2.2 Task Capability Requirement Inference
Given a task description, flags, and options:
- If `--requires` contains explicit capabilities, use them.
- If `--requires-gh-write` is True or task contains GitHub review/PR/issue directives -> requires `write:github` and `run:shell`.
- If task contains code build, test execution (e.g. `pytest`, `npm test`, `cargo build`, `make`), or mutating keywords -> requires `run:shell` and `write:workspace`.
- If `--revokes` contains a capability, it is unconditionally removed from the allowed set.

---

## 3. Architecture & Interfaces

### 3.1 `synlynk/capability_probe.py`
Core module implementing:
1. `HARNESS_CAPABILITY_PROFILES`: Static capability baselines for `claude`, `codex`, `agy`, `grok`, `local`.
2. `infer_task_required_capabilities(task: str, task_type: str = None, requires: list = None, requires_gh_write: bool = False) -> set[str]`
3. `evaluate_harness_capabilities(harness: str, required_capabilities: set[str], grants: list = None, revokes: list = None) -> CapabilityEvaluation`
4. `probe_harness_runtime_capability(harness: str, capability: str) -> bool` (with caching)
5. `resolve_capable_dispatch_harness(...) -> str`

### 3.2 Integration with `dispatch.py`
In `dispatch_agent()` and `resolve_dispatch_harness()`:
- Resolve task requirements *before* creating worktrees or invoking sub-processes.
- Evaluate candidate harness. If missing capabilities, reroute or fail closed.
- Record capability routing decision in telemetry.

### 3.3 Integration with `launch_dag.py`
In `LaunchDAG`:
- When assigning harnesses to DAG nodes, filter out incapable harnesses.
- In `handle_job_outcome()`, ensure secondary failover targets satisfy all required capabilities.

---

## 4. Verification & Test Plan

1. **`tests/test_capability_taxonomy.py`**: Unit tests for capability inference, baseline mappings, grant/revoke overrides.
2. **`tests/test_fail_closed_routing.py`**: Tests verifying fail-closed error raising on forced incompatible dispatches (e.g. `grok` + `run:shell` or `write:github`).
3. **`tests/test_autonomous_capability_rerouting.py`**: Tests verifying autonomous rerouting from incapable harnesses to capable fallbacks.
4. **`tests/test_dag_capability_filtering.py`**: Tests verifying milestone DAG scheduler filters incapable harnesses prior to execution.
5. **Full Regression Suite**: Verify 100% pass across all 3,345+ test cases in the repository.
