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
| job-92c3cd46 | #1973 (Track 2 gate) | **Open PR #2017, review pending** | `unpushed_branch` label was WRONG — verified pushed, clean 330-line diff. 6th+ job-status false-negative instance (gh:#2015). Tripped COST_INFLATION ($11.81/3.8M tokens). |
| job-95c665cb | review/merge PR #2017 | **Genuinely FAILED** | Confirmed via `gh pr view 2017 --json reviews` → `[]` (zero reviews posted) and job exit code 0 with 0 files touched over 30m. Unlike the Codex jobs above, this `failed` label was **correct**, not a false negative — first clean confirmation this wave that the label can also be right. Re-dispatched as job-579024a4 (see below). |
| job-594ec949 | #1963 (Track 1) | **Open PR #2019, review pending** | `unpushed_branch` label WRONG — verified pushed, clean 2-file/144-line diff matching the task exactly. |
| job-3561f357 | #1941 (Track 2) | **Open PR #2018, review pending** | `unpushed_branch` label WRONG — verified pushed, clean 1-file/29-line diff. |
| job-69ba7fa6 | #1974 (Track 2) | **Open PR #2020, review pending** | `unpushed_branch` label WRONG — verified pushed, clean 4-file/104-line diff. |
| job-45c98165 | #1969 (Track 3) | **Open PR #2021, review pending** | `unpushed_branch` label this time was **correct** — `git ls-remote` confirmed the branch genuinely never reached origin, unlike the other 4 Codex jobs. Local commit was sound (4 files, 133/7 lines, matched the task) — Claude pushed it directly and opened the PR as a deploy action rather than re-dispatching. |
| job-b1e83605 | #1978 (Track 4) | **Open PR #2022, review pending** | `unpushed_branch` label was WRONG — verified pushed. Diff touches 14 files (README/CHANGELOG/logo SVGs/website pages/CLI wizard strings) — confirmed this is legitimate positioning-copy scope per the issue, not scope creep (#1963's precedent made this worth double-checking). Claude pushed it directly and opened the PR. |
| job-0f409e7d / dc0c0318 / 9550f92d / f32b385f / a78bf313 / 579024a4 | review+merge PRs #2017/#2018/#2019/#2020/#2021/#2022 | **Resolved** — see outcomes below | Re-dispatched as `claude`/qa-role jobs (cross-harness+model vs. Codex authorship) for all 6 open Wave 1 PRs, per Hardened PR Review Policy. The first attempt (job-95c665cb, PR #2017 only) genuinely failed; these 6 superseded it. |

**Final Wave 1 PR outcomes (verified directly via `gh pr view`, not job labels):**

| PR | Issue | Final state | Notes |
|---|---|---|---|
| #2017 | #1973 | **MERGED** (11:46 UTC) | README stale-count CHANGES_REQUESTED review was genuine/correct; fixed (3783→3788), re-reviewed APPROVED, merged squash once CLEAN. |
| #2018 | #1941 | **MERGED** (pre-existing from earlier wave processing) | |
| #2022 | #1978 | **MERGED** (11:34 UTC) | Pushed+opened directly by Claude after job-45c98165/b1e83605-class push gap; review APPROVED, merged. |
| #2019 | #1963 | **MERGED** (12:10 UTC) | Hit a genuine (not false-negative) `DIRTY`/`CONFLICTING` merge state in README.md (test-count badge/sentence: both sides changed the same lines — 3784 vs 3788). Resolved by cloning to a scratch dir (`/tmp/pr2019-fix`), merging `origin/main` in, taking the correct live count (**3789**, confirmed via `pytest --collect-only` at merge time), and pushing the resolved commit (`09f88b4`) directly to the PR branch before `update-branch`/merge could proceed. job-9550f92d showed `TASK_DELIVERY_FAILED` ("no corroborating git activity") despite having posted a real `APPROVED` review, and job-6013719d (PR #2014's review) showed the identical pattern despite that PR actually merging — **new false-negative subtype, confirmed twice**: review-only tasks don't touch the worktree by design, so the receipt-protocol's git-activity check misfires on them specifically. Feeds #2015. |
| #2020 | #1974 | **MERGED** (12:02 UTC) | job-dc0c0318 (re-review, same PR) ran 2174s (36min) with zero log output and finished `TASK_DELIVERY_FAILED` — a third instance of the same review-only false-negative, confirmed only after the PR had already merged via an earlier successful review job's APPROVE. |
| #2021 | #1969 | **MERGED** (12:17 UTC) | Last Wave-1 PR to land. Needed `update-branch` cycles across essentially every subsequent sibling merge (#2018/#2022/#2014/#2020/#2019 each knocked it BEHIND again) — see cascading-BEHIND finding below. Once merged, **the cost-inflation circuit breaker lifts**: new parallel Codex implementation dispatches are no longer held. |

**Also discovered and resolved this pass:** PR #2014 (`fix(ci): scope release-docs to release events`, the actual #2012 fix) merged at 11:54 UTC — this was the actual root cause clearing the release-docs CI gate bug that had been producing spurious `BLOCKED` states on #2019/#2020/#2021.

**New finding — cascading BEHIND on sequential Wave-1 merges:** merging 7 PRs into `main` in quick succession repeatedly knocked whichever Wave-1 PRs were still open back into `BEHIND` state, each requiring its own `update-branch` → CI-wait cycle (observed ~5 rounds total across #2019/#2020/#2021 before all cleared). None of these were genuine merge conflicts (`mergeable: MERGEABLE` throughout, except the one real README conflict on #2019 above) — purely a side effect of merging siblings one at a time while others are still catching up. Worth considering for future waves: either serialize wave merges more tightly (merge the whole batch back-to-back rather than interleaving with CI waits), or use GitHub's native merge queue if enabled, to avoid burning ~5 redundant CI cycles across macOS+Linux matrix jobs. Flagging as Track-1-adjacent (dispatch/merge-sequencing), not a new issue on its own — revisit only if it recurs at larger wave sizes.

### New evidence this wave feeds back into prioritization

- **#2015 gains a 6th+ false-negative instance** across 5 of 6 Wave-1 jobs (`unpushed_branch` shown when the branch was in fact pushed) — strengthens the case that `synlynk pr check`/job-status reporting itself (also Track 1, dispatch.py-adjacent) needs to move up, not just the scope-guard (#1963) and GOVERNS gate (#1990).
- **job-45c98165 and job-95c665cb are evidence the label is sometimes right** — `unpushed_branch`/`failed` is not *always* a false negative. The operative rule stays "never trust the label alone, verify every time," not "assume the label is always wrong."
- **Systemic TOKEN_BLOAT/COST_INFLATION across Wave 1**: all 5 Codex implementation jobs tripped TOKEN_BLOAT (2.15M–4.1M tokens vs. ~500K baseline); 4 of 5 also tripped COST_INFLATION ($11.81/$8.69/$10.52/$12.52/$6.66 — only job-3561f357/#1941 escaped the cost trip). This is a materially worse cluster than #1969's own historical evidence table and is itself the strongest live argument for keeping #1969 (now PR #2021) at the front of the review queue — **merge it before dispatching further Codex-heavy waves** to avoid compounding real-dollar cost on the same root cause. Decision: proceed with Wave 2 dispatch now (per the "continue autonomously" mandate) but hold off issuing *additional parallel Codex implementation jobs* beyond what's already queued until PR #2021 merges or is confirmed not the fix.
- **#1969's priority is now confirmed correct** by live same-session evidence, not just historical record — keeping it ahead of #1923/#1926/#1951 in Track 3's queue.
- **#1960 and #2008 confirmed already-fixed-but-open** (PRs #1964/#2009 merged, issues never auto-closed) — zero new work needed, just bookkeeping. Not re-queued.
- **#2012 was already further along than tracked** (PR #2014 open, not stalled) — removed from the active queue, just needs review like any other open PR.

### Planned Wave 2 (next, launching now)

1. Root-cause issue for the Track 3 regen-bug family (#1995/#1999/#1917/#1915) — open as one investigation before four separate fixes, per original plan.
2. Track 1: #1990 (GOVERNS hard-fail gate), #1991 (cross-harness review enforcement) — once #1963 lands, since both touch the same job-finalization path and sequencing avoids rebase churn.
3. Track 2: #1975/#1977 once #1974 merges.
4. Track 4: #1979.
5. Track 5: hold — #1980 needs Track 1 to land first per epic; #1981/#1982/#1983 are mostly business-development/outreach work, not autonomous-dispatch-shaped (flagging for Nikhil's direct attention rather than queuing to Codex/Grok).
6. `feat/codex/cost-audit-1951` worktree (PR #1968) remains **held for Nikhil's manual review** — 53-file/2460+/3065- diff that deletes unrelated blog posts/devlogs/plans/tests alongside a legitimate `cost_audit.py` feature. Not merged or re-dispatched.
7. ~~Cost-inflation circuit breaker~~ — **LIFTED 2026-10-04 12:17 UTC**, the moment PR #2021 (#1969) merged. New parallel Codex implementation dispatches for Wave 2 are no longer held.

### Wave 1 closeout (2026-10-04)

All 7 Wave 1 PRs merged: #2017 (11:46 UTC), #2014 (11:54 UTC), #2022 (11:34 UTC — earliest), #2018 (pre-existing), #2020 (12:02 UTC), #2019 (12:10 UTC), #2021 (12:17 UTC, last). Worktree Hygiene Protocol run immediately after: removed 7 feature worktrees/branches (`job-92c3cd46`, `job-3561f357`, `job-594ec949`, `job-69ba7fa6`, `job-45c98165`, `job-b1e83605`, `job-b86f460e`), 9 zero-commit review-probe worktrees/branches (`job-0f409e7d`, `job-579024a4`, `job-9550f92d`, `job-95c665cb`, `job-a78bf313`, `job-dc0c0318`, `job-f32b385f`, `job-6013719d`, `job-b2cf88cd` — all confirmed 0 own commits + 0 dirty files before deletion), one stray superseded worktree (`job-review`, duplicate of #2019's already-merged content at a stale test count), and the `/tmp/pr2019-fix` scratch clone. `feat/codex/cost-audit-1951` and `feat/grok/containerized-dispatch` (with its nested dispatch sub-jobs) deliberately left alone — neither has a merged PR.
