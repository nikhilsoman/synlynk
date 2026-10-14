---
title: "The model catalog refreshes itself every 24 hours"
date: 2026-10-14
series: "Building the OS for Multi-Agent Development"
post: 270
pr: 2297
status: open
author: "synlynk team"
version: "0.25.0"
tags: [posts]
type: pr
---
# The model catalog refreshes itself every 24 hours

The previous goalpost, after dispatch started reading `harness_models`, was a catalog that could go stale. Sub-task 1 stored `discovered_at`. Sub-task 2 taught `run_model_catalog_discovery()` to fill those rows from live probes, config files, and the curated fallback. Sub-task 4 made `resolve_tier_model` and `dispatch --model` trust `status='active'` rows. Nothing re-ran discovery unless someone typed `synlynk models discover`.

## What changed

`is_model_catalog_stale(conn, threshold_hours=24)` sits next to `is_probe_stale` and `is_smoke_test_stale`. It reads `MAX(discovered_at)` from `harness_models`. An empty table, a missing table, or a timestamp older than 24 hours is due. A row written 23 hours 59 minutes ago is not. The parser accepts both the `Z` form used by the rest of the watch and the offset form `upsert_harness_model()` actually writes, and it treats both as UTC.

`maybe_trigger_staleness_checks()` still runs the free probe and the opt-in smoke test as one or the other. Catalog discovery is a separate step in that same sequence. It calls `run_model_catalog_discovery()` and commits, so the daemon tick and a short-lived CLI thread both leave the new `discovered_at` on disk. CLI startup still reaches the check only through `spawn_staleness_check_thread()`. The daemon tick still calls `maybe_trigger_staleness_checks()` directly. A process-level in-flight flag makes a second overlapping call return without starting another discovery pass. After a successful pass, the fresh `discovered_at` keeps the window closed for the next 24 hours.

Probe and smoke behavior is unchanged: a stale probe still does not also launch the paid smoke test.

## Goalpost

Discovery now rewrites `state.db` on the same 24-hour cadence the capability watch already uses, from both the daemon and CLI startup. The remaining step for v0.25.1 is the release cut once this refresh is on main with the schema, the discovery pass, and live dispatch resolution.
