# Workspace identity W1 — Product-scoped GitHub Apps (install and secrets)

**Date:** 2026-09-16  
**Status:** Approved in chat 2026-09-16 (Nikhil): store PEMs on the machine per product **now** (approach A); **no PEM on disk for teammates** when Teams land (approach C, W4). Implementation is **out of scope** until this spec is on `main` and a plan exists.  
**Issue:** [#914](https://github.com/nikhilsoman/synlynk/issues/914)  
**Depends on:** `docs/superpowers/specs/2026-09-16-workspace-identity-w0-vocabulary-design.md`  
**Author:** Nikhil Soman (brainstorm with Grok, Home Conductor)

---

## 1. Problem

W0 locks **one GitHub App per agent type**, product-isolated. Today `synlynk identity init --role <role>` still:

- Creates a **new** App per **repo**, even when `identity_slug` matches (`synlynk-vdowrx-qa` on two clones would still be two Apps if inited twice).
- Stores `app_id`, PEM, and `installation_id` under **the repo** at `.synlynk/github_apps/<role>.json` (gitignored).
- Mints tokens in a way that has already broken in **worktrees** (relative PEM path, missing `.synlynk/github_apps/` in `worktrees/job-*`).

W1 says where the private key lives, how a second repo of the **same product** uses the **same** App, and what is deferred to Teams (W4).

No code in this file.

---

## 2. Decision (locked)

| When | Secret home | Who holds the PEM |
|:---|:---|:---|
| **W1 (now)** | **A** — product store on the machine | The operator who ran `identity init` (today: Nikhil). One PEM per **type** per **product**. |
| **W4 (Teams)** | **C** — no PEM on member disks | A daemon or org secret mints **installation tokens** for members and swarm runners. Members never copy PEMs. |

W1 must not put PEMs in git, in repo trees that swarm clones, or in runner images. W4 must not require rewriting App **names** or **charters** — only how tokens are obtained.

---

## 3. GitHub’s real install model

A GitHub App has:

1. **App credentials** — `app_id` + PEM (create-once).
2. **Installation** — one `installation_id` per **account** (user or org) the App is installed on.
3. **Repository list** — that installation may include selected repos or all repos in the account.

Tokens are minted **per installation**, not per repo. Repo access is the installation’s configured list.

**W1 assumption:** all constituent repos of a product live under **one** GitHub account/org (e.g. `Dialify/frontend` + `Dialify/backend`). Then: **one App per type, one installation, N repos**. Adding a repo is GitHub “add repository to this installation,” not a new App and not a new PEM.

**Out of scope:** a product whose repos span two orgs (two installations of the same App). That needs an explicit later spec.

Solo monorepo (`nikhilsoman/synlynk`): one type, one install, one repo. Degenerate case of the same layout.

---

## 4. Layout (approach A)

```
~/.synlynk/workspaces/<product>/          # product = identity_slug, e.g. vdowrx
  github_apps/
    qa.json                               # app_id, client_id, installation_id,
                                          # account, repos[], slug, created_at
    qa.pem                                # chmod 600
    frontend-qa.json
    frontend-qa.pem
    pm.json
    pm.pem
    ...

<repo>/.synlynk/config.json               # thin pointer
  {
    "identity_slug": "vdowrx"             # product id (already exists)
  }
```

- **No PEM** under `<repo>/.synlynk/github_apps/` after migration.
- Dispatch / daemon resolve `identity_slug` → `~/.synlynk/workspaces/<slug>/github_apps/<type>.*`.
- Worktrees **must not** look for PEMs relative to the worktree cwd. Token minting uses the product store (absolute paths). This is a W1 requirement, not a nice-to-have — it is a known live failure mode.
- Moving `state.db` to the workspace directory is **not** required in W1. The June 2026 workspace `state.db` spec remains the target for W2; W1 only relocates **App material**.

`qa.json` (illustrative, not a schema freeze):

```json
{
  "type": "qa",
  "kind": "qa",
  "canonical": true,
  "app_id": 123,
  "app_slug": "synlynk-vdowrx-qa",
  "installation_id": 456,
  "account": "Dialify",
  "repos": ["Dialify/vdowrx-web", "Dialify/vdowrx-api"],
  "private_key_path": "qa.pem"
}
```

Specialist `frontend-qa.json` has `"canonical": false`, `"kind": "qa"`, and `repos` defaulting to the home repo only.

---

## 5. Provisioning and adding a repo

**Create type (once per product):** W5 splits this. `synlynk type create` writes the type registry + charter (**no** App). `synlynk identity init --type <id>` then mints the App into the **product** store (`synlynk-<product>-<type>`). Human still completes GitHub’s install click (cannot be fully scripted). Do not run `identity init` for an id that is missing from `types.yaml`.

**Add repo to an existing type:** do **not** run `identity init` again. Open or API-update the installation’s repository list, then update `repos[]` in the product json. PM-scoped when agent creation is PM-owned (W0); until then, the operator who holds the PEM.

**Canonical types** (`qa`, `pm`, `tpm`, `architect`): after the first repo, adding the rest of the product’s repos is **expected**, because they merge/coordinate trains (W0 §5).

**Specialists:** default one home repo. Extra repos are explicit GitHub config, not implied.

If `identity init` is invoked in a second repo of the same product for a type that already exists in the product store: **fail closed** with “type exists; add this repo to the installation instead.” Never mint a second App for the same `(product, type)`.

---

## 6. Token minting

Unchanged algorithm (JWT from PEM → installation access token, ~1h, memory/daemon cache). Changed **inputs**:

- PEM path = product store, absolute.
- Cache key = `(product, type)` not `(repo_path, role)`.
- Worktree jobs inherit `GH_TOKEN` already minted by the parent/daemon from that store (`synlynk gh --role` / dispatch env). They do not read PEMs themselves.

Swarm runners (W7 / #1341): W1 forbids baking PEMs into the runner image. Until W4, runners receive a **short-lived installation token** from the master (same as dispatch children). That is a token handoff, not approach C yet (C is members never seeing PEMs on their laptops).

---

## 7. Migration from today’s per-repo Apps

For a product that already has `.synlynk/github_apps/<role>.json` in **one** repo:

1. Copy json + pem into `~/.synlynk/workspaces/<identity_slug>/github_apps/`.
2. Record `repos: [<this-repo>]`.
3. Point dispatch at the product store.
4. Leave or delete the repo copies only after a doctor check: mint token from the **product** path, `gh api user` / slug `[bot]` identity, one write-probe.
5. **Do not** auto-merge two already-created Apps that share a slug prefix (e.g. two `vdowrx-qa` Apps created by mistake). Human chooses the survivor; the other is uninstalled.

Doctor (#1630 slice) extends: `gh_write` required → durable type has App material **in the product store**, not only under the repo.

---

## 8. Permissions (manifest)

Unchanged from current role manifests unless W6 says otherwise:

- All types: `contents`, `issues`, `pull_requests`, `metadata`.
- Canonical `qa` only: whatever `policy.json` `merge_authority` requires to squash-merge (today: enough to merge without `--admin`; `actions` only if we need `gh run rerun` — that is W6, not W1).
- Specialists: **no** extra merge permission beyond what GitHub grants to the same App on that repo; **policy** still forbids train merges (W0 §8).

W1 does not invent per-repo permission *grants* inside one installation. GitHub’s selected-repo list is the access map.

---

## 9. Non-goals (W1)

- Approach C (PEM-less members) — **W4**
- Cross-org products (two `installation_id`s per type)
- Creating specialist types (`frontend-qa`) — **W5** (layout must *allow* extra files; W1 need not ship the PM CLI)
- Moving `state.db` to the workspace directory — **W2**
- Swarm runner drivers — **#1341 / W7** (token handoff rule in §6 only)
- Closing #914

---

## 10. Success

- `synlynk identity init` for `qa` in a `vdowrx` repo writes `~/.synlynk/workspaces/vdowrx/github_apps/qa.{json,pem}` and does not create a second App if run from another `vdowrx` repo.
- Adding `Dialify/vdowrx-api` to that qa installation is a GitHub install-repo change + `repos[]` update.
- A dispatch worktree can `synlynk gh --role qa` without a PEM inside the worktree.
- `rxcc` and `vdowrx` stores remain separate directories.
- Teammate PEM-less flow is specified only as “W4 / approach C,” not implemented here.

---

## 11. Test plan (when implemented; not this PR)

- Unit: product-store path resolution from `identity_slug`; refuse second App for same `(product, type)`; worktree mint uses absolute product PEM.
- Doctor: missing product-store material fails closed when `gh_write` required.
- Live (operator): migrate one existing role on a dogfood repo; mint; one comment as that bot; no new App in github.com/settings/apps.
