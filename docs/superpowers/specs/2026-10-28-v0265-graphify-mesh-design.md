# v0.26.5 — Graphify Lifecycle, Warm Traversals, and Mesh Refresh

**Status:** Proposed. Implementation is blocked until Nikhil signs off on this file.
**Authored:** 2026-10-27
**Author:** Grok, Mode A Home Conductor
**Base:** `origin/main` `6169b63a` (tag `v0.26.4`)
**Release:** v0.26.5, daily stable gate under epic [#2470](https://github.com/nikhilsoman/synlynk/issues/2470)
**Parent:** [#2458](https://github.com/nikhilsoman/synlynk/issues/2458)
**Governing goal:** `goal-e3840370` (active). Ledger outcome is the Vizor control plane. Graphify stories `story-issue-1579`, `story-issue-2133`, and `story-issue-2198` already sit on that goal. This release does not retitle the goal.
**Plan:** `docs/superpowers/plans/2026-10-28-v0265-graphify-mesh.md`

This spec is the delta against code that is already on `main`. It does not re-commission the v0.22 Graphify substrate.

---

## 1. Decision

v0.26.5 makes an existing Graphify install deterministic across workspace birth, the first real commit, and later HEAD movement, and it makes context packing read a precomputed traversal cache before it walks the live graph.

The canonical graph remains `.synlynk/graphify-out/graph.json`. `.synlynk/graph.json` becomes a small pointer manifest, not a second copy of the graph.

Extraction still means `graphify extract <repo> --code-only`. Synlynk does not invent symbols. A greenfield workspace gets an empty graph and an explicit `lifecycle: greenfield` stamp.

---

## 2. What already shipped

Verified on `6169b63a`. These behaviors stay. Tests that already cover them stay green. This release does not rewrite them.

| Surface | Where | Contract that stays |
|---|---|---|
| On-demand install | `synlynk/tool_installer.py` | `graphify` maps to package `graphifyy`. Method order is `uv`, then `pipx`, then `pip`. |
| Extract + stamp | `synlynk/scan.py` `_run_graphify_extract` | `--deep` runs extract. Success writes `built_at_commit` from `git rev-parse HEAD`. `SYNLYNK_SKIP_GRAPHIFY_EXTRACT=1` skips the subprocess. |
| Test isolation | `tests/conftest.py` `stub_graphify_extract` | Autouse stub. Opt out with `no_stub_graphify_extract`. Story `story-1ade229f` is satisfied in code and stays open in the ledger until a later close. |
| Dispatch staleness | `synlynk/dispatch.py` | Missing graph refreshes immediately. A present graph refreshes when `built_at_commit..HEAD` is more than 25 commits, or when age exceeds 7 days if the distance cannot be measured. Failures call `_warn_context_build_failure` (`CONTEXT_BUILD_DEGRADED`). |
| Context pack | `synlynk/pack.py` | Keyword score over `graphify-out/graph.json`, 1-hop callers and callees, signature inlining, reverse test filenames, default budget 1,500 tokens. |
| Watch drift | `synlynk/watch.py` | Compares HEAD to `built_at_commit` or `built_at` and re-extracts. |
| Daemon refresh | `synlynk/daemon.py` `_check_graph_staleness_and_refresh` | Background thread, 30s debounce. See the bug in section 4. |
| Mesh | `synlynk/mesh.py` | `merge_fleet_graphs`, `infer_cross_repo_edges` (route label contained in a client label, cross-repo only), `build_federated_mesh`. |
| Sparse cone | `synlynk/worktree_sparse.py` | AST-guided cone derivation already exists. |
| Impact routing | `synlynk/dispatch.py` `resolve_model_tier` | `impact_score > 12` selects `pro`. Architect, PM, TPM, and spec language select `reasoning`. |
| Cycles | `synlynk/heal_cycles.py` | `synlynk heal --cycles` files refactor stories. It does not edit source. |
| Role skills | `.synlynk/skills/` and `TOOL_ROLE_SKILLS` in `synlynk/charters.py` | Architect, QA, verifier, dev, builder, and PM skills are bound when the `graphify` binary is present. |
| Vizor | `synlynk/viz/graphify.py` | Canvas, community labels, staleness banner. Out of scope for this release. v0.26.6 owns the Vizor review. |

Prior specs remain the structural law for extraction, pack budgets, and the canvas:

- `docs/superpowers/specs/2026-09-25-ast-knowledge-graph-lifecycle-packager-sparse-worktrees-design.md`
- `docs/superpowers/specs/2026-09-26-ast-knowledge-graph-lifecycle-context-pack-and-kg-ux-design.md`
- `docs/superpowers/specs/2026-09-25-graphify-vizor-unified-canvas-design.md`
- `docs/superpowers/specs/2026-09-15-graphify-knowledge-graph-and-spike-harness.md`
- `project-docs/decisions/2026-09-14-graphify-expansion-multi-modal-research.md` (offline, zero-cloud, Apache-2.0 `graphifyy`)

---

## 3. Workspace lifecycle

```mermaid
flowchart TD
  scan["synlynk scan"] --> classify{"Source files beyond init templates?"}
  classify -->|yes| brown["Brownfield extract"]
  classify -->|no| green["Greenfield skeleton"]
  brown --> graph["graphify-out/graph.json"]
  green --> empty["Empty graph plus pointer"]
  first["First commit that adds source, or maintainer sweep after first merged PR"] --> brown
  graph --> cache["graph-cache/traversals.json"]
  empty --> cache
  drift["HEAD != built_at_commit"] --> brown
```

### 3.1 Classification

A workspace is **greenfield** when all of these hold:

- `git rev-list --count HEAD` is 0, or the only tracked files are Synlynk init templates (`project-docs/`, `.synlynk/`, instruction stubs, `README.md`, `LICENSE`).
- No source file exists under the repo with suffix `.py`, `.js`, `.ts`, `.tsx`, `.go`, `.rs`, `.java`, `.rb`, or `.php`, excluding `.synlynk/` and `project-docs/`.

Otherwise it is **brownfield**.

### 3.2 Brownfield

`synlynk scan` with no flags, on a brownfield repo whose `graphify-out/graph.json` is missing, runs `_run_graphify_extract` once after the existing topology scan. `--deep` keeps today's behavior and also rebuilds the warm cache.

A failed extract prints the stderr tail and records sentinel code `GRAPHIFY_EXTRACT_FAILED`. The scan command still exits 0 for the topology half. A dedicated non-zero comes from `synlynk doctor` and from `synlynk maintainer sweep --refresh-graph`.

### 3.3 Greenfield

`synlynk scan` on a greenfield repo does not call `graphify`. It writes:

- `.synlynk/graphify-out/graph.json` as `{"nodes":[],"edges":[],"lifecycle":"greenfield"}`
- `.synlynk/graphify-out/manifest.json` with `lifecycle: greenfield`, `built_at_commit: ""`, and `node_count: 0`
- `.synlynk/graph.json` as a pointer: `{"schema":1,"graph":".synlynk/graphify-out/graph.json","lifecycle":"greenfield"}`
- `.synlynk/graph-cache/traversals.json` as an empty cache with the same lifecycle

No symbol ids are synthesized.

### 3.4 First real tree

The first transition to brownfield happens in two places, both calling the same function `ensure_graph_for_head(repo_root)`:

1. `synlynk scan` and `synlynk watch` / daemon drift, when classification flips from greenfield to brownfield.
2. `synlynk maintainer sweep --refresh-graph`, which the conductor runs after a merged PR. There is no `cmd_pr_merge` in `synlynk/cli.py`. This release does not add a wrapper around `gh pr merge`.

`ensure_graph_for_head` no-ops when `built_at_commit` equals HEAD. On a greenfield manifest, any HEAD that now classifies as brownfield triggers extract.

### 3.5 Pointer manifest

Readers keep opening `graphify-out/graph.json`. The pointer exists so the roadmap phrase "`.synlynk/graph.json`" has one stable file without duplicating a multi-megabyte graph. Pack, mesh, heal, and dispatch do not switch their read path.

---

## 4. Bugs this release fixes

### 4.1 Daemon compares the wrong manifest key

`Daemon._check_graph_staleness_and_refresh` treats the graph as stale when `manifest["head_commit"] != HEAD`. Extract writes `built_at_commit` and does not write `head_commit`. After a successful extract the daemon therefore refreshes on every 30s tick.

Fix: use the same stamp rule as `watch.py` and `dispatch._read_graph_built_at_commit` (`built_at_commit`, then `head_commit`). Missing stamp still refreshes. Equal stamp does not.

### 4.2 Install does not fall through on failure

`install_tool` selects the first present manager and returns on that command's failure. If `uv` exists and `uv tool install graphifyy` fails, `pipx` and `pip` never run.

Fix: for `graphify` only, try each available method in order `uv`, `pipx`, `pip`. `pip` is `pip install --user graphifyy`. Log each failure to stderr. Return true on the first success. Do not `sudo`.

### 4.3 Swallowed extract and pack errors

`story-2341a70c` is still open. `dispatch._format_prompt_for_agent` already records `CONTEXT_BUILD_DEGRADED`. These still swallow:

- `scan._run_graphify_extract` `except Exception: return False`
- `pack.synthesize_context_pack` graph JSON parse `except Exception: return ""`
- `pack.synthesize_context_pack` story lookup `except Exception: pass`
- `watch.check_and_refresh_ast_on_drift` `except Exception: pass`
- `daemon._run_background_graph_refresh` `except Exception: pass`

Fix: each site logs one line and calls the existing context-build sentinel helper when a repo root is known. Pack still returns `""` on a bad graph so dispatch continues. The sentinel is the new signal. Do not broaden this sweep past graph extract, pack synthesis, watch refresh, and daemon refresh.

### 4.4 Maintainer has no graph sweep

`synlynk maintainer` implements `triage` and `probe` only. The roadmap command `synlynk maintainer sweep --refresh-graph` does not exist.

Add `sweep --refresh-graph`. It calls `ensure_graph_for_head`, rebuilds the warm cache, and, when `.synlynk/workspace.json` lists more than one repo, rebuilds the federated mesh at `.synlynk/mesh.json` via the existing `build_federated_mesh`. Exit 1 when extract fails. Without `--refresh-graph`, `sweep` prints the actions it would take and exits 0.

---

## 5. Warm traversal cache

New module `synlynk/graph_cache.py`. Successful extract and a successful greenfield skeleton write both call `write_traversal_cache(repo_root)`.

### 5.1 File

`.synlynk/graph-cache/traversals.json`:

```json
{
  "schema": 1,
  "built_at_commit": "<sha or empty>",
  "lifecycle": "brownfield",
  "paths": [
    {
      "id": "entrypoint:synlynk-cli",
      "kind": "entrypoint",
      "keywords": ["cli", "dispatch", "scan"],
      "nodes": [{"id": "...", "label": "...", "file": "...", "signature": "..."}]
    }
  ]
}
```

`paths` is capped at 40 chains. Each chain holds at most 8 nodes. The file stores ids, labels, files, and one-line signatures already on the node. It does not store file bodies.

### 5.2 Chains

Built only from nodes and edges already in `graph.json`:

| Kind | Rule |
|---|---|
| `entrypoint` | Nodes whose file basename is `cli.py`, `__main__.py`, or `main.py`, or whose label is `main`, followed by up to 3 outbound hops that stay inside the repo. |
| `route` | Nodes with `kind == "route"` or a label that starts with `/` or an HTTP verb, followed by up to 3 outbound hops. |
| `test_closure` | A `tests/test_*.py` node plus the symbols it points at. Cap 15 closures, preferring tests that touch the entrypoint and route chains. |
| `god_neighborhood` | Top 10 nodes by degree (in-degree + out-degree). Each stores 1-hop inbound and outbound neighbors, excluding the test files already listed. |

If the graph is empty, `paths` is `[]`.

### 5.3 Pack lookup

`synthesize_context_pack` loads the cache first.

A cache hit requires all of:

- `traversals.json` parses and `schema == 1`
- `built_at_commit` equals the manifest stamp (both empty is a valid greenfield hit)
- at least one path has two or more keyword hits against `_extract_keywords(task_text)`

The winner is the highest hit count, then the shortest chain. The pack is rendered from the cached nodes with the existing token cutter. Target budget stays 1,500 tokens. Hard cap stays 3,000.

On a miss, or on a stamp mismatch, the current live walk runs unchanged.

The 5ms figure is a unit-test budget against a fixture cache of 40 paths. It is not a production SLO. The benchmark in section 7 records the measured number.

### 5.4 Invalidation

Any successful extract overwrites the cache in the same process before `_run_graphify_extract` returns. A failed extract leaves the previous cache on disk and does not update `built_at_commit`. Pack then misses on the stamp check and uses the live graph.

---

## 6. Doctor

Add `_hc_graphify_dependency` to the doctor registry.

- Pass: `graphify` is on PATH (including the extra paths `is_tool_available` already searches) and `graphify --version` exits 0.
- Fail: binary missing, or version command exits non-zero. Remediation text is `synlynk doctor --fix graphify`.
- `--fix graphify` calls the fallback installer from section 4.2 and re-runs the check.
- The check does not run extract and does not download during a plain `synlynk doctor`.

---

## 7. Benchmark

`scripts/benchmark_graph_cache.py` runs 50 fixture queries against one checked-in small graph (not the live synlynk graph, and not a subprocess extract). It reports median and p95 latency, peak resident set if `resource` is available, and output characters for cache hits versus the live walk.

Findings land in `project-docs/benchmarks/graph_traversal_cache.md` in the same implementation PR as the script. The doc states the machine, the fixture size, and the three numbers. It does not claim a 75% disk reduction or a sub-5ms production SLO unless the run measured that.

A unit test asserts the script's pure compare function: given two timing series, it ranks the cache path faster only when its median is lower. The unit test does not assert a wall-clock budget beyond the 5ms fixture lookup in section 5.3.

---

## 8. Novel uses that are in scope

| Use | v0.26.5 action |
|---|---|
| Sparse cones | No new cone algorithm. Add one test that a god-neighborhood file from the cache is a legal input to the existing cone helper. |
| Reverse tests | Pack already lists test files on the live path. The `test_closure` cache kind is the warm form. No new `pytest` runner. |
| Contract drift | Add `mesh.contract_drift(previous_edges, current_edges)`. A drift row is a prior `cross-repo-call` edge whose route id is absent from the new graph while the client id remains. `maintainer sweep --refresh-graph` prints the rows and records sentinel `MESH_CONTRACT_DRIFT` when the list is non-empty. It does not block merge. |
| God-node routing | If any impact target's id is in the cache's `god_neighborhood` set, `resolve_model_tier` floors at `pro`. It does not force `reasoning`. Existing explicit `--model` still wins. Non-author review stays the global PR policy. This release does not add a second review gate. |
| Orphan symbols | `synlynk heal --orphans` lists functions and classes with in-degree 0, excluding nodes in entrypoint chains, test files, and dunder names. Default is a report. `--stories` files stories through the same path as `heal_import_cycles`. It does not edit `project-docs/todo.md` and it does not delete code. |

---

## 9. Role skills

Add one maintainer skill, `.synlynk/skills/graphify-maintainer-sweep/SKILL.md`, bound in `TOOL_ROLE_SKILLS["graphify"]["maintainer"]`.

Its instructions are executable commands that exist after this release:

- `synlynk maintainer sweep --refresh-graph`
- `synlynk heal --cycles`
- `synlynk heal --orphans`
- `synlynk doctor` for the graphify check

The four existing skills stay. Their tests in `tests/test_graphify_skills.py` and `tests/test_charter_graphify.py` gain the maintainer row.

---

## 10. Explicitly out of this release

- SCIP indexing (`story-575700b8`). Graphify remains the tree-sitter extractor.
- Daemon `dispatch_context` propagation (`story-3686d05a`). Different defect, different goal.
- Rewriting Vizor LOD, community naming, or the canvas (`v0.26.6`).
- Changing the 25-commit dispatch staleness threshold.
- A new `cmd_pr_merge`, automatic `gh pr merge`, or a merge block on contract drift.
- Installing Graphify during import, during `synlynk --version`, or during pytest collection.
- Copying the full graph to both `.synlynk/graph.json` and `graphify-out/graph.json`.
- Closing ledger stories inside the implementation PR. Story status changes are a separate ledger action after the code is on `main`.
- Version bump, CHANGELOG, README, and roadmap `[shipped]` flip. Those belong to the release PR after this design is accepted and the implementation PR has merged. Docs-only release notes stay out of the implementation branch.
- Document nodes in the code graph. Decision `dec-6d438fd0` records a curated deterministic markdown sidecar as the candidate and defers the evaluation to `goal-34c225e1` and `story-bae335b6`. This release does not drop `--code-only`, does not call the semantic LLM extract, and does not add doc nodes. The calibration calls Graphify's local markdown parser directly, on its own goal, after v0.26.5.

---

## 11. Acceptance

1. `install_tool("graphify")` tries the next manager when the earlier one fails, and never uses `sudo`.
2. `synlynk doctor` fails the graphify check when the binary is absent, and `--fix graphify` is the only doctor path that installs it.
3. A fixture repo with no source files gets an empty graph, a pointer manifest, and zero calls to `graphify extract`.
4. A fixture repo with one `.py` file gets one extract call from `synlynk scan`.
5. After extract, `traversals.json` `built_at_commit` matches the manifest. Pack uses the cache when two keywords hit, and the live walk when they do not.
6. Daemon refresh does not fire when `built_at_commit` equals HEAD.
7. `synlynk maintainer sweep --refresh-graph` exits 1 when extract returns false, and writes `.synlynk/mesh.json` when the workspace config lists two repos.
8. `heal --orphans` prints and, with `--stories`, does not write `todo.md`.
9. `contract_drift` reports a removed route that a surviving client edge still names.
10. A god-neighborhood target floors the model tier at `pro` unless `--model` is set.
11. Sentinel events exist for extract failure and for non-empty contract drift. Pack parse failure is visible the same way.
12. `pytest` for the new tests passes without a real `graphify` subprocess, under the existing autouse stub except where a test opts out and supplies its own fake.

---

## 12. Ledger reconciliation

| Story | On `main` today | This release |
|---|---|---|
| `story-issue-1579` | Substrate, skills, mesh, spike spec exist. Ledger status `open`. | Do not rebuild. Leave the ledger row for a close after acceptance. |
| `story-5ce5a997`, `story-24219f0f` | Live pack exists. No warm cache. | Warm cache is the remaining work. |
| `story-issue-2198` | Dispatch refresh and `CONTEXT_BUILD_DEGRADED` exist. | Finish the swallowed sites in section 4.3. |
| `story-issue-2133` | Stale-graph refresh exists. Sparse cones exist but are not the default worktree. | No default-worktree change. God-node floor and warm pack are the cost levers in this release. |
| `story-2341a70c` | Open. Dispatch path is logged. Other sites still swallow. | Section 4.3. |
| `story-1ade229f` | Done in `tests/conftest.py`. Ledger still `open`. | No code. Note only. |
| `story-3686d05a` | Unrelated. | Out of scope. |
| `story-575700b8` | Brainstorm. | Out of scope. |

---

## 13. Sign-off

Reply on this file if the lifecycle rules, the cache hit rule, the non-blocking contract drift sentinel, and the out-of-scope list are accepted. Implementation starts only after that sign-off, on this branch, in worktree `.worktrees/feat-grok-v0265-graphify-mesh`.
