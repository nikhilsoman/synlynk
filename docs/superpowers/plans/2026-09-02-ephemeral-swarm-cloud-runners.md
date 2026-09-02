# Implementation Plan: Ephemeral Swarm Cloud Runner Drivers (Fly.io, K8s, Hetzner)

**Issue:** [#1341](https://github.com/nikhilsoman/synlynk/issues/1341)  
**Spec:** `docs/superpowers/specs/2026-09-02-ephemeral-swarm-cloud-runners-design.md`  
**Goal:** `goal-005ea87d` (Ephemeral Swarm Execution Infrastructure)  
**Date:** 2026-09-02  

---

## Tasks

- [ ] **Task 1: Pluggable Runner Interface & Driver Manager (`synlynk/runners/base.py`, `synlynk/runners/manager.py`)**
  - Implement `SwarmRunnerDriver` ABC (`provision`, `stream_telemetry`, `collect_results`, `destroy`).
  - Implement `RunnerManager` registry reading driver configurations from `.synlynk/config.json`.
  - Add SQLite schema migrations in `synlynk/db.py` for `swarm_runners`.
  - Add unit tests in `tests/test_runners.py`.

- [ ] **Task 2: Fly.io Machines v2 & Local Drivers (`synlynk/runners/fly.py`, `synlynk/runners/local.py`)**
  - Implement `FlyRunnerDriver` communicating with Fly.io Machines REST API with auto-destruct watchdogs and log streaming.
  - Implement `LocalRunnerDriver` for local test isolation and development.
  - Add unit tests in `tests/test_runners.py`.

- [ ] **Task 3: Swarm Fan-Out CLI & Relay Integration**
  - Register CLI commands in `synlynk/cli.py` and `synlynk/taxonomy.py`:
    - `synlynk swarm dispatch [--driver fly|k8s|local] [--batch-size N]`
    - `synlynk swarm status`
    - `synlynk swarm destroy [--all]`
  - Stream remote runner receipts and progress events into `synlynk relay` and `synlynk watch`.

- [ ] **Task 4: Documentation, Blog Post, and Full Suite Verification**
  - Author blog post `docs/blog/168-pr1351-ephemeral-swarm-cloud-runners.md` and index in `docs/blog/README.md`.
  - Update `project-docs/memory.md` and devlogs. Ensure all pytest tests pass.
