---
title: "Tiered Help from the Command Taxonomy"
date: 2026-10-04
series: "Building the OS for Multi-Agent Development"
post: 247
pr: "2020"
issue: "1974"
status: published
author: "synlynk team"
version: "0.25.0-dev"
tags: [posts, taxonomy, help, surface, user-experience]
type: story
---

## The Broader Goal at the End of the Previous PR

PR #2010 (2026-10-04) wired the OpenRouter dispatch gateway — expanding harness capability to
include frontier models beyond the core five. The goalpost at that point was surface polish: the
core orchestration layer was complete, and user-facing commands needed refinement to match the
expanded scope.

## What Changed: Surfacing the Taxonomy to Users

The COMMAND_TAXONOMY (previously internal-only, used for telemetry and validation) became the
source of truth for human-facing command discovery. This PR took that read-only step further by
building a tiered help system directly from taxonomy entries, grouped into four command tiers:
- **Core** (8 commands) — the essential daily set: `init`, `dispatch`, `status`, `jobs`, `decide`, `pr check`, `exec`, `doctor`
- **Workflow** (maturity tier ≤ 2) — intermediate use cases
- **Advanced/Admin** (tier 3 and latent) — operator-level utilities
- **All** (`synlynk help --all`) — complete command catalog

No behavior change to any existing command. The existing `--help` output and top-level help remain
untouched. This is pure read-side surface.

## Technical Implementation

The implementation is minimal — under 60 lines of new taxonomy code plus CLI wiring:

- `entries_for_help(group, include_all=False)` filters taxonomy entries by group
- `format_tiered_help(group, include_all=False)` renders compact, human-readable output with
  trigger phrases from the taxonomy as inline hints
- `synlynk help` command added to the top-level CLI with `group` argument (optional, defaults to
  "core") and `--all` flag
- Early exit in `main()` to handle help before the normal parser boots, avoiding import overhead

Tests confirm all taxonomy groups render correctly and the core tier matches the canonical list.

## Guardrail

Issue #1973 (sibling to #1974) captured baseline advanced-command usage metrics before this shipped.
Post-launch monitoring will compare actual usage (from telemetry) against that baseline — the
guardrail is that advanced-command usage must not drop after this help system ships, confirming
the new surface didn't inadvertently obscure the commands power users relied on.

## What Was Achieved

One surface command now serves as the entry point to the entire command space, removing the need to
consult separate documentation for command discovery. The hierarchy (core → workflow → advanced)
mirrors the maturity model already embedded in COMMAND_TAXONOMY, so it requires zero additional
maintenance — each taxonomy entry's `maturity_tier` automatically slots it into the right tier.

## New Goalpost

The command taxonomy is now the bridge between what the system *can do* (execution capabilities
tracked in `capability_ratings`/`cost_entries`) and what users *can discover* (surface via
tiered help). The next step is expanding that bridge: using trigger phrases and taxonomy hints to
power fuzzy command search, AI-assisted command recommendation, and shell completion scaffolds —
all derived from the same taxonomy source, keeping discovery, routing, and execution consistently
aligned as the feature set grows.

No deploy or migration required. The PR is backward-compatible; all existing commands work exactly
as before.
