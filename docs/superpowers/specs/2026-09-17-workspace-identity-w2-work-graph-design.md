# Workspace identity W2 — Product work graph (`state.db`)

**Date:** 2026-09-17  
**Status:** Approved in chat 2026-09-17 (Nikhil): issues stay in constituent repos; one product `state.db`; claim/link pointers only; project-docs slice per repo + home-repo rollup; **tracker protocol** (GitHub Issues default, Linear named, others stub). Implementation is **out of scope** until this spec is on `main` and a plan exists.  
**Issue:** [#914](https://github.com/nikhilsoman/synlynk/issues/914)  
**Depends on:** W0, W1  
**Reconciles:** `docs/superpowers/specs/2026-06-07-synlynk-workspace-multi-repo-design.md` (shared workspace `state.db`, `repo_id` on stories). **Does not** revive machine Ed25519 as the GitHub actor — that identity model is superseded by W1 Apps.  
**Author:** Nikhil Soman (brainstorm with Grok, Home Conductor)

---

## 1. Problem

W0: GitHub **issues stay in-repo**; GOVERNS/epic **spans repos**; costs tagged `repo_id` + **type**.

Today `state.db` is still a **per-repo** file. A vdowrx frontend story cannot share a parent goal with an api story without two graphs. W1 put Apps on `~/.synlynk/workspaces/<identity_slug>/` and **deferred** moving `state.db`. Copies of SQLite/WAL have already produced malformed DBs in this project — the graph must not be forked per clone.

W2 moves **one** `state.db` to the product store and defines what **tracker** pointers it holds. PRs stay on GitHub (the forge). Tickets may be GitHub Issues, Linear, or a later adapter. No code in this file. **#914 stays OPEN.**

---

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| Forge (PRs, Apps, merge) | **GitHub only** in this program |
| Tracker (tickets) | Pluggable. Default **GitHub Issues**. Named second adapter: **Linear**. Jira / Asana / ShotGrid / Monday / … = same protocol, stub |
| GitHub Issues (when selected) | Stay in the **constituent repo** that owns the files |
| Graph | Product `state.db` only — goals/epics span repos; stories do not |
| How many DBs | **One** file; no repo copy of SQLite |
| Tracker objects in the DB | **Claim/link only** — not a replica of every ticket/PR |
| `project-docs/` | Per-repo **slice** + product rollup in the **home repo** |
| Directory key | `identity_slug` (same as W1). UUID `workspace_id` is not the product path |
| GitHub actor | W1 Apps / W5 types. Not Ed25519 |

---

## 3. Layout

```
~/.synlynk/workspaces/<identity_slug>/
  state.db                 # only graph; WAL/SHM stay beside it
  github_apps/             # W1
  types.yaml               # W5
  policy.json              # W6
```

Repo `.synlynk/config.json`: `identity_slug` + `repo_id` (and existing thin fields). No `state.db` under the repo after migrate.

Doctor: leftover repo `state.db` → **warn**, then **fail** once migrate has a copy on the product path. Do not read two graphs and “union” them.

---

## 4. Forge vs tracker

| Layer | Who | Optional? |
|:---|:---|:---|
| **Forge** | GitHub PRs, Apps, reviews, `can_merge` | **No** — Linear cannot merge a train |
| **Tracker** | Tickets the graph **claims** | Yes — chosen at onboard / organigram |

Pack default: all three packs start on **GitHub Issues**. A product may **connect Linear** (or a stub provider) without leaving GitHub for PRs. Studio ShotGrid / agency Asana are the same `tracker` protocol, unimplemented.

Pointer shape (illustrative): `{ "tracker": "github"|"linear"|<open>, "container": "org/frontend"|"HITCH", "id": "412" }`. Stories still have `repo_id` because **code/PRs** live in a git repo even when the ticket is Linear.

OAuth for Linear (etc.) uses W8 `connector` / product-store creds, not a second secret layout. Organigram “Connect tracker” is the UX; W3 deep-links the same pointers.

## 5. Graph

| Object | Spans repos? | Tracker / forge |
|:---|:---|:---|
| Story | **No** — required `repo_id` | Optional ticket pointer (`tracker`+`container`+`id`); optional GitHub **PR** number in that repo |
| Job / cost | **No** — `repo_id` + **type id** | PR if the job opened one; ticket if claimed |
| Epic / GOVERNS goal | **Yes** — children may have different `repo_id`s | No requirement for a meta-repo ticket |

**Claim/link:** a tracker ticket or GitHub PR gets a `state.db` row only when ingest, dispatch, or a human **claims** it. Unlinked tickets stay at the tracker. Body/comments stay at the tracker; CI/file lists stay on GitHub. tpm shards from the tracker + GitHub (short-lived cache allowed), not from a SQLite dump of the org.

Stories never span two git remotes. An epic may parent a frontend story and an api story.

---

## 6. Generated docs

Workers do not hand-edit `todo.md`. `synlynk story done` (etc.) writes `state.db`, then write-through:

- **Each constituent repo:** `todo.md` / `costs.md` **slice** for that `repo_id` (cost rows include type id).
- **Home repo** of the product (W8 organigram / first repo / solo checkout): full GOVERNS, roadmap, memory for the product.
- Solo monorepo: that repo **is** the home repo — today’s layout.

Do not write the full product markdown into every constituent repo (union-merge × N remotes).

---

## 7. Migration (when implemented)

1. Resolve `identity_slug`. Create product dir if needed.
2. If product `state.db` does not exist: **copy** the current repo `state.db` there; set that checkout’s `repo_id`.
3. Point `generate_context` / story CLI at the product path.
4. Stop writing the repo copy. Doctor the leftover.
5. **Do not** auto-merge two already-divergent `state.db` files for the same slug (same human-picks-survivor rule as W1 Apps).

June 2026 `workspaces/<name>/state.db` path is this path when `name` = `identity_slug`.

---

## 8. Non-goals (W2)

- Vizor / GitHub Projects board — **W3** (reads these pointers)
- Member sync of `state.db` — **W4**
- Implementing the Linear SDK or any stub tracker
- Replacing GitHub as the forge
- Full tracker/GitHub clone/mirror
- Closing #914
- Performing the file move in this docs PR

---

## 9. Success

- Two vdowrx repos share one `state.db`; an epic can parent one story per repo; each story’s GitHub issue lives on its own remote.
- `rxcc` and `vdowrx` remain separate directories / DBs.
- Cost rows for a hitchcock `director` job carry `repo_id` + type `director`.
- An untracked tracker ticket does not appear in `todo.md` until claimed.
- A product can record `tracker: linear` on a story and still merge the PR as GitHub `qa`.
- After migrate, dispatch worktrees do not carry a private `state.db` graph (they use the product path, like PEMs).

---

## 10. Test plan (when implemented; not this PR)

- Unit: resolve DB from `identity_slug`; story requires `repo_id`; epic children differ by `repo_id`; cost/job require type id; claim vs unlinked ticket; pointer `{tracker, container, id}`; leftover repo DB doctor; refuse silent merge of two DBs; unknown tracker id fail-closed.
- No live GitHub or Linear ingest required for unit tests.
