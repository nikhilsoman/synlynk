# Standardizing Harness vs. Workspace Agent Separation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 1, Phase 2, and Phase 3 of the Harness vs. Workspace Agent separation defined in `docs/superpowers/specs/2026-08-30-harness-agent-separation-design.md`, resolving issue #1255.

**Architecture:**
- **Zero Breaking Changes:** All existing CLI invocations (`--force-agent`, `--agent`, `--to-agent`) continue to work via deprecation aliases.
- **Strict Distinction:** "Harness" = execution backend tool (`claude`, `codex`, `grok`, `agy`, `local`). "Agent" = functional workspace role identity (`pm`, `architect`, `tpm`, `dev`, `designer`, `qa`, `marketing`, `synlynk-bot`).
- **Config Fallback:** Transparently read `.harnesses/` first with fallback to `.agents/`.

**Tech Stack:** Python 3 stdlib (`argparse`, `os`, `json`), `pytest`.

---

### Task 1: Phase 1 — Documentation & Instruction Cleansing (Non-Breaking)

**Files:**
- Modify: `docs/strategy/2026-08-15-two-imperatives-roadmap.md`
- Modify: `GEMINI.md`, `CLAUDE.md`, `GROK.md`
- Modify: `synlynk/probe.py`
- Modify: `tests/test_synlynk.py`, `tests/test_agent_quota_tracking.py`

- [ ] **Step 1: Update Living Strategy Roadmap**
  In `docs/strategy/2026-08-15-two-imperatives-roadmap.md` line 7, replace:
  `1. **Execution autonomy** — workspace agents (Agy/Grok/Codex) take over all implementation/testing/dispatch work; Claude stays PM/review/deploy only.`
  With:
  `1. **Execution autonomy** — workspace agents (dev/qa/designer/marketing) execute implementation and verification tasks through autonomous harnesses (Codex/Grok/Agy); Claude stays PM/review/deploy only.`

- [ ] **Step 2: Update Instruction Preambles**
  In `GEMINI.md`, `CLAUDE.md`, `GROK.md`:
  Change `- **Agent name:** <Name>` to `- **Harness:** <Name>` and clarify that the executing identity is a Harness backend acting on behalf of Workspace Agents.

- [ ] **Step 3: Update Capability Allocation SOP in `synlynk/probe.py`**
  In `synlynk/probe.py` around line 59, update `_CAPABILITY_ALLOCATION_SOP` table headers:
  Change `| Role | Harness | Tasks |` to:
  `| Task Domain | Preferred Harness | Fallback Harnesses | Assigned Agent Role |`
  and update rows to clearly distinguish the skill domain from the agent role.

- [ ] **Step 4: Verify test suite assertions on SOP headers**
  Run: `python3 -m pytest tests/test_synlynk.py tests/test_agent_quota_tracking.py -v`
  Ensure all assertions pass.

- [ ] **Step 5: Commit Phase 1**
  `git commit -m "docs: clarify harness vs workspace agent across strategy and instruction templates (#1255)"`

---

### Task 2: Phase 2 — CLI Flag Standardization & Deprecation Layer

**Files:**
- Modify: `synlynk/cli.py`
- Modify: `tests/test_agent_cli.py`

- [ ] **Step 1: Add `--force-harness` to `dispatch` parser and alias `--force-agent`**
  In `synlynk/cli.py`, in `dispatch_parser`:
  Add `--force-harness` as canonical flag:
  ```python
  dispatch_parser.add_argument(
      "--force-harness", "--force-agent",
      action="store_true",
      dest="force_agent",
      help="Bypass capability routing — dispatch to the exact harness specified"
  )
  ```

- [ ] **Step 2: Add `--to-harness` to `jobs handoff` parser**
  In `jobs_sub.add_parser("handoff")`:
  Support `--to-harness` alongside `--to` and `--to-agent`:
  ```python
  handoff_p.add_argument("--to-harness", "--to-agent", "--to", dest="to_agent", default=None)
  ```

- [ ] **Step 3: Update `_warn_deprecated_harness_flag`**
  In `synlynk/cli.py`:
  Warn if `--force-agent` is used without `--force-harness`, or `--to-agent` without `--to-harness`:
  ```python
  if "--force-agent" in argv and "--force-harness" not in argv:
      print("  warning: --force-agent is deprecated, use --force-harness instead", file=sys.stderr)
  if "--to-agent" in argv and "--to-harness" not in argv:
      print("  warning: --to-agent is deprecated, use --to-harness instead", file=sys.stderr)
  ```

- [ ] **Step 4: Write unit tests for CLI flag aliasing & warnings**
  In `tests/test_agent_cli.py`:
  Add `test_dispatch_cli_force_harness_and_deprecated_force_agent()` and `test_jobs_handoff_cli_to_harness()`.

- [ ] **Step 5: Commit Phase 2**
  `git commit -m "feat(cli): add canonical --force-harness and --to-harness with deprecation aliases (#1255)"`

---

### Task 3: Phase 3 — Configuration Directory & Internal Function Renames

**Files:**
- Modify: `synlynk/support_engineer.py`
- Modify: `synlynk/__init__.py`
- Modify: `synlynk/cli.py`
- Modify: `tests/test_agent_cli.py`

- [ ] **Step 1: Rename functions in `synlynk/support_engineer.py` with aliases**
  Rename `cmd_agent_list` to `cmd_harness_list`.
  Check `.harnesses/` directory first, fall back to `.agents/`.
  Retain alias: `cmd_agent_list = cmd_harness_list`.

- [ ] **Step 2: Rename functions in `synlynk/__init__.py` with aliases**
  Rename `cmd_agent_add` -> `cmd_harness_add`.
  Rename `cmd_agent_configure` -> `cmd_harness_configure`.
  Rename `cmd_agent_run` -> `cmd_harness_run`.
  Retain backward-compatible aliases:
  ```python
  cmd_agent_add = cmd_harness_add
  cmd_agent_configure = cmd_harness_configure
  cmd_agent_run = cmd_harness_run
  ```

- [ ] **Step 3: Update `synlynk/cli.py` harness command dispatching**
  In `elif args.command == "harness":` invoke the canonical `cmd_harness_*` functions.

- [ ] **Step 4: Write unit tests verifying harness configuration & listing**
  Add unit tests in `tests/test_agent_cli.py` verifying both `.harnesses/` and `.agents/` directory resolution.

- [ ] **Step 5: Commit Phase 3**
  `git commit -m "refactor: rename internal harness management functions and support .harnesses/ directory (#1255)"`

---

### Task 4: Verification & Regression Gate

- [ ] **Step 1: Run focused test suites**
  Run: `python3 -m pytest tests/test_agent_cli.py tests/test_dispatch.py tests/test_synlynk.py -q`
- [ ] **Step 2: Run complete pytest suite**
  Run: `python3 -m pytest -q`
- [ ] **Step 3: Open PR for Issue #1255**
  Create PR against `main`, linking `story-a646edf9`, `goal-a222b393`, and `goal-85656c82`.
