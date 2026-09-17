# Workspace identity W3 — Product board (Vizor) and export protocol

**Date:** 2026-09-17  
**Status:** Approved in chat 2026-09-17 (Nikhil): Vizor Board reads product `state.db`; GitHub Projects v2 is not the SoT; tracker adapters do **import and export**; generic export protocol for other surfaces. Implementation is **out of scope** until this spec is on `main` and a plan exists.  
**Issue:** [#914](https://github.com/nikhilsoman/synlynk/issues/914)  
**Depends on:** W0, W2  
**Hosted:** Teams/Enterprise web Vizor is **W9**, not this file. Local Vizor remains the dogfood surface.  
**Author:** Nikhil Soman (brainstorm with Grok, Home Conductor)

---

## 1. Problem

W2 is the product graph. Humans still need a **board**: one place to see claimed work across constituent repos, sliced by `repo_id` and type, with deep-links to GitHub Issues or Linear.

Today Vizor Gantt/Observatory are **one checkout**. GitHub Projects v2 was named in the program table as if it were the board. That fights Linear-tracker products and would make Projects the second graph.

W3 is the **layer above tickets**. Native UI is Vizor. External boards are adapters. No code in this file. **#914 stays OPEN.**

---

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| Board SoT | Product `state.db` (W2). Vizor Board/Gantt render it |
| GitHub Projects v2 | One **adapter**, not the board. Setup lives with that adapter |
| Tracker sync | When adding Linear (or Jira, Asana, ShotGrid, Projects, …): **import and export**, both directions |
| Other surfaces | **Export protocol** (stubs): Slack, Notion, CSV, … — no SDKs in this epic |
| Organigram | W8 tab — humans + types, not the work board |
| Hosted web | **W9** — entire Vizor, not a subset |

Status changes in Vizor write `state.db` (same path as `synlynk story done`), then W2 doc slices. Vizor does **not** scrape GitHub Projects or Linear as truth.

---

## 3. Vizor Board (local)

Product-scoped: one graph, all `repo_id`s. Filters: repo, type id, epic/goal.

Existing tabs (Gantt, Journeys, Architect Map, Effort, Efficiency, Observatory, onboarding/roles) stay. Add **Board** (claimed stories/epics). **Organigram** is W8.

Solo monorepo: same machine, one `repo_id` — looks like today’s Vizor plus Board.

Cards deep-link W2 pointers `{tracker, container, id}` and GitHub PRs.

---

## 4. Import / export (adapters, not this PR)

Each tracker adapter (Linear named in W2; GitHub Issues already the default; Projects v2 / Jira / Asana / ShotGrid / Monday stub) **must** declare:

| Direction | Job |
|:---|:---|
| **Import** | Claim/link tickets into `state.db` (W2 ingest) |
| **Export** | Push story/epic status (and optional cards) to that surface |

GitHub Projects v2 requires GitHub setup anyway — explore it **when** that adapter is built, together with Linear, not as a one-off in W3 implementation.

**Export protocol** (illustrative): `{ "surface": "linear"|"github_projects"|"notion"|<open>, "product": "<slug>" }`. Unknown surface → fail closed until implemented. Same spirit as W8 `gateway`.

---

## 5. Non-goals (W3)

- Implementing Board UI, Linear SDK, Projects v2 sync
- Hosted Vizor / OAuth / `synlynk.com/<slug>` — **W9**
- Replacing GitHub as the forge
- Closing #914

---

## 6. Success

- A vdowrx Board shows frontend + api stories from one `state.db`; cards open GitHub or Linear as pointed.
- Dragging a card to Done updates the DB and the home-repo/slice docs, not Projects-as-truth.
- Hitchock on GitHub Issues needs no Projects setup to use Vizor Board.
- Adding Linear later is an adapter with import+export, not a new graph.

---

## 7. Test plan (when implemented; not this PR)

- Unit: Board query is product-scoped; filter `repo_id` / type; unknown export surface fail-closed; status write goes to `state.db` not a tracker mock as SoT.
- No live Projects/Linear in unit tests.
