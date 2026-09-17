# Workspace identity (#914) — Program implementation sequencer

> **For agentic workers:** Do **not** implement this file as one PR. Execute **one wave plan at a time**. Wave 1: `docs/superpowers/plans/2026-09-17-workspace-identity-wave1-product-store.md` (REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans).

**Goal:** Land the #914 identity program in **dogfood-first slices** so solo×monorepo (`synlynk`, `rxcc`, `vdowrx`) keeps working while product-scoped Apps, types, and doctor stop forking per clone.

**Architecture:** Specs W0–W9 on PR #1647 are the constitution. Implementation is **not** those specs in one branch. Each wave is a separate feature branch/PR, Codex-implemented, qa-reviewed, squash-merged **without** `--auto`. `#914` stays OPEN until Wave 1 (at least) is on `main`; later waves close remaining scope or spawn child issues.

**Tech Stack:** Python 3.10+ stdlib, existing `synlynk/team.py` manifest flow, `synlynk/github_app_auth.py`, `synlynk/doctor.py`, `synlynk/dispatch.py`, pytest.

**Harness:** Codex (`--requires-gh-write` only when a wave opens a PR). Grok does not implement CLI. Docs-only already on `chore/grok/914-w0-vocabulary`.

---

## Explicitly **not** Wave 1

| Spec | Why later |
|:---|:---|
| W4 members, relay token mint, join≠init | Needs minter process |
| W9 hosted Vizor, OAuth, `synlynk.com/<slug>` | Needs W4 |
| W8 organigram LLM, Vizor onboard UI | Needs types+packs on disk first |
| W3 Board tab, export protocol runtimes | Needs W2 graph |
| Linear / Projects / ShotGrid adapters | Tracker protocol is data-shaped in W2; no SDK |
| Studio/agency pack **runtime** | Ship YAML **data** in Wave 3; hitchcock can `--pack studio` then |
| Connector OAuth/gateway vendors | Stub fields only until a connector wave |
| Swarm cloud drivers | #1341; W7 only binds identity (token handoff already exists for dispatch children) |

---

## Waves (each = its own plan + PR)

| Wave | Plan file | Specs | Dogfood outcome |
|:---|:---|:---|:---|
| **1** | `2026-09-17-workspace-identity-wave1-product-store.md` | W1, W5 (minimal), W7 doctor slice | Apps+types live under `~/.synlynk/workspaces/<identity_slug>/`; second `identity init` fail-closed; worktree mint uses **absolute** product PEM |
| **2** | *(write after Wave 1 merges)* | W2 `state.db` move, W6 product `policy.json` wins, `check-merge` kind resolution | One graph; `--role director` cannot train-merge |
| **3** | | W8 packs YAML (`software-product` required; `studio`/`agency` data), `synlynk type create`, `--pack` | Hitchock can seed studio types without Apps until `identity init` |
| **4** | | W7 add-repo CLI/organigram hook, remaining doctor table | Second remote does not mint App-2 |
| **5** | | W3 Board over `state.db` | Local Vizor Board |
| **6** | | W4 + W9 | Teams + hosted entirety |

Do not start Wave 2 plan until Wave 1 is on `main` (or explicitly stacked).

---

## Wave 1 file map (locked)

| File | Responsibility |
|:---|:---|
| Create `synlynk/product_store.py` | Resolve `identity_slug` → product root, `github_apps/`, `types.yaml`, `types/<id>/` |
| Modify `synlynk/team.py` | `_role_app_dir` / `cmd_identity_init_role` write **product** store; refuse second App |
| Modify `synlynk/dispatch.py` | `_resolve_github_apps_dir` prefers product store |
| Modify `synlynk/github_app_auth.py` | PEM path absolute under product store |
| Modify `synlynk/gh_role.py` | Same resolution |
| Modify `synlynk/doctor.py` | Fail-closed `gh_write` looks at **product** App material |
| Create `synlynk/types_registry.py` | Load/save `types.yaml`; `type create`; canonical seed |
| Modify `synlynk/cli.py` | `synlynk type create`; `identity init --type` alias of `--role` |
| Create `synlynk/packs/software-product.yaml` | Canonical eight (type id = kind id) |
| Test `tests/test_product_store.py` | Paths, fail-closed, migrate copy |
| Test `tests/test_types_registry.py` | Seed, duplicate, unknown kind |

Co-Authored-By: implementer harness trailer. Branch: `feat/codex/914-wave1-product-store` (or `feat/codex/914-w1-product-store`). Never commit `main`.

---

## Success (program)

- synlynk dogfood: `identity init --role qa` writes `~/.synlynk/workspaces/<slug>/github_apps/qa.{json,pem}`; a dispatch worktree `synlynk gh --role qa` works **without** `.synlynk/github_apps` in the worktree.
- Second init for the same `(slug, qa)` prints fail-closed and does not create a new GitHub App.
- `rxcc` and `synlynk` remain different directories.
- #914 still OPEN after Wave 1; comment on the issue pointing at the merged PR and remaining waves.
