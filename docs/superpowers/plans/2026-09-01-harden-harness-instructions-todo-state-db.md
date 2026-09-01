# Implementation Plan: Harden Harness Instructions to Prohibit Hand-Editing Generated todo.md (#1317)

- **Tracking Story:** `story-5cc37133`
- **Linked Goal:** `goal-a222b393`
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-09-01

---

## Proposed Changes

### 1. `synlynk/instructions.py`
- In `_build_claude_instructions()`:
  - Replace `- Update task status in project-docs/todo.md — do NOT delete tasks: [ ] active · [x] done...` with:
    ```markdown
    - Do NOT hand-edit `todo.md` — it is an auto-generated view projected from `state.db` at checkpoint time.
    - Update task status in `state.db` via `synlynk story done <id>` (or `synlynk story create/update`).
    - Run `synlynk checkpoint` at task boundaries to archive completed stories and regenerate `todo.md`.
    ```
- In `_build_gemini_instructions()`:
  - Replace `- Update task status in project-docs/todo.md` with the same `state.db` / `synlynk story done` directive.
- In `_build_codex_instructions()`:
  - Add explicit directive prohibiting `todo.md` hand-edits.
- In `_build_copilot_instructions()` & `_build_windsurf_rules()`:
  - Replace checkbox editing directives with `state.db` / `synlynk story done` guidance.

### 2. Root Directive Files
- Update `GEMINI.md`, `CLAUDE.md`, `AGENTS.md`, `GROK.md`, `.github/copilot-instructions.md`, and `.windsurfrules` to match the hardened instructions.

### 3. Tests (`tests/test_instructions.py`)
- Add unit tests asserting:
  - `test_instruction_templates_prohibit_direct_todo_edits()`: Asserts generated instruction templates do not contain `[ ] → [x]` or `- Update task status in project-docs/todo.md`.
  - `test_instruction_templates_direct_to_story_and_checkpoint()`: Asserts generated instruction templates contain `synlynk story done` and `synlynk checkpoint`.

---

## Verification Steps
1. `pytest tests/test_instructions.py -v`
2. `pytest tests/test_synlynk.py -q`
3. `pytest tests/test_doctor.py -q`
