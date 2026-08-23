# gh-write Identity Hardening (Phase 1 Closeout) — Design

**Date:** 2026-08-23
**Status:** Approved (pending final user sign-off on this written doc)
**Author:** Claude (pm), brainstormed with Nikhil Soman
**Relates to:** #423 (GitHub identity limitation), #569 (fail-closed token resolution), #426 (gh-write routing table)
**Superseded by (future):** `docs/superpowers/specs/2026-08-19-gh-write-broker-design.md` (resolves #865) — see §5.

## 1. Motivation

This session live-tested #423's role-scoped GitHub App write identity end-to-end for the first time, on two harnesses:

- **Agy** (`job-488c152f`) — succeeded, but only after fixing a real synlynk bug (`_run_tc7()` checked `settings["allowRules"]`, a key that doesn't exist in the actual `~/.gemini/antigravity-cli/settings.json` schema; the real path is `settings["permissions"]["allow"]`, filed as issue #1106, fixed in PR #1107) and required discovering, by reading dispatch code directly, that `--requires-gh-write` alone is not sufficient — a separate `--grant run:shell` is needed or the dispatch fails closed with `PermissionEnforcementError`.
- **claude** (`job-a7ab9a0c`) — succeeded cleanly on the first attempt with just `--grant run:shell` added up front, no preflight bugs, no local operator-config precondition, ~3x cheaper and faster than the Agy path.

Both results were independently verified against the live GitHub API (`gh pr view 1105 --json reviews`), not taken on the dispatched job's own self-report — both reviews on PR #1105 were confirmed authored by the distinct App bot login `synlynk-synlynk-dev`, not the shared personal `nikhilsoman` account.

Meanwhile, CLAUDE.md's #426 routing table still states "route gh-write to Grok by default." This is now empirically false in this environment: Grok's dispatch sandbox denies `bash` entirely (`job-3e428904` reported "OK, exit 0" but `git diff origin/main` showed zero real change — a total silent no-op at the harness level, masked by a misleadingly generic job status). Codex remains blocked by `workspace-write` sandbox network egress rules to `api.github.com` (pre-existing, not re-tested this session). The static `HARNESS_CAPABILITY_BASELINES` table in `synlynk/_constants.py` also disagrees with observed reality (`agy.can_gh_write: False` despite a live-proven successful write; `grok.can_gh_write: True` despite a live-proven total failure) — whatever routing logic reads that table is working from stale data.

This design closes three concrete gaps surfaced by those tests so Phase 1 of the informal "full autonomy roadmap" (`project-docs/memory.md`, 2026-08-22 entry) can be marked done: **branch protection can be turned on for real, backed by role-scoped identities, not just "the mechanism is provably reachable in isolation."**

## 2. Scope

In scope — three targeted changes to `synlynk/dispatch.py` / `synlynk/_constants.py`, plus one CLAUDE.md correction:

1. Fix the gh-write harness default and the stale capability baseline data it reads from.
2. Make `--requires-gh-write` auto-imply the `run:shell` permission.
3. Fail closed (not silently default to `dev`) when no role is resolvable for a gh-write dispatch.

Out of scope: rebuilding role-to-story tagging infrastructure (existing `_role_for_story` machinery is reused, not replaced), Phase 2 (porting the qa-gate pattern to rxcc), actually configuring GitHub branch protection rules, and — critically — the gh-write broker (§5).

## 3. Design

### 3.1 Harness default: claude primary, Agy fallback

`HARNESS_CAPABILITY_BASELINES` in `synlynk/_constants.py` gets its `can_gh_write` values corrected to match live-tested reality:

| harness | current value | corrected value | basis |
|---|---|---|---|
| `claude` | `True` | `True` (unchanged, now confirmed) | `job-a7ab9a0c`, live-verified |
| `agy` | `False` | `True` | `job-488c152f`, live-verified (post TC-7 fix) |
| `grok` | `True` | `False` | `job-3e428904`, live-verified failure (sandbox denies bash) |
| `codex` | `False` | `False` (unchanged) | pre-existing, network egress sandboxed |
| `local` | `False` | `False` (unchanged) | not exercised this session, no change in evidence |

Routing logic that consults this table (`_harness_for_org_role`, and the `--force-agent`-absent auto-selection path used by `--requires-gh-write`) will pick `claude` first when no explicit harness is named, and fall back to `agy` if `claude` is unavailable (e.g., not installed, or its own preflight fails). This is a data correction plus an ordering preference, not new routing machinery — `_harness_for_org_role` already iterates candidates in a defined order; `claude` needs to sort before `agy` for gh-write-eligible candidates specifically.

CLAUDE.md's Capability-Based Task Allocation section gets its gh-write routing line corrected:

> **GitHub write routing (#426):** ~~Route any task that requires GitHub write actions to **Grok by default**.~~ Route any task that requires GitHub write actions to **claude by default, Agy as fallback** (live-verified 2026-08-23; see `docs/superpowers/specs/2026-08-23-gh-write-identity-hardening-design.md`). Grok's dispatch sandbox denies `bash` execution entirely in this environment (confirmed via `git diff origin/main` showing a total silent no-op despite a generic "OK, exit 0" job status — do not trust job-status alone for Grok gh-write attempts). Codex's `workspace-write` sandbox blocks network egress to `api.github.com` by design.

### 3.2 `--requires-gh-write` auto-implies `run:shell`

In `_permissions_to_flags` (or the permission-resolution step that calls it — `_build_subprocess_env`/the dispatch call site that assembles the effective `permissions` list before flags are computed), when `requires_gh_write` is `True`, add `"run:shell"` to the effective permission set unconditionally, before task-type defaults (`_ROLE_PERMISSION_DEFAULTS`) are applied and before the agy read-only-only check runs. This means a `--task-type review` dispatch (whose default profile is `["read:*"]`) with `--requires-gh-write` set no longer needs the caller to separately remember `--grant run:shell` — gh-write inherently requires shell execution to invoke `gh`, so requiring both flags in tandem was redundant, not a safety feature.

`--grant`/`--revoke` continue to work unchanged for every other permission. This does not weaken the agy `PermissionEnforcementError` check for genuinely read-only-only dispatches that don't declare `--requires-gh-write` — that path is untouched.

### 3.3 Fail closed on unresolvable role for gh-write

Today, role resolution for a gh-write dispatch falls back silently: `agent_role or _role_for_story(story_id) or "dev"`. This conflates identities #423 was built to separate — e.g., a review-type gh-write dispatch with no `--story`/`--as-agent` currently authenticates as `dev`, not as whatever role is semantically doing the reviewing (`qa`, `pm`, etc.).

New behavior: when `requires_gh_write` is `True`, remove the `or "dev"` fallback. Role must be resolvable via one of:
- `--as-agent <registered-agent-id>` (existing)
- `--story <id>` where the story has a tagged `role` column (existing, via `_role_for_story`)
- a new explicit `--role <role>` dispatch flag (new — the supported path for ad-hoc/manual dispatches, like the live tests run this session, that don't have a registered story or agent)

If none resolve, raise the same class of fail-closed error `_resolve_dispatch_gh_token` already raises when no token is provisioned for a role — a `RuntimeError` before any subprocess is spawned, not a silent `dev`-role write. Non-gh-write dispatches are unaffected; `dev` remains the default there.

## 4. Testing

Unit tests (mirroring the TC-7 regression-test pattern from PR #1107):
- `--requires-gh-write` with no other grants produces an effective permission set containing `run:shell`.
- `--requires-gh-write` with no resolvable role (`--as-agent`, `--story` with tagged role, or `--role` all absent) raises before subprocess spawn.
- `--requires-gh-write` with `--role qa` (no story/agent) resolves and authenticates as `qa`, not `dev`.
- Harness auto-selection for a gh-write dispatch with no `--force-agent` picks `claude` when available; falls back to `agy` when `claude` preflight fails; does not pick `grok`.

No live re-test is required for this spec's own automated tests. However, Phase 1's actual exit criterion — branch protection turned on for real — needs one further live dispatch after this ships, using an explicit named role (e.g. `--role qa`), as final validation that the fail-closed role check and the new default routing work together in practice. That live-test-and-flip-branch-protection step is a Phase 1 completion task tracked separately, not part of this spec's test suite.

## 5. Relationship to the gh-write broker design (#865)

`docs/superpowers/specs/2026-08-19-gh-write-broker-design.md` (approved, blogged, resolves closed issue #865) describes a structurally stronger fix: a non-LLM broker process that mediates every GitHub write, keeps installation tokens out of the agent's sandbox entirely (never as an env var, never in a worktree file), and — critically — requires removing direct `gh` CLI and GitHub MCP write-tool access from every harness with `can_gh_write: true`, so the broker becomes the *only* path capable of a write, not merely the recommended one.

That design was never implemented (no `gh_broker.py`, no implementation plan, nothing tracked in `project-docs/memory.md` as active work) — it is an orphaned approved spec.

**This design (§3) is explicitly an interim hardening of the mechanism the broker was designed to retire**, not a replacement for it. The live tests this session (both Agy and claude directly invoking `gh pr review` with an injected installation token) are a working instance of exactly the unenforced-bypass gap §4 of the broker design calls out: *"Grok, Claude, and Agy... retain live `gh` CLI and GitHub MCP tool access by default, so a prompt instructing 'use the broker instead' is a convention, not enforcement."* Hardening §3.1–3.3 makes the current mechanism safer to rely on for Phase 1's near-term exit criterion (branch protection live, role-scoped identities behind it), but does not close that structural gap.

**Action:** file a tracking issue reviving the broker design as "Phase 1b" — the next real architectural step once Phase 1 (this spec) ships — rather than leaving it silently orphaned. This spec's implementation plan should not attempt to build the broker; that remains a separate, larger effort with its own plan.
