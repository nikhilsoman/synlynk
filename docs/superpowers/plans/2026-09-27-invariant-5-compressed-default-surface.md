# Invariant 5: Compressed Default Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce Invariant 5 (Compressed Default Surface) by establishing standardized Role & Harness vocabulary, compressed 5-stage GOVERNS rollup defaults (`Plan → Build → Verify → Ship → Sustain`), and synchronized documentation.

**Architecture:** Create `synlynk/governs_compressed.py` with two-way stage translation and formatted summary renderers; integrate compressed stage views into `synlynk governs`, `synlynk status`, and CLI help messages; update `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md` with accurate architectural descriptions.

**Tech Stack:** Python 3.10+, SQLite WAL, Pytest, Click/Argparse CLI.

**Spec:** `docs/superpowers/specs/2026-09-27-invariant-5-compressed-default-surface-design.md`

## Global Constraints
- Every git commit must include the trailer: `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>`.
- Preserve backward compatibility: internal 7-stage GOVERNS FSM and SQLite storage remain intact; compressed view is an ergonomic projection.
- 100% test pass rate across full 3,382+ test suite.

---

### Task 1: Compressed GOVERNS Stage Mapper & Formatting Engine
**Files:**
- Create: `synlynk/governs_compressed.py`
- Test: `tests/test_governs_compressed.py`

- [ ] **Step 1: Write the failing unit tests in `tests/test_governs_compressed.py`**
- [ ] **Step 2: Implement `compress_governs_stage` and `format_compressed_governs_summary` in `synlynk/governs_compressed.py`**
- [ ] **Step 3: Run pytest and verify 100% pass rate on new tests**
- [ ] **Step 4: Commit Task 1 changes**

---

### Task 2: CLI Integration for Compressed GOVERNS Surface
**Files:**
- Modify: `synlynk/governs_cli.py`, `synlynk/cli.py`, `synlynk/status.py`
- Test: `tests/test_cli_compressed_surface.py`

- [ ] **Step 1: Write CLI tests asserting default compressed 5-stage output and `--full` 7-stage output**
- [ ] **Step 2: Update `synlynk governs` and `synlynk status` to render compressed view by default**
- [ ] **Step 3: Verify CLI tests pass**
- [ ] **Step 4: Commit Task 2 changes**

---

### Task 3: Documentation Realignment & Vocabulary Standardization
**Files:**
- Modify: `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`

- [ ] **Step 1: Update architecture descriptions in `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`**
- [ ] **Step 2: Ensure Role vs Harness distinctions are clearly standardized**
- [ ] **Step 3: Run full pytest regression suite**
- [ ] **Step 4: Commit Task 3 changes**
