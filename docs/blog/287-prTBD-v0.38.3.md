---
title: "v0.38.3 Milestone Retrospective: Harness Parity Phase 3: Live Routing + Manifest Mechanics"
date: 2026-11-20
series: "Building the OS for Multi-Agent Development"
post: 287
pr: "#5395"
version: "0.38.3"
author: "Synlynk Core Team"
status: "published"
tags: ["release", "harness-parity", "live-routing", "manifest-mechanics", "tpm"]
---

## The Broader Goal at the End of the Previous Milestone
With v0.38.2 shipping the Intent Capture primitive, the next critical architectural milestone was delivering **Harness Parity Phase 3: Live Routing & Manifest Mechanics** per ratified architectural decision `dec-8ed62afa`. This phase transitions synlynk from static routing tables to a living, empirical capability and cost-weighted routing engine, while introducing automated harness manifest introspection and preflight version rediscovery.

## What This Milestone Shipped
Milestone v0.38.3 delivers all 14 constituent stories across pull requests #5395, #5392, and #5369:
1. **Dynamic Capability Routing Engine (`LiveQueryRouter`, PR #5395):**
   - Implemented `synlynk/routing.py` querying a 14-day rolling window of empirical capability ratings and cost data from `state.db`.
   - Wired live query fallback ranking directly into dispatch resolution with rotation state migration `m0035_routing_rotation_state`.
2. **Autonomous Harness Manifest Subsystem (PR #5395):**
   - Implemented `synlynk/harness_manifest.py` schema validation and introspection.
   - Added CLI subcommands `synlynk harness onboard` and `synlynk harness probe`.
   - Automated CLI-version-hash preflight rediscovery during dispatch, sentinel site audits, and fail-closed gates for local harness rerouting (`--allow-reroute`).
3. **Attribution Threading & FinOps Hardening (PR #5395):**
   - Added migration `m0036_requested_harness_attribution`, recording both `requested_harness` and executing harness across cost entries and capability ratings.
   - Resolved Muse subscription billing defaults and hardened concurrent SQLite schema mutations against contention.
4. **Goal-Aware Release Packaging (gh:#5372, PR #5392):**
   - Uncapped specification task mining (`mine_specs_and_decisions()`), extracting top-level atomic tasks directly from plans.
   - Goal-aware release packaging clustering up to 12 active constituent stories derived directly from strategic roadmap arcs.

## What This Achieved on the Path to Autonomy
Synlynk now dynamically chooses the best harness for each task type based on continuously updated empirical performance data, self-heals its harness configurations via live manifest probing, and bundles goals into coherent releases without manual intervention.
