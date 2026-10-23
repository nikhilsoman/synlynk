# Muse Capability Readiness — Design Spec

Status: proposed, pending sign-off
Date: 2026-10-23
Related: gh:#2554 (bug this spec fixes), Empirical Capability Assessment Policy (CLAUDE.md), v0.25.3 decision agenda (parent gh:#2458)

## Problem

Three Muse-related surfaces disagree, and one over-grants authority ahead of any empirical evidence:

1. **Capability mismatch.** `synlynk/_constants.py`'s `HARNESS_CAPABILITY_BASELINES["muse"]` sets `can_gh_write: True` and `roles: ["builder", "verifier", "architect"]` — advertising GitHub-write and review/architect authority. But `synlynk/capability_probe.py`'s `HARNESS_CAPABILITY_PROFILES` has **no entry for `muse` at all**, so `evaluate_harness_capabilities()` falls through to the generic default (`CAP_SHELL/CAP_WORKSPACE_WRITE/CAP_NET=True, CAP_GH_WRITE=False`, `CAP_REVIEW` absent). The two sources of truth for "what can Muse do" disagree with each other, and neither one reflects the policy direction below.
2. **Routing gap.** `.synlynk/policy.json`'s `overrides.dev_authority.task_allocation` has no `muse` entry in any task type's `harness` or `fallback` list (confirmed by direct read 2026-10-23) — Muse cannot receive dispatch for `implement`/`test` even though `capability_policy.not_yet_calibrated` already lists it as a harness awaiting its first empirical samples, i.e. the policy already expects Muse to start accumulating `capability_ratings` rows, but routing never sends it anything to be rated on.
3. **Status/probe disagreement.** gh:#2554 reports `synlynk status` showing Muse as `TIER unsupported` / 0 capacity while `synlynk probe` reports `ok`, with a version skew between the two surfaces (1.4.11 vs 1.4.12). Not yet root-caused in this spec — see Plan-stage question below.

## Decision (Nikhil, 2026-10-23, v0.25.3 decision agenda)

Give Muse full **implement/test** authority now. **Review authority (`CAP_REVIEW`) and `CAP_GH_WRITE` beyond what implement/test dispatch needs are explicitly deferred** until Muse clears the same ≥5-merged-job empirical bar every other harness is held to under the Empirical Capability Assessment Policy.

Rationale: the non-authoring-reviewer backstop in the Hardened PR Review Policy protects against a bad *implementation* by Muse (a different harness reviews it) — it does not protect against a bad *review verdict* by Muse itself, since the review step is the backstop with nothing behind it. Granting review authority pre-emptively would remove that safety margin asymmetrically relative to every other harness's onboarding path.

## Proposed design

### 1. Capability profile (`synlynk/capability_probe.py`)

Add an explicit `muse` entry to `HARNESS_CAPABILITY_PROFILES` (currently absent, relying on the generic fallback — making it explicit removes ambiguity and lets this entry diverge from the fallback deliberately):

```python
"muse": {
    CAP_SHELL: True,
    CAP_WORKSPACE_WRITE: True,
    CAP_GH_WRITE: False,   # no review/merge authority yet; implement/test dispatch doesn't require it
    CAP_NET: True,
    CAP_REVIEW: False,     # deferred until Muse clears min_sample_size (5) per Empirical Capability Assessment Policy
},
```

`CAP_GH_WRITE: False` here means Muse cannot be routed to `review`/`gh_write` task types via `evaluate_harness_capabilities()`; it does not block Muse's own implement/test dispatch from making ordinary (non-GH-write) commits inside its worktree.

### 2. Baseline metadata (`synlynk/_constants.py`)

Update `HARNESS_CAPABILITY_BASELINES["muse"]`:
- `can_gh_write: True` → `can_gh_write: False` (matches the capability-profile change above; re-flip when Muse clears the sample bar, same pattern as Grok's `can_gh_write` flip was handled in gh:#2034).
- `roles: ["builder", "verifier", "architect"]` → `roles: ["builder"]`. `verifier`/`architect` imply review/design authority not yet granted. Re-add once empirically cleared.

### 3. Routing (`.synlynk/policy.json`)

Add `muse` to the `fallback` list for `implement` and `test` task types in `overrides.dev_authority.task_allocation` (append after existing fallbacks — Muse is unmeasured, so it is a fallback option, not promoted ahead of calibrated harnesses):

```json
"implement": {"harness": "codex", "fallback": ["grok", "agy", "muse"]},
"test":      {"harness": "codex", "fallback": ["grok", "agy", "muse"]}
```

Do **not** add `muse` to `review`, `gh_write`, `pm`, `brainstorm`, `architecture-review`, or `deploy` entries — consistent with the capability changes above. Per this file's own existing note field, this routing change is recorded as a reviewed-PR edit with its rationale inline (this spec + gh:#2554), not a silent edit.

### 4. Status/probe/capacity consistency

Plan-stage investigation required (not yet root-caused): confirm why `synlynk status` reports Muse `TIER unsupported`/0 capacity while `synlynk probe` reports `ok`, and reconcile the 1.4.11 vs 1.4.12 version-skew source. Likely candidates to check at plan time: (a) `synlynk status`'s capacity/tier computation may read `HARNESS_CAPABILITY_BASELINES` or `task_allocation` (both currently muse-blank) while `probe` reads the live CLI directly — the routing fix in §3 may resolve the 0-capacity symptom as a side effect, but the version-skew needs its own direct check. (b) Confirm both commands' version-string source (hardcoded constant vs. live `muse --version` probe) before assuming the fix.

## Explicitly out of scope for this spec

- Actually promoting Muse to `review`/`gh_write`/`pm`/`deploy` authority — blocked on the ≥5-merged-job empirical bar, tracked for a future reassessment, not this spec.
- Root-causing the version-skew mechanism beyond identifying where to look — deferred to the plan/implementation stage as a concrete investigation step, since it may turn out to be a one-line fix or may need more digging.
- Any change to the sweep/backfill operational runs (decision 5 of the v0.25.3 agenda) — tracked separately, held pending a bounded cost estimate per Nikhil's 2026-10-23 direction.

## Testing

- Unit test: `evaluate_harness_capabilities("muse", {CAP_GH_WRITE})` returns `satisfied=False` (currently would also return False via the generic fallback, but this locks in the explicit entry so a future fallback-default change can't silently re-grant it).
- Unit test: `evaluate_harness_capabilities("muse", {CAP_SHELL, CAP_WORKSPACE_WRITE})` returns `satisfied=True`.
- Config test: `.synlynk/policy.json`'s `implement`/`test` fallback lists include `"muse"`; `review`/`gh_write`/`pm`/`deploy` do not.
- Manual verification: `synlynk status` and `synlynk probe` report consistent capacity/tier for Muse after the routing fix (or, if still inconsistent, the plan's investigation step documents the remaining root cause as a follow-up issue rather than silently leaving it).

## Release

No named release implications — this is a routing/capability-config correctness fix for v0.25.3's Muse readiness gate, not a feature.
