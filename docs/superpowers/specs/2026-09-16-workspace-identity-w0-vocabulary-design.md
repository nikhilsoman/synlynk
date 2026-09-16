# Workspace identity W0 — Vocabulary and authority

**Date:** 2026-09-16  
**Status:** Approved in chat 2026-09-16 (Nikhil). Spec written; implementation is **out of scope** until later W* specs are approved.  
**Issue:** [#914](https://github.com/nikhilsoman/synlynk/issues/914)  
**Author:** Nikhil Soman (brainstorm with Grok, Home Conductor)  
**Program:** Teams, multi-repo workspaces, member-dispatch, swarms. This file is **W0 only**.

---

## 1. Why W0 exists

#914 asked for workspace-level GitHub App identities. That ticket is the identity layer for Teams, multi-repo products, and humans dispatching agents. One spec cannot cover it.

W0 locks **vocabulary and authority** so W1 (install/secrets) and later specs do not invent a second identity system.

**Not this spec:** App provisioning code, PEM layout (see W1), swarm runner drivers, Projects v2 boards, `synlynk join`. Those are W1+.

**#914 stays OPEN** until the workspace-App program (at least W1) is specified and the scoped work is done. The doctor slice in PR #1630 is not this program.

---

## 2. Product vs repo topology

| Term | Meaning |
|:---|:---|
| **Product / workspace** | One product. Mutually exclusive from other products. `rxcc` ≠ `vdowrx`. |
| **Monorepo** | One GitHub repo that is the **entire** product. |
| **Multirepo** | Several GitHub repos that **together** are one product (frontend, backend, data-pipeline, …). Separation of concerns, not separate products. |

**Today’s dogfood:** this machine only has **monorepos**. Each checkout is a different product. Nikhil works on all of them; they remain mutually exclusive. `synlynk-rxcc-qa` and `synlynk-vdowrx-qa` **must stay different GitHub actors**. That is correct and is not relaxed by #914.

#914 is **not** “one qa bot for the human’s whole GitHub.” It is: **inside one product**, how do agents, humans, and repos relate?

W1 must degenerate to the solo × monorepo cell: one repo install, one agent set, no fake frontend/backend split required on `synlynk` or `rxcc`.

---

## 3. Identity stack (must stay distinct)

| Layer | What it is | GitHub actor? |
|:---|:---|:---|
| **Human member** | GitHub user (Nikhil, later teammates). Reserved gates: spec sign-off, irreversible release, billing, new **kinds**. | Yes — the human |
| **Product / workspace** | The product (`vdowrx`, `synlynk`). Owns repos, board, cost rollup, policy. | No |
| **Agent type** | Durable: **kind**, **charter** (constant), GitHub App, skills/tools, memory home, default install. | Yes — `{slug}-{type}[bot]` |
| **Worker** | Ephemeral execution of a type (dispatch / swarm). Same App, same charter, **this job’s** context pack. | No — borrows the type’s App |
| **Harness** | Claude / Codex / Grok / Agy / local. How the type runs. | Never |

**Team:** N human members on one product. They **share** agent types. They do not each get a private `qa` App. They **dispatch** types.

**PM** creates **types** inside **approved kinds**. A **new kind** (e.g. a future `security`) is an architect charter plus **human reserved sign-off**, then PM may instantiate types of that kind. `infra` is an approved kind if already treated as canonical, not a PM improvisation.

---

## 4. Kind vs type (family)

Canonical kinds include the existing role set (`pm`, `architect`, `tpm`, `dev`, `designer`, `qa`, `marketing`, `synlynk-bot`) and `infra` where already standardized.

**Specialization** is a new **type** under an approved kind, not a context pack on the canonical role.

Example: `frontend-qa` and `backend-qa` are `kind: qa`. Each has **its own charter** (constant), own App, own tools/skills/memory. They share **review laws** with canonical `qa` (non-author vs `dev`, instruction receipts, qa-gate).

`can_merge` in policy is **canonical `{product}-qa` only**. Specialists do not become a second merge government.

---

## 5. Install surface vs work surface

| Surface | Who answers | Default |
|:---|:---|:---|
| **Install** | GitHub App installation | Specialists: **home repo** only. PM may add repos later in GitHub install settings. Canonical `qa`, `pm`, `tpm`, `architect`: **all repos of that product**, or they cannot merge/coordinate a train. |
| **Work** | Charter + context pack + `policy.json` | Narrower than install. Wide GitHub access does not widen the charter. |

Never share Apps **across products**. `identity_slug` names the **product**, not the human’s laptop.

GitHub already allows attaching more repos to an existing App. That is configuration on the type, not a new product and not a new kind.

---

## 6. Charter vs context pack vs memory

| | **Charter** | **Context pack** | **Type memory** |
|:---|:---|:---|:---|
| Lifetime | Constant for the type | Ephemeral (one job / wave shard) | Durable on the type |
| Who authors | Architect (kind) / PM (type instance) | `tpm` (or Home as tpm) shards from the issue/PR graph | Gated synthesizer |
| Visible to human | Yes | Opaque / black box as a matter of course | Yes, as conventions |
| GitHub App | Bound to the type | No | No |

Workers **do not** write type memory. They may attach notes on the job/PR. A **gated synthesizer** (follow-up canonical `qa`, or scheduled `tpm`) promotes a few conventions into the type.

---

## 7. Swarm / fleet (velocity)

Velocity is **concurrent workers**, not App count.

A wave of 100 linked PRs:

- **1** agent type (e.g. `frontend-qa`) — one App, one charter  
- **100** workers — harness/swarm runners  
- **100** context packs — tpm-sharded, typically one PR or one disjoint file set each  

Do **not** provision 100 Apps. That would destroy review identity, memory, and PM’s job.

This binds to the ephemeral swarm runner idea (#1341 / `2026-09-02-ephemeral-swarm-cloud-runners-design.md`): compute is ephemeral; **identity is the type**.

---

## 8. Review and merge

GitHub auto-merge stays **off**.

| Situation | Who reviews | Who merges |
|:---|:---|:---|
| Linked / overlapping PR train | Specialist or canonical `qa` **workers** (review only) | Canonical `{product}-qa` follow-up (or Home as that role) when the graph is green |
| Independent PR, no file overlap | Same | That worker may squash-merge **as itself** (still the type’s App) |
| Spec / irreversible release / new kind | — | Human member (reserved) |

`policy.json` `merge_authority.can_merge` = canonical product-`qa` only. The disjoint-PR exception is a **scoped grant**, not a second `can_merge` role.

---

## 9. Related specs (do not fork)

| Spec | Relation to W0 |
|:---|:---|
| `2026-06-07-synlynk-workspace-multi-repo-design.md` | Workspace = product spanning N repos; shared `state.db`. **Reconcile in W1+** with the later GitHub App model (this file does not re-open machine Ed25519 vs Apps). |
| `2026-07-23-agent-github-identity-design.md` / `2026-08-09-synlynk-agent-roles-charters-design.md` | Role = GitHub App; harness is not the actor. Unchanged. W0 adds **type** (specialist) and **worker**. |
| `2026-08-11-identity-slug-override-design.md` | Slug is a **name** override, not shared Apps. Still true: slug ≠ multi-repo identity. W1 may *use* the slug as the product id for App names. |
| `2026-09-06-workspace-agent-identity-routing-design.md` | Dispatch `--role` mints the role App token; host `gh` is the human. Unchanged. |
| `2026-09-02-ephemeral-swarm-cloud-runners-design.md` | Workers = runners. W0 says they borrow the type’s App. |
| PR #1630 / #914 comments | Doctor fail-closed if durable role has no App material. **Not** cross-repo scope. |

---

## 10. Non-goals (W0)

- Merging `rxcc` and `vdowrx` (or any two products) into one App family  
- Hosted SaaS / portable-agent vision  
- Closing #914  
- Implementing install, PEM layout, board, or `synlynk join`  
- Letting PM grant `can_merge` to a specialist type  
- Human-edited context packs as the normal path  

---

## 11. Later specs in this program

| ID | Spec | Depends on |
|:---|:---|:---|
| **W1** | Product-scoped GitHub Apps: create once per type, install on the right repos, PEM/token home, worktree-aware minting — **specified** in `2026-09-16-workspace-identity-w1-install-secrets-design.md` (A now, C at Teams) | W0 |
| **W2** | Work graph inside a product (issues stay in-repo; GOVERNS/epic spans repos; costs tagged `repo_id` + type) | W0, W1 |
| **W3** | Shared Projects v2 / Vizor board per product | W0, W2 |
| **W4** | Members and member-dispatch (`synlynk join`; humans dispatch types) | W0, W1, W6 |
| **W5** | Specialization mechanics (declaring a type, charter files, skills/tools attach) | W0 |
| **W6** | Policy / blast radius / receipts; swarm **write** policy (review vs merge) | W0, W1 |
| **W7** | Runtime + surfaces (swarm identity, doctor/wizard “add repo to this product”) | W1, W6 |

**Order:** W0 (this file) → W1 and W5 in parallel enough to freeze App count → W6 → W2/W3 → W4 → W7.

Do not start W4 (Teams) until W1 and W6 exist as approved specs.

---

## 12. Success (program, not this file)

A teammate in a `vdowrx` frontend repo can `synlynk dispatch --role frontend-qa` (or the type’s alias). Reviews show as `synlynk-vdowrx-frontend-qa[bot]`. A 100-PR train is 100 workers, one type, 100 packs; merge of the train is canonical `synlynk-vdowrx-qa[bot]`. `rxcc-qa` never appears. A Sev1 rotates that product’s types, not 8×N Apps for every repo Nikhil has.

W0 success is narrower: **these words mean one thing** in every later spec.
