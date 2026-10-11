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

## 5. Arch council verdict (2026-10-10) and the two gates it added

`synlynk decide` panel (claude, agy, codex, grok) — decision recorded at `project-docs/decisions/2026-10-10-revised-dev-preview-roadmap-docs-strateg*`. All four panelists converged: the dependency topology (foundation → measurement → claims → swarm/release) is correct and approved as drafted. The approval is conditional on the date, not the sequence — the panel's own words: **"ship the narrower, honestly-labeled preview over a seven-pillar claim the evidence can't yet support by 10/31."** Two specific risks drove this:

- `#1926` (state.db consolidation) is a **single point of failure with zero float** in the 21-day window — every downstream pillar-3/4 measurement claim depends on it.
- The Empirical Capability Assessment Policy's own **≥5-merged-job sample bar** means "measured 20% Hermes contributor," Muse calibration, and exiting GOVERNS `observe` mode all require wall-clock time that proof-by-merged-sample consumes regardless of how well-ordered the plan is.

**Two gates added to this roadmap as a result (not a re-sequence — same phases, same order, now with explicit checkpoints):**

1. **End of Week 1 — hard checkpoint.** If `#1926` is not queryable *and* `#2136` is not merged by the end of Week 1, invoke the re-park trigger immediately (push the affected Week 2-4 items out of the dev-preview scope and say so in the roadmap row) rather than letting the slip cascade silently through Weeks 2-4.
2. **End of Week 2 — go/no-go on pillars 3 and 4 specifically.** If merged-job sample counts aren't trending toward the ≥5 bar by then, descope the local-model and capability-matrix pillars in the release claims from "measured" to "integrated, unmeasured" — and explicitly decide, and state in the release notes, whether GOVERNS ships in `observe` mode rather than let that become an undisclosed scope cut.

## 6. R1 next step (superseded by R2 below — kept for history)

Both gates are now load-bearing parts of this roadmap, not optional follow-up. Week 1 execution starts with the stale-goal reconciliation and the `#1926`/`#2136` work in Section 2 above, with the Week 1 checkpoint gate tracked against it from day one.

## 7. R2 reprioritization (2026-10-10, same day — Nikhil's revised view)

Nikhil's own words, verbatim framing: *"Local is definitely a nice-to-have capability — particularly since it offsets cost of other models — but not essential to functional proof and end-user benefit. Swarms and effective utilization of public model quotas is more important. Likewise being able to operate through various interfaces is essential."* This changes **priority weighting**, not the dependency topology the panel already approved in Section 5 — Weeks 1-2's foundation work (stale goals, #1926, #2136, three-lens P0s) is unaffected and stays first. The changes are to Weeks 2-4's content and to what counts as release-critical.

**Pillar 4 (local model) — demoted to non-blocking.** Hermes-3-Llama-3.1-8B remains the right "pick one" answer (still shipped, still zero-cost) and still gets wired into the capability report opportunistically, but it is removed from the Week 2 go/no-go gate (Section 5, gate 2) and from the release pitch's critical path. It is cost-offset infrastructure, not a functional-proof or end-user-benefit claim — if it isn't measured by release, that's fine, it ships unmeasured and undiscussed in the pitch, not as a disclosed scope cut.

**Pillar 7 (swarms) + public-model-quota utilization — elevated, now a release-critical claim.** This absorbs part of `#2108` ("Exploratory brainstorm: Managed execution nodes and swarms operated by Synlynk," currently PARKED per the held #1927 panel) — specifically the *swarm execution* dimension, not the *hosted managed service* dimension (that stays separate, see hosted-relay note below). "Effective utilization of public model quotas" has **no existing issue or goal** — this is a genuine gap, not a mischaracterized one; file a new issue this week under `goal-abecd18c` (swarm/containerized execution) covering quota-aware dispatch scheduling across public provider rate limits.

**Federated quota capture (`story-d84372cd`/`goal-005ea87d`) folded in as the mechanism satisfying the above — merged 2026-10-10.** Design spec + plan (docs-only PR #2165) and implementation + targeted tests (PR #2166) were built independently this session before this roadmap fold-in was decided. This is the literal "quota-aware dispatch scheduling" mechanism Section 7 calls for above — **no separate new issue needs filing for it**, superseding that line's instruction. `story-d84372cd` gets a secondary GOVERNS link to `goal-abecd18c` (pillar 7) alongside its existing primary link to `goal-005ea87d` (pillar 1, Full Fleet Harness Parity), since the same `quota_snapshots` data feeds both multi-harness parity and swarm/quota-aware dispatch routing. It is also a Week 2 input for pillar 3's capability-matrix allocation — a capability report that ranks harnesses on cost/quality without quota headroom can route work to a harness that is already exhausted. **Status:** both #2165 and #2166 confirmed `MERGED` via `gh pr view` (squash commits `cca3822c` and `9e66e519` respectively) — this fold-in now ties pillars 3 and 7 to shipped infrastructure, not code in review.

**Pillar 1 — broadened from "multi-CLI harness" to "multi-interface," and now release-critical, not partial-credit.** Original pillar 1 text ("usable from Claude/Codex/Grok/Agy/Muse CLIs") undersold what Nikhil actually wants: CLI-only is explicitly called out as the current limitation to escape. Existing tracking, now elevated from "future consideration"/P2 to active Week 2-3 work:
- `#2126` (BS-15, "Harness independence — home/away paradigm, OpenRouter direct API, 3rd-party IDE plugins [Cursor/Warp/Pi]") — explicitly logged as "a future consideration, not urgent" when filed 2026-10-08. **That framing is now superseded** — this is the IDE/agentic-framework/OAuth expansion pillar.
- `#2103` ("[P2] Build a thin VS Code client for dispatch, jobs, and logs," Cross-Lens Opportunity #2) — **correction to Section 3 below**: this was wrongly described in R1 as having "no exact tracking issue found." It exists, it's P2, and under R2 it should move to P1/Week 2-3, not stay P2.
- `#1708` ([Epic] Wave 4: Synlynk Model Hub & Provider Aggregator), `#1711` ([W4-T1.3] Universal Provider Aggregators — OpenRouter, LiteLLM, Fal.ai — & Tool Gateways), `#2076` (GenericAPIAdapter for OpenRouter/LiteLLM-proxy/OpenAI-compatible endpoints) — this is the **BYOK/model-provider** half of pillar 1 (OAuth public provider accounts + bring-your-own-key via OpenRouter/LiteLLM). All three already open; none yet scheduled in R1's Week 2-3. Pull into Week 2-3 alongside `#2126`/`#2103`.
- **Genuinely new scope, no issue found:** Cursor and JetBrains as named targets (only VS Code has a filed issue; Cursor/Warp/Pi are mentioned only inside `#2126`'s body as open questions, not scoped work items). File these as explicit sub-items under `#2126` this week rather than assume VS Code coverage implies the others.

**Hosted relay for personal use — pulled forward into immediate (dev-preview) scope, reversing R1's disposition.** R1 (Section 3) parked this as a "distribution/monetization play, not preview-blocking" alongside the GitHub App distribution surface. Nikhil's instruction reverses that for the relay specifically: *"Immediately after this schedule is done and dev preview releases we will move towards Teams edition; a hosted relay for personal use should be in immediate scope."* Read precisely, this means: the relay does not have to ship *inside* the 4-week dev-preview window, but it must be designed and started now, inside this roadmap's scope, as the direct architectural predecessor to Teams edition — not deferred to "post-v1.0, unscheped" the way R1 treated it. No existing issue was found for personal-use hosted relay specifically (`#1402` is the closest — "Distributed state.db sync protocols... enterprise cost aggregation" — but it's enterprise-framed, not personal). File a new issue this week scoped explicitly to **personal-use** hosted relay (single-tenant, not the enterprise sync `#1402` already covers and not full Teams multi-tenancy), explicitly as Teams edition's forerunner.

**Forward note — Teams edition is the named next epic, immediately after dev preview.** No architecture decision made in Weeks 1-4 (especially the hosted-relay design above) should foreclose multi-tenancy. This doesn't mean building Teams features now — it means the personal-use relay's design should not hard-code single-tenant assumptions it would be expensive to unwind in the very next epic.

## 8. R2 arch council verdict (2026-10-10, same day)

`synlynk decide` panel (claude, agy, codex, grok) — decision recorded at `project-docs/decisions/2026-10-10-r2-reprioritization-of-the-dev-preview-r*`. Approved R2 as a **reweighting of release-critical claims, not a reordering of execution** — all four panelists converge:

- **(a) Week 1 sequencing is unmoved.** The foundation gates (#1926, #2136, three-lens P0s) stay first regardless of the pillar reweighting — swarms/quota work on an unconsolidated telemetry layer would produce false signals, so demoting pillar 4 frees no slot at the front of the queue. It only removes Hermes-local measurement from the Week 2 go/no-go gate (Section 5, gate 2).
- **(c) Sequencing within pillar 1/7's new scope:** provider/BYOK plumbing first (OpenRouter/LiteLLM via `#2076`, minimum-viable slice of `#1708`/`#1711`) — both multi-interface clients and swarm/quota logic consume that auth/provider surface, not the reverse. Then **one thin interface proof** (`#2103`, VS Code) before fanning out to Cursor/JetBrains/Warp/Pi under `#2126`. Build the swarm/quota trial on top only once the provider layer and at least one client exist to validate it against.
- **(b) Personal-use hosted relay — approved for design-now, with hard constraints:** strictly a spec/architecture track (trust boundaries, tenancy model, forward-compatible migration path to Teams), filed under its own goal **outside** the dev-preview GOVERNS tree, **zero implementation or dispatch slots against it before the Week 1 gate is green**, and no code from it ships inside the 10/31 window by construction.
- **Standing instruction from the panel:** if Week 1's gate slips, pillar 7 and multi-interface work re-park behind it — the schedule does not compress to protect the date.

## 9. Next step

File the personal-use-hosted-relay spec issue (own goal, outside the dev-preview GOVERNS tree, per the panel's constraint above) this week, then begin Week 1 execution per Section 2/5. The public-model-quota-aware swarm dispatch issue is **no longer needed** — superseded by folding the federated quota-capture work (`story-d84372cd`/`goal-005ea87d`, secondary-linked to `goal-abecd18c`) directly into Section 7; PRs #2165 and #2166 are both merged. Both R2-elevated pillars (1 and 7) wait behind the Week 1 gate exactly as the panel specified — no dispatch slots against provider/BYOK, interface, swarm, or relay work until `#1926` is queryable and `#2136` is merged.

## 10. Herdr bundling + UX-layer decision — parked, new pillar candidate [NEW]

Raised 2026-10-10 during the federated-quota-capture brainstorm: should Herdr become a bundled core install-time dependency (alongside Graphify and Superpowers), and should synlynk adopt Herdr more broadly as its standard UX/UI layer for synlynk-powered workflows generally? This is explicitly **not yet decided** — Nikhil's instruction is to route it through a `synlynk decide` arch-council round, the same mechanism used for the R1/R2 verdicts in Sections 5 and 8 above, and only then fold the verdict into this roadmap as a pillar.

**Tracking (created, not yet actioned):**
- `goal-cbeaa152` — "Decide whether Herdr becomes a bundled core dependency... and the standard UX/UI layer for synlynk-powered workflows." New goal, same pattern as the hosted-relay spec track in Section 8(b): **outside** the dev-preview GOVERNS tree, zero implementation or dispatch slots against it.
- `story-272f0252` — "Brainstorm + arch-council design session: Herdr as bundled dependency and standard UX/UI layer." Linked primary to `goal-cbeaa152`. Stage `open` — brainstorm/design session not yet run.

**Disposition, following the panel's own precedent for the hosted relay (Section 8(b)):** this is a spec/decision track only until a verdict exists. No code, no install-mechanism change, no `synlynk decide` dispatch before the Week 1 gate (Section 5) is green — same standing instruction the panel gave for pillar 7/relay work: if Week 1 slips, this re-parks behind it too. Once a verdict exists, it either becomes an explicit pillar 8 in Section 1's map (if adopted) or gets closed out with the panel's reasoning recorded (if declined) — not left ambiguous.

## 11. Week 3-end gate — paper-track go/no-go (Gemma 4 Developer Agent Competition) [NEW]

Raised 2026-10-10: Google DeepMind's "Gemma 4 Developer Agent Competition" (Kaggle, post-train a fixed `gemma-4-31b-it-qat-w4a16-ct` model via LoRA/RL into an autonomous SWE agent, evaluated in a no-internet single-model ADK sandbox) has an optional **Paper Submission Award** track (separate signup, deadline 2026-11-12, $35,000 prize pool, encouraged topics include PEFT/RL tuning for SWE agents and capability/cost measurement methodology) in addition to its main competitive-agent track (entry deadline 2026-11-25, final submission 2026-12-02).

**Assessed fit (2026-10-10):** the competitive-agent track is architecturally incompatible with synlynk's actual thesis — the eval sandbox is single-model, no-internet, and ADK-harness-only, while synlynk's value proposition is multi-harness orchestration across live providers. A competitive trained-agent submission would be an unscoped standalone ML post-training research project, not an extension of this roadmap's engineering, and is **explicitly not part of dev-preview scope**. The **paper track**, by contrast, fits directly: synlynk's own empirical capability/quota/swarm measurement data (capability_ratings, cost_entries, quota_snapshots once Section 7's federated quota capture merges) is exactly the kind of evidence the paper track's encouraged topics ask for, and Weeks 1-3 of this roadmap are already producing it as a byproduct of foundation + measurement work, not as new effort.

**Gate:** at the end of Week 3, decide go/no-go on **drafting and submitting a paper** by the 2026-11-12 deadline, based strictly on whether Weeks 1-3's actual results (capability report from pillar 3, quota-capture data from Section 7 once merged, swarm trial progress from pillar 7) give enough real measured evidence to write from. No-go is the default if the Week 1 or Week 2 gates (Section 5) have already slipped — a paper written from an unmeasured or descoped pillar is not viable. This gate decides the paper track only; it does **not** reopen, imply, or gate any competitive trained-agent submission, which stays out of scope regardless of this gate's outcome.

**Tracking:** `goal-11ee99c9` / `story-9442caf8` — created as a **standalone project outside this roadmap's GOVERNS tree** (see that goal for the full post-training/distillation framing), not as a dev-preview pillar. This Week-3 gate is the only point of contact between the two: a "go" here authorizes spending time on the paper specifically using this roadmap's own measured data as evidence, nothing more. It does not pull the standalone goal's broader post-training/distillation work into dev-preview scope.

## 12. Harness×mode (home/away) PM-duty allocation, draft [NEW]

Draft allocation across all 4 weeks, built directly from Section 2's task list and the current Default Agent Role / Empirical Capability Assessment policies. This table is **provisional, not binding** — exactly the kind of decision `synlynk capability report` (#1993) is meant to eventually generate from measured data rather than hand-authored heuristics, per the Empirical Capability Assessment Policy (CLAUDE.md). It records today's best-guess routing so Week 1-4 work has a starting allocation, not a locked grant.

**Week 1 — Foundation and reset**
| Task | Harness | Mode | Note |
|---|---|---|---|
| Stale-goal reconciliation | Claude | Home | PM judgment calls on which goals to re-date/close/supersede; log via `synlynk cost log` |
| #1926 state.db consolidation | Codex | Away | Continuation of existing work (job-1fddce5c branch) |
| Three-lens P0 security/correctness fixes | Codex / Grok | Away | Split by issue domain once each is filed |
| Job-status reconciliation Bug A (#2136/#2137/#2130) | Codex | Away | Already dispatched (job-cd62e187/PR #2160) — verify merged |

**Week 2 — Multi-CLI parity + capability measurement (pillars 1 & 3)**
| Task | Harness | Mode | Note |
|---|---|---|---|
| Muse calibration batch (≥5 samples, implement/test) | Muse | Away | First real opportunity for Muse per policy — no interactive Muse pane exists yet, away-only for now |
| #1993 capability report build | Codex | Away | Spec exists (#1927 held panel); Claude (home) reviews |
| #1937 cost-inflation re-investigation | Grok | Away | Backend/pipeline debugging; Agy deprioritized per its timeout-reliability history |
| Three-lens P1 reliability/perf items | Codex / Grok | Away | Split by issue |

**Week 3 — Local model measurement + domain pack (pillars 4 & 6)**
| Task | Harness | Mode | Note |
|---|---|---|---|
| Hermes-tier dispatch routing + measurement wiring | Codex | Away | CLI-plumbing fit |
| #2102 soak test / #2104 eval wiring | Grok | Away | Infra/data-structure fit |
| First domain pack onboarding | Agy | Away | Content/template/subpages — Agy's core lane |

**Week 4 — Swarm proof + release (pillar 7 + release)**
| Task | Harness | Mode | Note |
|---|---|---|---|
| Swarm field trial | **Dynamic — not hand-picked** | Away | The whole point of pillar 7 is to pick harnesses from #1993's measured output, not this table |
| Infra-role deploy re-validation | Agy / Codex / Grok / Muse rotation | Away | Directly tests whether Claude's deploy exclusivity still holds |
| Release mechanics (CHANGELOG/VERSION/`gh release`) | Claude | Home | PM/deploy lane, interim default |
| Release blog post content | Agy or Codex | Away | Per Blog Post Protocol — authored by implementation agent, not Claude by hand |

**Cross-cutting rules baked into every row:**
- Every "Away" row auto-populates `cost_entries`/`capability_ratings` via `dispatch_agent()` — no extra step.
- Every "Home" row needs a manual `synlynk cost log --pr <N> --harness claude` entry per the Cost Capture Protocol.
- Every review/merge step must go to a harness+model *different* from the implementer (Hardened PR Review Policy) — so e.g. if Codex implements, Agy or Grok reviews-and-merges, not Codex-approve-fallback.
- This table itself is provisional — exactly the kind of data `synlynk capability report` (#1993) is meant to eventually replace with generated, measured routing. Revisit once that lands or once any row accumulates ≥5 merged-job samples contradicting it.
