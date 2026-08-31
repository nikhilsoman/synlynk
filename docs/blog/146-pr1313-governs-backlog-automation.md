---
title: "PR #1313 — GOVERNS Backlog Automation: Auto-Associate Discovered and Planned Work"
date: 2026-08-31
series: "Building the OS for Multi-Agent Development"
post: 146
pr: "#1313"
issue: "#1203"
status: open
---

# PR #1313 — GOVERNS Backlog Automation: Auto-Associate Discovered and Planned Work

## The Broader Goal

In autonomous multi-agent development fleets, tasks and technical debt are discovered dynamically during interactive sessions, autonomous dispatch jobs, and health diagnostics (`synlynk doctor`).

Part of the **Autonomous Operations Activation** roadmap (#1198), Issue #1203 implements **GOVERNS Backlog Automation**: a deterministic, deduplicated, lifecycle-aware subsystem that captures discovered work, maps it to the 7-stage GOVERNS taxonomy (`goal`, `open`, `visualize`, `execute`, `release`, `notify`, `sustain`), and safely synchronizes it with GitHub Issues without spam or duplication.

## What Was Missing & Root Cause

Previously:
- No automated subsystem existed to capture and structure discovered work across devlogs, job outputs, or doctor failures.
- Unstructured auto-filing risked duplicate-issue spam on GitHub.
- Discovered work was not tied to the 7-stage GOVERNS lifecycle model or tracked in `state.db`.

## What Shipped

1. **Deterministic Fingerprinting & 4-Layer Anti-Spam Deduplication (`synlynk/backlog.py`):**
   - Implemented `compute_fingerprint(title, source_ref)` using SHA-256 over normalized title and source references.
   - Enforced deduplication across `state.db:stories` unique fingerprint index, existing titles, and open GitHub issues.

2. **Signal Extraction Heuristics (`synlynk/backlog_extractor.py`):**
   - Added extractors for devlog follow-up sections and `<!-- discover: ... -->` markers.
   - Added parsers for out-of-scope `FOLLOWUP:` / `TECH-DEBT:` items in autonomous job outputs.
   - Added doctor failure conversion into `governs:sustain` maintenance tasks.

3. **Data Model & Schema Migration (`synlynk/db.py`, `synlynk/__init__.py`):**
   - Bumped `_DB_MIGRATION_VERSION` to 5.
   - Added `fingerprint`, `source_type`, `source_ref`, and `governs_stage` columns with unique index on `stories`.

4. **CLI Subcommand Surface (`synlynk/cli.py`):**
   - Added `synlynk backlog capture` for staging discovered work.
   - Added `synlynk backlog list` for inspecting staged backlog items.
   - Added `synlynk backlog sync` for dry-run and upstream GitHub issue creation.

5. **Session Checkpoint Integration (`synlynk/__init__.py:checkpoint`):**
   - Automatically scans session devlogs during checkpoint/session boundary and stages new action items into the backlog.

6. **Comprehensive Unit & Integration Test Suite (`tests/test_backlog_automation.py`):**
   - Added 8 test cases covering fingerprint normalization, deduplication, signal extraction, staging, GitHub syncing, and CLI commands.
