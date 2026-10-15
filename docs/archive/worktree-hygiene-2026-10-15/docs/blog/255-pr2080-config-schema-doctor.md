---
title: "PR #2080 — Doctor checks config.json and policy.json without a JSON Schema library"
date: 2026-10-06
series: "Building the OS for Multi-Agent Development"
post: 255
pr: "#2080"
status: open
author: "synlynk team"
version: "unreleased"
tags: [posts]
type: pr
---

# PR #2080 — Doctor checks config.json and policy.json without a JSON Schema library

## The Broader Goal at the End of the Previous PR

v0.24.0 still needs dispatch, review, and local config to fail in the open
instead of drifting quietly. #2074 made a missing GOVERNS link visible on
stdout and in `sentinel.md` while #1990's hard-fail is still unbuilt. The
three-lens follow-ups plan then split the next config-trust work into four
independent tasks. This PR is Task C, issue #2065.

## Strategic Shifts in This PR (if any)

No strategy change. `pyproject.toml` still declares `dependencies=[]`, so
this does not add `jsonschema`. The checker covers the small known key set
(wrong type, missing required key, bad enum), not `$ref` or a full recursive
schema. That matches the design's P1-1 scope note.

## What This PR Shipped

- `synlynk/config_schema.py` exports `validate()`, `CONFIG_SCHEMA`, and
  `POLICY_SCHEMA`. `validate()` returns a list of human-readable errors.
  Config requires `schema_version` (int), `budget` (object with
  `limit_usd` and `limit_requests`), `harness_billing` (object), and
  `workspace_id` (string). `identity_slug`, `local_fallback`, and
  `local_auto_threshold` stay optional. Policy requires `schema_version`
  and `repo_id`, and checks `capability_policy.mode` against `empirical`
  and `heuristic`.
- `synlynk doctor` registers `_hc_config_schema` and `_hc_policy_schema`
  immediately after `_hc_identity_slug`. A missing file warns. A parse error
  or schema error fails and names the field. A matching file is ok.
- The live repo config (`schema_version`, `budget`, `harness_billing`,
  `workspace_id`) and policy (`mode: empirical`) both pass. A config that
  drops a required top-level field, or sets `budget` to a non-object, fails
  validation, so `synlynk doctor` no longer reports that file as OK.
- Tests: `tests/test_config_schema.py` (5) and
  `tests/test_doctor_config_schema.py` (2).

Plan: `docs/superpowers/plans/2026-10-06-three-lens-followups-plan.md` Task C.
Design: `docs/superpowers/specs/2026-10-06-three-lens-followups-design.md`.

## Brainstorm Visuals Used

None. This follows the committed design and plan.

## What This Achieved on the Path to Autonomy

A bad `config.json` or `policy.json` now shows up in `synlynk doctor` before
dispatch reads the wrong type or an illegal capability mode. The fleet still
has no third-party schema dependency.

## Strategic Note: The Goal at the End of This PR

The other three-lens follow-ups remain independent: sample-size-gated
empirical routing (#2063), durable routing-fallback logs (#2064), and the
cross-adapter conformance suite (#2062). #1990's GOVERNS hard-fail is still
the next enforcement step for the warning #2074 shipped.
