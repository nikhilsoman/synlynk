<!-- generated - source of truth is state.db -->
---
decision_id: dec-2802c17e
topic: "v0.26.7 Vizor Interactive spec panel 20261031

You are on a synlynk decide panel. The wrapper may ask for 200-400 words; ignore that cap. Answer ALL FOUR questions with evidence. End with a clear position. Do not implement code.

AGENDA SPEC (Proposed, PR #4969, issue #4966, milestone v0.26.7):
docs/superpowers/specs/2026-10-31-v0.26.7-vizor-interactive-write-path-design.md

Read that file if you can. Digest if you cannot:

v0.26.6 tagged (heartbeat, SSE, read-only sentinel). Next number is v0.26.7 — one slot, not two. Original Jantt cut is Wave E inside this edition. Skinny payloads #2671/PR #4963 shipped. Waves: A link repair #4967; B row Gantt #4968 (GOVERNS columns, task rows, fill volume); C write-path sweep (daemon currently drops VizorHandler POSTs such as /note); D sentinel HUD #2672; E Jantt vendor GOVERNS-only; F dive list. Chrome is index.html iframe. Live 404s: /tube.html /timeline.html /note. Board stage/status already writes. GOVERNS edits lock-by-default. No VERSION bump until the named-release cut. #2470 unchanged. Epic #2458 stays open.

LIVE HUB (screenshot 2026-10-31, http://localhost:33333/w/synlynk/index.html Agent Roles): sidebar lists synlynk plus base, bprepo, chore-local-unattended-lifecycle, coldtest, and many djob-* folders. Roles show Dispatch-only, Target Harnesses Unassigned, No charter excerpt, Edit Charter buttons. Breadcrumb TELEMETRY > Agent Roles.

QUESTIONS

1. VIEW: Does this spec cover Vizor as a local dashboard to view all synlynk activity for a set of workspaces on the user's machine? What is missing (jobs, heartbeats, sentinel, costs, board, gantt, graphify, hub, multi-workspace)?

2. CONTROL: Does this spec cover Vizor as a local dashboard to control, manage, and engage all synlynk services without the terminal (install may be the exception)? Map each service (dispatch, stage/status, notes, roles/charters, sentinel ack, viz --ensure, daemon, identity, worktree cleanup) to live-write / stub / missing.

3. JANTT vs SYNLYNK GANTT: Does Jantt qualify as replacement or enhancement of the current Gantt page? Classical calendar CPM vs synlynk's high-velocity agentic GOVERNS stages, and non-software workspaces (e.g. content creation). Should Wave B (row Gantt) stand even if Wave E never vendors Jantt?

4. CLEAN ENVIRONMENT: Temp worktrees and other folders creep into the Vizor workspace list (djob-*, job-*, coldtest, chore-local-unattended-lifecycle in the screenshot). How should Hub/registry filter or fence them so the local dashboard stays a clean set of real workspaces?

Decision framing: keep one v0.26.7 edition; do not drop Jantt; do not mess up milestone sequence after v0.26.6. Say what must be in the spec before sign-off vs Wave F dive."
date: 2026-10-31
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
v0.26.7 Vizor Interactive spec panel 20261031

You are on a synlynk decide panel. The wrapper may ask for 200-400 words; ignore that cap. Answer ALL FOUR questions with evidence. End with a clear position. Do not implement code.

AGENDA SPEC (Proposed, PR #4969, issue #4966, milestone v0.26.7):
docs/superpowers/specs/2026-10-31-v0.26.7-vizor-interactive-write-path-design.md

Read that file if you can. Digest if you cannot:

v0.26.6 tagged (heartbeat, SSE, read-only sentinel). Next number is v0.26.7 — one slot, not two. Original Jantt cut is Wave E inside this edition. Skinny payloads #2671/PR #4963 shipped. Waves: A link repair #4967; B row Gantt #4968 (GOVERNS columns, task rows, fill volume); C write-path sweep (daemon currently drops VizorHandler POSTs such as /note); D sentinel HUD #2672; E Jantt vendor GOVERNS-only; F dive list. Chrome is index.html iframe. Live 404s: /tube.html /timeline.html /note. Board stage/status already writes. GOVERNS edits lock-by-default. No VERSION bump until the named-release cut. #2470 unchanged. Epic #2458 stays open.

LIVE HUB (screenshot 2026-10-31, http://localhost:33333/w/synlynk/index.html Agent Roles): sidebar lists synlynk plus base, bprepo, chore-local-unattended-lifecycle, coldtest, and many djob-* folders. Roles show Dispatch-only, Target Harnesses Unassigned, No charter excerpt, Edit Charter buttons. Breadcrumb TELEMETRY > Agent Roles.

QUESTIONS

1. VIEW: Does this spec cover Vizor as a local dashboard to view all synlynk activity for a set of workspaces on the user's machine? What is missing (jobs, heartbeats, sentinel, costs, board, gantt, graphify, hub, multi-workspace)?

2. CONTROL: Does this spec cover Vizor as a local dashboard to control, manage, and engage all synlynk services without the terminal (install may be the exception)? Map each service (dispatch, stage/status, notes, roles/charters, sentinel ack, viz --ensure, daemon, identity, worktree cleanup) to live-write / stub / missing.

3. JANTT vs SYNLYNK GANTT: Does Jantt qualify as replacement or enhancement of the current Gantt page? Classical calendar CPM vs synlynk's high-velocity agentic GOVERNS stages, and non-software workspaces (e.g. content creation). Should Wave B (row Gantt) stand even if Wave E never vendors Jantt?

4. CLEAN ENVIRONMENT: Temp worktrees and other folders creep into the Vizor workspace list (djob-*, job-*, coldtest, chore-local-unattended-lifecycle in the screenshot). How should Hub/registry filter or fence them so the local dashboard stays a clean set of real workspaces?

Decision framing: keep one v0.26.7 edition; do not drop Jantt; do not mess up milestone sequence after v0.26.6. Say what must be in the spec before sign-off vs Wave F dive.

## Panel Inputs

### claude
[model=default; version=2.1.311 (Claude Code)]

## Analysis

**1. VIEW.** The spec covers Vizor's view inventory thoroughly for synlynk's own write surface (section 3's 19-row table, section 4 links, section 5 Gantt layout), but it is explicitly scoped to a single workspace's existing pages, not "all synlynk activity for a set of workspaces." Jobs, heartbeats (v0.26.6), sentinel (read-only, #2672 deferred), costs, board (live), and Gantt are all present or in-flight. Missing from this edition by design: multi-workspace aggregation/switching, graphify (dive list only, inspect-source is a stub), and Hub's cross-workspace rollup (filtering is dive, not aggregation). The spec is honest about this — it's a per-workspace write-path sweep, not a multi-workspace rollup spec. That's fine for v0.26.7 scope but should be named explicitly as a gap for a future edition, not silently assumed solved.

**2. CONTROL.** Mapping is strong and the most complete part of the spec (section 3 + section 6). Dispatch: not addressed here (out of scope, presumably pre-existing elsewhere). Stage/status: live-write today, kept. Notes: stub→live (proxy `/note`). Roles/charters: stub, CTA exists on `VizorHandler` but not daemon — proxy-or-hide decision deferred to sweep, which is acceptable but should be a Wave C decision point, not left open-ended. Sentinel ack: explicitly out of scope (#2672). `viz --ensure`/daemon/identity/worktree cleanup: not mentioned at all — these are CLI-level services with no Vizor control-surface mapping in this spec. That's a real gap if "control everything without the terminal" is the long-term bar, but it's consistent with the spec's stated boundary (Vizor write-path for existing handlers only, not new CLI-replacement surface).

**3. JANTT vs GANTT.** The spec gets this right: Wave B (row Gantt — stages as fixed columns, tasks as rows, fill-volume cells) stands on its own and fixes a real defect (current layout inverts tasks into column headers). Wave E (Jantt vendoring) is correctly sequenced *after* B, scoped GOVERNS-only, explicitly barred from Firebase/CRDT cloud rooms and from `workspace_views.logical`. This correctly treats Jantt as a potential CPM-calendar *option* layered on top of a row model that must exist regardless of whether Jantt ever lands — not a prerequisite. Classical CPM (fixed calendar dates, dependency chains) is a mismatch for agentic GOVERNS velocity and non-software workspaces (content creation has no CPM dependency graph); keeping Jantt optional and decoupled is the correct hedge. Wave B shipping independently of Wave E is good design.

**4. CLEAN ENVIRONMENT.** Correctly identified (Hub row, dive list) but deferred — not committed to A–C. Given the screenshot shows `djob-*`/`coldtest`/`chore-local-unattended-lifecycle` already cluttering the live Hub, this is close to becoming a trust/usability problem for the dashboard's core promise. It's reasonable as dive-list for *this* edition, but it shouldn't slip past v0.26.7 entirely.

## Position

**Approve for sign-off**, with one addendum before Nikhil signs: add an explicit note in section 8 (or a new short section) stating that multi-workspace aggregation and CLI-service parity (viz --ensure, identity, worktree cleanup) are known-out-of-scope for v0.26.7, deferred to a future edition — not silently solved. Also recommend the Hub junk-slug filter be pulled from Wave F into Wave C's scope or an explicit Wave C.5, given it's already visibly degrading the live dashboard today, not a hypothetical future issue. Everything else — the single v0.26.7 slot, Jantt-after-row-Gantt sequencing, lock-by-default GOVERNS edits, Role App token restriction — is sound and should ship as written.

### agy
[model=default; version=1.4.12]

**Last completed task:** `docs: v0.26.7 Vizor Interactive (write-path) edition spec` ([121794e9](file:///Users/nikhilsoman/dev/synlynk/.worktrees/docs-grok-v0267-vizor-interactive/docs/superpowers/specs/2026-10-31-v0.26.7-vizor-interactive-write-path-design.md), PR [#4969](https://github.com/nikhilsoman/synlynk/pull/4969))  
**Next task from `todo.md`:** Review & decision on v0.26.7 Vizor Interactive write-path design spec ([#4966](https://github.com/nikhilsoman/synlynk/issues/4966))

---

### 1. VIEW: Local Dashboard Coverage & Gaps
The proposed spec ([2026-10-31-v0.26.7-vizor-interactive-write-path-design.md](file:///Users/nikhilsoman/dev/synlynk/.worktrees/docs-grok-v0267-vizor-interactive/docs/superpowers/specs/2026-10-31-v0.26.7-vizor-interactive-write-path-design.md)) **does not** fully cover Vizor as an integrated local dashboard for *all* synlynk activity across workspaces on the host machine. Instead, it addresses intra-workspace iframe rendering and navigation repairs for a single workspace at a time.

**Evidence of gaps across core view dimensions:**
* **Multi-workspace & Hub:** The Hub ([`_workspace_index_html`](file:///Users/nikhilsoman/dev/synlynk/.worktrees/docs-grok-v0267-vizor-interactive/synlynk/vizor_daemon.py#L447-L495)) simply renders disconnected cards linking to `/w/<slug>/index.html`. There is no cross-workspace aggregation or unified operational summary.
* **Jobs & Dispatches:** Dispatched background jobs (`job-*`, `djob-*`) have no telemetry card or live run monitor. Dispatches are invisible unless checking console logs.
* **Heartbeats:** While the daemon maintains a render heartbeat ([`vizor_daemon.py:300`](file:///Users/nikhilsoman/dev/synlynk/.worktrees/docs-grok-v0267-vizor-interactive/synlynk/vizor_daemon.py#L300)), individual agent session heartbeats across local workspaces are not rolled up or monitored.
* **Sentinel:** Read-only per v0.26.6 contract ([`overview.html`](file:///Users/nikhilsoman/dev/synlynk/.worktrees/docs-grok-v0267-vizor-interactive/docs/superpowers/specs/2026-10-31-v0.26.7-vizor-interactive-write-path-design.md#L44)). Machine-wide invariant checks, stale locks, and failed verifications are absent from Hub view.
* **Costs:** `effort.html` and `efficiency.html` exist per workspace, but machine-level fleet burn rate, token spend, and multi-workspace budget rollups (`project-docs/costs.md`) have no dashboard view.
* **Board & Gantt:** Board writes work; Gantt view is broken by inverted drill layout (tasks as columns) and 404ing `/note` writes ([`gantt.py`](file:///Users/nikhilsoman/dev/synlynk/.worktrees/docs-grok-v0267-vizor-interactive/docs/superpowers/specs/2026-10-31-v0.26.7-vizor-interactive-write-path-design.md#L107-L115)).
* **Graphify & Logical:** Graphify inspect is dead (`href="#"`); Logical expand-for-detail is deferred to Wave F after skinny payloads stripped the embed tree.

---

### 2. CONTROL: Terminal-Free Management & Service Mapping
The spec recognizes the architectural defect—that `synlynk/viz/server.py` implements handlers that [`synlynk/vizor_daemon.py`](file:///Users/nikhilsoman/dev/synlynk/.worktrees/docs-grok-v0267-vizor-interactive/synlynk/vizor_daemon.py#L889-L913) completely drops—but it does **not** provide terminal-free operation across the synlynk platform.

**Service Mapping:**
1. **stage/status:** **LIVE-WRITE**. Exposed on daemon via `/w/<slug>/api/board/stage` and `/api/board/status` ([`vizor_daemon.py:889-913`](file:///Users/nikhilsoman/dev/synlynk/.worktrees/docs-grok-v0267-vizor-interactive/synlynk/vizor_daemon.py#L889-L913)).
2. **notes:** **STUB / 404**. Gantt client fires `fetch('/note')`; daemon has no route, returning 404 despite `VizorHandler._handle_note_request` existing in `server.py:246`.
3. **roles/charters:** **STUB**. `roles.html` provides "Edit Charter" buttons and `POST /roles/create`, but daemon drops it. Target harnesses show unassigned.
4. **sentinel ack:** **STUB (READ-ONLY)**. Sentinel panel is strictly read-only per v0.26.6 lock; ACK writes are deferred to Wave D ([#2672](https://github.com/nikhilsoman/synlynk/issues/2672)).
5. **dispatch:** **STUB**. `VizorHandler._handle_dispatch_request` exists in `server.py:248`, but the daemon does not proxy it and no frontend control view exposes dispatch trigger controls.
6. **worktree cleanup:** **STUB**. `_handle_worktree_clean_request` exists in `server.py:258`, but has no daemon route and no UI button on Hub/Chrome.
7. **viz --ensure:** **MISSING**. No interface to inspect daemon health, trigger render pumps, or verify port leases (`MEMORABLE_VIZOR_PORTS`) from the browser.
8. **daemon lifecycle:** **MISSING**. Daemon start/stop/restart is strictly CLI-based (`synlynk viz daemon`).
9. **identity / auth:** **MISSING**. No UI to select or inspect agent role tokens or credential states; local write auth relies on implicit `authorize_local_request` sidecars.

---

### 3. JANTT vs. SYNLYNK GANTT: Replacement vs. Enhancement
* **Jantt is an enhancement, not a replacement.**
* **Classical CPM vs. Agentic GOVERNS:** Jantt is built around calendar-day Critical Path Method (CPM) with ISO timestamps (`start`, `end`, working calendars, dependencies). In contrast, synlynk is an autonomous multi-agent system executing discrete milestone transitions (GOVERNS: Goals, Opportunities, Values, Execution, Review, Next, Ship) where sub-tasks advance through stages in minutes or hours, not calendar weeks. 
* **Non-Software Workspaces:** For content creation, publishing, or multi-week product roadmaps, calendar-based CPM is valuable at the strategic tier. However, for active agentic pipeline execution, stage occupancy, dependency blockers, and fill volume represent true pipeline health.
* **Wave B Standing:** **Wave B (row Gantt) MUST stand on its own.** Wave B fixes an egregious native rendering bug ([#4968](https://github.com/nikhilsoman/synlynk/issues/4968): tasks rendering as columns and labels overflowing cells) using lightweight GOVERNS-only payloads. It must not depend on Jantt. Wave E vendoring (`@jantt/core` + `@jantt/standalone`) can sit alongside Wave B or offer an alternate calendar toggle, without cloud/CRDT coupling.

---

### 4. CLEAN ENVIRONMENT: Hub Worktree & Workspace Fencing
* **The Root Cause:** In [`synlynk/vizor_daemon.py:166-177`](file:///Users/nikhilsoman/dev/synlynk/.worktrees/docs-grok-v0267-vizor-interactive/synlynk/vizor_daemon.py#L166-L177), `_is_transient_test_path()` only filters test prefixes like `/pytest-` and `synlynk-selftest`. Any background dispatch (`synlynk dispatch`), subagent worktree, or CLI operation calling `open_state_db()` writes directly to `state_registry.json`. Thus, `djob-*`, `job-*`, `chore-*`, and `.worktrees/*` entries leak straight onto Hub's cards.
* **Required Fencing Strategy:**
  1. **Registration Fencing:** Dispatch runners and subagent worktree sessions must pass `--transient` or set `SYNLYNK_EPHEMERAL_WORKSPACE=1`, omitting registration in `state_registry.json` entirely.
  2. **Daemon Hub Filter Rule:** Upgrade `_is_transient_test_path()` to `_is_ephemeral_workspace(slug, repo_path)` to exclude patterns matching `djob-*`, `job-*`, `chore-*`, `coldtest*`, or any repo path located under `.worktrees/`.
  3. **Hub UI Split:** By default, display only canonical primary repositories. Provide a collapsed secondary drawer or filter toggle (*"Active Ephemeral Worktrees [N]"*) for debugging running agent jobs without cluttering the primary dashboard.

---

### Recommendation & Panel Position
**I recommend CONDITIONAL SIGN-OFF on the v0.26.7 spec.** 
Do not split the release into v0.26.8; keep the single coherent v0.26.7 milestone. Wave B must stand independently to fix native agentic Gantt rendering, with Jantt remaining strictly in Wave E as an opt-in calendar enhancement. However, **Hub workspace fencing (Question 4) must NOT be relegated to the Wave F dive list**; leaking transient worktrees directly degrades the dashboard's primary user experience. The spec should promote Hub ephemeral slug filtering into Wave A/C scope, while keeping brainstorm file serving, Journeys redirect cleanup, and Graphify inspect in Wave F. With this adjustment, approve and sign off on PR [#4969](https://github.com/nikhilsoman/synlynk/pull/4969).

### codex
[model=default; version=codex-cli 0.163.0]

1. **View:** Partially. The spec gives Vizor a strong read/write surface for board, Gantt, activity, topology, telemetry, roles, and hub, and explicitly preserves heartbeat/SSE, sentinel read-only behavior, skinny payloads, and Graphify-related views. However, “all synlynk activity across a clean set of local workspaces” is not yet fully specified. Jobs/dispatch history, heartbeat health, sentinel state, costs, board, Gantt, Graphify, Hub, and multi-workspace aggregation need an explicit coverage matrix. Costs and job lifecycle are especially absent; the Hub is only slated to filter transient slugs in Wave F.

2. **Control:** The write-path intent is correct, but coverage is uneven. Board stage/status is already live. Dispatch, notes, approve/kill, daemon stream, graph refresh, onboarding, roles/charters, worktree cleanup, and tool installation exist in `VizorHandler` but are missing from the always-on daemon, so they are currently stubs/gaps requiring proxying or retargeting. Sentinel acknowledgement is hosted by this milestone but remains dependent on #2672’s write-path spec. `viz --ensure`, identity/token behavior, and service lifecycle are not mapped. Worktree cleanup is listed as a route but needs explicit authorization and confirmation semantics. The spec should add a service-by-service live-write/stub/missing table before sign-off.

3. **Jantt vs Synlynk Gantt:** Jantt is not a replacement for the current semantic model. It is a classical calendar/CPM engine using `start`, `end`, and `dependsOn`; Synlynk’s Gantt is a high-velocity, stage-oriented GOVERNS view that also fits non-software workspaces such as content creation. Wave B therefore stands independently: it fixes the inverted task-as-column layout, preserves GOVERNS-only payloads, and establishes the correct row model. Wave E can enhance or sit beside it through an adapter, but must not be a dependency.

4. **Clean environment:** Hub/registry should distinguish canonical registered workspaces from generated/ephemeral worktrees using explicit metadata, path roots, and lifecycle/TTL—not filename filtering alone. `job-*`, `djob-*`, `coldtest`, and chore/test folders should be hidden by default, with an explicit “show transient” control and safe allowlisting for real workspaces.

**Position:** Keep one v0.26.7 edition, retain Waves A–E and Jantt, and preserve the post-v0.26.6 sequence. Require the service coverage matrix, multi-workspace/activity coverage, and clean-registry contract in the spec before sign-off; defer deeper UI/product dives to Wave F.

### grok
[model=default; version=grok 1.0.70 (f50904eaee6c) [stable]]

I'll read the v0.26.7 Vizor spec and the live hub evidence, then answer all four panel questions with a clear position.**Position:** Keep a single **v0.26.7** edition after tagged v0.26.6. Do not open v0.26.8, retitle #2470, or close #2458. Do not drop Jantt. Sign off only after the spec states the view boundary, a named control matrix, the Wave B/E coexistence rule, and a Hub fence. Wave F stays the dive list.

## 1. View

The spec covers Vizor as a **per-workspace** local dashboard, not as a machine-wide view of all synlynk activity.

What already renders, and what this edition does with it:

| Surface | In the spec | Gap |
|---|---|---|
| Hub | Read cards from `state_registry`; junk slugs are a dive | No cross-workspace rollup |
| Heartbeat / SSE | Shipped in v0.26.6; Overview is read-only | No fleet heartbeat view. Gantt still uses `EventSource('/events')` against daemon `/w/<slug>/api/daemon/stream` (dive) |
| Sentinel | Read panel stays read-only until #2672 | HUD is Wave D, and it still needs its own write-path spec |
| Jobs | Observatory is an existing read view; Activity only gets link repair | No job log, stream, or history contract |
| Costs | Effort is "classify; no silent stubs" | No burn, per-job, or cross-workspace cost view |
| Board | Live read/write | Kept |
| Gantt | Wave B is the real view fix | Today tasks are columns (`viz/gantt.py`) |
| Graphify | Tube iframe + link repair | Inspect-source is `href="#"` (dive) |
| Multi-workspace | Daemon `/` lists every registry product | Chrome is one iframe (`index.html` → `#view-frame`). Sidebar on the 2026-10-31 shot is inside synlynk, breadcrumb TELEMETRY > Agent Roles |

Missing as a product promise: one place that shows jobs, heartbeats, sentinel, and costs **across** the workspace set. Say that is out of this edition.

## 2. Control

This is not a terminal-free control plane. `authorize_local_request` plus daemon proxy of handlers that already exist is the committed control work. `synlynk/viz/server.py` implements `POST /note`, `/dispatch`, `/approve`, `/kill`, `/roles/create`, `/worktrees/clean`, `/tools/install`, `/graph/refresh`. `vizor_daemon.py` `do_POST` special-cases only `/w/<slug>/api/board/stage`, `board/status`, and proposal sign. Anything else falls through to `VizorHandler` **without** that workspace's cwd. Live `GET /note` is 404. Gantt `fetch('/note')` hits the origin root.

| Service | Class |
|---|---|
| Board stage/status | **Live-write** (`update_stage_for_context` / `update_status_for_context`) |
| GOVERNS stage/date edits | **Specified, not live.** Lock-by-default, transactional `roadmap update` into `state.db` |
| Notes | **Stub.** Handler writes `.synlynk/viz-notes.json`. Daemon path is the Wave C defect |
| Dispatch / approve / kill | **Handler only.** Not a named wave. Cwd-scoped `uxcore.dispatch` is unspecified |
| Roles / charters | **Stub + missing.** `POST /roles/create` can provision. Edit Charter in `synlynk/viz/roles.py` has no listener. The screenshot (Dispatch-only, Unassigned, "No charter excerpt", Edit Charter) matches that. Spec says "proxy or hide," and parks it on the dive list |
| Sentinel ack | **Missing** until #2672. Correctly not a silent Overview write |
| `viz --ensure`, daemon start/stop | **Missing.** Launchd/systemd ensure stays inside the daemon. No UI |
| Identity | **Missing.** Role App tokens only; no identity UI. Correct boundary |
| Worktree cleanup | **Handler only** (`/worktrees/clean`). Not in the inventory |

Install can stay a terminal exception. Do not sign a sweep whose classification table is "write it during implementation."

## 3. Jantt vs synlynk Gantt

Wave B stands even if Wave E never vendors Jantt.

Current Gantt is a stage ribbon plus an inverted drill: `repeat(N, 1fr)` where N is task count, names are column headers, bars overflow. Wave B is the synlynk model: **columns = GOVERNS stages** (fixed px, horizontal scroll), **rows = stories**, **cell fill = done / active / queued / blocked**. That matches high-velocity agentic stages. It also fits non-software workspaces, which still move through GOVERNS stages and often have no honest calendar.

Jantt is classical CPM (`start` / `end` ISO, `dependsOn`). The spec already says it is not the layout fix, and that it consumes GOVERNS-only JSON, never `workspace_views.logical`, with no Firebase/CRDT. Treat Wave E as an **optional calendar projection beside** the row grid, not a replacement and not a second source of truth. Content workspaces that grow real dates can use it later. Shipping B unblocks E. E does not gate the tag (section 7: D–F may land if ready; they do not hold the cut forever).

## 4. Clean Hub

The screenshot is the registry, not a sidebar bug. `_registered_workspaces()` returns every `state_registry` product whose `repo_path` and `canonical_path` exist. The only fence is `_is_transient_test_path` (`/pytest-`, `synlynk-selftest`, …). It does **not** drop `djob-*`, `job-*`, `coldtest`, or `chore-local-unattended-lifecycle`. `ensure_registered_product()` will mint a first-class product for any slug. The Hub search box only hides cards in the DOM. Each of those slugs is still polled and rendered.

A `job-*` / `djob-*` prefix filter, which is all section 8 promises, misses `coldtest` and `chore-local-*`. Fence at registry read, before sign-off:

- Default Hub and `poll_once` include products whose `repo_path` is **not** under `.worktrees/`, `job-` worktrees, or temp/pytest paths.
- Slug prefixes `job-` and `djob-` stay excluded even if the path check fails.
- Named fixtures (`coldtest`, unattended chore trees) need a registry `kind` (`product` vs `worktree` / `probe`) set at `ensure_registered_product` time. Prefix lists will rot.
- Do not delete registry rows in this edition. Hide and stop polling. Direct `/w/<slug>/` can keep working.
- Put an "Ephemeral" disclosure on the Hub if operators need them. Default view stays the real set: synlynk, base, bprepo, and peers that were actually registered as products.

## Before sign-off vs Wave F

**Write into the spec now:** one edition id (v0.26.7 only); view boundary (per-workspace reads stay, cross-workspace activity is out); the control table above with C limited to proxying calls the UI already makes, under workspace context; B canonical, E optional and same milestone; Hub fence rule (path + kind, not a CSS filter).

**Leave on Wave F:** Journeys stub, Settings `alert()`s, brainstorm file 404s, Graphify inspect, Logical expand, World/Infra writes, charter editor, daemon/ensure/identity controls, cross-workspace cost and job rollup.

Product code still waits for this file to be committed and for Nikhil's sign-off. No VERSION bump until the named-release cut.

## Synthesis
All four panelists converge on the same shape: approve the single v0.26.7 edition, keep Jantt as an optional Wave E enhancement that doesn't gate Wave B, and treat Hub junk-slug fencing as more urgent than the current Wave F placement implies. The real disagreement is only about how much must be nailed down in the spec text before sign-off vs. left to Wave C/F implementation discretion — codex and grok want an explicit named table/contract in the document itself; claude and agy are comfortable with a clear verbal commitment plus a promoted-priority note.

Convergent findings across all four:

1. **View**: This is a per-workspace write-path sweep, not a multi-workspace activity rollup. Costs, job/dispatch history, and cross-workspace aggregation are out of scope and should be *named* as deferred, not silently implied as solved.
2. **Control**: Uneven but mappable. Board stage/status is live. Notes/roles/charters/dispatch/approve/kill/worktree-cleanup all exist as `VizorHandler` routes but aren't proxied by the daemon per-workspace — that's exactly Wave C's defect to fix. `viz --ensure`, daemon lifecycle, and identity are correctly out of scope for a browser UI.
3. **Jantt vs Gantt**: Not a replacement. Wave B (row-based GOVERNS Gantt) is a correctness fix that must ship regardless of Wave E. Jantt's CPM/calendar model is a bad fit for agentic velocity and non-software workspaces, so it stays an optional, decoupled, GOVERNS-only-payload projection beside the row grid — never a dependency, never touching `workspace_views.logical`, never cloud/CRDT-coupled.
4. **Clean environment**: The current `_is_transient_test_path` filter is too narrow (misses `coldtest`, `chore-local-*`, broad `djob-*`/`job-*` patterns) and is only slated for Wave F. All four flag this as a live, visible defect today, not a hypothetical — it should be pulled forward (claude/agy: into Wave C scope; grok/codex: an explicit registry-level `kind`/path-root fence, not a filename-prefix list) rather than left to the dive list.

Decision: Approve PR #4969 as a single v0.26.7 edition (no split into v0.26.8, no change to #2470 or #2458), with Waves A–F and Jantt sequencing preserved exactly as proposed — Wave B stands independently of Wave E, and Wave E remains optional/GOVERNS-only/non-blocking. Before Nikhil signs off, the spec must be amended to add: (a) an explicit statement that multi-workspace/cross-workspace activity rollup, costs aggregation, and CLI-service parity (`viz --ensure`, daemon lifecycle, identity) are out-of-scope for this edition and deferred to a future one, not silently solved; (b) a named service-level live-write/stub/missing table for the Wave C write-path sweep (notes, roles/charters, dispatch, approve/kill, worktree cleanup) so implementation isn't left to discover scope mid-sweep; and (c) promotion of Hub ephemeral-workspace fencing out of Wave F into Wave A/C — using registry-level path-root/`kind` metadata rather than a brittle slug-prefix filter — since it is degrading the live dashboard today. With those three additions, sign off; everything else (lock-by-default GOVERNS edits, sentinel staying read-only pending #2672, no VERSION bump before the named-release cut) ships as written.

## Decision
Decision: Approve PR #4969 as a single v0.26.7 edition (no split into v0.26.8, no change to #2470 or #2458), with Waves A–F and Jantt sequencing preserved exactly as proposed — Wave B stands independently of Wave E, and Wave E remains optional/GOVERNS-only/non-blocking. Before Nikhil signs off, the spec must be amended to add: (a) an explicit statement that multi-workspace/cross-workspace activity rollup, costs aggregation, and CLI-service parity (`viz --ensure`, daemon lifecycle, identity) are out-of-scope for this edition and deferred to a future one, not silently solved; (b) a named service-level live-write/stub/missing table for the Wave C write-path sweep (notes, roles/charters, dispatch, approve/kill, worktree cleanup) so implementation isn't left to discover scope mid-sweep; and (c) promotion of Hub ephemeral-workspace fencing out of Wave F into Wave A/C — using registry-level path-root/`kind` metadata rather than a brittle slug-prefix filter — since it is degrading the live dashboard today. With those three additions, sign off; everything else (lock-by-default GOVERNS edits, sentinel staying read-only pending #2672, no VERSION bump before the named-release cut) ships as written.

> Signatures: see 2026-10-31-v0-26-7-vizor-interactive-spec-panel-202.json
