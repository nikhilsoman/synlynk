# Muse Capability Readiness — Implementation Plan

Status: ready for dispatch
Date: 2026-10-23
Spec: `docs/superpowers/specs/2026-10-23-muse-capability-readiness-design.md` (approved, merged via PR #2556)
Related: gh:#2554, Empirical Capability Assessment Policy (CLAUDE.md), v0.25.3 decision agenda (parent gh:#2458)

## Scope

Narrow Muse's existing over-grant of review/GitHub-write authority down to implement/test only, and make routing consistent with that narrowing. Four concrete edits, in one PR, by one dispatched implementer, reviewed by a harness+model different from the implementer per the Hardened PR Review Policy.

## Steps

### 1. `synlynk/capability_probe.py`

In `HARNESS_CAPABILITY_PROFILES["muse"]` (currently lines ~64-72 on `origin/main`):
- Change `CAP_GH_WRITE: True` → `CAP_GH_WRITE: False`.
- Change `CAP_REVIEW: True` → `CAP_REVIEW: False`.
- Replace the existing comment ("Provisionally enable calibration dispatches...") with one noting the narrowing, dated, citing this plan + gh:#2554 — same pattern as the Grok `CAP_GH_WRITE` history comment already in this file (lines ~51-57).
- Leave `CAP_SHELL`, `CAP_WORKSPACE_WRITE`, `CAP_NET` as `True`.

### 2. `tests/test_capability_taxonomy.py`

`test_muse_profile_allows_review_and_github_write_calibration` (lines 45-55) currently asserts the *opposite* of the target state — it asserts `CAP_GH_WRITE`/`CAP_REVIEW` are both granted. This test must be replaced, not left failing:
- Rename to `test_muse_profile_denies_review_and_github_write_pending_calibration`.
- Assert `evaluate_harness_capabilities("muse", {CAP_SHELL, CAP_WORKSPACE_WRITE})` → `allowed=True`.
- Assert `evaluate_harness_capabilities("muse", {CAP_GH_WRITE})` → `allowed=False`, `CAP_GH_WRITE` in `missing_capabilities`.
- Assert `evaluate_harness_capabilities("muse", {CAP_REVIEW})` → `allowed=False`, `CAP_REVIEW` in `missing_capabilities`.

Check `tests/test_muse_harness.py` for any other assertion depending on the old all-`True` profile (`test_muse_baseline_schema_tc0` at line 28 reads `HARNESS_CAPABILITY_BASELINES`, not `HARNESS_CAPABILITY_PROFILES` — distinct dict, see step 3 — confirm it doesn't also assert `can_gh_write is True` in a way step 3 would break; update if so).

### 3. `synlynk/_constants.py`

In `HARNESS_CAPABILITY_BASELINES["muse"]` (lines ~298-338):
- Change `"can_gh_write": True` → `"can_gh_write": False`.
- Change `"roles": ["builder", "verifier", "architect"]` → `"roles": ["builder"]`.
- Leave every other field (`cli`, `dispatch_flags`, `headless_contract`, `network_deps`, `auth_check`, `env_passthrough`, `strengths`) unchanged.

Re-check `tests/test_muse_harness.py::test_muse_baseline_schema_tc0` against this change; update its assertions if it checks `can_gh_write` or `roles`.

### 4. `.synlynk/policy.json`

In `overrides.dev_authority.task_allocation`:
- `implement.fallback`: `["grok", "agy"]` → `["grok", "agy", "muse"]`.
- `test.fallback`: `["grok", "agy"]` → `["grok", "agy", "muse"]`.
- Do not touch `review`, `gh_write`, `pm`, `brainstorm`, `architecture-review`, `deploy`, or any other task type.
- Add a one-line comment/note field (matching this file's existing annotation style) citing this plan + gh:#2554 for the routing change, consistent with the Empirical Capability Assessment Policy's requirement that `task_allocation` edits be traceable to a reviewed PR, not silent.

Add or update a config test (if one exists covering `task_allocation` shape, e.g. under `tests/test_policy*.py` — locate via `grep -rl "task_allocation" tests/`) asserting `"muse" in policy["overrides"]["dev_authority"]["task_allocation"]["implement"]["fallback"]` and the same for `test`, and asserting `"muse" not in [...]["review"]["fallback"]` / `["gh_write"]["fallback"]`.

### 5. Status/probe/capacity investigation (bounded, time-boxed)

Per the spec's §4, this is scoped as an investigation, not a guaranteed fix:
- Compare `synlynk status`'s muse tier/capacity computation (locate via `grep -n "muse" synlynk/status.py synlynk/__init__.py synlynk/vizor_daemon.py`) against `synlynk/probe.py`'s muse handling (confirmed present at lines ~1004 and ~1219 — `probe.py` invokes the live `muse` CLI directly via `subprocess.run([cli_bin, "exec", "--json", "--approval-mode", "never", ...])`).
- Check whether `status`'s capacity/tier reads `HARNESS_CAPABILITY_BASELINES`/`task_allocation` (both currently muse-blank on `fallback` before step 4, which step 4 partially addresses) versus `probe`'s live subprocess call — if `status` was keying "0 capacity" off the routing gap, step 4 may resolve it as a side effect.
- Separately confirm the 1.4.11 vs 1.4.12 version-skew source: check whether `status` and `probe` read the muse CLI version from the same place (a live `muse --version` call vs. a cached/stored value such as `harness_version_history`, referenced in `probe.py` around lines 690/1271/1291).
- **Time-box:** spend no more than ~30 minutes of dispatched-job time on this step. If root-caused, fix it in this same PR. If not root-caused within the time-box, file a follow-up issue with findings so far (what was checked, what wasn't) rather than leaving it silently unresolved — do not block the rest of this PR on it.

## Testing

- `pytest tests/test_capability_taxonomy.py tests/test_muse_harness.py -q` — must pass with the updated assertions from steps 2-3.
- Any `task_allocation`/policy config test touched by step 4.
- Full suite (`pytest -q`) to confirm no regression elsewhere — current `origin/main` baseline is 1568 passed, 2 skipped, 3 environment-only failures (missing website fixture/path, occupied daemon port), per the PR #2556 reviewer's verification; this PR's changes should not add to that failure count.
- Manual: `synlynk status` and `synlynk probe` reports for muse, before/after, captured in the PR description.

## Out of scope (per spec)

- Promoting Muse to `review`/`gh_write`/`pm`/`deploy` — blocked on the ≥5-merged-job empirical bar.
- The sweep/backfill operational runs (held separately per the v0.25.3 decision agenda, decision 5).
- #2547 (harness-velocity investigation) — untouched.

## Dispatch

Task type: `implement` (per `.synlynk/policy.json`, routes to `codex`, fallback `grok`/`agy` — this PR's own change extends that fallback list to include `muse`, but `muse` itself should not implement this PR, since it is the subject of the capability narrowing and has no track record yet).

Reviewer: cross-harness+model different from the implementer, per Hardened PR Review Policy. Follow the same dry-run → dispatch → verify-via-`gh pr view`-directly → Worktree Hygiene Protocol cleanup sequence used for PR #2555 and PR #2556 in this session.

## Release

No named-release implications — routing/capability-config correctness fix, not a feature.
