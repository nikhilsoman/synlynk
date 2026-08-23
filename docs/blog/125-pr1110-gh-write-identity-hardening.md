# PR #1110 — gh-write Identity Hardening: Phase 1 Closeout (#423)

**PR:** [#1110](https://github.com/nikhilsoman/synlynk/pull/1110)
**Date:** 2026-08-23
**Relates to:** #423, #569, #426

## Goal at the end of the previous PR

The immediately preceding PR (#731, v1.0 UX consolidation) landed a lesson about full-suite regression discipline, but the thread this PR actually continues goes back further: PR #517 built synlynk's per-role GitHub App identity system — each role (`dev`, `qa`, `architect`, etc.) can carry its own scoped GitHub App token, so a dispatched job's writes are attributable to the role doing the work, not to one shared personal account. That system had shipped, but as of this session it had never been live-tested end-to-end against a real PR. The informal "full autonomy roadmap" captured in `project-docs/memory.md` (2026-08-22 entry) named turning on real GitHub branch protection, backed by these role-scoped identities, as Phase 1's exit criterion — but nobody had actually dispatched a job that posted a real `gh pr review` under a role identity and checked whether it worked.

## What moved the goalpost this PR

This session ran that live test for the first time, on two harnesses:

- **Agy** (`job-488c152f`) — succeeded, but only after finding and fixing a real bug: `_run_tc7()` was checking `settings["allowRules"]`, a key that doesn't exist in the actual `~/.gemini/antigravity-cli/settings.json` schema (the real path is `settings["permissions"]["allow"]`). Filed as #1106, fixed in #1107. Also required discovering — by reading dispatch source directly, not from any doc — that `--requires-gh-write` alone wasn't sufficient; a separate `--grant run:shell` was needed, or the dispatch failed closed with `PermissionEnforcementError`.
- **claude** — succeeded cleanly on the first attempt with just `--grant run:shell` added up front. No preflight bugs, no local operator-config precondition, roughly 3x cheaper and faster than the Agy path.

Both results were verified against the live GitHub API (`gh pr view 1105 --json reviews`), not taken on the dispatched jobs' own self-reports — both reviews were confirmed authored by the distinct App bot login `synlynk-synlynk-dev`, not the shared personal account.

That test also surfaced that CLAUDE.md's #426 routing table ("route gh-write to Grok by default") was empirically false: Grok's dispatch sandbox denies `bash` entirely (`job-3e428904` reported "OK, exit 0" but `git diff origin/main` showed zero real change — a silent no-op masked by a misleading job status). The static `HARNESS_CAPABILITY_BASELINES` table in `synlynk/_constants.py` disagreed with observed reality in both directions: `agy.can_gh_write` was `False` despite a live-proven success, `grok.can_gh_write` was `True` despite a live-proven total failure.

Rather than re-litigating the identity/token architecture itself (already built, per #517), this PR scoped down to three concrete gaps the live test exposed, captured in a design doc (`docs/superpowers/specs/2026-08-23-gh-write-identity-hardening-design.md`) before any code was touched.

## What this PR shipped

Executed via `superpowers:subagent-driven-development` — one fresh Codex dispatch per task, spec-compliance and code-quality review against the actual diff before merging each one, PM/review/deploy work staying in this session per this project's role split.

1. **Corrected harness capability data** (`synlynk/_constants.py`): `agy.can_gh_write` False→True, `grok.can_gh_write` True→False, matching the live-tested results above.
2. **Harness selection ordering** (`synlynk/dispatch.py`, `_harness_for_org_role`): a new `_GH_WRITE_HARNESS_PRIORITY = ("claude", "agy")` constant makes gh-write auto-selection prefer claude, then agy — never grok — while leaving non-gh-write selection alphabetical and unchanged.
3. **#426 routing SOP correction** (`synlynk/probe.py`, both the static `_CAPABILITY_ALLOCATION_SOP` template and the dynamic `_repair_capability_allocation_sop` generator, which regenerate the checked-in CLAUDE.md): replaced "Route any task that requires GitHub write actions to Grok by default" with the corrected claude-primary/Agy-fallback text and the concrete sandbox-limitation reasoning (Grok denies bash, Codex blocks network egress to `api.github.com`).
4. **`--requires-gh-write` now auto-implies `run:shell`** (`synlynk/dispatch.py`): a `requires_gh_write=True` dispatch injects `"run:shell"` into `effective_grants` before `_resolve_dispatch_permissions` builds the final permission set — closing the exact friction this session's own live test hit (forgetting the separate `--grant run:shell` flag).
5. **Fail-closed role resolution for gh-write** (`synlynk/dispatch.py`, `synlynk/cli.py`): the old `agent_role or _role_for_story(story_id) or "dev"` fallback silently authenticated every unlabeled gh-write dispatch as the `dev` role — defeating #423's whole point of separating identities by role. That `or "dev"` is now removed for `requires_gh_write=True` dispatches; if no role resolves via `--as-agent`, a role-tagged `--story`, or the new `--role <role>` flag, `dispatch_agent` and `_build_subprocess_env` both raise `RuntimeError` before any subprocess spawns.

Five new unit tests were added across `tests/test_synlynk.py` covering: the `run:shell` auto-imply (and its non-gh-write no-op counterpart), the fail-closed raise with no role, `--role qa` resolving correctly, and the `_build_subprocess_env`-level equivalents. Two pre-existing gaps were caught by the two-stage review process rather than shipping silently: a stray dangling markdown bullet left in the regenerated CLAUDE.md, and — found only during the Task 6 full-suite run — a stale, unrelated test assertion (`test_directive_templates_contain_sop_headers`) still literally checking for the superseded `"Grok only"` table text, which the Task 3 dispatch had correctly left alone (it was out of that task's declared scope) but which the merge nonetheless broke. Both were fixed as targeted follow-up dispatches rather than folded silently into an earlier commit.

One recurring friction worth naming: this session's own `--requires-gh-write` auto-detection regex (`_task_requires_gh_write`) kept false-positiving on the dispatch prompts for Tasks 4 and 5, because those tasks' required code content literally contains the string `--requires-gh-write` — and `\bgh\b` matches "gh" even hyphen-bounded. For Task 5 and Task 4, the prompts couldn't be reworded around it (the trigger was in code the plan required, not incidental prose), so dispatch used the project's own documented `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1` escape hatch, verified safe because no role in this sandbox has a provisioned GitHub App token in the first place, and because both dispatched jobs' own instructions explicitly forbade touching `gh` at all.

## Brainstorm visuals

None were created for this design — the three fixes were narrow and code-shaped, not architectural or visual.

## What this achieves on the path to autonomy

Phase 1 of the full-autonomy roadmap's stated exit criterion — "branch protection can be turned on for real, backed by role-scoped identities" — depended on the identity mechanism actually working under realistic conditions (no manually-remembered extra flags, no silent identity conflation, correct default routing). This PR closes exactly those three gaps. It deliberately does not build the gh-write broker described in `docs/superpowers/specs/2026-08-19-gh-write-broker-design.md` (#865) — that design would make the broker the *only* path capable of a GitHub write by removing direct `gh`/MCP write access from every harness, which is a structurally stronger but separate effort. This PR is explicit interim hardening of the mechanism the broker is meant to eventually retire; a tracking issue (#1109) keeps that "Phase 1b" work from going silently orphaned.

## Next goalpost

One live dispatch remains before Phase 1 can be marked fully done: a real `--role qa` (or similar) dispatch against a live PR, using the new fail-closed path and corrected default routing together, followed by actually turning on GitHub branch protection backed by that role's identity. That live-test-and-flip-protection step is Phase 1's true completion task, tracked separately from this PR's automated test suite. Once done, Phase 2 — porting the same qa-gate pattern to rxcc — can start.
