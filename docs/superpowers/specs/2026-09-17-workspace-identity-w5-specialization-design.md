# Workspace identity W5 — Specialization (types, charters, skills, memory)

**Date:** 2026-09-17  
**Status:** Approved in chat 2026-09-17 (Nikhil): product-store types; two-step `type create` then `identity init --type`; kind-inherit + type skill delta; memory beside charter. Implementation is **out of scope** until this spec is on `main` and a plan exists.  
**Issue:** [#914](https://github.com/nikhilsoman/synlynk/issues/914)  
**Depends on:** `docs/superpowers/specs/2026-09-16-workspace-identity-w0-vocabulary-design.md`  
**Related:** `docs/superpowers/specs/2026-09-16-workspace-identity-w1-install-secrets-design.md` (Apps/PEMs; does not declare types)  
**Author:** Nikhil Soman (brainstorm with Grok, Home Conductor)

---

## 1. Problem

W0 locks **type** (durable: kind, charter, App, skills, memory) vs **worker** (ephemeral, borrows the type). W1 locks where the **App** lives. Neither says how a specialist such as `frontend-qa` becomes a type without becoming a second merge government.

Today:

- Org roles are the canonical eight. There is no first-class specialist type.
- `synlynk identity init --role` mints an App. It does not write a type registry.
- Charters/memory already exist under the **agent store** (`~/.synlynk/workspaces/<workspace_id>/agents/<id>/`, UUID workspace, repo-minted). That is not keyed by `identity_slug` and forks per clone if treated as the product type home.

W5 is how a specialist type becomes real: registry, charter, kind, skill delta, memory — **charter before App**. No code in this file.

**#914 stays OPEN.** This spec does not close it.

---

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| Store | **A** — product store, next to W1 Apps, keyed by `identity_slug` |
| Birth | **A** — two steps: `type create` (no GitHub write), then `identity init --type` (App) |
| Skills | **A** — inherit the kind; type stores add/remove only |
| Memory | **A** — `types/<id>/memory.md` beside `charter.md`; workers do not write it |

`can_merge` is **not** a type field. W6 owns merge grants. A skill delta cannot add merge authority.

---

## 3. Layout

```
~/.synlynk/workspaces/<product>/          # product = identity_slug, same root as W1
  github_apps/                            # W1: <type>.{json,pem} — optional until identity init
  types.yaml                              # W5: type index
  types/
    qa/
      charter.md
      memory.md
    frontend-qa/
      charter.md
      memory.md
```

Repo `.synlynk/config.json` stays a thin `identity_slug` pointer. Type files are **not** committed in the git tree.

Do **not** write W5 types under the UUID agent-store root (`~/.synlynk/workspaces/<workspace_id>/agents/`). That store remains the Phase-1/2 artifact home until a later migrate. W5 seeds **copy charter text** from it; they do not alias the directory.

Phase 2 `capability_ratings` / synthetic role-dispatch stories are **unchanged**. That is harness-routing signal, not type-convention memory.

---

## 4. Lifecycle

### 4.1 `synlynk type create <id> --kind <kind>`

Writes a `types.yaml` row and `types/<id>/charter.md` (seeded from the kind’s charter). Optionally creates empty `memory.md`.

- **No GitHub write.** No PEM. No App.
- Fail-closed if `kind` is not an **approved** kind.
- Fail-closed if `<id>` already exists on this product.
- Fail-closed if PM (or today’s operator) tries to `type create` a canonical id (`qa`, `pm`, …).
- PM may only create types **inside approved kinds**. A new kind remains architect charter + **human reserved sign-off** (W0).

`synlynk type` does not exist in the CLI today. This spec introduces it. Do not overload `synlynk agent init` to mint Apps or to mean “type.”

### 4.2 `synlynk identity init --type <id>`

Mints the GitHub App + PEM into `github_apps/` per W1.

- Fail-closed if the type does not exist in `types.yaml`, **except** empty-store + **pack-canonical** id (seed first — §4.4 / W8).
- Fail-closed if this `(product, type)` already has App material (W1: never a second App).
- App slug remains `synlynk-<product>-<type>` (W1).

Until agent creation is PM-owned in product, the operator who can write the product store runs both commands. The **split** still matters: a draft type is allowed; an accidental App is not.

### 4.3 Dispatch

`synlynk dispatch --role <id>` (or `--type <id>`) resolves `<id>` in `types.yaml`.

- GitHub writes fail-closed without App material (same spirit as doctor #1630).
- Local / harness work **may** run with charter + context pack only (no App). That worker must not call `synlynk gh`.
- Context packs stay ephemeral and tpm-authored (W0). They are not type files.

### 4.4 Canonical types (per product pack)

Canonical types are **per product**, from the industry **pack** (W8). They are **not** created via `type create`. Software dogfood still looks like today’s eight because the pack is `software-product`.

**Empty store vs `identity init`:** `identity init --type <canonical-id>` on a product with no `types.yaml` **seeds that product’s pack, then** mints the App. Pack comes from `--pack`, Vizor onboard, or default `software-product` when the scan looks like a software repo. `identity init --type frontend-qa` (or `figma`) on an empty store **fails** — specialists and connectors are never implied; `type create` (or organigram add) must have run.

Solo × monorepo software dogfood: `software-product` only. No fake `frontend-qa` / `edit` split required on `synlynk` or `rxcc`. Hitchcock uses pack `studio` (W8).

---

## 5. `types.yaml` (illustrative, not a schema freeze)

```yaml
schema_version: 1
types:
  qa:
    kind: qa
    canonical: true
  frontend-qa:
    kind: qa
    canonical: false
    home_repo: Dialify/frontend    # W0/W1: default install = this repo only
    skills_add:
      - playwright
    skills_remove: []
```

Required per type: `kind`, `canonical`. Charter/memory paths are implied as `types/<id>/charter.md` and `types/<id>/memory.md`.

Forbidden in this file:

- `can_merge`, merge grants, GitHub permission lists (W6 / W1 manifest)
- PEM paths, `app_id`, `installation_id` (W1 json)
- Context packs
- Kind definitions (approved kinds are shipped, not PM-edited here)

`home_repo` is omitted on canonical types that install on all product repos (W0 §5). Specialists default to one home repo; extra repos are GitHub install config (W1), not a new type.

---

## 6. Skills: kind inherit + type delta

The **kind** owns the review-law / baseline skill set (for `qa`: non-author, instruction receipts, qa-gate participation — the laws, not `can_merge`).

The **type** lists only `skills_add` / `skills_remove`. Effective skills = kind set minus remove plus add.

- Editing a qa review law updates every `kind: qa` type.
- `frontend-qa` may add Playwright, frontend fixture conventions, etc.
- A delta **cannot** grant `can_merge` or otherwise mint merge government.
- Empty delta is valid: a specialist that differs only by charter + home repo.

Approved kinds include the existing role set (`pm`, `architect`, `tpm`, `dev`, `designer`, `qa`, `marketing`, `synlynk-bot`) and `infra` where already standardized (W0). This spec does not add kinds.

---

## 7. Memory

`types/<id>/memory.md` is **type convention memory**: durable, human-visible, product-scoped.

- Workers **do not** write it. They may attach notes on the job/PR.
- A **gated synthesizer** (follow-up canonical `qa`, or scheduled `tpm`) promotes a few conventions into the type (W0 §6).
- Charter edits remain human/PM (existing charter revision discipline applies when implemented).
- Not git in the type’s home repo (rejected: ties product conventions to one remote and leaks into every swarm clone).
- Not repo `.synlynk/agents/` (rejected: forks per clone / constituent repo).

Team sync of charters/memory without PEMs is **W4**, same as token distribution.

---

## 8. Doctor (extends #1630)

| Condition | Result |
|:---|:---|
| Durable **canonical** type, `gh_write` required, no App material in product store | **Fail** (already #1630, path now product store per W1) |
| `types.yaml` row, missing `types/<id>/charter.md` | **Fail** |
| Specialist type, no App material | **Warn** — type exists; GitHub writes blocked until `identity init` |
| `identity init --type` for unknown id | **Fail** (CLI, not only doctor) |
| `type create` unapproved kind or duplicate id | **Fail** |

---

## 9. Migration from today’s agent store

For a product that already has Phase-1 charters:

1. Ensure `identity_slug` is set (W1 pointer).
2. Create `~/.synlynk/workspaces/<slug>/types.yaml` with the canonical eight (`canonical: true`).
3. Copy each canonical charter text into `types/<id>/charter.md`. Copy memory files if present.
4. Leave UUID `agent_store` in place until a dedicated migrate; do not delete it in the W5 implementation PR.
5. Specialists are **opt-in** via `type create`. Never auto-invent `frontend-qa` because the repo name contains “web.”

Do not auto-merge two App identities (W1 §7). Do not treat `workspace_id` UUID as the product key.

---

## 10. Non-goals (W5)

- PEM layout, token minting, worktree PEM paths — **W1**
- Merge policy, receipts, swarm review vs merge, specialist squash of disjoint PRs — **W6**
- Member sync of charters/memory; PEM-less teammates — **W4**
- Moving `state.db` — **W2**
- New kinds invented by PM
- Closing #914
- Implementation of `synlynk type` / identity-init changes (plan after this spec is on `main`)

---

## 11. Success

- `synlynk type create frontend-qa --kind qa` on product `vdowrx` writes `types.yaml` + `types/frontend-qa/charter.md` and does **not** create a GitHub App.
- `synlynk identity init --type frontend-qa` then writes `github_apps/frontend-qa.{json,pem}` and fails if the type row is missing.
- `dispatch --role frontend-qa` resolves that type; reviews (once App exists) show as `synlynk-vdowrx-frontend-qa[bot]`.
- Skill edits on kind `qa` apply to `frontend-qa`; `frontend-qa` cannot appear in `merge_authority.can_merge` via `types.yaml`.
- Solo synlynk dogfood keeps only `software-product` canonical types (W8).
- `rxcc` and `vdowrx` type stores remain separate directories.

---

## 12. Test plan (when implemented; not this PR)

- Unit: `type create` writes registry + charter, refuses unknown kind / duplicate / canonical id; `identity init --type` refuses missing type; effective skills = kind ∪ add − remove; doctor warn vs fail table.
- No live GitHub App creation in unit tests.
- Live (operator, later): one specialist on a throwaway product or unused type name; confirm a single App; delete if not kept.
