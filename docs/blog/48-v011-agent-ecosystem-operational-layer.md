# v0.11.0 — The Agent Ecosystem Operational Layer

**Date:** 2026-07-05
**Tag:** [v0.11.0](https://github.com/nikhilsoman/synlynk/releases/tag/v0.11.0)
**PRs:** #110, #113–#119

---

**One sentence:** synlynk v0.11.0 is the Agent Ecosystem Operational Layer — every dispatch now carries permissions and recovery paths, your terminal shows a live fleet of agents in real time, and the full workflow discipline is baked into every agent directive file at init.

---

## What v0.11.0 Is

v0.10.0 gave you a usable tool: install with pipx, run the wizard, dispatch agents, watch costs. v0.11.0 turns that tool into a system you can trust to run unsupervised.

Six interrelated milestones shipped:

1. **Modularise-init** — the 11,000-line `__init__.py` split into focused modules. This was the prerequisite that unblocked everything else.
2. **BS-16 Ecosystem Status** — `synlynk status` shows what your agent fleet can actually do: capacity bars, cycle coverage, dispatch mode gates.
3. **TC-2 fix arc** — eliminated the false-positive that was blocking all Agy dispatches from projects with a prior probe run.
4. **BS-13 Live Job Observatory** — `synlynk watch --live` and a new Vizor tab that shows every running agent, in real time, from one screen.
5. **BS-22 Vizor Efficiency** — the Efficiency tab got real data: R/W/T budget bars, a 6×4 cycle capability matrix, per-agent radar hexagons.
6. **BS-12 Agent Autonomy Bridge** — the trust boundary. Permissions, per-project harness config, handoff protocol, a doctor wizard with a Claude escalation escape, and six SOP blocks injected into every directive file.

---

## The Milestones

### Modularise-init

The first thing we did was split `synlynk/__init__.py`. At 11,268 lines, it had become unreadable and unextendable. Five modules extracted: `probe.py`, `sentinel.py`, `upgrade.py`, `dispatch.py`, `_constants.py`. `__init__.py` dropped to ~1,500 lines of CLI surface and orchestration.

This wasn't user-facing. It was the structural unlock that made BS-16 reviewable and BS-12 extensible.

### BS-16: Ecosystem Status + Capacity

```
synlynk status
synlynk status --json
```

The terminal `status` command shows you the state of your agent fleet: which agents are installed, what their harness compliance is, and how much of their R/W/T capacity budget is available. The `--json` flag emits a machine-readable snapshot — this is the data contract Vizor consumes for all live ecosystem data.

Three dispatch modes added: `eco` (respects R/W/T budget gates), `daily-grind` (default, current behaviour), `perf` (no gates, maximum throughput). Three new `_preflight_dispatch()` gates: `CAPACITY_EXCEEDED_INPUT`, `CAPACITY_EXCEEDED_OUTPUT`, `TOOL_PRESSURE`.

New `state.db` tables: `harness_status`, `cycle_capability`. `synlynk probe` now seeds Tier 1 capacity baselines into these tables on first run.

### TC-2 Fix Arc (PRs #114–116)

Three PRs in one day to close a painful false-positive. `_run_tc2` was seeding Agy's `--non-interactive` flag into the failed-flags list on first scan, then blocking every subsequent Agy dispatch in any project that had been probed. The fix: correct per-agent flag baseline maps, scope the validator to flags valid for that agent's CLI, and add the TC-2 preflight gate result to `synlynk logs` output.

### BS-13: Live Job Observatory

```
synlynk watch --live
```

Fullscreen terminal board: every running and recent job, with agent label, status, elapsed time, cost, and output tail. Auto-refreshes every 3s. The Vizor Observatory tab mirrors this in the browser — job fleet table via JS polling, per-agent status badges, cost rollup, and a job output drawer that opens on click.

Before this, observing a multi-agent run meant tail-following four separate log files. Now there's one surface.

### BS-22: Vizor Efficiency Enrichment

The Efficiency tab went from placeholder cards to a genuine capability dashboard:

- **R/W/T budget bars** — each agent card shows Read, Write, Test utilisation as a percentage of TIER1_CAPACITY
- **Cycle × Agent matrix** — 6×4 table (dream/plan/work/ship/maintain/engage × all four agents) with full/partial/none badges
- **Radar hexagons** — 80×80px SVG on each card, 6-axis polygon; at a glance you can see which agent has broad cycle coverage vs. deep specialization in one area

### BS-12: Agent Autonomy Bridge

The largest single PR in v0.11.0. Five scopes:

**Scope A — Permission Grants.** Role entries in `.synlynk/config.json` now carry default permission sets. `synlynk dispatch --grant <perm> --revoke <perm>` overrides per-task. The resolved set translates to `--allowedTools` for Claude, `--approval-policy` for Codex, and a `## Permissions` header section for Agy.

**Scope B — Per-Project Harness Config.** `synlynk configure agent <name>` writes overrides to `.agents/<agent>.json`. `dispatch_agent()` now merges at call time: baseline → project overrides → task grant/revoke. No more editing source to adjust a flag for a specific repo.

**Scope C — Handoff Protocol.** When a job hits STALL_NO_OUTPUT, FLATLINE, or QUOTA_EXHAUSTED, synlynk writes a `HANDOFF_PENDING` sentinel and surfaces it in `synlynk jobs --stalled`. The stalled view shows the recommended next agent. `synlynk jobs handoff <job_id> [--to <agent>]` transfers: appends a handoff note to the context file, increments `handoff_count`, launches a new dispatch with the full context, clears the sentinel.

**Scope D — Doctor Guided Fix Wizard.** `synlynk doctor` no longer just prints failures and exits. After each TC failure it shows a numbered fix menu — specific fix paths for TC-1 through TC-5. The last option, always available: "I'm stuck" — assembles TC results + agent config + last 5 telemetry rows and dispatches Claude to diagnose it conversationally from your terminal.

**Scope E — SOP Codification.** Six SOP blocks injected into all four directive files at `synlynk init` and `synlynk sync` time: PR Review Discipline, Brainstorm-First Policy, Design→Plan→Build Sequence, Capability-Based Task Allocation, Cost Visibility, Repo Hygiene. TC-5 in `synlynk doctor` checks their presence. `synlynk sync --repair-sops` re-injects any that are missing.

---

## Test Count

| Milestone | Tests |
|---|---|
| v0.10.0 (tag) | 616 |
| After modularise-init | 616 (no new tests, refactor only) |
| After BS-16 | 837 |
| After BS-12 | 868 |
| **v0.11.0** | **868** |

---

## What's Next

The operational layer is complete. The next milestone is replacing the `is_placeholder` data paths in Vizor with live BS-16 telemetry (the `harness_status` and `cycle_capability` tables are now populated — Vizor just needs to read them). After that, the D1 daily brief mode in `synlynk launch` for returning users, and the scan delta surfacing in job summaries.

The v1.0.0 GA push begins with the website (BS-5) and the community layer design. Target: September 2026.
