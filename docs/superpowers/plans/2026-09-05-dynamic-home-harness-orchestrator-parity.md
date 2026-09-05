# Dynamic Home Harness Orchestrator Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable any supported AI CLI (Agy, Claude, Codex, Grok) operating interactively to act as the autonomous project conductor, seamlessly surviving home switches without static directive conflicts.

**Architecture:** 
1. Symmetric Dual-Mode directives (Mode A: Home Conductor vs Mode B: Away Worker) across all core harness instruction templates.
2. Dynamic runtime home detection stamping session orchestrator authority and constitutional precedence into `.synlynk/context.md`.
3. Purging hardcoded Claude-centrism from shared SOP blocks in `synlynk/probe.py`.
4. `synlynk home [harness]` CLI command for zero-file-edit home switches.

**Tech Stack:** Python 3 (standard library only), pytest.

**Spec:** `docs/superpowers/specs/2026-09-05-dynamic-home-harness-orchestrator-parity-design.md`

## Global Constraints
- Standard library only (no external pip dependencies added to synlynk runtime).
- All 500+ existing tests must pass before any commit.
- Worktree branch: `feat/agy/dynamic-home-directives`.
- Commit trailer: `Co-Authored-By: AGY <noreply@antigravity.dev>`.

---

### Task 1: Purge Hardcoded Claude-Centrism from `synlynk/probe.py`

**Files:**
- Modify: `synlynk/probe.py:40-120`
- Test: `tests/test_probe.py`

**Interfaces:**
- Consumes: `SOP_BLOCKS` in `synlynk/probe.py`
- Produces: Sanitized SOP blocks referencing "Home Harness" and "Architect/PM role" instead of hardcoded "Claude"

- [ ] **Step 1: Write test asserting SOP blocks have zero hardcoded Claude authority**
  Add `test_sop_blocks_no_hardcoded_claude_authority` in `tests/test_probe.py`.
- [ ] **Step 2: Run test to confirm failure**
  `pytest tests/test_probe.py -k test_sop_blocks_no_hardcoded_claude_authority`
- [ ] **Step 3: Update `synlynk/probe.py`**
  Replace `"without explicit Claude approval"` with `"without explicit Home Harness approval"`.
  Replace `"escalate to Claude"` with `"escalate to the Home Harness"`.
  Replace `"Run the brainstorm using Claude via synlynk dispatch"` with `"Run the brainstorm using the Architect/PM role via synlynk dispatch (or locally if running in Home Conductor mode)"`.
- [ ] **Step 4: Run test to confirm pass**
  `pytest tests/test_probe.py`
- [ ] **Step 5: Commit**
  `git commit -m "fix(probe): purge hardcoded Claude-centrism from SOP blocks"`

---

### Task 2: Symmetric Dual-Mode Directives in `synlynk/instructions.py`

**Files:**
- Modify: `synlynk/instructions.py:454-650`
- Test: `tests/test_instructions.py`

**Interfaces:**
- Consumes: `_build_templates` in `synlynk/instructions.py`
- Produces: `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md` templates containing Mode A (Home) and Mode B (Away) with constitutional precedence

- [ ] **Step 1: Write failing test in `tests/test_instructions.py`**
  Verify generated `_claude_md`, `_gemini_md`, `_agents_md`, and `_grok_md` all contain `## Operating Mode: Home vs. Away`, `Mode A: Interactive Session (Home Conductor)`, and `Mode B: Dispatched Task (Away Worker)`.
- [ ] **Step 2: Run test to confirm failure**
  `pytest tests/test_instructions.py -k test_dual_mode_directives`
- [ ] **Step 3: Update `synlynk/instructions.py`**
  Add shared `_dual_mode_protocol` block.
  Inject into all harness markdown templates.
  Remove legacy subservient table (`| What you own | What you hand back to Claude |`) from `_gemini_md`.
- [ ] **Step 4: Run test to confirm pass**
  `pytest tests/test_instructions.py`
- [ ] **Step 5: Commit**
  `git commit -m "feat(instructions): introduce symmetric dual-mode home and away directives"`

---

### Task 3: Dynamic Runtime Home Detection & Constitutional Precedence in `synlynk/context.py`

**Files:**
- Modify: `synlynk/context.py`
- Test: `tests/test_context.py`

**Interfaces:**
- Consumes: `generate_context()` in `synlynk/context.py`, process tree and env vars
- Produces: Dynamically stamped `<!-- SYNLYNK SESSION RUNTIME STATE -->` banner in `.synlynk/context.md`

- [ ] **Step 1: Write failing test in `tests/test_context.py`**
  Verify `generate_context()` detects active harness from environment and stamps the Active Home Harness banner at line 1 of `context.md`.
- [ ] **Step 2: Run test to confirm failure**
  `pytest tests/test_context.py -k test_runtime_home_injection`
- [ ] **Step 3: Implement runtime home detection in `synlynk/context.py`**
  Implement `detect_active_harness(cfg)`.
  Prepend runtime state banner with constitutional precedence clause to generated context.
- [ ] **Step 4: Run test to confirm pass**
  `pytest tests/test_context.py`
- [ ] **Step 5: Commit**
  `git commit -m "feat(context): dynamic runtime home harness detection and precedence banner"`

---

### Task 4: Implement `synlynk home` CLI Verb

**Files:**
- Modify: `synlynk/cli.py`
- Test: `tests/test_home_cmd.py`

**Interfaces:**
- Consumes: `synlynk home [harness]`
- Produces: Displays or updates configured home harness in `config.json` and triggers context refresh

- [ ] **Step 1: Write failing test in `tests/test_home_cmd.py`**
  Test `synlynk home` outputs current home; `synlynk home agy` updates config and context.
- [ ] **Step 2: Run test to confirm failure**
  `pytest tests/test_home_cmd.py`
- [ ] **Step 3: Implement `cmd_home` in `synlynk/cli.py`**
  Wire into command parser and taxonomy.
- [ ] **Step 4: Run test to confirm pass**
  `pytest tests/test_home_cmd.py`
- [ ] **Step 5: Commit**
  `git commit -m "feat(cli): add synlynk home command for seamless harness switching"`

---

### Task 5: Instructions Repair for Existing Repositories

**Files:**
- Modify: `synlynk/instructions.py`
- Test: `tests/test_instructions.py`

**Interfaces:**
- Consumes: `synlynk instructions update --repair`
- Produces: Upgrades existing repo directive files to the new symmetric dual-mode schema

- [ ] **Step 1: Write test for updating legacy files**
  Test that `_repair_sops_only()` or repair flow updates legacy `GEMINI.md` and `CLAUDE.md`.
- [ ] **Step 2: Run test to confirm failure**
- [ ] **Step 3: Implement repair enhancement**
- [ ] **Step 4: Run test to confirm pass**
- [ ] **Step 5: Commit**
  `git commit -m "feat(instructions): repair upgrades legacy directive files to dual-mode"`

---

### Task 6: Full Test Suite Verification & Integration Check

**Files:**
- Full suite verification across `tests/`

- [ ] **Step 1: Run full pytest suite**
  `pytest tests/ -q`
- [ ] **Step 2: Fix any collateral test failures**
- [ ] **Step 3: Verify git status is clean and all commits are properly authored**
- [ ] **Step 4: Final commit / push prep**
