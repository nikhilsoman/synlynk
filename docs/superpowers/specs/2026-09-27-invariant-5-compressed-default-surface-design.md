# Invariant 5: Compressed Default Surface Design Spec

**Decision Record:** `dec-20260927-round-1` (Round 1 Deep Architectural & Performance Review)  
**Goal:** `goal-5be4eb8b` (v1.0.0 Dev Preview Mandatory Architectural Invariants)  
**Issue:** #1814  
**Date:** 2026-09-27  
**Author:** Agy (AntiGravity)  
**Co-Authored-By:** Agy (Gemini) <noreply@antigravity.dev>

---

## 1. Problem Statement

1. **Semantic Friction in User-Facing Vocabulary:**
   - The user-facing documentation and CLI conflate Agent, Harness, Role, and GitHub-App-Identity.
   - The documentation currently needs disclaimer paragraphs explaining the difference every time the terms appear.
   - The public surface should cleanly standardize on two distinct nouns:
     - **Role:** The persona/responsibility (e.g. `dev`, `qa`, `architect`, `pm`, `support`).
     - **Harness:** The backend execution engine (e.g. `codex`, `agy`, `claude`, `grok`, `local`).
   - GitHub App identity becomes an opt-in enhancement for multi-agent bot sign-offs rather than an onboarding blocker.

2. **GOVERNS Lifecycle Ceremony:**
   - The 7-stage internal GOVERNS FSM (`Dream → Plan → Work → Ship → Maint → Engag`) is mathematically robust and essential for deep auto-association, but exposes too much ceremony by default for quick tasks and first-time users.
   - A compressed 5-stage rollup (`Plan → Build → Verify → Ship → Sustain`) should be the user-facing default, with `--full` / `--raw` available for the full 7-stage model.

3. **Documentation Drift & Architecture Alignment:**
   - `CLAUDE.md`, `GEMINI.md`, and `AGENTS.md` retain legacy descriptions referencing "single-file CLI", conflicting with the actual 138-module modular architecture.
   - Instructions should be regenerated and aligned to current realities.

---

## 2. Architecture & Design

```
┌────────────────────────────────────────────────────────────────────────┐
│                        USER-FACING INTERFACE                           │
│  • Vocabulary: Role (Task Persona) + Harness (Execution Engine)        │
│  • Default GOVERNS: 5 Stages [Plan → Build → Verify → Ship → Sustain]   │
│  • Optional Flag: --full / --raw (Exposes full 7-stage FSM)            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     COMPRESSED GOVERNS MAPPER                          │
│                                                                        │
│   Compressed Stage      Internal GOVERNS Stages                        │
│   ─────────────────────────────────────────────                        │
│   1. Plan               dream, plan                                    │
│   2. Build              work                                           │
│   3. Verify             review, verify                                 │
│   4. Ship               ship                                           │
│   5. Sustain            maint, engag                                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    INTERNAL RUNTIME & LEDGER                           │
│  • 7-stage FSM (governs_fsm.py) & SQLite WAL (state.db)                │
│  • Fail-closed capability-probed routing (capability_probe.py)         │
│  • Single-writer transactions & Leased worktree locks (wal_ledger.py)  │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Vocabulary Standardization (`synlynk/roles.py`, `synlynk/cli.py`)
- Standardize helper functions:
  - `get_role_definition(role: str) -> dict`: Returns role configuration, responsibilities, default harness recommendation, and tools.
  - `get_harness_definition(harness: str) -> dict`: Returns harness engine capabilities, model defaults, and sandbox properties.
  - Ensure CLI help text and docstrings use `Role` for `--role` / `--as-agent` and `Harness` for `--harness` / positional engine.

### 2.2 Compressed GOVERNS Mapper (`synlynk/governs_compressed.py`)
- Define `COMPRESSED_STAGE_MAP`:
  ```python
  COMPRESSED_STAGES = ["plan", "build", "verify", "ship", "sustain"]

  STAGE_TO_COMPRESSED = {
      "dream": "plan",
      "plan": "plan",
      "work": "build",
      "review": "verify",
      "verify": "verify",
      "ship": "ship",
      "maint": "sustain",
      "engag": "sustain",
  }
  ```
- Functions:
  - `compress_governs_stage(stage: str) -> str`: Maps any 7-stage GOVERNS stage to its compressed 5-stage equivalent.
  - `format_compressed_governs_summary(items: list[dict], full: bool = False) -> str`: Renders ANSI/markdown stage progress.

### 2.3 CLI Integration (`synlynk/cli.py`, `synlynk/governs_cli.py`, `synlynk/status.py`)
- `synlynk governs`: Defaults to compressed 5-stage rollup table; supports `--full` flag for complete 7-stage internal view.
- `synlynk status`: Displays compressed cycle capability header by default.

### 2.4 Documentation Modernization (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`)
- Update harness instruction files with accurate module count, Role vs. Harness definitions, and 5-stage summary.

---

## 3. Testing & Verification

1. **Unit Tests (`tests/test_governs_compressed.py`):**
   - Test stage compression mapping across all 7 internal stages.
   - Test formatting with default compressed view vs `--full` raw view.
   - Test empty, single-item, and mixed-item collections.
2. **CLI Tests (`tests/test_cli_compressed_surface.py`):**
   - Test `synlynk governs` default output format.
   - Test `synlynk governs --full`.
   - Test `synlynk roles` and `--help` output clarity.
3. **Full Regression Suite:**
   - Verify all 3,382+ existing unit tests pass cleanly.
