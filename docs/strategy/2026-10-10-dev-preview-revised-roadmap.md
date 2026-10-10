# Revised Roadmap: Dev Preview — 7 Pillars, Dependency-Ordered

**Date:** 2026-10-10
**Horizon:** ~4 weeks (target 2026-10-31, matching gh:#1515's existing working date)
**Supersedes-by-extension:** gh:#1515 (dev-preview launch epic) is not replaced — this roadmap is its execution backbone, extended to cover 4 goals #1515's current text doesn't mention (1, 3, 6, 7 below) and to fold in every open item from the five-track plan and three-lens review.

## 0. Framing

Nikhil's ask is to re-sequence **existing** work — most of the 7 pillars already have a GOVERNS goal, a shipped partial foundation, or a tracked issue cluster — around one deadline and one release artifact: a named dev-preview release that proves synlynk is usable, trustworthy, and economically self-aware. This is not a net-new-scope roadmap; it is a convergence roadmap. The governing discipline is: **everything in this doc already exists as a goal, issue, or shipped module** unless explicitly marked `[NEW]`.

Every phase below must close with a shippable, demoable increment. The release gate at the end (#1515 Phase 7 — Release Candidate/Announcement) is the forcing function; nothing is allowed to drift past it without being explicitly re-parked.

## 1. Pillar → existing GOVERNS goal map

| # | Pillar (Nikhil's words) | Existing goal(s) | Status |
|---|---|---|---|
| 1 | Usable from Claude/Codex/Grok/Agy/Muse CLIs | `goal-005ea87d` Full Fleet Harness Parity | Partial — Muse untested on PM/review/deploy lanes |
| 2 | Autonomously operate the GOVERNS SDLC | `goal-eacab0dc` Universal GOVERNS enforcement (loop) | In `observe` mode since PR #2120; re-hardening gated on 100-clean-pass streak |
| 3 | Capability-matrix task allocation + tokenomics/$-value accounting | `goal-adb60ccc` Fleet analytics job-success split | Blocked on #1926 state.db consolidation; #1993 capability-report generator not yet built |
| 4 | Local model pathway, pick one, 20% contributor | `goal-8d34c416` Productize local/sovereign; `goal-56d4beee` (stale, deadline passed 2026-09-01) | Roster shipped (#1984 closed); measurement layer missing |
| 5 | Brainstorm/plan rigor + execution velocity as foundation | No single goal — this is a *process* pillar, already encoded as CLAUDE.md's Brainstorm-First Policy + Design→Plan→Build | Practiced, not measured |
| 6 | Domain-pack competency → workspace agent fleets | `goal-06758149` Activate full Synlynk workspace agent fleet | Early |
| 7 | Deploy large swarms of workspace agent roles | `goal-abecd18c` Containerized/OS-level agent execution | Early, overlaps #1515 Phase 6 (field trial) |
| — | Dev-preview release itself | `goal-9ef9a965` (release announcement), `goal-85656c82` (DX v1.0), governing story `story-1aab8f83` | 7-phase roadmap, target 2026-10-31 |

**Stale-deadline reconciliation (do this first, Week 1, as part of #1515 Phase 1 "Foundation and reset"):**
- `goal-5be4eb8b` "v1.0.0 Dev Preview Mandatory Architecture" — deadline 2026-10-01, passed. Re-date to 2026-10-31 or fold into `goal-9ef9a965`/`goal-85656c82`; don't run two dev-preview goals in parallel.
- `goal-56d4beee` "Local agent offloads..." — deadline 2026-09-01, passed. Supersede with `goal-8d34c416` since #1984 already shipped the thing this goal was tracking.
- `goal-d38e3c83` "Fleet dispatch scheduler v2" — deadline 2026-08-10, passed. Close or re-date against pillar 7's swarm-dispatch work; don't let a dead deadline sit on the goal graph while pillar 7 work starts.
- `goal-d3333441` "v0.24.0: Autonomous Platform, Sovereign..." — deadline 2026-10-12, 2 days out. Check its linked stories now; either it closes clean before Week 1 ends or its remainder folds into this roadmap's Week 1-2 work rather than slipping silently.

## 2. Dependency-ordered phases

### Week 1 — Foundation and reset (blocks everything else)
Maps to #1515 Phase 1. Nothing in Weeks 2-4 can be trusted until this closes.

1. **Stale-goal reconciliation** (above) — `[process]`, no code.
2. **#1926 state.db consolidation (Track 3)** — hard blocker for pillar 3 (capability/cost data is scattered across 11,000+ per-job shards per `[[stray-local-state-db]]`). This is the single highest-leverage dependency in the whole roadmap: #1993, #2102, #2104 and the entire tokenomics pillar cannot start without it.
3. **P0 items from the three-lens review** — security/correctness findings graded C+/B in the review must close before anything ships as a "preview," since a dev preview that gets picked apart on security in week one defeats pillar 5's "rigor" promise. Treat these as release-blocking, not backlog.
4. **Job-status reconciliation Bug A fix** (gh:#2136, #2137, #2130) — spec and plan already written this session (`docs/superpowers/specs/2026-10-10-unpushed-branch-verification-retry-design.md`, `docs/superpowers/plans/2026-10-10-unpushed-branch-verification-retry.md`). Dispatch this now via `synlynk dispatch` to a non-Claude implementer per Default Agent Role — it's small, self-contained, and currently causing false-negative job statuses that will corrupt every dispatch-wave metric pillar 3 needs. **Sequencing note: this fix should land before the Week 2 dispatch waves below, or those waves' own success/failure telemetry will be unreliable.**

### Week 2 — Multi-CLI parity + capability measurement wiring (pillars 1 & 3)
Maps to #1515 Phases 2-3 plus the Track 1/2 five-track items.

1. **Pillar 1:** Close the Full Fleet Harness Parity gap for Muse specifically — Muse has "not yet had the opportunity" per the Empirical Capability Assessment Policy. Run a calibration dispatch batch (≥5 samples per task type) through Muse on implement/test lanes first (lowest blast radius), per the policy's own minimum-sample-size rule. Do **not** calibrate Muse on deploy yet — deploy needs the Infra agent role re-validation called out separately below.
2. **Pillar 3 (build):** Ship #1993 (`synlynk capability report`) now that #1926 has unblocked aggregate querying. This is the literal mechanism that turns the Empirical Capability Assessment Policy from aspiration into a runnable command — it is this roadmap's single highest-priority `[NEW-ish]` build item (spec/design exists per #1927's held panel, implementation does not).
3. **Pillar 3 (cost accounting):** Re-open #1937 (cost-inflation finding) as a fresh investigation, not a re-close — the five-track plan confirms #1969/PR #2021 did not move Codex job costs. This directly feeds the "$-value accounting" half of pillar 3; a capability matrix without reliable cost-per-job numbers is half a product.
4. **Three-lens P1 items** (reliability/performance grade B-) close in this window — they're the items most likely to resurface as regressions once dispatch volume increases in Weeks 3-4.

### Week 3 — Local model measurement + domain-pack onboarding (pillars 4 & 6)
Maps to #1515 Phase 4-5 plus `goal-8d34c416`/`goal-06758149`.

1. **Pillar 4, "pick one":** Recommend **Hermes-3-Llama-3.1-8B** as the answer. It's already shipped (`synlynk/models.py`, `locality="on_device_local"`, `entitlement_tier=ZERO_COST_LOCAL`), already closed out of #1984 (top-3 recommendation from the five-POV review), and tool-calling-capable at a size that runs on-device. The remaining work is not model selection — it's **measurement**: wire it into #1993's capability report so "20% contributor" becomes a number the report can show, not a claim. Concretely: route a fixed slice of implement/test dispatch traffic to the `hermes` tier for the duration of this roadmap and read its `pr_review_cycles`/cost numbers back out of the same `capability_ratings`/`cost_entries` tables pillar 3 just made queryable.
2. **Pillar 4 soak test:** #2102 (SQLite soak test) and #2104 (eval/benchmark wiring) — both already-filed issues, not new scope — are the concrete deliverables that make "20% contributor" demonstrable at the release demo.
3. **Pillar 6:** First domain pack (context/skills/tools/data bundle) onboarded as a workspace agent fleet — scope this to **one** concrete domain pack for the preview (don't try to generalize the packaging format in 1 week), proving the *pathway* exists rather than shipping full general competency. This matches #1515's own scope-discipline clause: demonstrate the mechanism, park the breadth.

### Week 4 — Swarm deployment proof + release candidate (pillar 7 + release)
Maps to #1515 Phases 6-7.

1. **Pillar 7:** One end-to-end field trial dispatching a **swarm** (plural, concurrent) of workspace agent roles at a single complex task, using the Week 1 fix and Week 2 capability report to pick harnesses by measured fit rather than the suspended hand-authored table. This is the pillar most dependent on everything upstream — it cannot run credibly before Weeks 1-3 land.
2. **Infra agent role / deploy re-validation:** per the Default Agent Role reassessment, deploy capability (currently Claude-only by historical Pulumi precedent) must be re-tested through the Infra agent role before the release candidate ships with any deploy-routing claim in its pitch. If this can't clear ≥5 samples by Week 4, the release pitch should say "deploy routing remains Claude-default, pending validation" rather than imply it's been reassessed.
3. **Release mechanics:** CHANGELOG, VERSION bump, `gh release create`, roadmap row to ✅ Shipped, blog post in `docs/blog/`, one-sentence pitch, README `--check-docs` pass — per the Named Release Policy. The one-sentence pitch is the actual test of whether pillars 1-7 cohered: if it can't be said in one sentence, the scope wasn't coherent.

## 3. Cross-Lens Opportunities and P2 items — explicit disposition

Per "address ALL recommendations," every Cross-Lens Opportunity and P2 item gets an explicit line, not a silent drop:

- **Opportunities with no exact tracking issue found** (distribution surface: VS Code extension + GitHub App; hosted-relay managed service) — **flagged as genuine filing gaps**, not folded into this roadmap's 4-week scope. File two new issues this week (`chore`-labeled, linked to `goal-c7113f58` "Over-the-Horizon Strategic Expansion," the correct post-v1.0 home) so they're tracked without inflating the preview's scope. Do not build either inside this 4-week window — they're distribution/monetization plays, not preview-blocking.
- **P2 items not explicitly scheduled above** — land wherever slack appears in Weeks 2-3; none is a release blocker, all stay visible on the roadmap row so they don't silently vanish.
- **Already-parked items in #1515's scope-discipline clause** (enterprise sync, speculative rebase, semantic code graphs, kernel sandboxing, SCIP/tree-sitter work under `goal-2a05ef8a`/`goal-bf5af39f`/`goal-d8cb407d`) — **stay parked**. None of the user's 7 pillars constitutes the "concrete dependency" #1515's clause requires to unpark them; pillar 6/7's domain-pack and swarm work use existing dispatch/worktree primitives, not semantic code graphs or enterprise sync.

## 4. What this roadmap deliberately does not do

- It does not re-litigate the Default Agent Role split's outcome — it only re-validates deploy via the Infra role, per the already-open 2026-10-04 reassessment. Claude's PM/review/deploy lane stays the *interim* default throughout, unchanged by this roadmap.
- It does not build a new capability-matrix format — #1993 already has a design; this roadmap sequences its implementation, it doesn't redesign it.
- It does not attempt "general competency" in 4 weeks — pillar 6 ships one domain pack as a proof of pathway, explicitly not full generality, matching the user's own "pathway to" framing rather than "ship general competency."

## 5. Next step

Re-run the arch council: `synlynk decide` with this roadmap's 7 pillars and phase structure as the topic, panel across the harnesses with live PM/review standing (Claude, Agy, Codex at minimum; Grok/Muse if session auth allows), `--record` so the decision lands in `project-docs/decisions/` and is linked back to `goal-9ef9a965`/`goal-85656c82`.
