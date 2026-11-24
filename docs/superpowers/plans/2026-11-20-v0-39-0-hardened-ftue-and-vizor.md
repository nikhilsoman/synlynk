# v0.39.0 Implementation Plan: Hardened FTUE & Vizor HUD

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a bulletproof First-Time User Experience (FTUE) and interactive Vizor HUD supporting any 1+ of the 5 core harnesses (Claude, Codex, Agy, Grok, Cursor) + OpenRouter (BYOK), eliminating all failure modes uncovered in early-adopter sessions (#5413, #5363, #5302), and gating release readiness via clean Linux VM acceptance tests.

**Architecture & References:**
- Design Spec: [docs/superpowers/specs/2026-11-15-ftue-onboarding-vm-testbed-and-discovery-design.md](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-11-15-ftue-onboarding-vm-testbed-and-discovery-design.md) (gh:#5302)
- Incident RCA: [docs/rca/2026-11-20-onboarding-incident-5413-rca.md](file:///Users/nikhilsoman/dev/synlynk/docs/rca/2026-11-20-onboarding-incident-5413-rca.md) (gh:#5413)
- Incident Analysis: [docs/rca/2026-11-20-onboarding-incident-5413-analysis.md](file:///Users/nikhilsoman/dev/synlynk/docs/rca/2026-11-20-onboarding-incident-5413-analysis.md)
- LIVE-33 RCA: [docs/rca/2026-11-18-LIVE-33-onboarding-unpublished-workspace.md](file:///Users/nikhilsoman/dev/synlynk/docs/rca/2026-11-18-LIVE-33-onboarding-unpublished-workspace.md) (gh:#5364 / gh:#5363)
- Editions Boundary: [docs/superpowers/specs/2026-11-13-synlynk-editions-boundary-and-opt-in-gating-design.md](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-11-13-synlynk-editions-boundary-and-opt-in-gating-design.md) (goal-ecffdaaf)
- Decision Record: [project-docs/decisions/2026-11-20-re-prioritization-of-synlynk-roadmap-cor.md](file:///Users/nikhilsoman/dev/synlynk/project-docs/decisions/2026-11-20-re-prioritization-of-synlynk-roadmap-cor.md) (`dec-3ebc85f6`)

**Tech Stack:** Python 3.12+, SQLite (`state.db`), `OrbDriver` VM runner (Ubuntu 24.04), Bottle (Vizor HTTP server), Pytest.

---

## File Structure & Touchpoints

```text
synlynk/
  wizard.py             # FTUE screens, OpenRouter BYOK prompt, multi-digit index picker, cwd guards
  launch.py             # first-win dispatch, workspace parameter propagation, atomic commit
  editions.py           # personal profile gating: require_linked_goal_mode=False
  dispatch.py           # synthetic first-win story bypass, proxy env passthrough verification
  _constants.py         # universal proxy allowlists (OPENAI_BASE_URL, GEMINI_BASE_URL, ANTHROPIC_BASE_URL)
  onboard_repair.py     # new: synlynk onboard repair [--dry-run|--apply] self-healing tool
  cli.py                # wiring onboard repair subcommand, init cwd guards
tests/
  test_wizard_openrouter_byok.py    # unit tests for zero-harness OpenRouter fallback
  test_wizard_workspace_params.py   # verifies workspace name & repo preservation
  test_wizard_atomic_commit.py      # verifies zero disk writes on dispatch failure
  test_onboard_repair.py            # verifies fence, stash, and orphaned config cleanup
  test_ftue_vm_acceptance.py        # clean Ubuntu 24.04 VM acceptance ladder across 6 providers
  test_vizor_e2e_audit.py           # 16-page Vizor route, layout, and static asset crawler
```

---

## Tasks

### Phase 1: FTUE Wizard Hardening & OpenRouter BYOK (gh:#5413, #5302)

- [ ] **Task 1: OpenRouter BYOK Fallback in Wizard Screen 1**
  - In `synlynk/wizard.py:_wiz_screen_harness`, replace the zero-harness dead end (`⚠ No harnesses found on PATH`) with an interactive OpenRouter prompt.
  - If 0 local CLIs detected, or if the user presses `[O]`, prompt for `OPENROUTER_API_KEY`, validate via `synlynk.gateway.cmd_gateway_probe`, and set `home_harness="openrouter"`.
  - Author `tests/test_wizard_openrouter_byok.py` with mock stdin/stdout to verify 100% test coverage.

- [ ] **Task 2: Repo Picker Multi-Digit Index & Scoped Scan**
  - In `synlynk/wizard.py:_wiz_screen_topology` and repo picker:
    - Replace single-character key reading with full line input (`sys.stdin.readline().strip()`) so numbers $\ge 10$ toggle the correct repository.
    - Default repo selection to ONLY the current repository (`cwd`).
    - Require explicit `--discover` flag to walk `~/dev` or `~/projects`, preventing ambient selection of ~78 unrelated repos.
    - Validate with unit tests in `tests/test_wizard_workspace_params.py`.

- [ ] **Task 3: CWD Self-Protection & Git Root Guards**
  - In `synlynk/wizard.py` and `synlynk/cli.py:cmd_init`:
    - Refuse to initialize or write workspace files if `cwd` is within Synlynk's own source repository (preventing tool self-pollution).
    - Require `cwd` to be a valid Git repository root. If run from `~` or an arbitrary directory, fail early before writing any files with an actionable error: `Please run synlynk init inside a git repository`.

---

### Phase 2: Atomic Workspace Commit & Parameter Preservation (gh:#5413, #5363)

- [ ] **Task 4: Preserve Confirmed Workspace Name & Repos**
  - In `synlynk/wizard.py`: pass confirmed `{workspace_name, repos, topology}` directly from `wizard_init` into `cmd_launch_ftue` and `_wiz_screen_launch`.
  - In `synlynk/launch.py`: prevent `run_workspace_scan()` from rescanning CWD and overwriting the chosen workspace name (e.g. `roku`) with the directory's parent name (`dev` / `jitendra.agrawal`).
  - Verify that the first dispatch job metadata and workspace config record the user's chosen workspace name.

- [ ] **Task 5: Atomic Workspace Commit on Dispatch Failure**
  - In `synlynk/wizard.py:wizard_init`:
    - Guard post-dispatch writes: if `dispatch_agent` raises an exception or returns a non-zero failure, abort the wizard immediately.
    - Do NOT write `.synlynk/config.json`, do NOT generate `context.md`, and do NOT write role fences if dispatch failed.
    - Guard `guard_dirty_worktree`: do NOT run `git stash` if dispatch failed.
  - Author `tests/test_wizard_atomic_commit.py` to verify that a failed dispatch leaves the repository bit-for-bit clean.

---

### Phase 3: Editions Gate & First-Run GOVERNS Bypass (gh:#5413, goal-ecffdaaf)

- [ ] **Task 6: Wire Zero-Friction Personal Profile into Dispatch**
  - In `synlynk/editions.py` and `synlynk/dispatch.py:_dispatch_capability_preflight`:
    - When `edition == "personal"` (the default for all new inits), ensure `require_linked_goal_mode=False`.
    - If `story_id` is None during FTUE first-win launch, auto-generate a synthetic first-win story ID (`story-ftue-firstwin`) so preflight passes cleanly without requiring a GOVERNS roadmap version, phase, or parent goal.
    - Ensure Agent Studio role routes and charter validations remain dormant.

- [ ] **Task 7: Universal Proxy & Gateway Environment Passthrough Parity**
  - In `synlynk/_constants.py:HARNESS_CAPABILITY_BASELINES`:
    - Add `OPENAI_BASE_URL`, `OPENAI_API_KEY` to `codex` env passthrough.
    - Add `GEMINI_BASE_URL`, `GEMINI_API_KEY` to `agy` env passthrough.
    - Ensure custom LiteLLM / DGX ports (`127.0.0.1:8000`, `127.0.0.1:4000`) pass connectivity checks in `synlynk/probe_binding.py`.

---

### Phase 4: Self-Repair Tooling & Verification Contracts (gh:#5413, #5302)

- [ ] **Task 8: Implement `synlynk onboard repair` Command**
  - Author `synlynk/onboard_repair.py` implementing the repair logic from #5413 RCA:
    - `--dry-run` (default): scans for orphaned `$HOME/.synlynk/context.md`, role-fence diffs inside Synlynk source checkout, and safety stashes.
    - `--apply`: safely restores tool source files, deletes orphaned home context, and reports stashed work without dropping data.
  - Wire into `synlynk/cli.py` under `synlynk onboard repair`.
  - Author `tests/test_onboard_repair.py`.

- [ ] **Task 9: End-to-End Clean VM Acceptance Matrix & Vizor Route Audit**
  - Execute `tests/test_ftue_vm_acceptance.py` using `OrbDriver` on clean Ubuntu 24.04 VM:
    - 6 provider configurations: Claude, Codex, Agy, Grok, Cursor, OpenRouter BYOK.
    - Greenfield `synlynk init` and Brownfield repo adoption with 100% exit 0.
  - Execute `tests/test_vizor_e2e_audit.py` verifying all 8 Vizor views render cleanly with zero 404s and responsive layouts.

---

## Acceptance Criteria

1. **Clean Greenfield & Brownfield Onboarding:** Running `synlynk init --wizard` completes in under 3 minutes with any 1+ of the 6 providers (including OpenRouter BYOK) with zero manual config edits.
2. **Zero False-Positive Init Errors:** Running `synlynk init --dry-run` or inspecting an uninitialized directory creates zero disk files and causes no subsequent init errors.
3. **No Workspace Amnesia or Publish-After-Failure:** If dispatch fails, zero workspace files or role fences are written. If dispatch succeeds, the user's chosen workspace name is 100% preserved.
4. **Tool Integrity Guard:** Running `synlynk init` inside the Synlynk source repository is cleanly refused.
5. **Automated VM Pass:** Full acceptance test matrix runs and passes in an isolated Ubuntu 24.04 VM.
