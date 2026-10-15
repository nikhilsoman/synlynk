# Implementation Plan: v0.21.0 Sprint 1 Ephemeral Swarm Infrastructure

**Story:** `story-3aeb1c7a`  
**Spec:** `docs/superpowers/specs/2026-09-12-v0.21.0-swarm-engine-and-context-compaction-design.md`  
**Scope:** Cluster A only

## Tasks

- [ ] Add Docker and Kubernetes Job runner drivers using the existing
  `SwarmRunnerDriver` contract. Configure bounded lifetimes and avoid requiring
  provider SDK dependencies; use the Docker/Kubernetes CLIs or standard APIs.
- [ ] Register `docker` and `k8s` drivers through `RunnerManager` configuration.
- [ ] Expose configured drivers in `synlynk swarm dispatch`, validate batch
  sizes and driver names, and preserve persisted runner state and relay progress.
- [ ] Make `synlynk swarm destroy` operate on individual or all active runners.
- [ ] Add focused driver, manager, and CLI tests with mocked external processes
  or API responses; run the requested pytest files.

## Completion criteria

- Local, Fly, Docker, and Kubernetes drivers share one lifecycle contract.
- A configured Docker/Kubernetes runner can be provisioned, observed, and
  destroyed through the manager/CLI without cloud access in unit tests.
- Invalid batch sizes and unavailable drivers fail clearly, with no partial
  runner records.
