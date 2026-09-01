---
title: "PR #1318 — Hardening: Prohibit Direct todo.md Hand-Edits Across Harness Instruction Templates"
date: 2026-09-01
series: "Building the OS for Multi-Agent Development"
post: 144
pr: "#1318"
issue: "#1317"
status: open
---

# PR #1318 — Hardening: Prohibit Direct todo.md Hand-Edits Across Harness Instruction Templates

## The Broader Goal at the End of the Previous PR

PR #1316 shipped the automated live in-sandbox GitHub-write probe (TC-9, issue #1213), closing the empirical verification gap across the fleet. Following that landing, an audit of model behavior revealed a chronic reflex where dispatched agents across all harnesses repeatedly attempted to hand-edit `project-docs/todo.md` directly.

## What Was Missing & The Real Root Cause

An audit of instruction templates in `synlynk/instructions.py` and active directive files (`CLAUDE.md`, `GEMINI.md`, `GROK.md`, `.github/copilot-instructions.md`, `.windsurfrules`) identified a direct contradiction:
- The instruction templates explicitly commanded agents to `- Update task status in project-docs/todo.md ([ ] → [x])`.
- In synlynk's runtime architecture, however, `state.db` is the authoritative single source of truth; `todo.md` is an auto-generated view projected at `synlynk checkpoint`, and `_hc_todo_drift` in `synlynk doctor` warns against manual hand-edits.

## What Shipped

1. **Instruction Template Hardening (`synlynk/instructions.py`):**
   - Updated `_session_protocol`, `_build_cursor_mdc()`, `_build_copilot_instructions()`, and `_build_windsurf_rules()` to explicitly prohibit hand-editing `todo.md` and direct agents to use `synlynk story done <id>` (or `synlynk story create/update`) and `synlynk checkpoint`.
2. **Directive Files Alignment:**
   - Updated root directive files (`GEMINI.md`, `CLAUDE.md`, `GROK.md`) to eliminate legacy checkbox hand-edit instructions.
3. **Unit Test Coverage (`tests/test_instructions.py`):**
   - Added `test_instruction_templates_prohibit_direct_todo_edits()` asserting that all generated templates prohibit direct `todo.md` edits and reference `state.db` / `synlynk story done` / `synlynk checkpoint`. All 15 tests pass.
