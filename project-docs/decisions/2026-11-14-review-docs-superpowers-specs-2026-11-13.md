<!-- generated - source of truth is state.db -->
---
decision_id: dec-7855dfad
topic: "Review docs/superpowers/specs/2026-11-13-decide-panel-briefing-and-agenda.md in full (it points at four new specs plus the already-shipped drift gate). Work through its 9-item agenda: cross-spec consistency, per-spec feasibility/viability/SWOT/architecture, a code-proximity/dependency matrix, improvement opportunities, themed execution tracks with dependency-ordered prioritization, and an incremental Core/Personal/Team/Enterprise edition launch sequence under the new Constitution. Return a single prioritized roadmap as your final decision."
date: 2026-11-14
panel: [claude, agy, codex]
status: approved
---

## Topic
Review docs/superpowers/specs/2026-11-13-decide-panel-briefing-and-agenda.md in full (it points at four new specs plus the already-shipped drift gate). Work through its 9-item agenda: cross-spec consistency, per-spec feasibility/viability/SWOT/architecture, a code-proximity/dependency matrix, improvement opportunities, themed execution tracks with dependency-ordered prioritization, and an incremental Core/Personal/Team/Enterprise edition launch sequence under the new Constitution. Return a single prioritized roadmap as your final decision.

## Panel Inputs

### claude
[model=default; version=2.1.323 (Claude Code)]

**Panel position (Claude seat):**

**1. Sequencing error, not just bundling.** Shipping #1 (drift gate) and then writing #10 (Approach C, which retires it) in the same epic is a real inconsistency, not a false alarm — but it's not wasted work either. #1's detection layer (observe/enforce pattern, `pr_check.py` wiring) is the reusable substrate #8's citation-gate explicitly borrows from. Treat #1 as a necessary stepping stone whose *elimination logic* informs #10's design, not sunk cost to regret.

**2. Dependency reality:** #9 (Editions) is the only spec with zero hard dependencies — pure additive registry code, buildable today, in parallel with everything else. #8 (Constitution) depends only on #1's pattern (already shipped) — second in line. #10 (Approach C) is architecturally the riskiest (FK-to-view backfill) and functionally *replaces* #1, so it must follow a dual-write/bake period, not run concurrent with #8's reuse of #1. #7 (IBPD Phase 3) is the most downstream — it presumes the governance substrate from #8 and #10 is stable.

**3. Immediate blocker:** the branch is 3 commits behind main missing exactly the gate #10 assumes exists. Rebase before any implementation dispatch — this is a hard gate, not parallelizable housekeeping.

**4. GOVERNS-linkage gap is also a hard gate**, per standing policy (`feedback_pm_session_governs_linkage_gap`) — create goals/parent issue now, not at dispatch time, for #7/#8/#9/#10.

**Recommended track order:** Track A (housekeeping: rebase + GOVERNS linkage, blocks everything) → Track B (#9 Editions registry, parallel, no dependency) → Track C (#8 Constitution, reuses #1) → Track D (#10 Approach C, retires #1, requires dual-write bake) → Track E (#7 IBPD Phase 3, depends on C+D stable).

**Edition sequencing:** Core ships once Track A/B land (Editions registry needs no governance maturity). Personal gates on #8's Delivery Tier reaching "Cited" for core laws. Team/Enterprise gate on #10 being fully cut over (single source of truth is a trust requirement for multi-seat), plus Platform Vision Phase 1 for Editions' Hosted bolt-ons regardless of this epic's internal pace.

**Final decision:** Prioritize A → B → C → D → E, with Core/Personal launchable after B/C, Team/Enterprise blocked until D completes and Platform Vision Phase 1 lands independently.

### agy
[model=default; version=1.5.8]

**Last completed task:** Review + merge PR #2596: synlynk.com platform vision spec (`story-ca8afaf8`)  
**Next task from `todo.md`:** Inject session-start bearings card: tpm sweep/wake, --as-agent, PR-review-as-dispatch (`gh:#5233`)

---

### Decide Panel Analysis & Recommendation: Roadmap Drift Governance Epic

Sequencing detection ([Spec #1](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+intent-based-engineering-drift-governance-spec/docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md)) prior to elimination ([Spec #10](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+intent-based-engineering-drift-governance-spec/docs/superpowers/specs/2026-11-13-fully-derived-roadmap-approach-c-design.md)) was the correct engineering choice: #1 established immediate runtime sentinel defense and validation fixtures while isolating the schema blast radius of #10 (migrating `roadmap_arcs`/`roadmap_phases` to SQL `VIEW`s and managing the `cost_entries` foreign key backfill).

Across the agenda items, technical feasibility and architectural integrity are sound:
1. **Constitution ([#8](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+intent-based-engineering-drift-governance-spec/docs/superpowers/specs/2026-11-13-synlynk-constitution-charter-governance-design.md)) & Editions Registry ([#9](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+intent-based-engineering-drift-governance-spec/docs/superpowers/specs/2026-11-13-synlynk-editions-boundary-and-opt-in-gating-design.md))** exhibit the highest code proximity (~85%). Promoting live code checks from `evaluate_asimov_invariants()` in [synlynk/tpm_sweep.py](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+intent-based-engineering-drift-governance-spec/synlynk/tpm_sweep.py#L58-L90) and adding `synlynk/editions.py` are purely additive with near-zero migration risk.
2. **Approach C ([#10](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+intent-based-engineering-drift-governance-spec/docs/superpowers/specs/2026-11-13-fully-derived-roadmap-approach-c-design.md))** structurally extinguishes the drift problem by dynamically deriving the roadmap from ratified `decisions` and `goals`, cleanly deprecating #1's write gate.
3. **IBPD Phase 3 ([#7](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+intent-based-engineering-drift-governance-spec/docs/superpowers/specs/2026-11-13-intent-based-product-development-design.md))** unlocks product orchestration value, but strictly depends on #10's derived single source of truth and #8's normative backing.
4. **Housekeeping Gaps**: Rebase against `origin/main` (resolving the 3-commit lag) and wiring GOVERNS parent tracking issues are mandatory pre-dispatch gates, though non-blocking for panel ratification.

We structure execution into three dependency-ordered tracks aligned with the incremental edition rollout:
- **Track 1: Constitutional Norms & Edition Registry (v0.30.1)**: Implement #8 and #9. Codify Laws 0–3 across Prose → Cited → Injected delivery tiers; ship `synlynk/editions.py`. Powers **Core** (unmetered local CLI) and **Personal** (opt-in local relay).
- **Track 2: Structural Drift Elimination (v0.31.0)**: Rebase `origin/main` and land #10. Convert roadmap storage into dynamic SQL `VIEW`s, backfill FK references, and decommission #1's manual sync gate.
- **Track 3: Commercial Entitlements & IBPD (v0.32.0)**: Implement #7. Package **Team** (seat licensing and workspace bundling) and **Enterprise** (SSO, data residency, and audit policies), keeping Hosted relay bolt-ons appropriately blocked on Platform Vision Phase 1.

**Final Position**:
I vote **APPROVE with Phased Sequencing**. Execute Track 1 immediately as zero-risk additive governance, mandate a clean branch rebase and GOVERNS parent tracking issue creation prior to Track 2, and require Track 2 completion before dispatching Track 3.

### codex
[model=default; version=codex-cli 0.167.0]

The panel should sequence this as a governance-to-product program, not four parallel builds. Detection before elimination was correct: the shipped drift gate is reusable scaffolding, test evidence, and migration telemetry; Approach C should retire it only after a verified cutover, so its work is not sunk cost.

Feasibility and architecture are uneven:

- **IBPD Phase 3:** viable strategically, but not an immediate build target. It depends on Phase 2 multi-tenant execution, Platform Vision Phases 1–2, pilots, pricing, and liability decisions. Strength: compelling outcome-based thesis; threat: premature commercialization.
- **Constitution:** highly feasible and valuable now. It formalizes already-live Asimov checks and reuses Harness²’s non-self-interested RSI. Main risks are ambiguous law boundaries, undefined thresholds, and unresolved six-archetype/eight-role mapping. Validate #5233’s RCA before coding.
- **Editions:** most feasible, additive, and independently shippable. The registry, config defaults, doctor check, CLI, and 212-module inventory have low blast radius. Its weakness is advisory licensing: Team/Enterprise are bundles, not enforceable capability walls.
- **Approach C:** architecturally strongest long term, but highest migration risk. Views and goal-owned identity are sound; the `cost_entries` FK retarget/backfill, legacy parity diff, unstable view IDs, and removal of four write paths require a staged, reversible migration.

Dependency matrix: shipped gate = 100% mature baseline; Constitution ≈60% code-proximate and depends only on existing gate patterns; Editions ≈35%, independent; Approach C ≈80%, hard-dependent on the gate’s behavior and requiring a retirement bridge; IBPD ≈15%, downstream of Platform Vision.

Recommended tracks: (1) housekeeping and Constitution validation/citation gate; (2) independent Editions registry and inventory; (3) Approach C dual-write, parity verification, cost-entry backfill, then cutover; (4) Phase-3 pilots and commercial/legal design only after Phase 2 foundations.

Launch incrementally: Core first with unchanged local governance; Personal adds Wingman, Intent Capture, and optional Agent Studio; Team adds bundled defaults/multi-seat semantics after Editions; Enterprise follows Accounts/Entitlements and Platform Vision Phase 1. SSO, RBAC, audit retention/export, and residency remain Phase-1-blocked. Constitution Delivery Tier is orthogonal to editions: require cited governance broadly; inject only where Sentinel/RCA evidence justifies it.

My position: approve the roadmap in that order, create the missing GOVERNS parent linkage before dispatch, rebase before implementation, and track the five side tickets as parallel housekeeping—not hard blockers except where pilots or migration validation expose them.

## Synthesis
**Decision:** Execute in five dependency-ordered tracks, with mandatory housekeeping gating everything else.

**Track 0 (hard blocker, before any dispatch):** Rebase this branch onto `origin/main` (3 commits behind, missing the shipped drift gate #1's own merged state), and create the GOVERNS parent tracking issue + linked goal/story for #7/#8/#9/#10 now — not at dispatch time, per the standing `feedback_pm_session_governs_linkage_gap` policy. All three panelists and policy converge here; this is not parallelizable.

**Track 1 — Editions Registry (#9):** Ship first and independently. Zero hard dependencies, additive-only (`synlynk/editions.py`, config defaults, doctor check, CLI), lowest blast radius of the four specs. Unlocks **Core** (unmetered local CLI, no governance maturity required) and most of **Personal** immediately.

**Track 2 — Constitution (#8):** Second, reusing #1's already-shipped observe/enforce detection pattern and `evaluate_asimov_invariants()` wiring (~60-85% code-proximate per agy/codex). Before coding, validate against #5233's RCA and resolve the undefined law-boundary/threshold and archetype/role-mapping ambiguities codex flagged. Delivery Tier reaching "Cited" for core laws gates the rest of **Personal**.

**Track 3 — Approach C (#10):** Third, and explicitly *not* concurrent with Track 2's reuse of #1 — it retires #1's write gate, so it needs a staged dual-write/parity-verification bake period (view conversion, `cost_entries` FK backfill, legacy-parity diff) before cutover, not a parallel build. Full single-source-of-truth cutover is a hard trust prerequisite for **Team/Enterprise** multi-seat semantics.

**Track 4 — IBPD Phase 3 (#7):** Last. Least code-proximate (~15%), strategically sound but genuinely downstream — depends on Track 3's derived roadmap being stable, Track 2's normative backing, and externally on Platform Vision Phase 1 pilots/pricing/liability work that is itself gating Enterprise regardless of this epic's pace.

**Edition launch sequence:** Core → ships after Track 0+1. Personal → after Track 1 + Track 2 reaches "Cited." Team/Enterprise → blocked until Track 3 fully cuts over *and* Platform Vision Phase 1 lands independently (SSO/RBAC/residency/audit are Phase-1-blocked regardless). Side tickets (#5233 RCA, cost-inflation, sandbox findings) ride as parallel housekeeping, not hard gates, except where they directly block a track's verification step.

## Decision
**Edition launch sequence:** Core → ships after Track 0+1. Personal → after Track 1 + Track 2 reaches "Cited." Team/Enterprise → blocked until Track 3 fully cuts over *and* Platform Vision Phase 1 lands independently (SSO/RBAC/residency/audit are Phase-1-blocked regardless). Side tickets (#5233 RCA, cost-inflation, sandbox findings) ride as parallel housekeeping, not hard gates, except where they directly block a track's verification step.

**Addendum (panel composition caveat, noted 2026-11-14):** This decision was reached with a 3-member panel (claude, agy, codex). Grok was excluded after a hard failure — an API 402 'Payment Required: Grok Build usage balance exhausted' error — not a transient timeout, so it was dropped rather than retried. This is one harness short of the originally configured 4-member panel. All three remaining members still differ from each other in both harness and model, satisfying the Hardened PR Review Policy's cross-harness+model bar for this decision, but the panel was not run at full configured quorum. Flagged here for visibility; no retry was attempted since the failure is a billing-exhaustion condition, not expected to clear on its own.

> Signatures: see 2026-11-14-review-docs-superpowers-specs-2026-11-13.json
