---
title: "PR TBD — GH-Write Fail-Closed: No More Silent Personal Keyring"
date: 2026-08-09
series: "Building the OS for Multi-Agent Development"
post: 109
issue: 569
---

# GH-Write Fail-Closed — No More Silent Personal Keyring

## Broader goal

Epic B (job-truth + GH-write plan): stop shared-identity review/merge and stop pretending env-token stripping blocks `gh`.

## What moved

#569 showed strip-and-warn is false security — `gh` uses host keyring via `HOME`. B0/B1 **fail closed** without a role App token; when a token mints, inject it and isolate `GH_CONFIG_DIR`.

## Shipped

- `--requires-gh-write` + no App → `RuntimeError` with `identity init` instructions
- Token present → `GH_TOKEN`/`GITHUB_TOKEN` + isolated `GH_CONFIG_DIR`
- Escape hatch: `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1` (warned)
- Design: `docs/superpowers/specs/2026-08-09-gh-write-identity-fail-closed-design.md`

## New goalpost

Operators must provision role Apps for real GH-write dispatches. Process routing to Grok/Agy remains until bots are installed; product no longer claims "will fail" while succeeding as the human.
