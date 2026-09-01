# Design Spec: Harden Harness Instructions to Prohibit Hand-Editing Generated todo.md (#1317)

- **Issue:** #1317 (Harden harness instructions across fleet to prohibit hand-editing generated todo.md)
- **Tracking Story:** `story-5cc37133`
- **Linked Goal:** `goal-a222b393`
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-09-01
- **Status:** Approved

---

## 1. Problem Statement & Motivation

### 1.1 Symptoms
Dispatched agents across multiple harnesses (Claude, Agy, Codex, Grok) frequently attempt direct filesystem writes to `project-docs/todo.md` (e.g. rewriting `[ ]` checkboxes to `[x]`), tripping filesystem permission guards or inducing divergence from `state.db`.

### 1.2 Root Cause Analysis
An audit of instruction templates in `synlynk/instructions.py` and existing repository directive files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md`, `.github/copilot-instructions.md`, `.windsurfrules`) revealed an explicit instruction conflict:

1. **Legacy Instruction Directive:**
   The instruction templates repeatedly instructed:
   ```markdown
   - Update task status in project-docs/todo.md — do NOT delete tasks:
     `[ ]` active · `[x]` done · `[-]` deferred · `[~]` superseded · `[>]` absorbed
   ```
   Or in `GEMINI.md`:
   ```markdown
   - Update todo checkboxes as tasks complete ([ ] → [x])
   ```

2. **Architectural Contradiction:**
   `synlynk` runtime uses `state.db` (`stories` table) as the single authoritative source of truth:
   - `_generate_todo_md()` (in `synlynk/db.py`) stamps `todo.md` with:
     ```markdown
     # Tasks (generated - source of truth is state.db)
     # Edit via: synlynk story create/update | Do NOT hand-edit this file
     ```
   - `synlynk checkpoint` archives completed stories from `state.db`, appends to devlogs, and regenerates `todo.md`.
   - `_hc_todo_drift` in `synlynk doctor` actively warns if `todo.md` has drifted from `state.db` regeneration.

When models read the legacy instruction text, they follow the explicit command to edit `todo.md` directly, causing accidental drift.

---

## 2. Proposed Changes & Specifications

### 2.1 Instruction Template Hardening (`synlynk/instructions.py`)
Update all instruction builders:
- `_build_claude_instructions()`
- `_build_gemini_instructions()`
- `_build_codex_instructions()`
- `_build_copilot_instructions()`
- `_build_windsurf_rules()`

Replace all direct checkbox edit instructions with the canonical `state.db` workflow:
```markdown
- Do NOT hand-edit `todo.md` — it is an auto-generated view projected from `state.db` at checkpoint time.
- Update task status in `state.db` via `synlynk story done <id>` (or `synlynk story create/update`).
- Run `synlynk checkpoint` at task boundaries to archive completed stories and regenerate `todo.md`.
```

### 2.2 Repository Directive Files Update
Update existing root directive files to eliminate contradictory hand-edit instructions:
- `GEMINI.md`
- `CLAUDE.md`
- `AGENTS.md`
- `GROK.md`
- `.github/copilot-instructions.md`
- `.windsurfrules`

### 2.3 Unit Testing & Verification (`tests/test_instructions.py`)
Add unit tests verifying:
1. Generated instruction templates for all harnesses do not contain legacy `[ ]` / `[x]` hand-edit directives.
2. Generated instruction templates contain explicit warnings against hand-editing `todo.md` and reference `synlynk story done` and `synlynk checkpoint`.

---

## 3. Review & Verification
- Non-authoring review discipline: Agy authors, Codex reviews.
- All unit tests pass across `test_instructions.py`, `test_synlynk.py`, and `test_doctor.py`.
