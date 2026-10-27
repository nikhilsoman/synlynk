# Plan: v0.26.5 Graphify lifecycle and warm traversals

**Status:** Blocked on sign-off of `docs/superpowers/specs/2026-10-28-v0265-graphify-mesh-design.md`.
**Goal:** `goal-e3840370`
**Epic:** [#2470](https://github.com/nikhilsoman/synlynk/issues/2470)
**Release:** v0.26.5
**Authored:** 2026-10-27
**Branch:** `feat/grok/v0265-graphify-mesh`
**Worktree:** `.worktrees/feat-grok-v0265-graphify-mesh`
**Base:** `6169b63a`

Do not dispatch implementation tasks from this plan until Nikhil accepts the spec. One implementation PR follows. The version bump and release notes are a later release PR.

Each task is test-first. The autouse stub in `tests/conftest.py` stays. Tests that need a fake extract opt out with `no_stub_graphify_extract` and patch `subprocess.run` themselves.

## Task 1 — Installer fallback

Files: `synlynk/tool_installer.py`, `tests/test_tool_installer.py`.

- Add a graphify-only loop over available methods `uv`, `pipx`, `pip`.
- `pip` argv is `pip install --user graphifyy`.
- On `CalledProcessError`, log and try the next method.
- Test: `uv` present and failing, `pipx` present and succeeding, exactly two subprocess calls.

## Task 2 — Doctor check

Files: `synlynk/doctor.py`, a focused test module `tests/test_doctor_graphify.py`.

- `_hc_graphify_dependency` uses `is_tool_available` plus `graphify --version`.
- Plain doctor does not install.
- `--fix graphify` calls `install_tool("graphify")` and rechecks.
- Register the check next to the other `_hc_*` checks without changing their order relative to each other.

## Task 3 — Lifecycle helper

Files: `synlynk/scan.py`, `tests/test_scan_graphify_auto.py`.

- `classify_workspace(repo_root) -> "greenfield" | "brownfield"` per spec section 3.1.
- `write_greenfield_skeleton(repo_root)` writes the empty graph, manifest, and `.synlynk/graph.json` pointer.
- `ensure_graph_for_head(repo_root)` no-ops on a matching `built_at_commit`, writes the skeleton for greenfield, and calls `_run_graphify_extract` for brownfield when missing or greenfield-stamped.
- `cmd_scan` calls `ensure_graph_for_head` after a successful no-flag scan. `--deep` still extracts on brownfield and writes the skeleton on greenfield.
- Failed extract logs and emits `GRAPHIFY_EXTRACT_FAILED`. Scan's topology exit status stays unchanged.

## Task 4 — Warm cache

Files: new `synlynk/graph_cache.py`, `synlynk/pack.py`, `tests/test_graph_traversal_cache.py`.

- `write_traversal_cache` implements the four kinds and the caps in spec section 5.
- Call it at the end of a successful `_run_graphify_extract` and from `write_greenfield_skeleton`.
- `synthesize_context_pack` checks the cache with the two-keyword rule before the live walk.
- Tests use a fixture graph dict. No `graphify` binary.
- One test asserts the cache lookup on that fixture finishes in under 5ms.

## Task 5 — Sentinel sites and daemon stamp

Files: `synlynk/scan.py`, `synlynk/pack.py`, `synlynk/watch.py`, `synlynk/daemon.py`, existing dispatch/watch tests.

- Replace the silent `except` sites listed in spec section 4.3 with a log line plus the existing context-build sentinel helper.
- Daemon staleness reads `built_at_commit` before `head_commit`.
- Test: manifest with only `built_at_commit` equal to HEAD does not start the refresh thread.

## Task 6 — Maintainer sweep and mesh drift

Files: `synlynk/maintainer.py`, `synlynk/cli.py`, `synlynk/mesh.py`, `tests/test_maintainer_graph_sweep.py`.

- `synlynk maintainer sweep --refresh-graph` calls `ensure_graph_for_head`, rewrites the cache, and writes `.synlynk/mesh.json` when workspace config has two or more repos.
- `mesh.contract_drift` as specified. Non-empty result emits `MESH_CONTRACT_DRIFT` and still exits 0 when extract succeeded.
- Extract failure exits 1.
- Default `sweep` without the flag is a dry report.

## Task 7 — Orphans, god-node floor, maintainer skill

Files: `synlynk/heal_cycles.py` or a sibling `synlynk/heal_orphans.py`, `synlynk/cli.py`, `synlynk/dispatch.py`, `.synlynk/skills/graphify-maintainer-sweep/SKILL.md`, `synlynk/charters.py`, `tests/test_graphify_skills.py`, `tests/test_charter_graphify.py`, `tests/test_dispatch.py`.

- `heal --orphans` report, and `--stories` creates stories without touching `todo.md`.
- `resolve_model_tier` floors at `pro` when a target id is in the cache god-neighborhood. Explicit model bypasses the floor.
- Skill file and charter binding for `maintainer`.

## Task 8 — Benchmark note

Files: `scripts/benchmark_graph_cache.py`, `project-docs/benchmarks/graph_traversal_cache.md`, `tests/test_graph_traversal_cache.py`.

- 50 fixture queries, cache versus live walk.
- Commit the measured markdown beside the script.
- The ranking helper is unit-tested. The markdown is the record of one local run, labeled with the date and fixture size.

## Task 9 — Verification before PR

From the worktree:

- `pytest tests/test_tool_installer.py tests/test_doctor_graphify.py tests/test_scan_graphify_auto.py tests/test_graph_traversal_cache.py tests/test_maintainer_graph_sweep.py tests/test_graphify_skills.py tests/test_charter_graphify.py tests/test_watch_graph_drift.py tests/test_dispatch.py -q`
- `python3 bin/synlynk.py pr check` once a PR exists.
- Do not bump `VERSION`. Do not edit the roadmap shipped flag in this PR.

## Release PR, after the implementation PR merges

Separate branch `release/v0.26.5` from updated `main`:

- `VERSION` `0.26.5`
- `CHANGELOG.md`, `README.md`, generated roadmap row
- `python3 bin/synlynk.py release --check-docs --role pm`
- Non-author review, then tag `v0.26.5`
- Rollup comments on `#2458` and `#2470`

## Commit trailer

`Co-Authored-By: Grok <noreply@x.ai>`
