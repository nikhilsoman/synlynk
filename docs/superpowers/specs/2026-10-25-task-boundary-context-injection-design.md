---
title: "Task-Boundary Context-Pack Injection Design Specification"
date: 2026-10-25
status: draft
author: "Agy (Home Conductor)"
goal: "goal-9ef9a965"
epic: "#2458"
milestone: "v0.25.6"
arc: "governance"
issue: "#2603"
---

# Task-Boundary Context-Pack Injection Design Specification (gh:#2603)

## 1. Intent & Context

Headless dispatch (`synlynk dispatch`) automatically assembles and injects structured context into dispatched worker prompts (active goals, repo architecture, instructions, charter, scope fences, and recent telemetry).

In contrast, interactive Home Conductor sessions (Claude, Agy, Grok, Codex operating in terminal/chat mode) currently rely on manual context compaction discipline (clearing logs, writing devlogs, referencing memory) at task boundaries.

This specification designs automated **Task-Boundary Context-Pack Injection** to systematically provide fresh, bounded context packets whenever a conductor transitions across task or story boundaries, preventing context drift without waiting for high-watermark token compaction (#2574).

---

## 2. Complementary Relationship with #2574

- **#2574 (Token-Threshold Compaction):** Reactive defense triggered when conversation context reaches a token ceiling (e.g., 70% of window).
- **#2603 (Task-Boundary Context Injection):** Proactive structural hygiene triggered at lifecycle transitions (e.g., moving between tasks in an implementation plan, starting a new workstream, or following a PR merge).

---

## 3. Context-Pack Architecture

### Pack Contents
When generated via `synlynk context pack [--task <id>] [--format json|markdown]`, the context pack synthesizes:
1. **Governing Anchors (4 Coordinates):** Active Goal ID, Parent Epic, Target Milestone, Subsystem Arc.
2. **Repository Baseline:** Active checkout commit SHA, git status of shared main vs worktree, recent 3 merged commits.
3. **Task Scope & Invariants:** Story ID, acceptance criteria, allocated harness/model, file touch fences.
4. **Attestation & Cost Bounds:** Review model tier rule (`--model claude-sonnet-5`), historical burn rate, and required commit trailers.
5. **Fresh Memory Deltas:** Memory entries added since the previous session boundary.

### Injection CLI & Integration
```bash
synlynk context inject --story <story-id>
```
Outputs an optimized, bounded markdown context block (< 2,500 tokens) ready for interactive session consumption or agent prompting.

---

## 4. Implementation Phasing

- **Phase 1 (v0.25.6):** Design specification committed and reviewed.
- **Phase 2 (v0.26.1 / Workspace-Agent Operations):** CLI command `synlynk context pack` implementation and automated shell hook wiring.
