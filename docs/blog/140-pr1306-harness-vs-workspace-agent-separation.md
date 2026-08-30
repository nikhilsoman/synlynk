---
title: "PR #1306 — Standardizing Harness vs. Workspace Agent Separation Across CLI Flags, Configs, and Docs"
date: 2026-08-30
series: "Building the OS for Multi-Agent Development"
post: 140
pr: "#1306"
issue: "#1255"
merged: 2026-08-30
---

# PR #1306 — Standardizing Harness vs. Workspace Agent Separation Across CLI Flags, Configs, and Docs

## The Core Distinction

In multi-agent architectures, confusing an **actor** with their **tooling** creates subtle yet pervasive systemic bugs:
* **Workspace Agents** are the persistent org-chart roles (\`pm\`, \`architect\`, \`tpm\`, \`dev\`, \`designer\`, \`qa\`, \`marketing\`, \`synlynk-bot\`). They hold charters, durability policies, lifecycle accountability, and distinct GitHub App bot identities (\`synlynk-<repo>-<role>[bot]\`). They are **who** owns the work.
* **Harnesses** are the swappable execution backends (\`claude\`, \`codex\`, \`grok\`, \`agy\`, \`local\`). They provide model access, process sandboxing, and token cost tracking. They are **how** compute and turn executions take place.

PR #1306 resolves issue #1255, completing the transition initiated by #1202 to eliminate conflation across CLI surfaces, configuration directories, and documentation.

---

## What Changed

### 1. Documentation & Instruction Cleanliness (Phase 1)
* **Roadmap Precision:** Corrected \`docs/strategy/2026-08-15-two-imperatives-roadmap.md\` line 7 to clearly state that autonomous workspace agents (\`dev\`, \`qa\`, \`designer\`, \`marketing\`) execute via autonomous harnesses (\`codex\`, \`grok\`, \`agy\`).
* **Vendor Instruction Preambles:** Updated \`GEMINI.md\`, \`CLAUDE.md\`, and \`GROK.md\` preambles to explicitly state \`- **Harness:** <Name>\`.
* **Design & Plan Specs:** Committed formal Design Spec (\`docs/superpowers/specs/2026-08-30-harness-agent-separation-design.md\`) and Implementation Plan (\`docs/superpowers/plans/2026-08-30-harness-agent-separation.md\`).

### 2. CLI Surface Standardization (Phase 2)
* **\`synlynk dispatch\`:** Added canonical \`--force-harness\` flag to pin an execution backend, deprecating \`--force-agent\` with a non-breaking warning.
* **\`synlynk jobs handoff\`:** Added canonical \`--to-harness\` flag alongside \`--to\` / \`--to-agent\`.
* **Deprecation Layer:** Extended \`_warn_deprecated_harness_flag\` to warn on deprecated flags without breaking existing scripts.

### 3. Directory & Function Alignment (Phase 3)
* **\`.harnesses/\` Directory Support:** Configuration loaders now inspect \`.harnesses/\` first, transparently falling back to legacy \`.agents/\`.
* **Internal Function Aliasing:** Renamed \`cmd_agent_add/configure/list/run\` to \`cmd_harness_add/configure/list/run\`, preserving dual-exports for backward compatibility.
* **Database & Lock Safety:** Prevented SQLite same-thread lock contention during probe and calibration sweeps by guarding unneeded DML updates and releasing read locks early.

---

## Verification

* **Full Core Test Suite:** 496/496 tests in \`tests/test_synlynk.py\` pass.
* **Dispatch Tests:** 107/107 tests in \`tests/test_dispatch.py\` pass.
* **Agent CLI Tests:** 72/72 tests in \`tests/test_agent_cli.py\` pass.
