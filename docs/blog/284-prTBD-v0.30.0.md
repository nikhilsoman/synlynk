---
title: "v0.30.0 Milestone Retrospective: Fleet Expansion & Agent Studio"
date: 2026-11-10
series: "Building the OS for Multi-Agent Development"
post: 284
pr: "#5192"
version: "0.30.0"
author: "Synlynk Core Team"
status: "published"
tags: ["release", "agent-studio", "local-harness", "openrouter", "governance"]
---

## Overview

Synlynk `v0.30.0` marks the delivery of Horizon 2's core foundation: **Fleet Expansion & Agent Studio**. This milestone unifies agent role management, unlocks zero-token-cost local execution on Apple Silicon, integrates OpenRouter BYOK model aggregation, and narrows Muse execution to strict builder/tester roles under empirical capability governance.

## What Shipped in v0.30.0

### 1. Vizor Agent Studio (Role Management & Lifecycle)
- **10-Role Taxonomy:** Expanded known roles with `secops`, `infra-devops`, and promoted `maintainer` with markdown charter frontmatter schema.
- **Actor Attribution:** Every charter mutation carries `actor_type` (`human`, `agent`, `service`) and `workspace_id`.
- **BAU Charter Editor:** Integrated slide-over drawer editor in Vizor with live `/roles/charter/update` endpoint and Enforced/Guidance badges.
- **Role Deprecation & Revocation:** One-step lifecycle command `synlynk agent deprecate <role>` paired with GitHub App identity revocation `synlynk identity revoke --role`.
- **5-Step FTUE Wizard:** Step-by-step role onboarding wizard in Vizor UI.
- **Unified Capability Registry:** Native hooks catalog, local MCP/skill tooling scoped by `harness_bindings`, and third-party issue filing dedup gate.

### 2. Local Silicon Harness Qualification
- Rebaselined local harness profiles for Apple Silicon MLX and Ollama socket detection.
- Qualified zero-token-cost local execution via `synlynk dispatch local` across Ornith, Qwen2.5-Coder, and Gemma4.

### 3. OpenRouter BYOK Gateway & Muse Adapter
- **BYOK Setup Wizard:** Added `synlynk configure openrouter` (`--key`, `--models`, `--base-url`, `--disable`, `--probe`) writing atomically to `.synlynk/registry.json`.
- **OpenRouter Dispatch:** HTTP `/chat/completions` integration with fallback chain and structured token usage parser.
- **Muse Readiness:** Narrowed capability profiles to deny review and GitHub write pending empirical calibration, with 100% test coverage.

## Verification & Metrics
- **Test Suite:** 5,525 tests collected clean; full 6-job CI matrix passing 100% green.
- **Zero Regressions:** Maintained strict non-author review discipline and governance invariants across all merged PRs (#5190, #5191, #5192).
