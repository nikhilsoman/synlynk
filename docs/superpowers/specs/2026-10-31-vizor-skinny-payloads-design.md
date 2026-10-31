---
title: "Vizor view-scoped payloads"
date: 2026-10-31
status: Accepted
author: "Grok (Home Conductor)"
goal: "goal-e3840370"
epic: "#2458"
milestone: "v0.26.7"
arc: "platform"
issue: "#2671"
---

# Vizor view-scoped payloads

## Status

Accepted 2026-10-31. Nikhil signed the first cut in the home session after the #2671 / Jantt evaluation: stop embedding `workspace_views.logical` in Gantt, Tube, Efficiency, Effort, and Logical HTML. This cut does not bump VERSION, does not edit CHANGELOG, and does not vendor Jantt.

## Problem

`generate_viz_data()` builds one dict that includes the logical graph (~17.6 MB: thousands of nodes and edges, nested `attrs_json`). `_write_cache` hands that dict to every generator. Gantt, Effort, Efficiency, and Tube serialize the whole dict into `window.VIZOR_DATA`. Logical serializes every node and edge, then paints 12 HLD cards per tier and 16 LLD cards.

Live cache `~/.synlynk/vizor-cache/synlynk/` (2026-10-30, reconfirmed 2026-10-31): Gantt / Tube / Efficiency / Effort / Logical are 18–19 MB HTML each. Overview is 28 KB. Board is 12 KB. HTTP 200 is fast. Chrome stalls on JSON parse.

Gantt JS only reads `releases` / `dreams` / `goals` / `spec_verifications` / `product_id` / `notes` (~80 KB). Effort uses `costs` and `dreams` (~39 KB). Efficiency uses `agents`, `telemetry`, `ecosystem` (~426 KB). Tube already has `ARCHITECT_NODES` / `ARCHITECT_EDGES`.

## Decision

1. Each generator embeds only the keys it reads. Helper `view_embed(data, keys)` copies those keys. Gantt, Effort, Efficiency, and Tube never serialize `workspace_views`.
2. Logical first paint is a projection: HLD cards stay server-rendered from the full graph; `LOGICAL_NODES` is at most 16 slim records (`id`, `label`, `kind`); `LOGICAL_EDGES` is empty. Detail-on-expand JSON is a later cut.
3. A unit test builds a fixture with a large logical graph and asserts those five HTML documents stay small and do not contain a sentinel that only exists on the dumped graph.

Board already fetches `api/board`. Leave that pattern in place. Do not ship one shared `data.json`.

## Jantt constraint (v0.26.7)

Superseded by `dec-144d1e68` / the v0.26.7 edition spec: **Jantt is a benchmark only**. Synlynk Gantt (GOVERNS stage grid) is the canvas of record. Do not vendor `@jantt/*` in v0.26.7. This payload cut remains the substrate: any future calendar projection, if it ever exists, consumes a GOVERNS-only document and never `workspace_views.logical`.

## Out of scope

gzip / brotli, canvas/vis-network for Logical, per-view JSON files on disk, hosted Vizor, VERSION, the release tag, sentinel HUD CTAs (#2672), the workspace-refresh `TypeError`.
