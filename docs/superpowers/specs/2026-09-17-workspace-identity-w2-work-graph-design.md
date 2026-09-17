# Workspace identity W2 — Product work graph (`state.db`)

**Date:** 2026-09-17  
**Status:** Approved in chat 2026-09-17 (Nikhil): issues stay in constituent repos; one product `state.db`; claim/link pointers only; project-docs slice per repo + home-repo rollup. Implementation is **out of scope** until this spec is on `main` and a plan exists.  
**Issue:** [#914](https://github.com/nikhilsoman/synlynk/issues/914)  
**Depends on:** W0, W1  
**Reconciles:** `docs/superpowers/specs/2026-06-07-synlynk-workspace-multi-repo-design.md` (shared workspace `state.db`, `repo_id` on stories). **Does not** revive machine Ed25519 as the GitHub actor — that identity model is superseded by W1 Apps.  
**Author:** Nikhil Soman (brainstorm with Grok, Home Conductor)

---

## 1. Problem

W0: GitHub **issues stay in-repo**; GOVERNS/epic **spans repos**; costs tagged `repo_id` + **type**.

Today `state.db` is still a **per-repo** file. A vdowrx frontend story cannot share a parent goal with an api story without two graphs. W1 put Apps on `~/.synlynk/workspaces/<identity_slug>/` and **deferred** moving `state.db`. Copies of SQLite/WAL have already produced malformed DBs in this project — the graph must not be forked per clone.

W2 moves **one** `state.db` to the product store and defines what GitHub pointers it holds. No code in this file. **#914 stays OPEN.**

---

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| GitHub issues | Stay in the **constituent repo** that owns the files |
| Graph | Product `state.db` only — goals/epics span repos; stories do not |
| How many DBs | **One** file; no repo copy of SQLite |
| GitHub objects in the DB | **Claim/link only** — not a replica of every issue/PR |
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

## 4. Graph

| Object | Spans repos? | GitHub |
|:---|:---|:---|
| Story | **No** — required `repo_id` | Optional pointer: issue and/or PR number **in that repo** |
| Job / cost | **No** — `repo_id` + **type id** (`qa`, `director`, `frontend-qa`, …) | PR/issue if the job opened one |
| Epic / GOVERNS goal | **Yes** — children may have different `repo_id`s | No requirement for a meta-repo issue |

**Claim/link:** a GitHub issue or PR gets a `state.db` row only when ingest, dispatch, or a human **claims** it onto a story/goal/job. Unlinked issues remain on GitHub only. Issue **body**, comments, labels, CI, and file lists stay on GitHub. tpm shards context packs from GitHub (and/or a short-lived cache), not from a SQLite dump of the org.

Stories never span two remotes. An epic may parent a frontend story and an api story.

---

## 5. Generated docs

Workers do not hand-edit `todo.md`. `synlynk story done` (etc.) writes `state.db`, then write-through:

- **Each constituent repo:** `todo.md` / `costs.md` **slice** for that `repo_id` (cost rows include type id).
- **Home repo** of the product (W8 organigram / first repo / solo checkout): full GOVERNS, roadmap, memory for the product.
- Solo monorepo: that repo **is** the home repo — today’s layout.

Do not write the full product markdown into every constituent repo (union-merge × N remotes).

---

## 6. Migration (when implemented)

1. Resolve `identity_slug`. Create product dir if needed.
2. If product `state.db` does not exist: **copy** the current repo `state.db` there; set that checkout’s `repo_id`.
3. Point `generate_context` / story CLI at the product path.
4. Stop writing the repo copy. Doctor the leftover.
5. **Do not** auto-merge two already-divergent `state.db` files for the same slug (same human-picks-survivor rule as W1 Apps).

June 2026 `workspaces/<name>/state.db` path is this path when `name` = `identity_slug`.

---

## 7. Non-goals (W2)

- Vizor / GitHub Projects board — **W3**
- Member sync of `state.db` — **W4**
- PEM / type / policy files (W1 / W5 / W6) except sharing the directory
- Full GitHub clone/mirror
- Closing #914
- Performing the file move in this docs PR

---

## 8. Success

- Two vdowrx repos share one `state.db`; an epic can parent one story per repo; each story’s GitHub issue lives on its own remote.
- `rxcc` and `vdowrx` remain separate directories / DBs.
- Cost rows for a hitchcock `director` job carry `repo_id` + type `director`.
- An untracked GitHub issue does not appear in `todo.md` until claimed.
- After migrate, dispatch worktrees do not carry a private `state.db` graph (they use the product path, like PEMs).

---

## 9. Test plan (when implemented; not this PR)

- Unit: resolve DB from `identity_slug`; story requires `repo_id`; epic children differ by `repo_id`; cost/job require type id; claim vs unlinked issue; leftover repo DB doctor; refuse silent merge of two DBs.
- No live GitHub ingest required for unit tests.
