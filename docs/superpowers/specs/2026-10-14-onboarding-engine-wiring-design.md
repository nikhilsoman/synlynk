# Design: Wire the Onboarding-Engine Dead Modules Into Live Commands

**Status:** Proposed (awaiting Nikhil's sign-off)
**Tracking issue:** gh:#2310
**Target branch:** `feat/claude/onboarding-engine-wiring-2310`
**Author:** Claude (home/PM session)
**Supersedes-in-part:** `docs/superpowers/specs/2026-10-01-unified-onboarding-journeys-and-lifecycle-design.md` (that spec's architecture is still correct; this spec only closes the gap between what it describes and what is actually wired into `main`)

## 1. Problem

The 2026-10-01 fleet dispatch (PR #1894) built five modules against the DECIDE panel decision `dec-00b401f2` ("Unified Onboarding Journeys & Self-Updating Lifecycle"). Its completion report claimed "100% Complete & Verified Green (25/25 Tests Passing)." Verified directly against `main` on 2026-10-14 (gh:#2310): four of the five are dead code — built, unit-tested in isolation, never imported by any CLI command, `wizard.py` TUI flow, or Vizor REST surface:

| Module | Status on `main` |
|---|---|
| `synlynk/onboarding_state.py` | Wired — called from `wizard.py` and `viz/server.py` |
| `synlynk/topology_discovery.py` | **Dead** — zero callers outside its own file/tests |
| `synlynk/probe_binding.py` | **Dead** — zero callers. `synlynk probe` (`cli.py`) is unrelated pre-existing harness-version-probe code |
| `synlynk/fleet_templates.py` + `synlynk/version_policy.py` | **Dead** — only import each other |
| `synlynk/first_win_loop.py` | **Dead** — zero callers |
| `synlynk/upgrade.py: upgrade()` | Wired to `synlynk upgrade`, but single-workspace only; no `--all` |

This blocks master-plan item 6 ("auto-upgrade/bundled deps"): the two pieces that item maps to — dependency/harness binding (`probe_binding.py`) and cross-workspace auto-upgrade (`upgrade --all`, informed by `version_policy.py`/`fleet_templates.py`) — do not exist in any reachable form today, despite tests claiming otherwise.

## 2. Non-Goals

- No redesign of the 2026-10-01 architecture. The modules' internal logic (dependency/harness probing, version policy comparison, fleet template merge, first-win diff verification) is sound and stays as-is unless a bug is found while wiring it in.
- No change to `onboarding_state.py` or its existing `wizard.py`/`viz/server.py` integration — that path already works.
- No new "auto" (non-opt-in) upgrade behavior. The 2026-10-01 panel's invariant stands: cross-workspace upgrade stays an explicit command, dry-run-first, with rollback snapshots — never triggered from the daemon.
- No attempt to fully audit or revive Vizor as a whole (that is master-plan item 7, tracked separately per the user's explicit request to treat it as its own audit-and-revival effort).

## 3. Design

### 3.1 `synlynk probe --deps` (wires `probe_binding.py`)

`synlynk probe` currently only probes harness *model* versions (`cli.py:3183` → `cmd_probe` in `synlynk/probe.py`), rewriting capability fences. `probe_binding.py` solves a different, currently-unserved problem: verifying *system* dependencies (git/python/gh/pytest/graphify) and *harness* install+auth status, matching the 2026-10-01 panel's "probe, plan, confirm" invariant for 1-click dependency/harness binding.

Add a `--deps` flag to the existing `probe` subcommand (`cli.py` `probe_parser`) rather than a new subcommand — same mental slot ("check what's available before trusting it"), avoids a second `probe`-shaped command name:

```
synlynk probe --deps [--harness <name>]
```

- Calls `probe_binding.probe_all_dependencies()` and (if `--harness` given) `probe_binding.probe_harness_live(name)`, else `probe_binding.probe_all_harnesses()`.
- Prints a table: dependency/harness, installed?, version, auth status, install hint for anything missing.
- Exit code 0 if nothing is `missing`/`unverified` required by the current fleet template (see 3.2); non-zero otherwise, so it's usable as a preflight gate in CI or `synlynk doctor`.
- No side effects — this is a read-only probe, matching the panel's "never silent/automatic install" rule. If something is missing, the output's `install_hint` is informational only; the human runs it themselves.

### 3.2 `synlynk fleet` (wires `fleet_templates.py`)

New subcommand group, since there's no existing "fleet" command surface to extend:

```
synlynk fleet list                      # fleet_templates.list_fleet_templates()
synlynk fleet apply <template> [--dry-run]
```

- `apply` calls `fleet_templates.apply_fleet_template(repo_dir, template_name)`, which writes `.synlynk/config.json`'s `roles` key. This is the same config shape `cmd_roles`/dispatch routing already reads — confirm via `grep -n '"roles"' synlynk/cli.py` during implementation that `apply_fleet_template`'s output shape matches what `task_allocation`/dispatch routing expects, since it was never exercised end-to-end.
- `--dry-run` prints the template's role table without writing the config.
- No automatic application during `synlynk init` — the panel's decision explicitly says "hold templates and upgrade until a second non-synlynk workspace completes the full loop," so this stays a manual, named command, not a wizard default.

### 3.3 `synlynk upgrade --all` (wires `version_policy.py`, closes the actual "auto-upgrade" gap)

This is the piece that most directly maps to item 6's "auto-upgrade" wording. Add to the existing `upgrade` command:

```
synlynk upgrade --all [--dry-run]
```

- Reads a list of known workspace repo dirs. Source for 2026-10-14: `~/.synlynk/workspaces/*/` registrations (confirm exact registry location/API during implementation — likely the same source `synlynk status`/`synlynk jobs --all` already reads, per `[[stray-local-state-db]]` memory noting the canonical `state.db` path is `~/.synlynk/workspaces/<name>/state.db`).
- For each workspace, calls `version_policy.plan_upgrade([repo_dirs], dry_run=...)` to produce the upgrade plan, then `version_policy.check_version_policy(repo_dir, current_version)` to check whether that workspace's own `min_version` policy is satisfied.
- `--dry-run` (default true unless `--yes` given, matching the existing single-workspace `upgrade --dry-run` convention) prints the plan without applying.
- Applying wraps each workspace's upgrade in the existing `rollback_checkpoint_upgrade()` (already used by single-workspace `upgrade()`) — one checkpoint per workspace, not one global checkpoint, so a failure in workspace 3 of 5 doesn't block rollback of 1-2.
- Never invoked automatically from the daemon or any background path — explicit CLI invocation only, per the panel's invariant.

### 3.4 `first_win_loop.py` — decide fate, don't blindly wire

Unlike the other three, `first_win_loop.execute_first_win_cycle()` already depends on `onboarding_state` internals (`get_or_create_session`, `advance_stage`, `STAGE_S10_BUILD_EXPERIENCE`) and looks designed to be called from the `wizard.py`/`viz/server.py` onboarding flow at the final "build experience" stage — but nothing calls it. Two options, pick during implementation after re-reading `wizard.py`'s current S10 handling:

- **(a)** If `wizard.py`/`viz/server.py`'s S10 stage currently does nothing or something shallower, wire `execute_first_win_cycle()` in as the real implementation.
- **(b)** If S10 already has different, working logic that supersedes this module's intent, retire `first_win_loop.py` (delete + remove its test file) rather than wire in a second, conflicting S10 implementation.

Do not wire it in without first confirming which case applies — this module's `verify_first_win_effect()` (git-diff-based) duplicates logic that may already exist elsewhere for CI/test verification; check for an existing diff-check helper before assuming this is the only one.

### 3.5 `topology_discovery.py` → `onboarding_state.py` integration

`onboarding_state.py` is already wired into `wizard.py`/`viz/server.py` for topology *confirmation* (`confirm_topology` is imported at `viz/server.py:294`), but the discovery *engine* that's supposed to feed evidence-scored candidates into that confirmation step (`topology_discovery.py`) is never called. Read `confirm_topology`'s current implementation first — if it already does its own ad hoc discovery inline, this task is "replace that inline logic with `topology_discovery.py`'s scored-archetype output"; if it expects a topology to already exist with no discovery step at all, this task is "call `topology_discovery.py` before `confirm_topology` and feed its result in."

## 4. Testing

- Existing unit tests (`test_probe_binding.py`, `test_fleet_version_engine.py`, `test_first_win_loop.py`, `test_onboarding_topology.py`) stay as regression coverage for the modules' internal logic — they were legitimately passing, just insufficient.
- New integration tests, one per wired command, that actually invoke the CLI entry point (`synlynk probe --deps`, `synlynk fleet list`/`apply`, `synlynk upgrade --all --dry-run`) and assert on real output/side effects — not just the underlying module function in isolation. This is the exact gap that let PR #1894 ship dead code undetected; closing it is the point of this spec, not an afterthought.
- Full suite via `pytest -q` (per the gh:#2240 cost-inflation fix — never `-v` on a dispatched job's full-suite run).

## 5. Rollout

1. This spec + the accompanying plan, committed on this branch, opened as a PR, reviewed and merged first (mirrors item 5/gh:#2305's sequence).
2. Build dispatched per-task to Codex/Grok (not Agy — per standing feedback memory on Agy's repeated timeout/billing failures), one PR per task in §3.1-3.5, each independently reviewable.
3. Cross-harness+model review required per CLAUDE.md's Hardened PR Review Policy — same as every PR this session.

## 6. Open Questions for Implementation (not blocking spec approval)

- Exact source of "all known workspaces" for `upgrade --all` (§3.3) — needs one grep pass into `~/.synlynk/workspaces/` registry code before Task 3 starts.
- Whether `fleet_templates.apply_fleet_template`'s `config["roles"]` shape actually matches what dispatch routing reads (§3.2) — flagged as a risk, not resolved here.
- `first_win_loop.py`'s fate (§3.4) — wire in or retire, decided by reading current `wizard.py` S10 behavior at implementation time, not here.
