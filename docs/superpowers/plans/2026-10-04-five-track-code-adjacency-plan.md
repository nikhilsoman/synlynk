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
2. ~~Dispatch #2012 completion~~ — already resolved independently; PR #2014 was already open, just needed review/merge (not actually stalled).
3. ~~Dispatch Track 2's #1973 first~~ — done, see Wave 1 log below.
4. Open one root-cause investigation issue for the Track 3 write-through regen-bug family (#1995/#1999/#1917/#1915) before dispatching four separate fixes — still pending, queued for Wave 2.
5. Check `feat/codex/cost-audit-1951` worktree state before re-dispatching #1951 — still pending.

## Autonomous dispatch log

Continuing per Nikhil's 2026-10-04 instruction: "pick the most optimal order that prioritizes
earliest completion of the full roadmap, continue autonomously till all done, ensure issues
that you discover during implementation are evaluated for their impact on this roadmap and
prioritized on this basis." Ordering principle: front-load safety/scope hardening (we're running
many parallel dispatches unattended), run independent low-risk items in parallel immediately,
hold strictly-sequenced items until their gate lands, and re-prioritize live based on evidence
surfaced by each wave's own jobs — not a fixed queue decided up front.

### Wave 1 (dispatched 2026-10-04)

| Job | Issue | Status | Notes |
|---|---|---|---|
| job-92c3cd46 | #1973 (Track 2 gate) | **Merged pending** (PR #2017) | `unpushed_branch` job-status label was WRONG — verified via direct git/gh inspection (branch was pushed, PR open, clean 330-line diff). 6th+ instance of the job-status-truth false-negative pattern (gh:#2015). Also tripped COST_INFLATION ($11.81/3.8M tokens) despite correct, scoped output — live evidence feeding into #1969's priority bump below. |
| job-95c665cb | review/merge PR #2017 | Running | Dispatched to `claude` harness specifically for cross-harness+model review per the 2026-10-04 Hardened PR Review Policy (reviewer must differ from implementer in harness+model, not just role). |
| job-594ec949 | #1963 (Track 1) | Running | **Priority-bumped to Wave 1**: this is the scope-enforcement guard against exactly the failure class we're exposed to by running 5+ parallel dispatches right now (job-20633904 precedent: a narrow task produced a 13-file, 500-line unrelated deletion while tripping the same TOKEN_BLOAT+COST_INFLATION combo seen on #1973 just now). |
| job-3561f357 | #1941 (Track 2) | Running | Independent of #1973's sequencing gate — flaky CI test fix, reduces false-failure noise for every other PR landing during this run. |
| job-69ba7fa6 | #1974 (Track 2) | Running | Issue text confirms dependency on #1973 is "not required to block shipping" — safe to run in parallel, only needs to *merge* after #1973 merges. |
| job-45c98165 | #1969 (Track 3) | Running | **Priority-bumped ahead of the regen-bug cluster and #1923/#1926/#1951**: issue already names a suspected root cause (preflight/context-size decoupling in `dispatch.py` ~2793-2834, worsened by merge-conflict retry loops re-sending full context) and today's #1973 cost spike is a live, fresh data point for it. This is the single highest-leverage fix for "earliest completion of the full roadmap" — every other track's dispatches are being taxed by whatever this bug is. |
| job-b1e83605 | #1978 (Track 4) | Running | No dependencies, mechanical copy-swap, runs fully parallel. |

### New evidence this wave feeds back into prioritization

- **#2015 gains a 6th+ false-negative instance** (job-92c3cd46) — strengthens the case that `synlynk pr check`/job-status reporting itself (also Track 1, dispatch.py-adjacent) needs to move up, not just the scope-guard (#1963) and GOVERNS gate (#1990).
- **#1969's priority is now confirmed correct** by live same-session evidence, not just historical record — keeping it ahead of #1923/#1926/#1951 in Track 3's queue.
- **#1960 and #2008 confirmed already-fixed-but-open** (PRs #1964/#2009 merged, issues never auto-closed) — zero new work needed, just bookkeeping. Not re-queued.
- **#2012 was already further along than tracked** (PR #2014 open, not stalled) — removed from the active queue, just needs review like any other open PR.

### Planned Wave 2 (next, pending Wave 1 results)

1. Root-cause issue for the Track 3 regen-bug family (#1995/#1999/#1917/#1915) — open as one investigation before four separate fixes, per original plan.
2. Track 1: #1990 (GOVERNS hard-fail gate), #1991 (cross-harness review enforcement) — once #1963 lands, since both touch the same job-finalization path and sequencing avoids rebase churn.
3. Track 2: #1975/#1977 once #1974 merges.
4. Track 4: #1979.
5. Track 5: hold — #1980 needs Track 1 to land first per epic; #1981/#1982/#1983 are mostly business-development/outreach work, not autonomous-dispatch-shaped (flagging for Nikhil's direct attention rather than queuing to Codex/Grok).
6. Check `feat/codex/cost-audit-1951` worktree before dispatching #1951.
