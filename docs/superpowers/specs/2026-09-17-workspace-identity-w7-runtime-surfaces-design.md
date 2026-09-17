# Workspace identity W7 — Runtime surfaces (add-repo, swarm, doctor)

**Date:** 2026-09-17  
**Status:** Approved in chat 2026-09-17 (Nikhil): add-repo via organigram/CLI never mints a second App; swarm worker = type + pack + token handoff; extend existing doctor (product-aware). Implementation is **out of scope** until this spec is on `main` and a plan exists.  
**Issue:** [#914](https://github.com/nikhilsoman/synlynk/issues/914)  
**Depends on:** W1, W4, W6, W8  
**Author:** Nikhil Soman (brainstorm with Grok, Home Conductor)

---

## 1. Problem

W0–W6, W8, W9 define types, Apps, graph, members, board, hosted Vizor. Runtime still has three holes:

1. A second git remote of the same product runs `identity init` and mints a **second App**.
2. Swarm runners (#1341) might bake PEMs or use host `gh`.
3. `synlynk doctor` still thinks identity lives under the **repo**.

W7 is the contract for add-repo, swarm identity, and doctor. No new identity model. No code in this file. **#914 stays OPEN.**

---

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| Add repo | Organigram or CLI; **never** `identity init` for an existing `(product, type)` |
| Swarm | N workers × 1 type × N packs; **token handoff only** |
| Doctor | Extend **existing** `synlynk doctor`, product-aware — not a second binary |
| Wizard | Onboard remains W8; W7 is add-repo + doctor fix-it copy |

---

## 3. Add repo

Admin/operator adds `org/api` on the organigram (or `synlynk workspace add-repo --yes` for CI):

1. Same **reach** sheet as onboard (W8): canonical spine defaults to **all** product repos; specialists/connectors stay **home** unless extended.
2. GitHub installation repository list updates (human may still click GitHub).
3. Product `github_apps/<type>.json` `repos[]` updates.
4. New clone `.synlynk/config.json`: same `identity_slug`, new `repo_id`.
5. W2 `repos` row in product `state.db`.

No new App, PEM, or `types.yaml` row. `identity init --type qa` in that clone: **fail closed** — “type exists; add this repo to the installation instead” (W1).

---

## 4. Swarm runtime

Matches W0/W1/W4:

- Identity is the **type**. Compute is ephemeral.
- Master/minter injects `GH_TOKEN` (installation token). Image contains **no** `.pem`, no `identity init`, no writable product `state.db` (telemetry via master/API).
- `synlynk gh` uses the injected token. Host `gh` is never the fallback.
- Doctor runs on the **master** before fan-out (product store, grants, connector allowlists). Runners do not run identity-init doctor.

#1341 drivers (Fly/K8s/Hetzner) stay that spec. W7 only binds **identity**.

---

## 5. Doctor (product-aware)

| Fail | Warn |
|:---|:---|
| Durable canonical type, `gh_write` required, no product App material | Specialist/connector with no App |
| `identity init` would mint a second App for `(product, type)` | Product vs repo `policy.json` drift (product wins) |
| `can_merge` contains a type whose kind is not `qa` | Leftover repo `state.db` before migrate completes |
| Connector empty allowlist / unknown protocol | Teams member machine has a `.pem` |
| Add-repo / dispatch without `identity_slug` | |
| Swarm master missing minter | |

Fix-it copy: “add this clone to product X” vs “mint a new App” — never the latter when the type exists.

---

## 6. Non-goals (W7)

- Implementing add-repo CLI, doctor rows, swarm drivers
- Hosted Vizor — **W9**
- Closing #914

---

## 7. Success

- Checking out `org/api` and adding it to `vdowrx` does not create `synlynk-vdowrx-qa-2`.
- A 100-PR swarm reviews as one `frontend-qa` App; no PEM in the runner image; merge of the train is still canonical `qa`.
- `synlynk doctor` in a worktree fails closed on missing **product** App material, not missing `.synlynk/github_apps/` in the worktree.
- Solo synlynk (one repo) add-repo is a no-op path: already the only remote.

---

## 8. Test plan (when implemented; not this PR)

- Unit: add-repo does not call App create; second `identity init` same `(product, type)` fails; swarm fixture has no pem path; doctor fail/warn table; missing `identity_slug` fails dispatch.
- No live GitHub install-repo API in unit tests.
