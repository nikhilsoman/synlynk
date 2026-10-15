# Plan: Wire Onboarding-Engine Dead Modules Into Live Commands

**Spec:** `docs/superpowers/specs/2026-10-14-onboarding-engine-wiring-design.md`
**Tracking issue:** gh:#2310

## Task 1 — `synlynk probe --deps` (wires `probe_binding.py`)
- [ ] Add `--deps` flag to the existing `probe` subparser in `synlynk/cli.py`.
- [ ] New `cmd_probe_deps(harness: str | None)` calling `probe_binding.probe_all_dependencies()` + `probe_binding.probe_all_harnesses()` (or single-harness variant if `--harness` given).
- [ ] Table output: dependency/harness, installed?, version, auth status, install hint.
- [ ] Exit code non-zero if any required dependency/harness is `missing`/`unverified`.
- [ ] Integration test invoking the real CLI entry point (`subprocess` or direct `main()` call with `["probe", "--deps"]`), not just `probe_binding`'s functions directly.
- [ ] `pytest -q tests/test_probe_binding.py tests/test_cli_probe_deps.py` green.

## Task 2 — `synlynk fleet list` / `synlynk fleet apply` (wires `fleet_templates.py`)
- [ ] New `fleet` subcommand group in `synlynk/cli.py` with `list` and `apply <template>` actions.
- [ ] `apply` supports `--dry-run` (print role table, no write).
- [ ] Before wiring the write path, grep `cli.py`/dispatch routing for how `.synlynk/config.json`'s `roles` key is actually read, and confirm `fleet_templates.apply_fleet_template()`'s output shape matches — fix the shape on either side if it doesn't, call out any mismatch found.
- [ ] Integration test for both `list` and `apply --dry-run` via the real CLI entry point.
- [ ] `pytest -q tests/test_fleet_version_engine.py tests/test_cli_fleet.py` green.

## Task 3 — `synlynk upgrade --all` (wires `version_policy.py`)
- [ ] Locate the existing workspace registry (`~/.synlynk/workspaces/*/`) read path used by `synlynk status`/`synlynk jobs --all`; reuse it, don't invent a second one.
- [ ] Add `--all` flag to `upgrade` subparser; when set, iterate registered workspaces, call `version_policy.plan_upgrade()` then `version_policy.check_version_policy()` per workspace.
- [ ] `--dry-run` prints the plan without applying (default behavior unless `--yes`).
- [ ] Apply path wraps each workspace's upgrade in its own `rollback_checkpoint_upgrade()` call — one checkpoint per workspace.
- [ ] Never invoked from the daemon or any background/automatic path — CLI-only, explicit invocation.
- [ ] Integration test: multi-workspace dry-run plan output via real CLI entry point.
- [ ] `pytest -q tests/test_fleet_version_engine.py tests/test_upgrade_all.py` green.

## Task 4 — `first_win_loop.py` fate decision
- [ ] Read current `wizard.py`/`viz/server.py` S10 (`STAGE_S10_BUILD_EXPERIENCE`) handling before writing any code.
- [ ] If S10 has no real implementation yet: wire `first_win_loop.execute_first_win_cycle()` in as the handler.
- [ ] If S10 already has a working, different implementation: delete `synlynk/first_win_loop.py` + `tests/test_first_win_loop.py`, note why in the PR description.
- [ ] Check for an existing git-diff-based verification helper elsewhere in the codebase before keeping `verify_first_win_effect()` — dedupe if one already exists.
- [ ] Either way, PR description states which branch of this decision was taken and why.

## Task 5 — `topology_discovery.py` → `onboarding_state.py` integration
- [x] Read current `confirm_topology()` implementation (called from `viz/server.py:294`) to determine whether it does its own inline discovery or expects a pre-existing topology.
- [x] Wire `topology_discovery.py`'s evidence-scored archetype discovery into whichever point in the flow currently lacks it (either replacing inline logic, or feeding `confirm_topology` before it runs).
- [x] Integration test exercising the real `wizard.py` or `viz/server.py` entry point, not `topology_discovery.py` in isolation.
- [x] `pytest -q tests/test_onboarding_topology.py tests/test_onboarding_state.py` green.

**Decision (job-3466d7fc):** `confirm_topology()` has no inline discovery — it only persists.
Wired by calling discovery before confirm (`propose_topology` /
`discover_and_confirm_topology`) from `viz/server.py` confirm handler and wizard S4 advance.
Integration test hits `VizorHandler.do_POST`.

## Sequencing
Tasks 1-3 are independent of each other and of Tasks 4-5 — dispatch in parallel. Task 4 and Task 5 both touch the `wizard.py`/`viz/server.py` onboarding flow — dispatch sequentially (Task 5 first, since Task 4's S10 decision may depend on whether topology discovery changes anything upstream) to avoid merge conflicts on the same files.

## Verification (every task)
- `pytest -q` (not `-v` — gh:#2240) full suite green before PR.
- Cross-harness+model review per CLAUDE.md's Hardened PR Review Policy.
- `synlynk pr check` from within the task's own worktree before merge.
