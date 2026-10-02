# Implementation Plan: Parallel Swarm Tech-Debt Remediation & Vizor Visual Rigor

**Date:** 2026-10-02  
**Spec Reference:** `docs/superpowers/specs/2026-10-02-parallel-swarm-tech-debt-and-vizor-visual-remediation-design.md`  
**Execution Strategy:** Multi-harness parallel worktree swarm with orthogonal file closures.

---

## Task Breakdown & Dispatch Sequence

### Task 1: Fix #341 — Grok Agent-File Detection
- **Story:** `story-ab44c45c`
- **Harness:** Codex (`--force-harness`)
- **Files Touched:**
  - `synlynk/__init__.py`
  - `synlynk/scan.py`
  - `tests/test_scan.py`
- **Verification Command:** `pytest tests/test_scan.py -q`

### Task 2: Fix #345 — GROK.md Domain Ownership & SOPs
- **Story:** `story-e332c8ea`
- **Harness:** Codex / Agy (`--force-harness`)
- **Files Touched:**
  - `GROK.md`
- **Verification Command:** `python3 -c "assert 'TODO: fill domains' not in open('GROK.md').read()"`

### Task 3: Fix #344 — GEMINI.md Stale Content & Flags
- **Story:** `story-294a855a`
- **Harness:** Codex / Agy (`--force-harness`)
- **Files Touched:**
  - `GEMINI.md`
- **Verification Command:** `python3 -c "assert '472 tests' not in open('GEMINI.md').read()"`

### Task 4: Fix #263 — Vizor Effort & Cost GOVERNS Migration & CSS Overlap
- **Story:** `story-8dadb376`
- **Harness:** Agy / Grok (`--force-harness`)
- **Files Touched:**
  - `synlynk/viz.py`
  - `tests/test_viz.py`
- **Verification Command:** `pytest tests/test_viz.py -q`

### Task 5: End-to-End Visual Verification
- Re-run `capture_vizor.py` across all 7 views.
- Verify `vizor_synlynk_effort.png` confirms clean CSS progress bar rendering and dark theme fidelity.
