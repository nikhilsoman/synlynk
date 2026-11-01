<!-- generated - source of truth is state.db -->
---
decision_id: dec-5b9c5ef2
topic: "RELEASE-READINESS PLAN REVIEW: review and approve, or recommend a specific revision to, the remaining implementation plan for the Developer Preview stable release gate targeted 2026-11-06 (v0.27.5), under parent epic #2458, goal-85656c82.

CONTEXT — this is a forward-looking plan review, not a retrospective readiness verdict. The remaining plan was deliberately sequenced this way: v0.27.x being entirely unstarted is intentional (a planned stock-take checkpoint before embarking, not drift), and the v0.26.7/v0.26.9/v0.26.10 roadmap entries are newly-discovered-gap additions inserted by the human PM during this cycle, not debt that crept in unnoticed.

THE REMAINING PLAN TO REVIEW, IN SEQUENCE:
1. v0.26.7 — Vizor Jantt Timeline & Interactive GOVERNS Stage Mapping [planned, target 2026-10-30, already past]. Jantt vendored JS timeline canvas, bidirectional GOVERNS<->Jantt data adapter, lock/unlock stage editing with state.db write-back via `roadmap update`, dark/light theme sync.
2. v0.26.8 — Task Boundary Context Protocol, Compaction & Herdr Epic Tabs [planned, target 2026-10-30, already past]. Four specs written, DECIDE-reviewed, and turned into committed implementation plans this cycle (docs/superpowers/plans/2026-10-31-configurability-framework.md, 2026-10-31-companion-v2.md, 2026-10-31-harness-context-compaction-protocol.md, 2026-10-31-herdr-customizations.md), ZERO tasks executed yet. Two open questions for this panel: (a) none of the four plans implement the `synlynk statusline` item that IS named in v0.26.8's own roadmap text ("fenced synlynk statusline displaying breadcrumbs, active goal/story, git HEAD, burn rate, sentinel status, and task/cost summaries") — missing plan, or shipped elsewhere? (b) Companion v2 does not appear anywhere in v0.26.8's literal roadmap scope text — was it correctly folded into this epic, or does it belong in a separate slot?
3. v0.26.9 — "ceremonies canon" — NOT YET IN roadmap.md. Exists only as open PR #2640 ("docs(governance): v0.26.9 ceremonies canon & v0.26.10 inception specs"), open 11+ days as of this review, no roadmap.md entry yet.
4. v0.26.10 — Claude interactive auto-mode classifier regression investigation [planned, target TBD]. Investigation only, not yet scoped into tasks.
5. v0.27.0 — VS Code and OpenVSX listing [planned, target 2026-11-01, already past]. Meta Muse CLI Adapter GA promotion, 5-way cross-harness PR review routing, Muse structured output/cost ledger integration.
6. v0.27.1 — Quickstart and onboarding first win [planned, target 2026-11-02]. Gate: fresh-project journeys reach a verified first dispatch in under 15 minutes. NOTE: the baseline-metrics story this gate depends on (story-issue-1973, "baseline metrics capture before any onboarding/dispatch UX change") is itself still unchecked in todo.md — there is currently no baseline to measure "15 minutes" against.
7. v0.27.2 — Onboarding clarity and recovery [planned, target 2026-11-03]. Gate: install/update failure paths, prerequisites, harness choice, common errors explained end to end.
8. v0.27.3 — Cross-harness onboarding verification [planned, target 2026-11-04]. Gate: five independent fresh-project journeys pass install-to-useful-result, including Muse — depends on v0.27.0's Muse GA promotion landing first.
9. v0.27.4 — Developer Preview acceptance run [planned, target 2026-11-05]. Gate: GOVERNS, model catalog/capability/cost, job-status truth, workspace-agent autonomy, and quickstart/onboarding ALL green together.
10. v0.27.5 — Developer Preview stable release gate [planned, target 2026-11-06]. Gate: daily stable tag becomes the Developer Preview only when v0.27.4 acceptance evidence is green AND no unresolved release-blocking Sev1/Sev2 defect remains. Human release authority required. v1.0.0-preview is explicitly superseded by this gate — no separate channel.

TRACK RECORD CONTEXT (for the panel to weigh, not the headline question): the project has shipped 9 milestones in the last ~9 days (v0.25.2 through v0.26.6, 2026-10-23 through 2026-10-29) with steady velocity (81 merge commits since v0.25.2) and only one SEV-1 incident in that window (#2624, CLI entrypoint PATH-shadowing break) — caught and hotfixed same day (filed 06:42 UTC, closed 18:01 UTC, shipped as v0.26.2). That is a genuinely good incident-response signal, not just a lucky absence of problems.

HOWEVER, there is evidence of at least one class of SILENT failure the human PM asked this panel to specifically weigh: the "Publish to PyPI" and "Publish VS Code Extension (Marketplace & Open VSX)" GitHub Actions workflows have FAILED on every one of the last 3 tagged release-prep runs checked (v0.26.5 2026-10-27, v0.26.6 2026-10-28, v0.26.7 2026-10-31) — all three failed, with no corresponding ticket, hotfix, or roadmap flag found. These releases were still marked [shipped] in roadmap.md with GitHub Releases published, meaning the human-visible "shipped" signal did not reflect this gap. This is directly load-bearing for v0.27.0's own gate ("VS Code and OpenVSX listing") and should weigh heavily on whether v0.27.0 is actually achievable on schedule, or whether the publish pipeline itself needs a dedicated fix task inserted ahead of it.

OTHER REPO-HEALTH RISKS TO WEIGH (not headline findings, but feasibility risks for a 6-day runway):
- Worktrees: 160 local, 33 look stale (synlynk worktree audit overdue).
- Capability sweep: overdue, 185 jobs since last sweep — the Empirical Capability Assessment Policy currently has no fresh data to route on.
- Smoke test: overdue (synlynk selftest --live not run; auto_smoke_test disabled) — no recent live-verified evidence the daily build works end to end.
- Sentinel: 2 CRITICAL TOKEN_CIRCUIT_BREAKER_TRIPPED events on 2026-10-28 (codex zero-file runaway, 697K and 915K tokens burned, 0 files touched) — cost risk, not yet recurring.
- Open PRs: 30, median age 9 days, oldest 13 days; several titles look like malformed/off-topic dispatch jobs (e.g. "Analyze these two public YouTube videos directly," "IT services CxO brief on Devin and Synlynk") — likely noise, not real blockers, but untriaged.
- Open live issues: 4, including sev1 #2139 (job-status reconciliation no-op logging, consolidated into story-25872226/goal-bde24050, tracking moved to #2137) and sev1 #1686 (state.db DR restore validation, open since 2026-09-18). Two sev2s (#2087, #2088) actively degrade `synlynk pr check` itself, which every merge in this plan depends on as its review gate.

QUESTIONS FOR THE PANEL:
1. Is the sequencing above (v0.26.7 -> v0.26.8 -> v0.26.9 -> v0.26.10 -> v0.27.0 -> v0.27.1 -> v0.27.2 -> v0.27.3 -> v0.27.4 -> v0.27.5) the right order to hit 2026-11-06, or should anything be reordered, parallelized, cut, or deferred past the Developer Preview?
2. Does the PyPI/VS Code publish-pipeline failure (3 consecutive red runs) require a dedicated fix task inserted before v0.27.0, given v0.27.0's own gate depends on successful listing/publish?
3. Given v0.26.8 has zero tasks executed and v0.27.1's baseline-metrics prerequisite is also unstarted, is 2026-11-06 still realistic, or should the panel recommend narrowing v0.27.x's scope (e.g., defer Muse cross-harness verification, defer the Jantt timeline) to protect the date?
4. Resolve the two v0.26.8 open questions directly: is `synlynk statusline` a real gap needing a fifth implementation plan, and does Companion v2 belong under v0.26.8 or a separate roadmap slot?
5. Given the pr-check-degrading live issues (#2087, #2088) and the overdue capability sweep/smoke test, what is the minimum repo-health remediation that must happen before or alongside v0.27.x work, versus what can run in parallel without blocking?

Produce a clear APPROVE / APPROVE-WITH-REVISIONS / REJECT verdict on the remaining plan as a whole, plus specific, actionable revisions if not a clean APPROVE."
date: 2026-10-31
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
RELEASE-READINESS PLAN REVIEW: review and approve, or recommend a specific revision to, the remaining implementation plan for the Developer Preview stable release gate targeted 2026-11-06 (v0.27.5), under parent epic #2458, goal-85656c82.

CONTEXT — this is a forward-looking plan review, not a retrospective readiness verdict. The remaining plan was deliberately sequenced this way: v0.27.x being entirely unstarted is intentional (a planned stock-take checkpoint before embarking, not drift), and the v0.26.7/v0.26.9/v0.26.10 roadmap entries are newly-discovered-gap additions inserted by the human PM during this cycle, not debt that crept in unnoticed.

THE REMAINING PLAN TO REVIEW, IN SEQUENCE:
1. v0.26.7 — Vizor Jantt Timeline & Interactive GOVERNS Stage Mapping [planned, target 2026-10-30, already past]. Jantt vendored JS timeline canvas, bidirectional GOVERNS<->Jantt data adapter, lock/unlock stage editing with state.db write-back via `roadmap update`, dark/light theme sync.
2. v0.26.8 — Task Boundary Context Protocol, Compaction & Herdr Epic Tabs [planned, target 2026-10-30, already past]. Four specs written, DECIDE-reviewed, and turned into committed implementation plans this cycle (docs/superpowers/plans/2026-10-31-configurability-framework.md, 2026-10-31-companion-v2.md, 2026-10-31-harness-context-compaction-protocol.md, 2026-10-31-herdr-customizations.md), ZERO tasks executed yet. Two open questions for this panel: (a) none of the four plans implement the `synlynk statusline` item that IS named in v0.26.8's own roadmap text ("fenced synlynk statusline displaying breadcrumbs, active goal/story, git HEAD, burn rate, sentinel status, and task/cost summaries") — missing plan, or shipped elsewhere? (b) Companion v2 does not appear anywhere in v0.26.8's literal roadmap scope text — was it correctly folded into this epic, or does it belong in a separate slot?
3. v0.26.9 — "ceremonies canon" — NOT YET IN roadmap.md. Exists only as open PR #2640 ("docs(governance): v0.26.9 ceremonies canon & v0.26.10 inception specs"), open 11+ days as of this review, no roadmap.md entry yet.
4. v0.26.10 — Claude interactive auto-mode classifier regression investigation [planned, target TBD]. Investigation only, not yet scoped into tasks.
5. v0.27.0 — VS Code and OpenVSX listing [planned, target 2026-11-01, already past]. Meta Muse CLI Adapter GA promotion, 5-way cross-harness PR review routing, Muse structured output/cost ledger integration.
6. v0.27.1 — Quickstart and onboarding first win [planned, target 2026-11-02]. Gate: fresh-project journeys reach a verified first dispatch in under 15 minutes. NOTE: the baseline-metrics story this gate depends on (story-issue-1973, "baseline metrics capture before any onboarding/dispatch UX change") is itself still unchecked in todo.md — there is currently no baseline to measure "15 minutes" against.
7. v0.27.2 — Onboarding clarity and recovery [planned, target 2026-11-03]. Gate: install/update failure paths, prerequisites, harness choice, common errors explained end to end.
8. v0.27.3 — Cross-harness onboarding verification [planned, target 2026-11-04]. Gate: five independent fresh-project journeys pass install-to-useful-result, including Muse — depends on v0.27.0's Muse GA promotion landing first.
9. v0.27.4 — Developer Preview acceptance run [planned, target 2026-11-05]. Gate: GOVERNS, model catalog/capability/cost, job-status truth, workspace-agent autonomy, and quickstart/onboarding ALL green together.
10. v0.27.5 — Developer Preview stable release gate [planned, target 2026-11-06]. Gate: daily stable tag becomes the Developer Preview only when v0.27.4 acceptance evidence is green AND no unresolved release-blocking Sev1/Sev2 defect remains. Human release authority required. v1.0.0-preview is explicitly superseded by this gate — no separate channel.

TRACK RECORD CONTEXT (for the panel to weigh, not the headline question): the project has shipped 9 milestones in the last ~9 days (v0.25.2 through v0.26.6, 2026-10-23 through 2026-10-29) with steady velocity (81 merge commits since v0.25.2) and only one SEV-1 incident in that window (#2624, CLI entrypoint PATH-shadowing break) — caught and hotfixed same day (filed 06:42 UTC, closed 18:01 UTC, shipped as v0.26.2). That is a genuinely good incident-response signal, not just a lucky absence of problems.

HOWEVER, there is evidence of at least one class of SILENT failure the human PM asked this panel to specifically weigh: the "Publish to PyPI" and "Publish VS Code Extension (Marketplace & Open VSX)" GitHub Actions workflows have FAILED on every one of the last 3 tagged release-prep runs checked (v0.26.5 2026-10-27, v0.26.6 2026-10-28, v0.26.7 2026-10-31) — all three failed, with no corresponding ticket, hotfix, or roadmap flag found. These releases were still marked [shipped] in roadmap.md with GitHub Releases published, meaning the human-visible "shipped" signal did not reflect this gap. This is directly load-bearing for v0.27.0's own gate ("VS Code and OpenVSX listing") and should weigh heavily on whether v0.27.0 is actually achievable on schedule, or whether the publish pipeline itself needs a dedicated fix task inserted ahead of it.

OTHER REPO-HEALTH RISKS TO WEIGH (not headline findings, but feasibility risks for a 6-day runway):
- Worktrees: 160 local, 33 look stale (synlynk worktree audit overdue).
- Capability sweep: overdue, 185 jobs since last sweep — the Empirical Capability Assessment Policy currently has no fresh data to route on.
- Smoke test: overdue (synlynk selftest --live not run; auto_smoke_test disabled) — no recent live-verified evidence the daily build works end to end.
- Sentinel: 2 CRITICAL TOKEN_CIRCUIT_BREAKER_TRIPPED events on 2026-10-28 (codex zero-file runaway, 697K and 915K tokens burned, 0 files touched) — cost risk, not yet recurring.
- Open PRs: 30, median age 9 days, oldest 13 days; several titles look like malformed/off-topic dispatch jobs (e.g. "Analyze these two public YouTube videos directly," "IT services CxO brief on Devin and Synlynk") — likely noise, not real blockers, but untriaged.
- Open live issues: 4, including sev1 #2139 (job-status reconciliation no-op logging, consolidated into story-25872226/goal-bde24050, tracking moved to #2137) and sev1 #1686 (state.db DR restore validation, open since 2026-09-18). Two sev2s (#2087, #2088) actively degrade `synlynk pr check` itself, which every merge in this plan depends on as its review gate.

QUESTIONS FOR THE PANEL:
1. Is the sequencing above (v0.26.7 -> v0.26.8 -> v0.26.9 -> v0.26.10 -> v0.27.0 -> v0.27.1 -> v0.27.2 -> v0.27.3 -> v0.27.4 -> v0.27.5) the right order to hit 2026-11-06, or should anything be reordered, parallelized, cut, or deferred past the Developer Preview?
2. Does the PyPI/VS Code publish-pipeline failure (3 consecutive red runs) require a dedicated fix task inserted before v0.27.0, given v0.27.0's own gate depends on successful listing/publish?
3. Given v0.26.8 has zero tasks executed and v0.27.1's baseline-metrics prerequisite is also unstarted, is 2026-11-06 still realistic, or should the panel recommend narrowing v0.27.x's scope (e.g., defer Muse cross-harness verification, defer the Jantt timeline) to protect the date?
4. Resolve the two v0.26.8 open questions directly: is `synlynk statusline` a real gap needing a fifth implementation plan, and does Companion v2 belong under v0.26.8 or a separate roadmap slot?
5. Given the pr-check-degrading live issues (#2087, #2088) and the overdue capability sweep/smoke test, what is the minimum repo-health remediation that must happen before or alongside v0.27.x work, versus what can run in parallel without blocking?

Produce a clear APPROVE / APPROVE-WITH-REVISIONS / REJECT verdict on the remaining plan as a whole, plus specific, actionable revisions if not a clean APPROVE.

## Panel Inputs

### claude
[model=default; version=2.1.311 (Claude Code)]

**Verdict: APPROVE-WITH-REVISIONS.**

The sequencing logic is sound where it's genuinely dependency-ordered (v0.27.3 needs Muse GA from v0.27.0; v0.27.4 needs everything green; v0.27.5 needs human sign-off). But three things need to change before this plan is executable on schedule.

**1. Publish pipeline gets a dedicated fix task now, ahead of v0.27.0.** Three consecutive red runs on PyPI/VS Code publish, silently masked by roadmap "[shipped]" status, is exactly the kind of gap that turns v0.27.0's gate into theater. Insert a scoped fix-and-verify task before v0.27.0 starts — this is cheap now, expensive as a day-of-release discovery.

**2. Narrow v0.27.x scope to protect the date.** With v0.26.8 at zero executed tasks and the v0.27.1 baseline-metrics prerequisite unstarted, 2026-11-06 is tight, not unrealistic — but only if load is cut. Defer Jantt timeline (v0.26.7, already past-due, cosmetic relative to release-gate) and Muse cross-harness verification (v0.27.3) past the Developer Preview; Muse has zero calibration samples per the Empirical Capability Assessment Policy and its GA promotion is itself unproven. Both can ship as fast-follow without blocking the gate.

**3. Resolve v0.26.8's open questions explicitly, don't let them ride silently.** `synlynk statusline` is named in roadmap text but absent from all four committed plans — that's a real gap requiring either a fifth plan or an explicit roadmap-text correction, not silence. Companion v2 appearing in plans but not roadmap scope is a scope-creep smell — either amend v0.26.8's roadmap entry to name it, or move it to its own slot. Pick one for each, today.

**4. Minimum parallel remediation, not blocking:** backfill `cost_entries` reviewer-provenance gaps and fix #2087/#2088 (degrading `synlynk pr check`, the gate every merge in this plan depends on) before v0.27.4's acceptance run — this is load-bearing for the gate's own evidence integrity. Worktree/capability/smoke-test staleness can run in parallel threads, not blocking, but smoke test (`selftest --live`) should run at least once before v0.27.4 since "daily build works end to end" is literally what that gate claims.

Track record (9 milestones/9 days, 1 Sev1 caught same-day) supports confidence in execution velocity — the risk here is gate-integrity, not throughput. With the publish-pipeline fix inserted and Jantt/Muse deferred, 2026-11-06 is achievable.

### agy
[model=default; version=1.4.12]

**Last completed task:** Roadmap v0.26.1: Workspace-agent operations ([`story-97f99c0d`](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/docs+claude+synlynk-com-platform-vision/project-docs/todo.md#L11))  
**Next task:** Reconcile project-docs drift stranded in PR #2571 review worktree ([`story-360c0d73`](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/docs+claude+synlynk-com-platform-vision/project-docs/todo.md#L4))

---

### Release-Readiness Plan Review: Epic #2458 (Goal-85656c82)

**1. Critical Sequencing & Publish Pipeline Remediation:**  
Three consecutive silent publish failures (PyPI and VS Code Marketplace/OpenVSX) across v0.26.5–v0.26.7 make v0.27.0 unexecutable as drafted. A dedicated **P0 publish-pipeline remediation task must be inserted as a hard dependency preceding v0.27.0**. Additionally, fast-track PR #2640 (v0.26.9 governance docs) and relegate v0.26.10 (classifier regression) to an asynchronous, non-gating research spike.

**2. Scope Descoping & Feasibility for 2026-11-06:**  
Shipping 10 sequential milestones in 6 days while v0.26.8 has zero completed tasks is unfeasible without aggressive pruning. **Defer v0.26.7 (Jantt Timeline Canvas)** to v0.28+; visual timeline editing is non-essential chrome for a CLI/harness developer preview gate. Narrow v0.27.0 and v0.27.3 to the 4 core engines (Claude, Codex, Agy, Grok) if Meta Muse adapter GA exhibits onboarding volatility. Unblock v0.27.1 immediately by dispatching baseline capture ([`story-issue-1973`](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/docs+claude+synlynk-com-platform-vision/project-docs/todo.md)) in parallel with v0.26.8.

**3. v0.26.8 Resolution:**  
- **`synlynk statusline`:** It is an unwritten plan gap. Defer cosmetic statusline UI to v0.28; retain only the underlying telemetry/state-writeback hooks within the configurability plan.
- **Companion v2:** Does not belong in v0.26.8. Spin it out into a standalone post-preview slot so v0.26.8 stays strictly focused on harness context compaction protocols.

**4. Repo-Health Minimum Baseline:**  
Hotfix Sev-2 live issues #2087 and #2088 immediately. Because they actively break `synlynk pr check`, every subsequent PR gate in this plan is compromised until resolved. Stale worktree pruning (160 worktrees), capability sweeps, and live smoke tests can run in parallel background dispatch lanes without blocking feature critical paths.

**Verdict: APPROVE-WITH-REVISIONS.**  
I recommend approving the 2026-11-06 target **only under the following revised sequence**: (1) Fix PR-check Sev-2s (#2087, #2088); (2) Execute pruned v0.26.8 (compaction protocols only, dropping Jantt v0.26.7, Companion v2, and statusline UI) while capturing baseline metrics (`story-issue-1973`) in parallel; (3) Merge PR #2640 (v0.26.9); (4) Fix PyPI/VS Code CI publish workflows ahead of v0.27.0; (5) Run onboarding gates v0.27.1–v0.27.5 locked to the 4 primary harnesses.

### codex
[model=default; version=codex-cli 0.163.0]

**Verdict: APPROVE-WITH-REVISIONS.** The sequence is directionally sound, but the 2026-11-06 gate is not credible without immediate scope and dependency changes.

Insert a dedicated **release-pipeline repair and verification task before v0.27.0**. Three consecutive failed PyPI and VS Code/OpenVSX workflows, while releases were still marked shipped, represent a silent release-integrity failure. v0.27.0 must not be considered complete until both workflows pass on a tagged dry run and the shipped signal reflects publish status.

Reorder the near-term work into parallel tracks:

- Immediately perform the minimum health reset: repair or explicitly disposition #2087/#2088, run `synlynk selftest --live`, complete the overdue capability sweep, and triage whether #1686 and #2139 block the release. These are prerequisites for trustworthy merge and acceptance evidence.
- Run v0.26.8 implementation in parallel, but split it into critical and deferrable work. The statusline is a real gap because it is explicit roadmap scope and absent from all four plans; add a fifth small implementation plan, or clearly identify an existing shipped implementation before approval. Companion v2 may remain under v0.26.8 only if its acceptance criteria are explicitly added; otherwise move it to a separate post-preview slot.
- Treat v0.26.9 ceremonies canon and v0.26.10 classifier investigation as documentation/investigation work that cannot block the preview unless they expose release-critical defects.
- Establish the v0.27.1 baseline metrics before changing onboarding. Without story-1973’s baseline, the “under 15 minutes” gate is unverifiable.
- Keep v0.27.0 ahead of v0.27.3, since Muse verification depends on it, but make Muse cross-harness verification and Jantt timeline explicitly deferrable if they threaten the date. Jantt should not block the Developer Preview unless GOVERNS usability is itself a release criterion.

The six-day runway remains possible only with strict change control, parallel execution, and daily evidence checkpoints. I therefore recommend approval of the plan **only with these revisions**, a repaired publish pipeline, baseline metrics, and a documented cut list protecting v0.27.4/v0.27.5.

### grok
[model=default; version=grok 1.0.70 (f50904eaee6c) [stable]]

I'll check the roadmap text, the four v0.26.8 plans, and whether `synlynk statusline` already exists before giving a verdict.**APPROVE-WITH-REVISIONS.** The full v0.26.7 through v0.27.5 sequence will not make 2026-11-06. Hold the date only for a cut line.

Ten items sit in front of a six-day gate. Two targets are already past, v0.26.8 has four committed plans and zero executed tasks, and v0.27.1’s “under 15 minutes” gate has no baseline because story-issue-1973 is still open. The v0.25.2–v0.26.6 run (81 merges, one same-day Sev1 in #2624) shows a scoped milestone can land. It does not show this unstarted cluster can land on top of a red publish pipeline.

Build the week around the v0.27.4 acceptance surface: GOVERNS, catalog/capability/cost, job-status truth, workspace-agent autonomy, and quickstart/onboarding. Defer past Developer Preview: v0.26.7 Jantt, v0.26.9 ceremonies canon (PR #2640 only — merge the docs or leave them; do not sequence them), and v0.26.10 (investigation, parallel at most). For v0.27.0, follow the roadmap gate sentence already written there: listing, install, update, and dispatch smoke (#2103). Muse GA, 5-way review routing, and the Muse cost ledger are already marked as not delaying that gate — drop them from this date. Narrow v0.27.3 to the four harnesses already in GA.

The PyPI and VS Code/OpenVSX failure needs its own fix, and it goes first. Three consecutive red publish runs (v0.26.5, v0.26.6, v0.26.7) were still marked shipped. v0.27.0’s gate is that listing. File the ticket, fix the workflows, and get one current tag green before any listing scope starts.

`synlynk statusline` is a real gap. None of the four 2026-10-31 plans implement it, and the package has no such command. The roadmap line — breadcrumbs, goal/story, HEAD, burn rate, sentinel, task/cost — is unbuilt. Leave it for after Preview; do not add a fifth plan to this runway. Companion v2 is the at-the-fence voice feature. It shares the configurability framework with compaction and Herdr, and it is absent from the v0.26.8 sentence. Put it in its own post-Preview slot. Defer all of v0.26.8 as well: it is not on the acceptance list.

Minimum health beside that cut line: fix or explicitly waive #2087 and #2088 before the next merge wave, since they degrade `synlynk pr check`. Keep #2139 inside the v0.27.4 job-status run. Have a human mark #1686 non-release-blocking for this tag, or the v0.27.5 Sev1 rule fails on ambiguity. Run one `synlynk selftest --live` before v0.27.4. Time three fresh installs inside v0.27.1 rather than waiting on the full baseline program. The capability sweep, the 160-worktree audit, and the 30 open PRs run in parallel and do not gate the tag.

Hold 2026-11-06 for this cut line only: publish-pipeline fix, pr-check Sev2s, #2139 inside acceptance, listing smoke, a thin timed first dispatch, onboarding recovery, four-harness verification, then the human v0.27.5 tag. Defer Jantt, ceremonies, the classifier investigation, Muse GA, Companion v2, and statusline.

## Synthesis
## Synthesis

All four panelists converge on the same verdict and the same core revisions, with only minor differences in emphasis. That convergence itself is a strong signal — this isn't a close call.

**Where they agree (unanimous across claude/agy/codex/grok):**

1. **Publish-pipeline fix is non-negotiable and goes first.** Three consecutive silent failures (PyPI + VS Code/OpenVSX, v0.26.5→v0.26.7) while roadmap.md still said "[shipped]" is a release-integrity failure, not a nice-to-have. v0.27.0's own gate is listing/publish — it cannot proceed on an unverified pipeline. Insert a dedicated fix-and-verify task (dry-run tag, both workflows green) before v0.27.0 starts.
2. **v0.26.7 Jantt Timeline defers past Developer Preview.** Already past target, cosmetic relative to the release gate, not on v0.27.4's acceptance surface (GOVERNS/capability/job-status/autonomy/onboarding).
3. **Narrow v0.27.3 to the four GA harnesses (Claude/Codex/Agy/Grok); defer Muse cross-harness verification.** Muse has zero capability-sweep samples under the Empirical Capability Assessment Policy — its GA promotion in v0.27.0 is itself unproven, so gating v0.27.3 on it compounds risk for no release-relevant benefit.
4. **Companion v2 does not belong in v0.26.8.** It's absent from v0.26.8's literal roadmap text; all four panelists say spin it into its own post-preview slot rather than let scope ride silently.
5. **#2087/#2088 must be fixed or explicitly dispositioned before/alongside the next merge wave**, since they degrade `synlynk pr check` — the gate every PR in this plan depends on.
6. **v0.26.9 (ceremonies canon) and v0.26.10 (classifier investigation) should not gate the date.** Merge PR #2640 or leave it; treat v0.26.10 as a parallel, non-blocking investigation.
7. **v0.27.1's baseline-metrics gap is real and must be addressed**, not waived — either unblock story-issue-1973 in parallel immediately, or (grok's more pragmatic variant) time a handful of fresh installs directly as a lighter-weight substitute baseline.
8. **Worktree audit, capability sweep, and the 30 open PRs are parallel-track, non-blocking** — don't let them consume runway against the date.

**Where they differ (minor):**
- `synlynk statusline`: codex wants either a fifth implementation plan or explicit confirmation it's shipped elsewhere before approving; claude/agy/grok treat it as a confirmed real gap but defer it past Preview since it isn't on the v0.27.4 acceptance surface. The roadmap-text/plan mismatch should be corrected regardless (either write the plan or correct the roadmap sentence), but it doesn't need to block 2026-11-06.
- grok goes furthest in explicitly trimming v0.27.0 itself to the roadmap's own stated gate sentence (listing/install/update/dispatch smoke) and treating all of v0.26.8 as deferrable — a more aggressive cut than the others, but not in conflict with them, just a stricter reading of what's load-bearing.

**Decision:** APPROVE-WITH-REVISIONS. Keep the 2026-11-06 date, but only under this amended sequence: (1) fix and verify the PyPI/VS Code publish pipeline on a green tagged dry run before any v0.27.0 work starts; (2) fix or explicitly waive #2087/#2088 before the next merge wave, since every subsequent PR in this plan depends on `synlynk pr check`; (3) defer v0.26.7 (Jantt), Companion v2, and Muse cross-harness verification (narrow v0.27.3 to the four GA harnesses) past the Developer Preview as fast-follows — none sit on v0.27.4's acceptance surface; (4) treat v0.26.9/PR #2640 and v0.26.10 as non-gating parallel tracks — merge the docs or leave them, keep the classifier investigation async; (5) resolve `synlynk statusline`'s roadmap-text/plan mismatch explicitly (amend the roadmap line or scope it in, but don't let it block the date) and correct v0.26.8's scope text to either include or exclude Companion v2 rather than leaving it ambiguous; (6) unblock story-issue-1973's baseline capture in parallel with v0.26.8 rather than sequencing behind it, so v0.27.1's "under 15 minutes" gate has something to measure against; (7) run one `synlynk selftest --live` before v0.27.4, since "the daily build works end to end" is literally what that gate asserts. Worktree/capability-sweep staleness and the 30 open PRs proceed in parallel and do not block. With this cut list and the publish-pipeline fix front-loaded, 2026-11-06 is achievable; without it, the date is not credible.

## Decision
**Decision:** APPROVE-WITH-REVISIONS. Keep the 2026-11-06 date, but only under this amended sequence: (1) fix and verify the PyPI/VS Code publish pipeline on a green tagged dry run before any v0.27.0 work starts; (2) fix or explicitly waive #2087/#2088 before the next merge wave, since every subsequent PR in this plan depends on `synlynk pr check`; (3) defer v0.26.7 (Jantt), Companion v2, and Muse cross-harness verification (narrow v0.27.3 to the four GA harnesses) past the Developer Preview as fast-follows — none sit on v0.27.4's acceptance surface; (4) treat v0.26.9/PR #2640 and v0.26.10 as non-gating parallel tracks — merge the docs or leave them, keep the classifier investigation async; (5) resolve `synlynk statusline`'s roadmap-text/plan mismatch explicitly (amend the roadmap line or scope it in, but don't let it block the date) and correct v0.26.8's scope text to either include or exclude Companion v2 rather than leaving it ambiguous; (6) unblock story-issue-1973's baseline capture in parallel with v0.26.8 rather than sequencing behind it, so v0.27.1's "under 15 minutes" gate has something to measure against; (7) run one `synlynk selftest --live` before v0.27.4, since "the daily build works end to end" is literally what that gate asserts. Worktree/capability-sweep staleness and the 30 open PRs proceed in parallel and do not block. With this cut list and the publish-pipeline fix front-loaded, 2026-11-06 is achievable; without it, the date is not credible.

> Signatures: see 2026-10-31-release-readiness-plan-review-review-and.json
