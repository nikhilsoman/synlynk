# Invariant 3: Fail-Closed Capability-Probed Routing Prior to Dispatch — Implementation Plan

**Plan ID:** `plan-20260927-invariant-3-fail-closed-capability-probed-routing`  
**Goal ID:** `goal-5be4eb8b` (*v1.0.0 Dev Preview Mandatory Architectural Invariants*)  
**Epic:** [#1805](https://github.com/nikhilsoman/synlynk/issues/1805)  
**Tracking Story:** `story-9e0b2e71`  
**Tracking Issue:** [#1810](https://github.com/nikhilsoman/synlynk/issues/1810)  
**Spec Reference:** `docs/superpowers/specs/2026-09-27-invariant-3-fail-closed-capability-probed-routing-design.md`  
**Author:** Agy (Gemini)  

---

## Tasks

- [x] **Task 1: Capability Taxonomy & Task Requirement Inferencer (`synlynk/capability_probe.py`)**
  - Define `CAP_SHELL`, `CAP_WORKSPACE_WRITE`, `CAP_GH_WRITE`, `CAP_NET` constants.
  - Implement `infer_task_required_capabilities(task, task_type, requires, requires_gh_write)`.
  - Add `HARNESS_CAPABILITY_PROFILES` with accurate static profiles for all supported harnesses.
  - Implement `evaluate_harness_capabilities(harness, required_capabilities, grants, revokes)`.
  - Implement `probe_harness_runtime_capability(harness, capability)` with memory cache.
  - Create `tests/test_capability_taxonomy.py` and verify with pytest.

- [x] **Task 2: Fail-Closed Capability Router (`synlynk/capability_probe.py`)**
  - Implement `resolve_capable_dispatch_harness(candidate_harness, task, required_capabilities, force_agent, fallback_chain)`.
  - Define `IncompatibleHarnessCapabilityError` and `NoCapableHarnessError`.
  - Support automatic autonomous rerouting across the fallback chain (`codex` -> `agy` -> `claude` -> `grok`).
  - Create `tests/test_fail_closed_routing.py` and `tests/test_autonomous_capability_rerouting.py`.

- [x] **Task 3: Integration into Dispatch Pipeline (`synlynk/dispatch.py`)**
  - Wire `resolve_capable_dispatch_harness` and `infer_task_required_capabilities` into `resolve_dispatch_harness()` and `dispatch_agent()`.
  - Ensure `--force-agent` raises explicit `IncompatibleHarnessCapabilityError` when forced onto an incapable harness.
  - Ensure automatic rerouting logs informative notices and updates job context.
  - Trigger Sentinel alert `CAPABILITY_ROUTING_REJECTED` on fail-closed rejections.
  - Verify with `tests/test_dispatch_capability_routing.py`.

- [x] **Task 4: Autonomous Milestone DAG Capability Filtering (`synlynk/launch_dag.py`)**
  - Update `LaunchDAG` node scheduler to filter harness candidates based on task required capabilities.
  - Update `handle_job_outcome()` failover chain to skip incapable harnesses.
  - Create `tests/test_dag_capability_filtering.py`.

- [ ] **Task 5: End-to-End Regression Verification & Documentation**
  - Run full test suite across the repository (ensure 100% pass across 3,345+ tests).
  - Open PR closing Issue [#1810](https://github.com/nikhilsoman/synlynk/issues/1810).
  - Dispatch non-author review to Codex (`qa` role) and merge.
