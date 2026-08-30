# PR #1275 — Granting Codex Full Harness Parity Across Review and GitHub-Write Tasks

## Where we left off

In PR #1271, we landed direct config-override network access (`-c sandbox_workspace_write.network_access=true`) for OpenAI Codex under `--requires-gh-write`. Immediately following that merge, we proved the capability empirically: in job `job-836e13a4`, Codex executed inside its sandboxed runner to inspect PR #1272, post an audit comment via `gh pr comment`, and close the PR via `gh pr close` under its role-scoped GitHub App identity (`synlynk-synlynk-qa`).

However, Codex remained structurally prevented from receiving ordinary review or GitHub-write tasks due to a legacy 4-layer lockout that originated in issue #426. Any dispatch to Codex with `--requires-gh-write` would automatically warn and reroute the task to Claude (`rerouted_to = capable_agents[0]`), unless an operator manually passed `--force-agent`.

Issue #1274 was opened to permanently remove this bypass and grant Codex full first-class harness parity across review and GitHub-write tasks.

## The 4-Layer Lockout Dismantled

PR #1275 updated all four layers that previously restricted Codex:

1. **Core Capability Baselines (`synlynk/_constants.py`):**
   - Flipped `HARNESS_CAPABILITY_BASELINES["codex"]["can_gh_write"]` from `False` to `True`.
   - Added `"verifier"` to Codex's baseline roles: `["builder", "verifier"]`.
   - Updated `strengths` to include `"pr review"`.

2. **Dispatch Auto-Rerouting (`synlynk/dispatch.py`):**
   - With `can_gh_write: True`, `dispatch_agent("codex", ..., requires_gh_write=True)` no longer triggers the #426 capability gate rerouting.
   - Codex dispatches proceed natively to execution without requiring `--force-agent` or emitting capability warnings.

3. **Fleet Policy & SOP Generation (`.synlynk/policy.json`, `synlynk/policy.py`, `synlynk/probe.py`):**
   - Updated `.synlynk/policy.json` and `synlynk/policy.py`:
     - `"review": {"harness": "codex", "fallback": ["claude", "agy"]}`
     - `"gh_write": {"harness": "codex", "fallback": ["claude", "agy"]}`
   - Updated `synlynk/probe.py` so initialized instruction tables dynamically route GitHub-write tasks to Codex by default, preventing future doc updates from reverting to Claude-only routing.

4. **Living Baseline Records & Directives:**
   - Updated `docs/harness-capability-baseline.md` to classify Codex as **Reliable** for both headless GitHub writes and non-authoring PR reviews.
   - Updated `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md` to align all agent instructions with the new fleet allocation.

## Test-Driven Development & Verification

The changes were backed by unit tests verifying the new behavior:
- `test_can_gh_write_baselines_match_live_verified_reality` in `tests/test_synlynk.py` asserting `can_gh_write` is `True` for Codex.
- `test_dispatch_agent_requires_gh_write_allows_codex_without_reroute` in `tests/test_dispatch.py` asserting dispatch does not reroute or warn.
- `test_codex_harness_baseline_includes_verifier_role_and_can_gh_write` in `tests/test_agent_cli.py`.
- Updated `test_dispatch_agent_requires_gh_write_force_agent_warns_and_proceeds` to target `grok` (the only remaining harness lacking headless shell writes).

All 2,349 tests passed cleanly across Python 3.8, 3.10, and 3.12 CI runners.

## Review and Merge Flow

- **Authorship:** Implemented by Codex via `synlynk dispatch` (`job-6144fa68` on base `feat/1274-codex-full-harness-parity`).
- **Review:** Reviewed by Agy (`synlynk pr check` passed, test verification verified green, approval review posted).
- **Merge:** Merged to `main` as `582b0f1153498c72aa4747a1dd242b52d9c47321`.

## Where this leaves the long-arc goal

OpenAI Codex is now an authorized, capable, and trusted first-class harness for all coding, testing, reviewing, and GitHub-write tasks across the synlynk fleet. With Claude currently constrained by quota and Grok undergoing headless permission mode stabilization, Codex provides critical resilience and execution bandwidth for autonomous operations.
