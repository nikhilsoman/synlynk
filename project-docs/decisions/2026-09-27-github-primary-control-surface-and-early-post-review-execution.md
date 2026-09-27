---
decision_id: dec-20260927-github-primary-control-surface
topic: "Establish GitHub as the primary remote control surface, standardize rich issue schemas & resolution receipts, and queue retrospective enrichment for early post-review execution"
date: 2026-09-27
panel: [nikhilsoman, agy]
status: approved
primary_goal: goal-d3333441
governing_loop: goal-eacab0dc
target_milestone: 2026-10-01
---

## Context & Topic

GitHub is the sole remote access and control surface for human operators, mobile oversight, and external integrations in the Synlynk autonomous engineering ecosystem. A forensic audit of all 456 GitHub issues revealed that 68% have thin or 1-line descriptions, primarily because:
1. SQLite `state.db` `stories` table schema lacked a `description` column.
2. `synlynk story create` and `synlynk backlog sync` generated 1-line stubs.
3. The background daemon (`synlynk/daemon.py`) had no GitHub Ingress Poller for remote `state:ready` triggers or comment commands (`/dispatch`, `/review`).
4. Completed PR merges did not automatically write back structured Execution Receipts (commits, diffstats, test evidence, token/$ costs) to GitHub issues.

## Decision

1. **Adopt Standardized Issue & Receipt Schema:**
   - Pre-Execution: Machine-readable header + rich markdown covering Objective (Why), Technical Scope & Scoped Paths (What), and Acceptance Criteria / TDD Contract.
   - Post-Execution: Structured Resolution Receipt comment (PR, commit SHA, files touched diff, verification test output, token burn and dollar cost, key architectural learnings).
2. **Commit Under October 1 Milestone Goal `goal-d3333441`:**
   - Primary Goal: `goal-d3333441` (*Control-plane trust and closure: unattended merge and autonomous execution by Oct 1*).
   - Governing Master Loop: `goal-eacab0dc` (*Universal GOVERNS enforcement*).
3. **Execution Priority: Early Post-Review Execution:**
   - Slated for implementation immediately following the upcoming Architecture Council and Business Reviews, provided no higher-severity blockers or critical release impediments emerge during the review.
4. **Retrospective Enrichment Pipeline (`synlynk issue enrich`):**
   - Harvests historical PRs, devlogs, specs, and telemetry to idempotently backfill rich descriptions and execution receipts across issues #1–#456.

## Spec & Lineage

- **Architectural Spec:** `docs/superpowers/specs/2026-09-27-github-primary-control-surface-and-issue-enrichment-design.md`
- **Tracking Stories:** `story-gh-control-surface`, `story-issue-enrichment-engine`
