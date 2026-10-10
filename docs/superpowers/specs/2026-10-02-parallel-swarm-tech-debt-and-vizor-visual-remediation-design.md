# Design Spec: Parallel Swarm Tech-Debt Remediation & Vizor Visual Rigor

**Date:** 2026-10-02  
**Status:** In Review / Ready for Plan  
**Target Milestone:** v0.24.1 / Pre-v0.25.0 Stabilization  
**Authors:** Agy, Nikhil Soman  
**Linked Goals:** `goal-005ea87d` (Full Fleet Harness Parity), `goal-e3840370` (Vizor Control Plane), `goal-8f64eff5` (Platform Health)

---

## 1. Executive Summary

During the pre-v0.25.0 verification sweep, two critical quality vectors were evaluated:
1. **Visual Testing Rigor:** Headless browser rendering of all 7 Vizor tabs revealed a critical layout failure in `effort.html` where progress bar backgrounds wrap directly over task text, top cards render with unstyled white themes, and legacy "Dream" nomenclature violates GOVERNS standards.
2. **Backlog Reality Audit:** Analysis of the 83 remaining open GitHub issues proved that not all open issues are resolved; four concrete code defects remain open, affecting fleet scanning, agent instruction consistency, and HUD accuracy (#341, #345, #344, #263).

This specification defines a **Parallel Swarm Remediation** leveraging Synlynk's `SwarmBatch` and `check_orthogonal_files` engine to dispatch four parallel worktree tasks across our multi-harness fleet, resolving these defects without merge collisions while instituting headless visual screenshot testing.

---

## 2. Visual Audit Findings & Fix Requirements

### 2.1 Findings Across Vizor Tabs
A complete headless Chrome audit (`--headless --screenshot`) was performed against the live Vizor server (`http://localhost:33333/`):
- **Overview (`/w/synlynk/index.html`):** Renders successfully with dark theme. Surfaced **505 un-deduplicated Sentinel alerts** (`#354`).
- **Effort & Cost (`/w/synlynk/effort.html`):** **CRITICAL DEFECT.** Progress bars for in-flight tasks have absolute/relative CSS positioning errors causing the teal/green progress bar fill to collide with and render behind/over the story title text (e.g. `The Autonomous Pl|atform, Boardroom & Concierge`). Top cards (`TOTAL SPEND`, `DREAMS IN FLIGHT`) display stark unbordered white cards, and the page uses outdated `Dream` terminology instead of GOVERNS `Goal`/`Milestone`.
- **Roles (`/w/synlynk/roles.html`):** 8 living charters rendered cleanly.
- **Architect Map (`/w/synlynk/tube.html`):** 441 nodes / 1900 edges rendered with level filters (L0–L3).
- **Efficiency (`/w/synlynk/efficiency.html`):** 1.0x headless efficiency, capacity tables, and GOVERNS cycle capability matrix rendered cleanly.
- **Observatory (`/w/synlynk/observatory.html`):** Worktree health and circuit breaker telemetry rendered cleanly.

### 2.2 Effort & Cost Tab Remediation Requirements
1. **Progress Bar Layout:** Disentangle progress bars from text rows. Replace overlapping background fills with structured flex rows:
   ```html
   <div class="effort-row">
     <div class="effort-label">The Autonomous Platform, Boardroom & Concierge</div>
     <div class="effort-bar-track">
       <div class="effort-bar-fill" style="width: 85%;"></div>
     </div>
     <div class="effort-cost">$3.38 (est: $3.38)</div>
   </div>
   ```
2. **GOVERNS Nomenclature:** Replace "DREAMS IN FLIGHT" and "By Dream" with "ACTIVE GOALS" and "By Goal / Milestone".
3. **Card Theming:** Ensure `.metric-card` inherits CSS variables `--card-bg`, `--card-border`, `--text` so dark mode applies consistently.

---

## 3. Backlog Tech-Debt Swarm Architecture

### 3.1 Orthogonality Matrix
To execute the remediation as a true parallel swarm without git merge conflicts, tasks must have zero file overlap:

| Task | Issue | Story ID | Assigned Role | Target Files | Orthogonality Check |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Task A** | #341 | `story-ab44c45c` | `dev` (Codex) | `synlynk/__init__.py`, `synlynk/scan.py`, `tests/test_scan.py` | Pass (Disjoint) |
| **Task B** | #345 | `story-e332c8ea` | `dev` (Codex/Agy) | `GROK.md` | Pass (Disjoint) |
| **Task C** | #344 | `story-294a855a` | `dev` (Codex/Agy) | `GEMINI.md` | Pass (Disjoint) |
| **Task D** | #263 | `story-8dadb376` | `dev` (Agy/Grok) | `synlynk/viz.py`, `tests/test_viz.py` | Pass (Disjoint) |

`check_orthogonal_files([Files_A, Files_B, Files_C, Files_D]) == True`.

### 3.2 Detailed Task Specifications

#### Task A: Fix #341 — Agent-File Detection for GROK.md
- **Problem:** `_AGENT_FILE_NAMES` in `synlynk/__init__.py` and `synlynk/scan.py` is `{"CLAUDE.md", "GEMINI.md", "AGENTS.md", "AI_INSTRUCTIONS.md"}`. It omits `GROK.md`, causing `synlynk scan` to undercount configured agents when Grok is active.
- **Fix:** Add `"GROK.md"` to `_AGENT_FILE_NAMES` in both files. Add unit test in `tests/test_scan.py` asserting that scanning a repo containing `GROK.md` recognizes Grok.

#### Task B: Fix #345 — GROK.md Instruction Completion
- **Problem:** `GROK.md` contains unpopulated placeholder text: `| TODO: fill domains for this agent | | |`.
- **Fix:** Populate domain ownership matching the capability allocation matrix:
  - `Canvas & Frontend Visualizations`: `synlynk/viz.py`, interactive HTML/SVG components, Canvas HUD.
  - `Infrastructure & Subprocesses`: Shell wrappers, packaging, runner drivers, background daemons.
  - `Instrumentation & Testing`: Cross-platform testing, browser verification scripts.

#### Task C: Fix #344 — GEMINI.md Stale Prose & Flag Sanitization
- **Problem:** `GEMINI.md` contains stale prose ("472 tests", "~6500 lines", omits Grok) and erroneously lists `--sandbox` under valid Gemini flags (which is a Codex Seatbelt flag).
- **Fix:** Update test count and repo description to reflect modular architecture (3,600+ tests, 4 core harnesses), and remove `--sandbox` from active flags if unsupported or clarify its scoped context.

#### Task D: Fix #263 — Vizor Effort & Cost GOVERNS Migration & CSS Fix
- **Problem:** Stage constants in `synlynk/viz.py` effort views reference obsolete stages, progress bar fills overlap text labels, and cards lack proper dark mode theming.
- **Fix:** Update stage constants to match `GOVERNS_STAGES`, fix CSS flexbox layout for effort bars, and add regression tests in `tests/test_viz.py`.

---

## 4. Verification & Quality Gates

1. **Subprocess Unit Tests:**
   - `pytest tests/test_scan.py`
   - `pytest tests/test_viz.py`
   - Total suite: 3,639+ tests passing green.
2. **Headless Browser Visual Regression:**
   - Re-run `capture_vizor.py` post-fix.
   - Assert `vizor_synlynk_effort.png` shows zero text collisions, unified dark mode, and GOVERNS labels.
3. **PR Review & Merge Oracle:**
   - Run `synlynk pr check` in each worktree branch.
   - Run `synlynk policy check-merge --role qa`.
