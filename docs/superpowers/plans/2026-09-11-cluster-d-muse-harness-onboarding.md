# Implementation Plan: Milestone v0.20.0 Cluster D — Next-Gen Harness Onboarding (Meta Muse Integration)

- **Target Milestone:** `v0.20.0`
- **Governing Goals:** `goal-250b6fb2` (Fleet Parity), `goal-8f64eff5` (Durable Platform Health)
- **Tracking Story:** `story-996159c6`
- **Design Spec:** `docs/superpowers/specs/2026-09-11-v0.20.0-visual-workspace-autonomous-onboarding-design.md` §6

---

## 1. Overview & Objectives
Cluster D adds **Meta Muse** as a first-class supported execution harness in synlynk.
Meta Muse provides high-speed code synthesis, surgical refactoring, and algorithmic reasoning via its dedicated CLI (`muse`).

Key deliverables:
1. **Harness Capability Baseline (`synlynk/_constants.py`):** Register `muse` in `HARNESS_CAPABILITY_BASELINES`, configuring CLI flags (`run --non-interactive -C <worktree> --prompt "$PROMPT"`), roles (`builder`, `verifier`, `architect`), network endpoints, and auth probe.
2. **Dispatch CLI Adapter (`synlynk/dispatch.py`):**
   - Inject `-C worktree_path` and `--output-format json` flags.
   - Format prompt in `_format_prompt_for_agent()` with mandatory `SYNLYNK_TASK_RECEIVED` and `SYNLYNK_INSTRUCTION_VERSION` headers and working directory constraints.
3. **Structured Token & Cost Tracking (`synlynk/costs.py`):**
   - Implement `_extract_muse_structured()` to parse Muse CLI JSON token counts (`input_tokens`, `output_tokens`, `cached_tokens`).
4. **Harness Probing & Discovery (`synlynk/probe.py`):**
   - Support `synlynk probe muse` and fast-path capability hash checks.
5. **Documentation & Capability Attestation (`docs/harness-capability-baseline.md`):**
   - Register Meta Muse in the official baseline documentation.
6. **Comprehensive Verification (`tests/test_muse_harness.py`):**
   - Full unit test coverage for baseline schema compliance, flag generation, prompt formatting, token extraction, and probing.

---

## 2. Execution Tasks

### Task 1: Register Meta Muse in `synlynk/_constants.py`
- Add `"muse"` baseline definition to `HARNESS_CAPABILITY_BASELINES`:
  - `cli: "muse"`
  - `can_gh_write: True`
  - `non_interactive_flags: ["run", "--non-interactive"]`
  - `prompt_flag: "--prompt"`
  - `prompt_via_arg: True`
  - `dispatch_flags`:
    - `valid_flags: ["--prompt", "--model", "--non-interactive", "-C", "--output-format"]`
    - `invalid_flags: ["--dangerously-skip-permissions", "--always-approve"]`
    - `required_flags: ["--non-interactive"]`
  - `headless_contract`: `requires_pty: False`, `stdout_flush_method: "native"`, `non_interactive_flag: "--non-interactive"`
  - `network_deps`: `required_endpoints: ["api.muse.meta.com:443"]`
  - `auth_check`: `probe: ["muse", "--version"]`, unauthenticated markers
  - `roles: ["builder", "verifier", "architect"]`
  - `env_passthrough: ["MUSE_API_KEY", "META_API_KEY"]`
  - `strengths: ["surgical refactoring", "algorithmic synthesis", "automated unit testing", "high throughput"]`
- Add `"muse"` to `NEXT_GEN_FLEET = frozenset({"muse"})` and update `EXTENDED_FLEET = frozenset({"local", "muse"})`.

### Task 2: Dispatch CLI Adapter & Prompt Formatting in `synlynk/dispatch.py`
- In `dispatch_agent()`:
  - Add `agent == "muse"` configuration: ensure `-C worktree_path` and `--output-format json` are included.
- In `_format_prompt_for_agent()`:
  - Add explicit `agent == "muse"` prompt template:
    - Include task and instruction receipt headers (`SYNLYNK_TASK_RECEIVED`).
    - Include working directory directive (`## Working Directory\n{working_dir}\nAll file edits MUST be in this directory.`).
    - Include story reference, file list, verify criteria, and context summary.

### Task 3: Token Usage & Cost Extraction in `synlynk/costs.py`
- Implement `_extract_muse_structured(output_text)`:
  - Support single JSON response and streaming event lines.
  - Parse `usage.input_tokens`, `usage.output_tokens`, and `usage.cached_tokens`.
- Wire `if agent == "muse":` in `extract_tokens()`.

### Task 4: Probing & Capability Documentation
- Update `synlynk/probe.py`:
  - Map `"muse"` in `harness_map`.
  - Ensure `_probe_agent("muse", ...)` and `_run_tc0("muse", ...)` pass cleanly.
- Update `docs/harness-capability-baseline.md`:
  - Document Meta Muse baseline, capability tier, CLI signature, and integration notes.

### Task 5: Test Suite Verification
- Author `tests/test_muse_harness.py`:
  - Test baseline structure and TC-0 schema compliance.
  - Test dispatch flags and CLI command string construction (`muse run --non-interactive -C <path> ...`).
  - Test prompt formatting with headers and working directory.
  - Test token extraction from Muse JSON outputs.
  - Test `_probe_agent` execution with mock binary.
- Run full test suite across Python 3.10 and 3.12.

### Task 6: 4-Doc Discipline & PR Workflow
- Update `roadmap.md`, `devlogs/agy.md`, `costs.md`, `memory.md`.
- Create PR #1560, await CI, submit QA review approval, squash-merge, and clean up worktree.
