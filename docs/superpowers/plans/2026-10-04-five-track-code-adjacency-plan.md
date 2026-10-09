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

**Status refreshed 2026-10-09** against the live PM-scoped GitHub issue state.
Open issues in this plan include #1993, #1927, #1937, #2023, #1980–#1983,
#1914, #2061, #2066, #2078, and #2079. #1926 and #1943 have since closed;
the three-lens fold-ins #2062–#2065 have also closed. The remaining adapter
conformance follow-ups are tracked explicitly below.

Role split in force: Claude = PM/review/deploy only. All implementation below routes
to Codex/Grok (Agy deprioritized per `feedback_prefer_codex_grok_over_agy` memory)
via `synlynk dispatch`.

**Policy-gate posture update (PR #2120, merged 2026-10-08):** this repository now
records GOVERNS and cross-harness review gate outcomes in `observe` mode, so those
gates diagnose without blocking merges. A 100-consecutive-clean-pass streak is the
re-hardening recommendation threshold. This lowers the current merge-enforcement
posture while evidence accumulates; it does not remove the adapter conformance suite
or close its residual failures (#2078/#2079).

---

## Track 1 — Dispatch/Harness Layer (gh:#1985)

**Shared surface:** `synlynk/dispatch.py` (4,265 lines), `synlynk/harness_adapters/*.py`,
`synlynk/_constants.py`, `synlynk/gh_shim.py`-adjacent identity plumbing.

| # | Title | Status | Notes |
|---|---|---|---|
| #1925 | Safe-by-default execution (flag-flip + containerization) | **CLOSED** 2026-10-04 | Shipped. |
| #1976 | Dispatch smart defaults + inference preview | **CLOSED** 2026-10-05 | Shipped. |
| #1984 | Hermes-class local roster | **CLOSED** 2026-10-05 | Shipped. |
| #2015 | Job status false-negative recurrence (5 instances, 2026-10-04) | **CLOSED** 2026-10-05 | Shipped. |
| #1963 | Codex deleted job_truth.py outside assigned scope | **CLOSED** 2026-10-04 | Shipped. |
| #1990 | GOVERNS hard-fail gate in dispatch preflight | **CLOSED** 2026-10-05 | Merged via PR #2046, issue closed. |
| #1991 | cross_harness_review_required enforcement in `pr check` | **CLOSED** 2026-10-04 | Merged via PR #2047, issue closed. |
| #1992 | Audit-log SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH usage | **CLOSED** 2026-10-05 | Merged via PR #2050, issue closed. |
| #1993 | Capability report → task_allocation routing | **OPEN** | Still the real gap — nothing dispatched. Highest-leverage pick for making Grok/Muse calibration self-service. |
| #1960 | LIVE-22 gh identity zone-boundary | **CLOSED** 2026-10-04 | Merged via PR #1964, issue closed. |
| #2008 | Job-status: lost verified remote task delivery | **CLOSED** 2026-10-04 | Merged via PR #2009, issue closed. |
| #2012 | Release-docs CI gate over-scoped | **CLOSED** 2026-10-04 | Shipped — the stalled push did land. |

**Sequencing:** #1963/#1990 (scope + gate enforcement) should land before further dispatch-heavy tracks run unattended, since they harden the thing every other track's dispatches depend on.

### Fold-in: 2026-10-06 three-lens decide-panel decision

Per `project-docs/decisions/2026-10-06-review-docs-reviews-2026-10-05-three-len.md` (panel: claude/codex/grok, synthesized decision), two new Track 1 items converged on by all three panelists reviewing `docs/reviews/2026-10-05-three-lens-strategic-review.md`:

| # | Title | Status | Notes |
|---|---|---|---|
| #2062 | Adapter conformance test suite + retire `LegacyAdapter` dual dispatch path | **CLOSED** 2026-10-08 | Suite landed and the incomplete legacy path was retired. The suite exposed residual adapter gaps tracked in #2078 and #2079. |
| #2078 | `translate_permissions` signature drift in Claude/Codex/Agy adapters | **OPEN** | Conformance follow-up: three adapter overrides omit the protocol's `skip_permissions` argument. |
| #2079 | LocalAdapter receipt SHA evidence missing from `parse_output` | **OPEN** | Conformance follow-up: local adapter does not populate `compatibility_evidence`. |
| #2064 | `_preflight_local_silent()` fallback visibility | **CLOSED** 2026-10-07 | Filed and resolved as a visible fallback/fail-closed behavior change. |

The panel treated P0-3/P1-3 (host-auth audit log, GOVERNS hard-fail) as **already resolved** — #1990/#1991/#1992 closed via PRs #2046/#2047/#2050 (2026-10-05/06) — not re-filed.

---

## Track 2 — CLI Surface & Taxonomy (gh:#1986)

**Shared surface:** `synlynk/taxonomy.py` (517 lines), `synlynk/__init__.py` (3,264 lines).

| # | Title | Status | Notes |
|---|---|---|---|
| #1973 | Baseline metrics capture | **CLOSED** 2026-10-04 | Shipped. |
| #1974 | Tiered `--help` | **CLOSED** 2026-10-04 | Shipped. |
| #1975 | Quickstart + guided first-run | **CLOSED** 2026-10-04 | Shipped. |
| #1977 | Docs restructure | **CLOSED** 2026-10-04 | Shipped. |
| #1927 | CLI core/packs split | **OPEN** | Still real. |
| #1941 | Flaky cold-start test | **CLOSED** 2026-10-04 | Shipped. |
| #1943 | Move cold-start/EPUB tests out of required CI | **CLOSED** 2026-10-08 | Required CI no longer blocks on EPUB validation; the validation workflow and marketing check were updated. |
| #2012 | Release-docs CI gate over-scoped | **CLOSED** *(cross-listed, owned by Track 1)* | Shipped. |
| #1918 | `decide --record` slug-collision overwrite bug | **CLOSED** 2026-10-05 | Shipped. |

**Sequencing (per epic, unchanged):** #1973 → #1974 → {#1975, #1977}.

### Fold-in: 2026-10-06 three-lens decide-panel decision

| # | Title | Status | Notes |
|---|---|---|---|
| #2065 | Schema validation of `.synlynk/config.json`/`policy.json` in `synlynk doctor` | **CLOSED** 2026-10-07 | JSON Schema validation was added to `synlynk doctor`. |

### Fold-in: pipx/release-docs freshness mechanism (Nikhil, 2026-10-06)

Nikhil flagged that the pipx-installed CLI (`~/.local/bin/synlynk`) silently goes stale against in-development worktree code, and asked for a mechanism ensuring workspace agents (marketing role) keep release-adjacent docs fresh as a standing responsibility, not a one-off fix.

**Proposed approach:** extend `synlynk doctor` with a `pipx_freshness` check (compare installed package version/commit against `origin/main`'s latest tag + `pyproject.toml` version; warn if stale, similar to the existing `HARNESS_VERSION_DRIFT` sentinel pattern from v0.9.9). Pair with a Named Release Policy addition (already a global rule — see CLAUDE.md "Named Release README Sync") requiring the **marketing** role to run a docs-freshness pass (README install instructions, CHANGELOG, blog index) as a mandatory step of every `synlynk release`, not just on request.

| # | Title | Status | Notes |
|---|---|---|---|
| #2066 | `synlynk doctor` pipx/version-freshness check | **OPEN** | Bundled with the opt-in auto-upgrade notice below. |
| #2066 | Marketing-role docs-freshness pass as mandatory `synlynk release` step | **IN SCOPE** | The #2066 issue requires release docs to be refreshed when the version-freshness behavior ships; no separate issue was filed. |

### Fold-in: auto-upgrade-on-release mechanism (Nikhil, 2026-10-06)

Nikhil asked whether downstream `synlynk` users get auto-upgraded on every Named Release — currently they do not; there is no push mechanism, only `synlynk upgrade` run manually.

**Proposed approach:** on `synlynk exec`/`synlynk status` startup, check installed version against the latest GitHub Release tag (cached, low-frequency check — e.g. once per 24h, not per-invocation) and surface a non-blocking "upgrade available" notice (reusing the `HARNESS_VERSION_DRIFT`-style sentinel UX), with an explicit opt-in `--auto-upgrade` daemon setting for users who want it fully automatic. Default stays notify-only — auto-upgrading a CLI that drives autonomous dispatch without consent is a real blast-radius risk (a bad release could break an unattended fleet mid-run).

| # | Title | Status | Notes |
|---|---|---|---|
| #2066 | Upgrade-available notice on startup (version-check against latest Release tag) | **OPEN** | Notify-only default. |
| #2066 | Opt-in `--auto-upgrade` daemon setting | **OPEN** | Same issue; deferred until the notify-only path is validated. |

---

## Track 3 — Data/Display Layer (gh:#1987)

**Shared surface:** `synlynk/viz.py` (11,632 lines), `synlynk/db.py` (4,083 lines).

| # | Title | Status | Notes |
|---|---|---|---|
| #1923 | Split viz.py | **CLOSED** 2026-10-05 | Shipped. |
| #1926 | state.db consolidation | **CLOSED** 2026-10-08 | Single workspace-owner DB consolidation landed. This removes the stated data-aggregation dependency for #1993. |
| #1995 | Cost-log regen drops rows on `synlynk cost log` | **CLOSED** 2026-10-05 | Shipped. |
| #1999 | `_rotate_project_doc()` duplication — 45x+ dupes, 160MB archive | **CLOSED** 2026-10-05 | Shipped. |
| #1917 | memory.md write-through drift | **CLOSED** 2026-10-05 | Shipped. |
| #1915 | costs.md regen from state.db drops main-only rows | **CLOSED** 2026-10-05 | Shipped. |
| #1969 | Cost inflation escalation (ongoing) | **CLOSED** 2026-10-04 | Shipped — but see #1937 below, the underlying cost problem is not actually resolved. |
| #1937 | Cost-inflation record ($133/44M tokens) | **OPEN** | Still real. #1969's fix (PR #2021) did not reduce Codex implementation-job costs — still $5.58–$15.93/job per the Wave 2 closeout below. Needs fresh investigation, not a re-close. |
| #1951 | Cost audit redesign | **CLOSED** 2026-10-04 | Shipped. |

**Note:** #1995/#1999/#1917/#1915 (all CLOSED 2026-10-05) were the same underlying "write-through regen destroys concurrent/main-only state" bug class hitting different files. Root-cause issue #2023 remains **OPEN** after #1926 closed; check whether it tracks a residual piece before closing it.

### Recurring autonomous-flow friction (Nikhil, 2026-10-06) — assessed, mostly already tracked here

Nikhil flagged three recurring pain points hurting the autonomous flow and asked whether a new investigation ticket is needed. Assessment: **no new umbrella ticket** — each has real, specific open issues already in this plan or elsewhere; the gap is sequencing/priority, not missing tracking:

1. **Cost entries dropped** → #2037 (turn_usage_json missing column, root-caused and fixed this session via #2055/PR #2054), #2051 (cross-harness gate hard-fails on a missing cost_entries row — the forcing-function that turns a dropped entry into a blocked merge), #481 and #1915/#1995/#1917/#1999/#2023 (the write-through regen family above), #510 (cost formula divergence).
2. **Forced manual merge/approve** → directly caused by #2051 above (false "no provenance" blocks) plus the broader self-approval/chicken-and-egg pattern (memory: `chicken-and-egg-dispatch-review-selfapproval.md`, LIVE-14/PR #1747) and #1991 (cross-harness review enforcement, Track 1, already open).
3. **Classifier not permitting certain actions** → hit live in this session: the auto-mode write classifier blocked `gh issue create` for this very roadmap update (External System Writes). No existing issue tracks *classifier scope being miscalibrated for already-authorized PM/role actions* specifically — #781 and #2056 cover classifier/verification *false positives* in dispatched jobs, not this interactive-session case. **This is the one genuinely new gap** — recommend filing it as a Track 1 item once filing is unblocked (see table below).

| # | Title | Status | Notes |
|---|---|---|---|
| #2096 | Auto-mode classifier blocks role-scoped GH writes already authorized via `.synlynk/github_apps` + explicit user go-ahead | **OPEN** | Investigation filed; the interactive role-scoped PM failure is tracked here. |

---

## Track 4 — Trust & Positioning Copy (gh:#1988)

**Shared surface:** none (content-only).

| # | Title | Status | Notes |
|---|---|---|---|
| #1978 | Positioning sentence everywhere | **CLOSED** 2026-10-04 | Shipped. |
| #1979 | Verify job outcomes as user-visible evidence (narrowed) | **CLOSED** 2026-10-04 | Shipped. |

### Fold-in: 2026-10-06 three-lens decide-panel decision

| # | Title | Status | Notes |
|---|---|---|---|
| #2063 | Correct README/site "live capability ledger / best harness" language | **CLOSED** 2026-10-07 | External claims were corrected to describe suspended empirical routing while #1926/#1993 work remained incomplete. |

No other new fold-ins from the past 48h beyond the decide-panel item. Can run fully parallel to all other tracks per epic.

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

- **#1914** (version drift, CI/release) — **OPEN**, not a clean adjacency fit to any track; leave standalone, revisit if it recurs.

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

### Wave 2 launched (2026-10-04, ~12:25 UTC)

All 6 Wave 2 dispatches issued via `synlynk dispatch codex --force-harness --role dev`:

| Job | Issue | Track | Task |
|---|---|---|---|
| job-e5daa609 | #1990 | 1 | GOVERNS hard-fail gate in `pr check` + dispatch preflight |
| job-ebb67741 | #1991 | 1 | `cross_harness_review_required` enforcement in `pr check` |
| job-34f5240c | #1975 | 2 | `synlynk quickstart`/`start` + guided first-run manifest |
| job-1794154e | #1977 | 2 | Docs restructure — journey-oriented, taxonomy-generated reference, glossary |
| job-2b9ba652 | #1979 | 4 | Verify job-outcome evidence is user-visible (narrowed scope) |
| job-7f4334af | #2023 | 3 | Root-cause-only investigation of the regen/write-through bug family (#1995/#1999/#1917/#1915) — comment-only, no fix; `--requires-gh-write --gh-write-expect comment_posted` |

**Routing correction discovered this wave:** attempted `--force-harness grok` for #1991 first; it failed closed with `IncompatibleHarnessCapabilityError: forced harness 'grok' lacks required capabilities: write:github` — confirms the existing `feedback_grok_auth_agy_fallback`/#426 finding that Grok's sandbox denies GitHub-write capability in this environment. All 5 implementation dispatches (which open PRs, a GH-write action) routed to Codex instead of splitting across Codex/Grok as originally planned. Also discovered `--role dev` is now required even for non-`--requires-gh-write` dispatches that open PRs — passing neither yields `RuntimeError: Dispatch refused: --requires-gh-write requires a resolvable role identity` (PR-opening apparently implies a GH-write capability check under the hood now, consistent with #569's hardening). Noting both for the next harness-capability-baseline reassessment cycle rather than filing fresh issues — neither is a regression, both are consistent with already-documented policy.

**Cost watch:** per the Wave 1 TOKEN_BLOAT/COST_INFLATION finding above (4 of 5 Codex implementation jobs tripped cost alerts, even after #1969/PR#2021 merged claiming to address the root cause), these 6 Wave 2 jobs are the first live test of whether #1969's fix actually reduced the cluster. Will verify actual token/cost figures via `synlynk jobs`/cost_entries once jobs complete, not just trust that the fix landed.

### Wave 2 closeout (2026-10-04)

PRs opened: #2029 (#1990), #2024 (#1991), #2026 (#1975), #2028 (#1977), #2027 (#1979). #2023's root-cause investigation posted its comment successfully (job-7f4334af).

**Job-status false-negative recurred for implementation jobs, not just review (feeds #2015):** 5 of 6 jobs showed failure-flavored labels (`succeeded_gh_write_failed` ×3, `unpushed_branch` ×2) despite all 5 PRs being genuinely open, pushed, and mergeable — verified directly via `gh pr list`/`gh pr view`, never trusting the label.

**Cost inflation NOT reduced by #1969/PR#2021:** the 5 Codex implementation jobs cost $5.58–$15.93 each (avg ~$9.4), essentially unchanged from Wave 1's pre-fix $1.96–$12.52 range. #1969's merged fix does not appear to address the actual root cause — flagged as a critical open finding in the tracker (Track 3, red) pending fresh investigation. Noted when closing #1969 manually.

**Three CI failures found and handled on merge:**
- PR #2026 (#1975): stale generated `docs/reference/commands.md`/README commands section (missing `quickstart`) plus a duplicate `<!-- commands:end -->` marker and a stale test-count badge. Mechanical — fixed directly via scratch clone + `scripts/generate_command_docs.py`, pushed.
- PR #2028 (#1977): `test_add_synlynk_release_command_to_synlynk__` seeded `docs/reference/commands.md` with a hardcoded stub instead of real generator output, which no longer satisfies the shipped-vs-planned commands check this same PR introduces. Fixed directly (seed with `render_reference_doc()` output), full suite verified green, pushed.
- PR #2029 (#1990): broke 3 pre-existing dispatch tests via two distinct root causes — (a) test fixtures dispatch without a linked GOVERNS goal, now hard-failing the new preflight gate as designed, and (b) a real latent bug in the new shadow-status-projection code (`job_status_projection.py::record_shadow_comparison`, from PR3/commit e5cf62f7): it reads `conn.row_factory` without a guard, breaking for any connection wrapper that doesn't expose that attribute. Judged non-mechanical — dispatched to Codex (job-a56ca18c) rather than hand-fixed, scoped to both root causes, targeting the existing branch/PR.

**Manual issue-closing:** 5 Wave 1 issues (#1963, #1969, #1978, #1941, #2012) remained OPEN despite merged PRs — the "Fixes #N" auto-close trap (PR body lacked a recognized closing keyword). Closed manually with comments linking each merged PR, per explicit user instruction.

**Tracker enhanced:** `scripts/track-status.sh` now shows TIME (start→merge) and COST columns per issue (static lookup from `daemon_jobs`/`cost_entries`, refreshed per wave) and a color-coded "inline findings" section per track for issues discovered mid-implementation, per explicit user request.

**Next:** merge #2024 and #2027 once CI is green post-`update-branch`; merge #2029 once job-a56ca18c's fix lands; run Worktree Hygiene Protocol cleanup on all newly-merged PRs; hold #2023's recommendation (a short design spec before dispatching #1995/#1999/#1917/#1915 fixes) for Nikhil's sign-off per Brainstorm-First Policy.
