<!-- generated - source of truth is state.db -->
---
decision_id: dec-20260925-goal-arc-triage
topic: "Goal and roadmap-arc triage: close shipped work, absorb empty Vizor duplicates, restore roadmap.md from state.db"
date: 2026-09-25
panel: [grok]
status: applied
backup: /Users/nikhilsoman/.synlynk/workspaces/backups/state-20260925T111303Z.db
---

## Topic

`project-docs/roadmap.md` on `main` was a brownfield skeleton (`feat+vizor-governs-board-and-gantt-ia`), while `roadmap_arcs` / `roadmap_phases` in canonical `state.db` still held the real history — with stale `planned` / `in_progress` flags on work that had already shipped. Thirty-five goals were all `active`, including 5/5 shipped epics and empty shells absorbed into the Vizor master goal.

This record is the cleaned triage. It was applied to `state.db` the same day, then `roadmap.md` was regenerated from the live arcs.

## Evidence used

- Canonical ledger: `~/.synlynk/workspaces/synlynk/state.db`
- Public product: **v0.22.0** (2026-09-24); Graphify canvas **#1777** on 2026-09-25
- Master 4-wave plan: `docs/superpowers/plans/2026-09-19-master-4-wave-roadmap-and-autonomous-execution.md`
- Wave tracker: `project-docs/master_wave_tasklist.md` (Wave 1–2 marked done; Wave 3–4 pending)
- CHANGELOG Unreleased: Wave 3 hosted Teams hub

## Goal triage

### Mark `done` (stories complete and shipped)

| Goal | Stories | Why |
|---|---|---|
| `goal-c75ff209` Model catalog & quota calibration | 5/5 | Shipped in v0.21 (#1727) |
| `goal-9011307c` Frontier QA testbed | 5/5 | Shipped in v0.21 (#1719) |
| `goal-bde24050` Job-status/cost truth + GH-write | 4/4 | Epic A/B on main; deadline 2026-08-31 |
| `goal-250b6fb2` Dynamic home-harness orchestrator parity | 1/1 | Wave 1 Task 1.2 shipped |
| `goal-6ebfe9b5` Loud harness failure | 2/2 | Criterion met as a standing bar; stories closed |
| `goal-3b45a961` Declarative fleet parity + in-browser role wizard | 0/0 | Shipped #1563; never linked stories |

### Mark `superseded` (absorbed)

| Goal | Successor | Why |
|---|---|---|
| `goal-70317121` Vizor workspace-first HUD | `goal-e3840370` | Empty shell after 2026-09-24 consolidation |
| `goal-f0489be9` Vizor World View radar | `goal-e3840370` | Same work lives as stories under the master Vizor goal |

### Keep `active` — now / next

| Goal | Stories | Role |
|---|---|---|
| `goal-e3840370` Vizor master control plane | 6/20 | Primary product surface |
| `goal-d3333441` Control-plane trust and closure | 1/4 | Deadline 2026-10-01 |
| `goal-85656c82` Developer Experience v1.0 | 4/26 | Wave 1 pillars shipped; taxonomy/FTUE still open |
| `goal-6733bbf1` state.db sole mutation for project-docs | 1/1 | Story closed but **criterion failed** — brownfield skeleton overwrote `roadmap.md` |
| `goal-8f64eff5` Platform health | 1/5 | Sentinel/worktree operating loop |
| `goal-005ea87d` Fleet harness parity | 7/9 | Two harness gaps remain |
| `goal-adb60ccc` Home vs headless analytics | 7/8 | One story left |
| `goal-ef42902a` Team/enterprise messaging | 1/2 | Wave 2 code shipped; goal not closed |
| `goal-a222b393` Agent charter framework | 4/7 | Remaining charter work |
| `goal-90e73dfd` GOVERNS checkpoint directives | 0/13 | Next named release |
| `goal-9ef9a965` Release announcement | 0/4 | v1.0.0 preview collateral |
| `goal-0c4e96ff` Book/blog readership | 1/22 | Blog protocol still paused for IP review |

### Keep `active` — Wave 3 / 4 / later (do not hide)

| Goal | Stories | Wave |
|---|---|---|
| `goal-d8cb407d` Enterprise state sync + multi-tenant billing | 0/2 | Wave 3 |
| `goal-56d4beee` Local oMLX 5th agent | 4/5 | Wave 4; deadline 2026-09-01 missed |
| `goal-c7113f58` DeepSeek / ACP / Herdr cockpit | 0/5 | Post-v1.0 |
| `goal-1d104154` Sparse/virtualized workspaces | 1/2 | Later |
| `goal-abecd18c` OS-level sandboxing | 0/1 | Later |
| `goal-2a05ef8a` SCIP / Tree-sitter graph | 0/1 | Overlaps Graphify; keep until scoped |
| `goal-bf5af39f` Speculative rebase / AST merge | 0/1 | Later |
| `goal-06758149` Fleet on rxcc / other products | 0/0 | Adoption, not synlynk-core |
| `goal-0b891b5f` Release agent | 0/0 | Spec exists, unbuilt |
| `goal-f424fc4c` TPM agent | 0/0 | Spec exists, unbuilt |
| `goal-36dc2ed3` Real maturity-tier detection | 0/0 | DX follow-on |
| `goal-71aacece` Suggestion telemetry | 0/0 | DX follow-on |
| `goal-bc0011cd` pr-check GOVERNS hard-block | 0/0 | After false-positive measurement |
| `goal-eacab0dc` Universal GOVERNS enforcement | 0/0 | After checkpoint pilot |
| `goal-d38e3c83` Scheduler v2 | 0/1 | Deadline 2026-08-10; still gated on v1 production data |

No goals were deleted.

## Arc triage

### Status corrections on existing arcs

| Version | Was | Now | Notes |
|---|---|---|---|
| `v0.9.5` Health Pulse | planned | superseded | Absorbed into v0.9.8 |
| `v0.9.6` Exit + Repair + Sync | planned | superseded | Absorbed into v0.9.8 |
| `v0.8.1–v0.8.4` Agent Fleet | planned | deferred | Post-GA; TPM/Release agents remain as goals |
| `v0.13.0` State Engine Tier 1 | in_progress | shipped | Followed by v0.13.1 patch |
| `epic-job-truth-2026-08` | in_progress | shipped | 9/10 phases done; leftover B3 deferred |
| `v0.19.0` Foundation & platform health | planned | shipped | Named release 2026-09-11 |
| `v0.20.0` BS-6 views & deep intel | planned | shipped | Named release 2026-09-19 |

### Duplicate brownfield rows (deleted)

These were parser accidents (markdown headings re-inserted as versions): `v0.1`, `v0.4.0`, `v0.5.0`, `v0.8.1` (ids 26–29). Canonical rows `v0.1–v0.3.0`, `v0.4.0–v0.4.2`, `v0.5.0–v0.6.1`, `v0.8.1–v0.8.4` remain.

### Named releases that existed in CHANGELOG but not as arcs (added)

| Version | Status | Target | Title |
|---|---|---|---|
| `v0.21.0` | shipped | 2026-09-23 | Autonomous Multi-Home & Teams Relay Mesh |
| `v0.22.0` | shipped | 2026-09-24 | Multi-Workspace Vizor Hub & Resilient State Isolation |
| `v0.23.0` | shipped | 2026-09-25 | Graphify Auto-Extraction & Vizor Unified Canvas |

### Current and next (unchanged intent, clarified notes)

| Version | Status | Target | Role |
|---|---|---|---|
| `v1.0.0-rc1` | planned | 2026-10-01 | 15-minute first-win field trials & zero-risk install |
| `1.0.0` | planned | 2026-10-01 | Developer Preview public launch (Wave 1 ceremony; **not yet tagged**) |
| `v1.0.0` | planned | post-preview | Community-layer GA (workgroup protocol, signed ledger) — distinct from `1.0.0` preview |
| `v1.1.0` / `v1.2.0` / `v1.3.0` | planned | Q4 2026–Q2 2027 | Map onto Wave 3 Teams Server, Wave 4 Model Hub, domain communities |
| `Future Expansions` | planned | TBD | Workspace-level multi-repo identities |

### Phase updates

- `v0.19.0` phases → `done`
- `v0.20.0` phases → `done`
- `epic-job-truth-2026-08` remaining `planned` phase (B3 MCP/review) → `deferred`

## Restore rule for `roadmap.md`

1. Mutate `roadmap_arcs` / `roadmap_phases` via `synlynk roadmap add` (or equivalent DB write + `_generate_roadmap_md()`).
2. Copy the generated view into git-tracked `project-docs/roadmap.md`.
3. Do not hand-edit the generated file. Brownfield `init --brownfield` must not overwrite a migrated ledger's roadmap; that is remaining work on `goal-6733bbf1`.

## Decision

Apply the tables above to canonical `state.db`, regenerate `roadmap.md` from live arcs, and keep the Vizor master goal plus Wave 3/4 goals active. Do not invent a v1.0.0 tag; Developer Preview remains the 01 Oct ceremony.

[@grok, @nikhilsoman]
