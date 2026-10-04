# Five-Track Code-Adjacency Plan (consolidated, 2026-10-04)

## Provenance

This plan is built on GitHub epics **#1985–#1989** ("Code-proximity regroup"), filed
2026-10-03, which superseded earlier by-POV-section epics #1971/#1972. The epics
group the 10-item Consolidated Architecture Roadmap, the Surface Simplification Plan,
and the Broader Five-POV Issues Remediation Plan
(`docs/strategy/2026-10-02-decide-panel-roadmap.md`) by shared code module rather than
by which panel section originally raised them.

This doc adds: (a) issues surfaced during the last ~48h of implementation work,
assigned to whichever track owns the file they touch, and (b) current status per
item as of 2026-10-04, verified directly against `gh pr view` / `gh issue view`
(not from `synlynk jobs` labels — see `feedback_pr_review_discipline` /
job-status-truth memory on why labels alone aren't trusted).

Role split in force: Claude = PM/review/deploy only. All implementation below routes
to Codex/Grok (Agy deprioritized per `feedback_prefer_codex_grok_over_agy` memory)
via `synlynk dispatch`.

---

## Track 1 — Dispatch/Harness Layer (gh:#1985)

**Shared surface:** `synlynk/dispatch.py` (4,265 lines), `synlynk/harness_adapters/*.py`,
`synlynk/_constants.py`, `synlynk/gh_shim.py`-adjacent identity plumbing.

| # | Title | Status | Notes |
|---|---|---|---|
| #1925 | Safe-by-default execution (flag-flip + containerization) | IN PROGRESS | Flag-flip half shipped. Containerization half dispatched to Grok (`feat/grok/containerized-dispatch`), brainstorm/spec stage per Brainstorm-First Policy. |
| #1976 | Dispatch smart defaults + inference preview | OPEN | Not yet dispatched. |
| #1984 | Hermes-class local roster | OPEN | Not yet dispatched. |
| #2015 | Job status false-negative recurrence (5 instances, 2026-10-04) | OPEN | Filed this session; evidence table for job-f9a82968/9380619d/2908b732/78e8e38c/23e81336. |
| #1963 | Codex deleted job_truth.py outside assigned scope | OPEN | Dispatch scope-enforcement gap. |
| #1990 | GOVERNS hard-fail gate in dispatch preflight | OPEN | |
| #1991 | cross_harness_review_required enforcement in `pr check` | OPEN | |
| #1992 | Audit-log SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH usage | OPEN | gh_shim.py-adjacent. |
| #1993 | Capability report → task_allocation routing | OPEN | |
| #1960 | LIVE-22 gh identity zone-boundary | **FIXED, not closed** | Merged via PR #1964 (2026-10-03). Needs manual `gh issue close 1960` — blocked here by auto-mode GH-write restriction. |
| #2008 | Job-status: lost verified remote task delivery | **FIXED, not closed** | Merged via PR #2009 (2026-10-04). Needs manual `gh issue close 2008` — same restriction. |
| #2012 | Release-docs CI gate over-scoped | IN PROGRESS, stalled | job-b86f460e made correct local commit (`c1d1d726`) but never pushed/opened PR. Needs re-dispatch to finish push+PR, or Claude to push directly as a deploy action. |

**Sequencing:** #1963/#1990 (scope + gate enforcement) should land before further dispatch-heavy tracks run unattended, since they harden the thing every other track's dispatches depend on.

---

## Track 2 — CLI Surface & Taxonomy (gh:#1986)

**Shared surface:** `synlynk/taxonomy.py` (517 lines), `synlynk/__init__.py` (3,264 lines).

| # | Title | Status | Notes |
|---|---|---|---|
| #1973 | Baseline metrics capture | OPEN | Sequencing: do this **first** per epic. |
| #1974 | Tiered `--help` | OPEN | Sequence before #1975/#1977 per epic. |
| #1975 | Quickstart + guided first-run | OPEN | |
| #1977 | Docs restructure | OPEN | |
| #1927 | CLI core/packs split | OPEN | |
| #1941 | Flaky cold-start test | OPEN | Perf/CI, CLI cold-start path. |
| #1943 | Move cold-start/EPUB tests out of required CI | OPEN | Same family as #1941. |
| #2012 | Release-docs CI gate over-scoped | *(cross-listed, owned by Track 1)* | Also touches `release --check-docs`, which #1977 extends — coordinate, don't duplicate. |
| #1918 | `decide --record` slug-collision overwrite bug | OPEN | Loose fit (decide.py, not taxonomy.py) — rides along here as a small CLI-command bugfix rather than a standalone track. |

**Sequencing (per epic, unchanged):** #1973 → #1974 → {#1975, #1977}.

---

## Track 3 — Data/Display Layer (gh:#1987)

**Shared surface:** `synlynk/viz.py` (11,632 lines), `synlynk/db.py` (4,083 lines).

| # | Title | Status | Notes |
|---|---|---|---|
| #1923 | Split viz.py | OPEN | |
| #1926 | state.db consolidation | OPEN | |
| #1995 | Cost-log regen drops rows on `synlynk cost log` | OPEN | db.py write-through. |
| #1999 | `_rotate_project_doc()` duplication — 45x+ dupes, 160MB archive | OPEN | Newly surfaced, un-triaged. db.py-adjacent regen-bug class. |
| #1917 | memory.md write-through drift | OPEN | Same regen-bug family as #1995/#1999. |
| #1915 | costs.md regen from state.db drops main-only rows | OPEN | Likely same root cause as #1995 — investigate together, don't fix twice. |
| #1969 | Cost inflation escalation (ongoing) | OPEN | cost_entries/db.py. |
| #1937 | Cost-inflation record ($133/44M tokens) | OPEN | Same family as #1969. |
| #1951 | Cost audit redesign | OPEN | Has a stale worktree `feat/codex/cost-audit-1951` already flagged NEEDS-REVIEW from earlier worktree-hygiene pass — check before re-dispatching, may already have partial work. |

**Note:** #1995/#1999/#1917/#1915 all look like the same underlying "write-through regen destroys concurrent/main-only state" bug class hitting different files (`project-docs/costs.md`, `memory.md`, archive rotation). Recommend one root-cause investigation issue before four separate fixes.

---

## Track 4 — Trust & Positioning Copy (gh:#1988)

**Shared surface:** none (content-only).

| # | Title | Status | Notes |
|---|---|---|---|
| #1978 | Positioning sentence everywhere | OPEN | |
| #1979 | Verify job outcomes as user-visible evidence (narrowed) | OPEN | |

No new fold-ins from the past 48h — nothing content/positioning-related surfaced. Can run fully parallel to all other tracks per epic.

---

## Track 5 — Go-to-Market (gh:#1989)

**Shared surface:** mostly non-code; `route --report` has latent overlap with Track 1.

| # | Title | Status | Notes |
|---|---|---|---|
| #1980 | `route --report` + 5-way benchmark kit | OPEN | Sequence **after** Track 1 lands (per epic). |
| #1981 | 90-day design-partner program | OPEN | |
| #1982 | Competitive matrix + agent-authorship framing | OPEN | |
| #1983 | Partnership moves (narrowed) | OPEN | |

No new fold-ins from the past 48h.

---

## Items considered and NOT placed in a track

- **#1914** (version drift, CI/release) — not a clean adjacency fit to any track; leave standalone, revisit if it recurs.

## Immediate next actions

1. Manually close #1960 and #2008 (GH-write blocked for Claude under auto mode this session).
2. Dispatch #2012 completion (push existing commit `c1d1d726` + open PR) — Codex re-dispatch or direct Claude deploy action.
3. Dispatch Track 2's #1973 (baseline metrics) first — it's the sequencing gate for #1974/#1975/#1977.
4. Open one root-cause investigation issue for the Track 3 write-through regen-bug family (#1995/#1999/#1917/#1915) before dispatching four separate fixes.
5. Check `feat/codex/cost-audit-1951` worktree state before re-dispatching #1951.
