# Workspace identity W4 — Members and member-dispatch

**Date:** 2026-09-17  
**Status:** Approved in chat 2026-09-17 (Nikhil): explicit product membership (GitHub identity); join ≠ init; PEM-less members (W1-C); default dispatch non-connector; graph via API not copied `state.db`. Implementation is **out of scope** until this spec is on `main` and a plan exists.  
**Issue:** [#914](https://github.com/nikhilsoman/synlynk/issues/914)  
**Depends on:** W0, W1, W6  
**Unlocks:** W9 hosted Vizor (OAuth maps to this roster)  
**Author:** Nikhil Soman (brainstorm with Grok, Home Conductor)

---

## 1. Problem

W0: a **team** is N human members on **one product**. They **share** agent types. They do not each get `synlynk-vdowrx-qa`. They **dispatch** types.

Today `synlynk join` is local git-user onboarding (devlog, context files). It does not create membership, mint tokens, or keep PEMs off the laptop. W1 deferred approach **C**: teammates never hold PEMs.

W4 is membership, grants, token minting, and how members see the graph. No code in this file. **#914 stays OPEN.**

---

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| Who is a member | **Explicit** invite or mapped GitHub org/team. Collaborator ≠ member |
| Identity now | GitHub user. Google/Apple/Microsoft later **alias the same member** (W9), not a second roster |
| `join` vs `init` | `init`/organigram creates product, packs, Apps. `join` accepts membership only |
| PEMs | Stay at minter (admin machine / relay vault). Members **never** copy `.pem` or connector `secret` |
| Dispatch tokens | Relay/daemon mints **short-lived installation tokens** (W1-C, same as swarm) |
| Default grants | All pack types except `kind: connector`. Merge still W6 |
| Connector / merge dispatch | Extra **admin** grant. Grant ≠ `can_merge` list |
| Graph | Members **read via API**. No copied `state.db` WAL |
| Replicable to member disk | `types.yaml`, `policy.json` (read-only). Not PEMs, not connector secrets |

---

## 3. Membership

A member record (illustrative): GitHub login, product slug, role `admin` | `member`, dispatch grants[], optional IdP aliases.

**Admin** humans: invite, revoke, grants, organigram expand, policy propose (human still confirms `can_merge` / reserved gates — W6).

`synlynk join`: accept invite (or org/team mapping) + GitHub OAuth/login + pointer at the product relay/daemon. **Does not** seed packs, **does not** `identity init`.

Hosted Vizor (`synlynk.com/<slug>`) uses this list. Non-member → 403.

---

## 4. Dispatch

`synlynk dispatch --role <type-id>` on a member machine:

1. Member authenticated; grant allows that type.
2. Minter returns installation token for **that type** (not the human’s `gh`).
3. GitHub attribution is `synlynk-<product>-<type>[bot]`.
4. W6 `check-merge` / receipts unchanged. Default grant does **not** let a member skip canonical `qa` for trains.
5. `kind: connector` refused without grant; secret injected only into that job at the minter (W6), never written to the member disk.

Humans still perform reserved merges (spec, release, new kind) as **themselves**.

---

## 5. Graph and files

| Artifact | Member laptop |
|:---|:---|
| `state.db` | No. API to minter. Optional JSON/HTTP cache |
| `types.yaml` / `policy.json` | Optional read-only replica |
| `github_apps/*.pem` | **Never** |
| `connectors/*/secret` | **Never** |
| `.synlynk/config.json` | `identity_slug` + relay URL + `repo_id` |

Solo operator (no team): still W1-A local PEMs + local `state.db`. W4 is off until a second member is invited.

---

## 6. Non-goals (W4)

- Implementing relay, invite CLI, OAuth apps
- Hosted Vizor UI — **W9**
- GitLab as forge
- Closing #914

---

## 7. Success

- Second hitchock human `join`s, dispatches `--role edit`, PR is `synlynk-hitchcock-edit[bot]`, no PEM in their `~/.synlynk`.
- They cannot dispatch `figma` until admin grants it.
- They cannot train-merge as `director`.
- Their laptop has no `state.db` copy; `story list` hits the minter.
- `rxcc` membership does not include hitchock.

---

## 8. Test plan (when implemented; not this PR)

- Unit: join does not mint App; collaborator not auto-member; default grant excludes connector; connector dispatch without grant fails; check-merge still kind `qa`; refuse writing pem to member fixture; story list without local DB uses API mock.
- No live GitHub App install in unit tests.
