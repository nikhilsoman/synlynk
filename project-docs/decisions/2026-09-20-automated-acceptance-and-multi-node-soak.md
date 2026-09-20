<!-- generated - source of truth is state.db -->
---
decision_id: dec-c830f41c
topic: "Automated Acceptance and Multi-Node Soak Testing Framework via OrbStack VMs"
date: 2026-09-20
panel: [claude, codex]
status: approved
---

## Topic
Automated Acceptance and Multi-Node Soak Testing Framework via OrbStack VMs

## Panel Inputs

### claude
[model=default; version=2.1.274 (Claude Code)]

**Position: adopt it, but scoped as a tiered, local-first framework. Don't make it a merge gate.**

**Why it's worth doing.** Wave 2 (relay bus, task leases and heartbeats, mesh collision detection, identity) has only been tested in a single process, on one filesystem, with one clock. The failure modes that matter for it are multi-node ones: lease double-claims, heartbeat un-stranding after `kill -9`, partitioned relay peers, and clock skew. Unit tests can't reach these. We have already had one: #1228, where daemon pidfile and github_apps paths are CWD-relative and break across worktrees. Separate VMs with their own `HOME`, state.db and network namespace expose that whole class of bug.

**Why OrbStack VMs specifically.** They boot in seconds. `orb` gives scriptable Linux machines with real `iptables` and `tc netem` for partitions and latency. Snapshots and clones make cheap N-node topologies. Plain OrbStack containers cover roughly 80% of this, so use VMs only where the test needs systemd, a real init or pidfile lifecycle, or kernel-level networking. Everything else should run in containers.

**Risks to manage.**
- **CI portability.** OrbStack is macOS-only and GitHub Actions can't run it. So this can't gate PRs. Run it as a pre-release and nightly local gate, and make it a required checklist item in `synlynk release`. Keep a container-only subset that CI can run.
- **Cost.** A soak that calls real agents burns money. Use stub harnesses that emit deterministic output, and log any real spend via `synlynk cost log`.
- **False greens.** Given #1377 and #202, assertions must check `state.db` invariants directly. Examples are exactly one lease holder per job, no orphaned `running` rows after a node kill, and relay event ordering. They must not read job-status labels.
- **Flakiness.** Adopt the existing rule that 1–2 reruns are fine and a third failure means stop and flag.

**Shape.**
1. **Acceptance tier:** 3 nodes, a scripted scenario, about 5 minutes, deterministic, run before releases.
2. **Soak tier:** opt-in, hours long, with chaos injection (kill, partition, skew), reporting invariant violations.
3. **Harness:** Python stdlib only, matching the project's no-dependency ethos, and driving `orb` via subprocess.

**Process.** The brainstorm-first policy applies. The untracked `project-docs/fleet_soak_test_plan.md` should become the spec input under `docs/superpowers/specs/`. Once the spec is approved, dispatch implementation to Codex (Python and CLI lane) and keep Claude on review.

I recommend approving the acceptance tier now and the soak tier after the acceptance tier has found its first real bugs.

### codex
[model=default; version=codex-cli 0.154.0]

An automated acceptance and multi-node soak-testing framework using OrbStack VMs could materially improve confidence in synlynk’s orchestration, networking, failure recovery, and state-consistency behavior. Multi-node tests would expose issues that unit tests and single-process integration tests miss: clock skew, process restarts, partial connectivity, concurrent writes, leader loss, worktree contention, and recovery after prolonged operation. OrbStack is attractive for developer workflows because it can provide lightweight, repeatable local Linux environments without requiring a full cloud cluster.

The main risk is treating OrbStack as the system boundary rather than as one execution backend. Tests optimized around macOS, Apple Silicon, local filesystem behavior, or OrbStack-specific networking may pass locally while failing in production Linux environments or hosted CI. Long soak tests also introduce resource contention, nondeterministic timing, difficult failure reproduction, and substantial CI cost. VM lifecycle, log collection, artifact retention, test timeouts, and cleanup must be first-class concerns. A framework that only reports “failed” will create more operational noise than confidence.

The strongest design is a layered harness: declarative node/topology definitions, provider-neutral lifecycle and networking interfaces, deterministic fault injection, structured event/assertion capture, and reproducible seeds. Start with a small acceptance suite covering node registration, dispatch, restart, state convergence, and cleanup. Run it on every change only at a short duration; reserve multi-hour or overnight soak runs for scheduled jobs. Use OrbStack as the fast local and macOS validation provider, while retaining at least one Linux-based CI or cloud provider for environmental diversity.

**My recommendation is to approve the framework, but not an OrbStack-only strategy.** Fund a narrow, provider-agnostic first phase with explicit resource budgets and failure-artifact requirements. OrbStack should be the primary developer feedback loop and scheduled soak environment, while production confidence must come from cross-provider runs and a small set of real Linux CI environments.

## Synthesis
## Synthesis

**Where the panel agrees**
- Multi-node testing is worth building. Wave 2 (relay, leases and heartbeats, mesh collision detection, identity) has only been exercised in a single process with one clock and one filesystem. #1228 shows the kind of bug that slips through.
- The framework should be tiered: a short deterministic acceptance tier, and an opt-in long soak tier with fault injection.
- Assertions must check `state.db` invariants directly, such as one lease holder per job, no orphaned `running` rows after a node kill, and relay ordering. They must not read job-status labels (#202, #1377).
- Use stub harnesses, not real agents, and log any real spend with `synlynk cost log`.
- Artifact capture, VM cleanup, timeouts and seeded reproducibility are core requirements, not extras.

**Where they differ, and how I resolve it**
1. **OrbStack-only vs. provider-neutral.** Codex is right that OrbStack is macOS-only and can't be the whole strategy. Claude is right that a full abstraction layer up front is over-engineering. I'll use a thin node-lifecycle interface with exactly two backends: `docker`, which runs in Linux CI, and `orb`, for VMs. The `orb` backend is used only where a test needs systemd, pidfile lifecycle, or kernel-level `iptables` and `tc netem`. This covers Linux diversity without speculative abstraction.
2. **Gate or not.** Claude says never a merge gate. Codex wants a short suite on every change. The container-based smoke subset runs in GitHub Actions, path-triggered on relay, jobs, mesh and identity changes, and is advisory (non-blocking) at first. It becomes a required check only after it has been stable for a few weeks. The OrbStack VM acceptance tier is a local pre-release and nightly gate, and a required item in `synlynk release`.
3. **Flakiness policy.** We keep the existing rule: 1–2 reruns are fine, and a third failure means stop and flag.

**Sequencing**
1. Promote `project-docs/fleet_soak_test_plan.md` into a spec under `docs/superpowers/specs/`. Nikhil approves it before any code, per the brainstorm-first policy.
2. Build the acceptance tier first: 3 nodes, about 5 minutes, covering registration, dispatch, restart, lease convergence, kill and recover, and cleanup.
3. Build the soak tier only after the acceptance tier has found or ruled out its first real bugs. It adds chaos (kill, partition, clock skew), seeded runs and invariant-violation reports.
4. Implementation goes to Codex via `synlynk dispatch` (Python and CLI lane), with Claude reviewing. It uses Python stdlib only, driving `orb` and `docker` via subprocess.

Decision: Approve building a tiered, provider-neutral multi-node acceptance and soak framework, with OrbStack VMs as the primary local backend and Docker containers as the Linux-CI backend. Phase 1 is the acceptance tier only, assertions are made against `state.db` invariants with stub harnesses. The container smoke subset runs as an advisory CI check, the VM tier is a local nightly and pre-release gate wired into `synlynk release`, and the soak tier is deferred until the acceptance tier has proven its value. No code is written until the spec derived from `fleet_soak_test_plan.md` is committed and Nikhil approves it.

## Decision
Decision: Approve building a tiered, provider-neutral multi-node acceptance and soak framework, with OrbStack VMs as the primary local backend and Docker containers as the Linux-CI backend. Phase 1 is the acceptance tier only, assertions are made against `state.db` invariants with stub harnesses. The container smoke subset runs as an advisory CI check, the VM tier is a local nightly and pre-release gate wired into `synlynk release`, and the soak tier is deferred until the acceptance tier has proven its value. No code is written until the spec derived from `fleet_soak_test_plan.md` is committed and Nikhil approves it.

> Signatures: see 2026-09-20-automated-acceptance-and-multi-node-soak.json
