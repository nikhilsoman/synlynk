# Canonical Release Execution Schedule

**Effective date:** 2026-10-22
**Authority:** `dec-f8835ba3`, roadmap parent #2458, and user approval on 2026-10-22
**Status:** Active as of 2026-10-22; PR #2534 is merged and roadmap state, release epics, milestones, and parent #2458 are synchronized

**Rebaseline:** This amendment supersedes the 2026-10-20 dated schedule. The
release families and their purpose remain canonical, while the daily stable
release stream and Dev Preview gate move forward. Local, OpenRouter, swarms,
Universal Gateway, capability-crawler/GTM, and public-announcement work are
not Dev Preview prerequisites. Muse remains an early core-harness dependency.
The legacy Developer Preview arcs `1.0.0`, `v1.0.0-preview`, and
`v1.0.0-rc1` are superseded; `v0.27.5` is the sole Dev Preview tag in this
schedule. The separate future `v1.0.0` GA arc is unchanged.

## Operating rule

The dates below are hard daily release gates for the single public stable
stream. There is no separate RC/DEV/PROD channel. A tag may be cut only when
that day's evidence gate passes. Missing a gate does not silently move
downstream work: record the blocker on #2458 within one day, keep the affected
release planned, and publish a revised date there. Never tag an unverified or
known-unsafe build merely to preserve the calendar.

The target is one named stable tag per calendar day. The schedule is also
acceleratable: dates are not a minimum wait. When a gate passes early, start
the next day's dependency sweep immediately and pull its work forward. If more
than one independent gate is ready, it may be bundled into the next stable
tag or released as an additional strictly ordered stable tag; do not wait for
the original date. Acceleration may not bypass dependencies, evidence, review,
the first Dev Preview acceptance gate, or human release authority.

## Calendar and gates

| Stable tag | Gate date | Delivery gate |
| --- | --- | --- |
| v0.25.2 | 2026-10-23 | Accumulated-PR reconciliation and first stable baseline. Resolve or explicitly gate dispatch-truth/process-lifecycle (#2530) and worktree-generated-doc safety (#2532) before autonomous work is relied upon. |
| v0.25.3 | 2026-10-24 | Muse is authenticated, model-allowlisted, low-privilege, and usable for roadmap work; model catalog, capability, and cost evidence is validated across core harnesses. No review/deploy/GitHub-write authority is implied. |
| v0.25.4 | 2026-10-25 | Job status and completion evidence are accurate and auditable, including GH-write outcomes; address or disposition #2138, #2139, #2309, and #2530 against current code. |
| v0.25.5 | 2026-10-26 | Release and CI integrity: address the self-test cleanup race/flakiness (#2527/#2526), concurrent release-doc count drift (#2522), and stale generated command docs/sparse-checkout false blockers (#2320), or record verified non-blocking dispositions. |
| v0.25.6 | 2026-10-27 | GOVERNS/model/cost/job-truth stability review closed; all selected stories have goal, release epic, and current delivery ticket; residual model correctness issues are fixed or explicitly held. |
| v0.26.0 | 2026-10-28 | Daemon reliability: restart, cancellation, recovery, scan containment, replay, and stop idempotence are evidence-tested. Revalidate #2464 and #1884; #2477 is closed and must not be reopened without new reproduction. |
| v0.26.1 | 2026-10-29 | Workspace-agent charters, authority, SOPs, and GOVERNS adherence are signed off and exercised; address #2305 where it blocks enforceable role procedures. |
| v0.26.2 | 2026-10-30 | Safe autonomous operations: claims/leases are enforced at work-start paths (#2511/#2528); approval, containment, audit, and recovery controls pass before broader autonomous execution. |
| v0.26.3 | 2026-10-31 | End-to-end autonomous operating day: workspace-agent roles plan, claim, dispatch, monitor, recover, and produce truthful evidence for a bounded roadmap task. Revalidate #2262 and adjacent job-orphan issues. |
| v0.27.0 | 2026-11-01 | VS Code/OpenVSX distribution gate: listing/publication, install, update, and dispatch smoke tests pass (#2103). |
| v0.27.1 | 2026-11-02 | Quickstart/onboarding first win: fresh-project journeys reach a verified first dispatch in under 15 minutes; revise #1515/#2472 scope to exclude deferred public announcement requirements. |
| v0.27.2 | 2026-11-03 | Onboarding clarity and recovery: install/update failure paths, prerequisites, harness choice, and common errors are explained and verified end-to-end. |
| v0.27.3 | 2026-11-04 | Cross-harness first-win verification, including Muse; five independent fresh-project journeys pass from install to useful, evidence-backed result. |
| v0.27.4 | 2026-11-05 | Full Dev Preview acceptance run: GOVERNS, model catalog/capability/cost, job status truth, workspace-agent autonomy, and quickstart/onboarding pass together. |
| v0.27.5 | 2026-11-06 | **Developer Preview stable release**, only if the v0.27.4 acceptance evidence is green and no unresolved release-blocking Sev1/Sev2 defect remains. |

Post-Preview ordering remains canonical but is deliberately undated until the
first preview is stable: v0.28.0 swarms/Universal Gateway; v0.28.1 capability
crawler/index and GTM; v0.29.0 residual backlog disposition. Local and
OpenRouter remain deferred candidates, not gates for this stream. Public
announcement/blog work is not a release blocker; per-PR blog generation stays
retired.

## Readiness snapshot at rebaseline

The 2026-10-22 `synlynk status` snapshot reports 98 local worktrees with 19
flagged stale, capability sweep overdue by 400 jobs, smoke test overdue, Codex
unavailable, and Muse unsupported with zero measured capacity. `synlynk watch
status` reports stopped. These are observed signals to refresh and disposition,
not diagnoses. The first daily dependency sweep must verify each against the
current environment. Audit worktrees non-destructively; do not run cleanup or a
live self-test while the #2527 self-test race remains unresolved. Do not count
Muse as roadmap capacity until authenticated onboarding and capability
evidence are current.

## Mandatory schedule controls

1. **Start-of-day dependency sweep (before implementation or tag work):**
   inspect the scheduled stories and their goals/parent epics, issue comments,
   linked and overlapping PRs, `origin/main`, specs/plans, and cross-release
   dependencies. Revalidate stale branches and tests; identify adjacent past
   work that can be safely completed in the same change; and scan open bugs,
   live issues, and tech-debt for directly relevant blockers or low-risk,
   complementary fixes. Check current `synlynk status`, daemon/watch state,
   capability-sweep freshness, and a non-destructive worktree audit; do not
   run cleanup or live self-tests concurrently with active scratch work.
   Record each candidate as `include today`, `separate
   ticket/release`, `deferred`, or `already fixed/superseded`, with evidence.
2. **Scope rule:** pull an adjacent fix into today's work only when it is
   reproducible or otherwise evidenced, shares the affected code/path, has a
   bounded review/test surface, and does not introduce unrelated authority or
   release risk. Sev1/release-integrity issues block affected tags; other
   deferrals need a ticket, owner/release, and reason. Do not let the sweep
   turn into unbounded cleanup.
3. **Ticket lock:** by 2026-10-27, every selected delivery story must have a
   goal, one release parent epic, and a current GitHub delivery ticket. Each
   of the existing 94 ticketless candidates must be freshness-checked and
   either mapped to a release-family with goal/epic/ticket links or explicitly
   deferred/archived with rationale. Use #2535 to update or reassign existing
   roadmap phase rows; do not edit canonical SQLite rows directly. The old
   allocation table is a starting index, not authority to implement stale or
   out-of-scope work.
4. **Daily closeout:** record the sweep disposition, shipped tag or missed
   gate, linked evidence, changed ticket count, new/closed defects, and next
   day's dependency in #2458. Do not wait for Friday to report a material
   blocker.
5. **No auto-promotion:** a stale plan, old green test, closed PR, or
   accumulated branch is not evidence that a release gate is complete.
6. **Acceleration:** if all dependencies and evidence for a later gate are
   already satisfied, move it forward after that day's sweep, update the
   release tickets and #2458 schedule, and preserve semver order. Work can
   advance early; tags never advance without the same quality, review, and
   acceptance gates.

## Existing placement index for the 94 ticketless candidates

This is the pre-rebaseline allocation, retained as an audit index rather than
a current commitment. It is not approval to implement every item. The daily
dependency sweeps must inspect story content and reassign eligible items to
the revised release families; Local, OpenRouter, swarms/Gateway, crawler/GTM,
and public-announcement items remain deferred unless separately approved.
By the ticket lock, every candidate receives a linked goal/epic/ticket or an
explicit deferred/archive disposition.

| Release | Candidates | Allocation |
| --- | ---: | --- |
| v0.25.2 | 6 | `story-9791a697`, `story-f336c1c5`, `harness-capability-registry-v2-plan-b-786`, `harness-rename-plan-a-786`, `story-5e2d2db2`, `story-bs8-probe` |
| v0.25.3 | 5 | `story-d84372cd`, `story-a7b5674c`, `story-7117bb01`, `story-74193239`, `story-a302384c` |
| v0.25.4 | 13 | `story-089c524e`, `story-08f5e280`, `story-1ade229f`, `story-514fde89`, `story-6e5795cf`, `story-78664ab2`, `story-8814681b`, `story-a5032986`, `story-b1f9d66b`, `story-d481115a`, `1218`, `story-057d4312`, `story-e4cd6595` |
| v0.26.0 | 6 | `story-a4442387`, `story-2e48a8c5`, `story-6f97c5a0`, `story-b4a90209`, `story-cb2c1d93`, `story-c04f64b1` |
| v0.26.1 | 5 | `story-0ad6c02b`, `story-272f0252`, `story-5ce5a997`, `story-bs8-consult`, `story-d59e1b3b` |
| v0.26.2 | 11 | `story-5dfe6b3f`, `story-620ca244`, `story-8faedf0a`, `story-b950515c`, `story-e0f0b014`, `story-f4171bdd`, `story-bs8-loop`, `governs-backlog-automation`, `story-bs8-meta-goals`, `story-bs8-split`, `story-ee4529d9` |
| v0.27.0 | 7 | `story-126d706f`, `story-43346243`, `story-8e8c952c`, `story-e528c886`, `story-18983f9f`, `story-3652dafe`, `story-3d52ea96` |
| v0.27.1 | 13 | `story-5019a85b`, `story-db3ce74c`, `story-0989ce14`, `story-615bc8f4`, `story-d5341d65`, `story-e5896237`, `story-e8c5d15f`, `ux1.0-regression-fix`, `story-4b288e24`, `story-9e2296f3`, `story-ca84004b`, `story-c822fd03`, `story-d4b40958` |
| v0.27.2 | 2 | `story-bs7-interop`, `story-fda756fd` |
| v0.28.0 | 5 | `story-9442caf8`, `story-c7064c40`, `story-2ebedf92`, `story-3aeb1c7a`, `story-ab6a0586` |
| v0.28.1 | 3 | `story-0ab760c5`, `story-33ab504a`, `story-c8e2b987` |
| v0.29.0 | 18 | `story-ffb0f3e6`, `story-1aab8f81`, `story-54d83487`, `story-6c5ff44e`, `story-b4b1167e`, `story-0127066f`, `story-2348ac34`, `story-541995f4`, `story-b75cb3e7`, `story-4fe0a8bf`, `story-5ef38956`, `story-f4dbf2ce`, `story-2161a277`, `story-565bf96f`, `story-631a6a86`, `story-e3a3170a`, `story-028d26d9`, `story-f6782d57` |

### Definitive Disposition of the 94 Ticketless Candidates (Locked for v0.25.6)

In accordance with the v0.25.6 daily gate and ticket lock mandate, all 94 candidates have received an audited, explicit disposition:

| Category / Cohort | Count | Candidates | Final Disposition | Governing Coordinates |
| :--- | :---: | :--- | :--- | :--- |
| **v0.25.2 Shipped** | 6 | `story-9791a697`, `story-f336c1c5`, `harness-capability-registry-v2-plan-b-786`, `harness-rename-plan-a-786`, `story-5e2d2db2`, `story-bs8-probe` | **Resolved / Shipped** | Release: `v0.25.2`, Epic: #2465, Goal: `goal-9ef9a965` (PR #2534) |
| **v0.25.3 Shipped** | 5 | `story-d84372cd`, `story-a7b5674c`, `story-7117bb01`, `story-74193239`, `story-a302384c` | **Resolved / Shipped** | Release: `v0.25.3`, Epic: #2466, Goal: `goal-9ef9a965` (PR #2577) |
| **v0.25.4 Shipped** | 13 | `story-089c524e`, `story-08f5e280`, `story-1ade229f`, `story-514fde89`, `story-6e5795cf`, `story-78664ab2`, `story-8814681b`, `story-a5032986`, `story-b1f9d66b`, `story-d481115a`, `1218`, `story-057d4312`, `story-e4cd6595` | **Resolved / Shipped** | Release: `v0.25.4`, Epic: #2467, Goal: `goal-079e2f37` (PR #2601) |
| **v0.26.0 Active** | 6 | `story-a4442387`, `story-2e48a8c5`, `story-6f97c5a0`, `story-b4a90209`, `story-cb2c1d93`, `story-c04f64b1` | **Active Planned** | Release: `v0.26.0`, Epic: #2469, Goal: `goal-079e2f37`, Arc: `runtime` |
| **v0.26.1 Active** | 5 | `story-0ad6c02b`, `story-272f0252`, `story-5ce5a997`, `story-bs8-consult`, `story-d59e1b3b` | **Active Planned** | Release: `v0.26.1`, Epic: #2470, Goal: `goal-eacab0dc`, Arc: `runtime` |
| **v0.26.2 Active** | 11 | `story-5dfe6b3f`, `story-620ca244`, `story-8faedf0a`, `story-b950515c`, `story-e0f0b014`, `story-f4171bdd`, `story-bs8-loop`, `governs-backlog-automation`, `story-bs8-meta-goals`, `story-bs8-split`, `story-ee4529d9` | **Active Planned** | Release: `v0.26.2`, Epic: #2470, Goal: `goal-9ef9a965`, Arc: `governance` |
| **v0.27.0 Active** | 7 | `story-126d706f`, `story-43346243`, `story-8e8c952c`, `story-e528c886`, `story-18983f9f`, `story-3652dafe`, `story-3d52ea96` | **Active Planned** | Release: `v0.27.0`, Epic: #2471, Goal: `goal-e3840370`, Arc: `runtime` |
| **v0.27.1 Active** | 13 | `story-5019a85b`, `story-db3ce74c`, `story-0989ce14`, `story-615bc8f4`, `story-d5341d65`, `story-e5896237`, `story-e8c5d15f`, `ux1.0-regression-fix`, `story-4b288e24`, `story-9e2296f3`, `story-ca84004b`, `story-c822fd03`, `story-d4b40958` | **Active Planned** | Release: `v0.27.1`, Epic: #2472, Goal: `goal-85656c82`, Arc: `frontend` |
| **v0.27.2 Active** | 2 | `story-bs7-interop`, `story-fda756fd` | **Active Planned** | Release: `v0.27.2`, Epic: #2473, Goal: `goal-85656c82`, Arc: `ecosystem` |
| **v0.28.0 Post-Preview** | 5 | `story-9442caf8`, `story-c7064c40`, `story-2ebedf92`, `story-3aeb1c7a`, `story-ab6a0586` | **Deferred (Post-Preview)** | Release: `v0.28.0`, Epic: #2474, Goal: `goal-bd5eaa14` (Milestone #10) |
| **v0.28.1 Post-Preview** | 3 | `story-0ab760c5`, `story-33ab504a`, `story-c8e2b987` | **Deferred (Post-Preview)** | Release: `v0.28.1`, Epic: #2475, Goal: `goal-06758149` (Milestone #11) |
| **v0.29.0 Post-Preview** | 18 | `story-ffb0f3e6`, `story-1aab8f81`, `story-54d83487`, `story-6c5ff44e`, `story-b4b1167e`, `story-0127066f`, `story-2348ac34`, `story-541995f4`, `story-b75cb3e7`, `story-4fe0a8bf`, `story-5ef38956`, `story-f4dbf2ce`, `story-2161a277`, `story-565bf96f`, `story-631a6a86`, `story-e3a3170a`, `story-028d26d9`, `story-f6782d57` | **Deferred (Post-Preview)** | Release: `v0.29.0`, Epic: #2476, Goal: `goal-51c4be3f` (Milestone #12) |


## Required bug and tech-debt reconciliation

- **First stability releases:** #2530 (false failure/orphan process) and
  #2532 (worktree generated-doc write target) are direct job-truth and data
  integrity risks. Include regression evidence before autonomous dispatch is
  relied upon. #2527/#2526, #2522, and #2320 are CI/release reliability items.
  `synlynk release --check-docs` currently reports
  `docs/reference/commands.md` stale; this needs a ticket-linked resolution
  before the release check is green. Close issues only after reproducing the
  race or verifying a fix on current main.
- **Model/catalog/cost:** revalidate #2441 and #2448--#2450 against merged
  work before adding tickets. The recent model-catalog PRs may resolve parts
  of this cohort; close or narrow only from current-code/test evidence. #1767
  (explicit-model fallback) is included only if still reproducible. Quota
  freshness/calibration may be deferred; missing/unknown data must remain
  explicit rather than presented as a valid estimate.
- **Muse:** #2457 and the low-privilege profile/probe scope of #2445 remain
  early capacity work. Refresh #2444/#2446 from current main. Muse review,
  deploy, and GitHub-write permissions remain disabled without separate
  capability evidence. Current `synlynk status` reports Muse as `unsupported`
  with no rated capability/capacity; do not count Muse as available until its
  onboarding and capability evidence are verified on the target environment.
- **Job truth:** revalidate #2138, #2139, #2309, #2438, and #2530. Fix active
  false terminal states, missing terminal evidence, or orphaned processes;
  archive/supersede only defects proven fixed.
- **Daemon/CI:** #2464, #1884, #2407, #2526, and #2527 are first-order
  candidates for the daemon/stability gates and must be reproduced against
  current main. #2477 is closed; do not carry its old work into this schedule
  without new evidence.
- **GOVERNS/autonomy:** #2305, #2511, #2528, and #2262 must be checked for
  overlap with current charter, claims, and daemon-autonomy implementation.
  The claim mechanism must be wired into actual work-start paths before it is
  treated as a collision-control gate.
- **PR queue:** refresh unique diffs only. #2444/#2446 are Muse candidates;
  #2523 is a release-doc candidate subject to #2522; duplicate/dirty followups
  #2519/#2521, #2516/#2520 and stale PRs require issue-comment and diff review
  before disposition. #2533/#2408 are Local work and deferred. #2175's
  per-PR blog convention is retired; public announcement work is not a Dev
  Preview gate.
- **Deferred after the first preview:** Local relay/pilot (#2525/#2533),
  OpenRouter (#2210 and related provider work), swarm/Kubernetes (#2367 and
  #2474), crawler/index/GTM (#2475), public announcement requirements, and
  unrelated code-intelligence or marketplace expansion. Bring forward only
  with a user-approved scope change or if a daily sweep finds a direct safety
  dependency.

## Artifact and planning policy

Existing approved plans may be used only after the pickup freshness check.
Draft or cross-cutting work requires renewed brainstorm/spec/plan approval:
workspace-agent charters, GOVERNS autonomy, swarms/gateway, capability
crawler/index, hosted Teams/relay, and any scope that materially changes the
VS Code distribution promise. Bounded bugs and regressions use a refreshed
mini-spec/plan where needed, rather than a new broad brainstorm.
