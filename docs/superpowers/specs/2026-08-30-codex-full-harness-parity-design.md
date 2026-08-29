# Design Spec: Grant Codex Full Harness Parity Across Review and GH-Write Tasks (#1274)

- **Date:** 2026-08-30
- **Status:** Draft
- **Related Issues:** #1274, #1268, #865, #426, #569, #1178
- **Authors:** Agy (Gemini) <noreply@antigravity.dev>, Nikhil Soman <nikhilsoman@gmail.com>

---

## 1. Executive Summary

Historically, OpenAI Codex was categorized as a "builder-only" execution harness in this repository, locked out of GitHub write actions (issue comments, PR reviews, and PR merges). This exclusion was codified under the belief that Codex's macOS Seatbelt sandbox (`-s workspace-write`) structurally and unbypassably blocked network egress to `api.github.com`.

In PR #1271, we proved this premise false: passing `-c sandbox_workspace_write.network_access=true` cleanly enables outbound HTTPS connectivity to `api.github.com`. Furthermore, in job `job-836e13a4`, Codex was dispatched with `--requires-gh-write --role qa` and successfully inspected PR #1272, posted comment 5464178002 under the `synlynk-synlynk-qa` bot identity, and closed PR #1272 directly from inside its sandbox.

Despite this live proof, Codex remains artificially throttled by legacy safety gates in four repo layers:
1. `synlynk/_constants.py` hardcodes `"can_gh_write": False` and excludes `"verifier"` from Codex roles.
2. `synlynk/dispatch.py` automatically reroutes Codex dispatches with `requires_gh_write=True` away from Codex to Claude unless `--force-agent` is manually passed.
3. `.synlynk/policy.json` excludes Codex from `"review"` and `"gh_write"` task allocations.
4. `docs/harness-capability-baseline.md` and repository instruction guides (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) still describe Codex as "Unreliable" for GitHub writes.

This design specification details the unified architectural changes to grant OpenAI Codex full first-class parity across implementation, testing, review, and GitHub-write tasks, removing the legacy rerouting bypass permanently.

---

## 2. Problem Statement & Historical Context

When `#426` established role routing and `#569` introduced role GitHub App tokens, Codex could not complete remote GitHub actions because network resolution failed under the default Seatbelt sandbox (`curl: (6) Could not resolve host: api.github.com`). 

To avoid failed dispatches, a runtime safeguard was added to `synlynk/dispatch.py:2282-2305`:
```python
if requires_gh_write:
    current_baseline = baselines_map.get(agent, {})
    if not current_baseline.get("can_gh_write", False):
        ...
        if force_agent:
            print("⚠ 'codex' cannot reliably complete GitHub-write actions...")
        else:
            rerouted_to = capable_agents[0] # Auto-reroute to Claude
            agent = rerouted_to
```

This bypass introduced severe failure modes:
1. **Single-Point-of-Failure on Claude:** Whenever a task required PR review or GitHub write, automated dispatches were redirected to Claude. When Claude hit rate limits or account spend limits (as occurred during this session), the entire autonomous workflow halted.
2. **Artificial Role Restriction:** Codex is capable of fast, high-quality test runs and code diff inspections, but `.synlynk/policy.json` and `_constants.py` denied it the `"verifier"` role.
3. **Disjointed User Experience:** Operators had to manually discover and supply `--force-agent` to allow Codex to perform tasks it was already equipped to complete.

---

## 3. Technical Architecture & Layered Updates

### Layer 1: Core Constants (`synlynk/_constants.py`)
Update `HARNESS_CAPABILITY_BASELINES["codex"]`:
- Change `"can_gh_write": False` to `"can_gh_write": True`.
- Update `"roles"` from `["builder"]` to `["builder", "verifier"]`.
- Update `"strengths"` to include `"pr review"`, `"code inspection"`, `"fast iteration"`.

### Layer 2: Dispatch Routing (`synlynk/dispatch.py`)
- Because `HARNESS_CAPABILITY_BASELINES["codex"]["can_gh_write"]` is now `True`, the block at lines 2282–2305 will naturally recognize Codex as capable.
- Dispatches of Codex with `--requires-gh-write` will no longer emit the `#426` warning or auto-reroute to Claude.
- PR #1271's logic in `dispatch_agent()` (auto-granting `_CODEX_NETWORK_PERMISSION` to add `-c sandbox_workspace_write.network_access=true`) remains active and will continue to inject network access whenever `requires_gh_write` is active.

### Layer 3: Fleet Policy Allocation (`.synlynk/policy.json`)
Update `dev_authority.task_allocation`:
- `"review"`: Update to `{"harness": "codex", "fallback": ["claude", "agy"]}` (or give Codex equal primary/fallback standing).
- `"gh_write"`: Update to `{"harness": "codex", "fallback": ["claude", "agy"]}`.

### Layer 4: Living Baseline & Documentation
Per the Harness Capability Reassessment Protocol (`CLAUDE.md` § Harness Capability Reassessment Protocol):
- Update `docs/harness-capability-baseline.md`:
  - Change Codex row:
    - **GitHub write:** **Reliable** (PR #1271 config override; verified in job `job-836e13a4` closing PR #1272 via `synlynk-synlynk-qa` token).
    - **PR review (non-authoring):** **Reliable** (tested live under `job-836e13a4` and unit test suite).
- Update `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md`:
  - Update capability tables to reflect Codex as implementer, tester, reviewer, and CLI-plumber.
  - Remove stale references asserting that Codex sandbox blocks `api.github.com`.

---

## 4. Test-Driven Development (TDD) Strategy

1. **`tests/test_synlynk.py`:**
   - Update `test_can_gh_write_baselines_match_live_verified_reality()`:
     ```python
     assert HARNESS_CAPABILITY_BASELINES["codex"]["can_gh_write"] is True
     ```
2. **`tests/test_dispatch.py`:**
   - In `test_dispatch_agent_requires_gh_write_force_agent_warns_and_proceeds`, replace `"codex"` with `"grok"` (since Grok remains `can_gh_write: False`).
   - Add `test_dispatch_agent_requires_gh_write_allows_codex_without_force_agent`: asserts that dispatching Codex with `requires_gh_write=True` without `force_agent=True` executes without rerouting and without warnings.
3. **`tests/test_agent_cli.py`:**
   - Add `test_codex_harness_baseline_roles_include_verifier()`: asserts that `"verifier"` is present in Codex's baseline roles.

---

## 5. Security & Isolation Invariants

- Non-gh-write dispatches to Codex continue to execute without `run:install`, meaning network egress remains blocked by default for normal local edits.
- Only dispatches with explicit or inferred `requires_gh_write` (or explicit `run:install`) receive network access.
- Subprocess environments continue to be scrubbed of operator host secrets via `_ENV_ALLOWLIST_BASE`.
