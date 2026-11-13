# Decide Panel Briefing & Agenda — Roadmap Drift Governance Epic (2026-11-13)

**Date:** 2026-11-13
**Prepared by:** Claude (PM/Architect, Home Conductor)
**Purpose:** Brief the multi-harness decide panel on everything produced this session, give it a structured agenda, and ask it to return a prioritized, dependency-aware execution roadmap — including edition launch sequencing — before any of this moves to implementation.
**Status:** Pre-panel briefing — not yet convened. `synlynk decide --panel ... --record` has not been run against this document.

---

## Part 1 — Briefing Note

### 1.1 What happened this session

Under a governing instruction to finish all pending brainstorms before dispatching them to a decide panel, three design specs were written and committed on `chore/intent-based-engineering-drift-governance-spec`, on top of a fourth spec/plan/implementation (the roadmap drift-detection gate) that had already shipped earlier in the same epic. All four are products of the same root problem — `decisions`, `goals`, and the rendered roadmap can silently diverge — approached at four different layers: detection (shipped), the business-model layer built on top of the resulting governance substrate (IBPD), the law the whole substrate answers to (the Constitution), the commercial-tier gating built on that law (Editions), and the structural elimination of the drift class itself (Approach C). None of the three newest specs has started implementation; none has a GOVERNS goal/parent-issue yet.

### 1.2 Artifacts for the panel to review

| # | Artifact | Location | Status |
|---|---|---|---|
| 1 | **Intent-Based Engineering & Roadmap Drift Governance** (origin spec for this whole epic) | `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md` | Shipped — Section 2 (drift gate) implemented and merged |
| 2 | Implementation plan for the drift gate | `docs/superpowers/plans/2026-11-13-roadmap-drift-governance.md` | Tasks 1–5 (gate) + 6 (data remediation) + 7 (docs) complete |
| 3 | Parent tracking issue | [`#5230`](https://github.com/nikhilsoman/synlynk/issues/5230) — "Roadmap Drift Gate: detect and gate decision-goal-roadmap-arc drift" | OPEN (tracks the shipped gate only, see 1.4) |
| 4 | Implementation PR — CLAUDE.md gate docs | [`PR #5240`](https://github.com/nikhilsoman/synlynk/pull/5240) | MERGED 2026-11-13 |
| 5 | Implementation PR — remediation outcomes | [`PR #5241`](https://github.com/nikhilsoman/synlynk/pull/5241) | MERGED 2026-11-13 |
| 6 | GOVERNS linkage for the shipped gate | goal-4c20a25c ← story-c77dae14 | Done |
| 7 | **Intent-Based Product Development & Master Roadmap Phase 3** | `docs/superpowers/specs/2026-11-13-intent-based-product-development-design.md` | Spec only, no code, no GOVERNS link yet |
| 8 | **Synlynk Constitution & Charter Governance** | `docs/superpowers/specs/2026-11-13-synlynk-constitution-charter-governance-design.md` | Spec only, no code, no GOVERNS link yet |
| 9 | **Synlynk Editions: Core/Opt-in/Hosted Boundary & Gating** | `docs/superpowers/specs/2026-11-13-synlynk-editions-boundary-and-opt-in-gating-design.md` | Spec only, no code, no GOVERNS link yet |
| 10 | **Fully-Derived Roadmap (Approach C)** | `docs/superpowers/specs/2026-11-13-fully-derived-roadmap-approach-c-design.md` | Spec only, no code, no GOVERNS link yet — explicitly retires artifact #1's shipped gate |
| 11 | Open, untouched side tickets from this epic's earlier triage | [`#5233`](https://github.com/nikhilsoman/synlynk/issues/5233) (cross-harness instruction-adherence RCA), [`#5234`](https://github.com/nikhilsoman/synlynk/issues/5234) (dispatch-to-existing-PR gap), [`#5236`](https://github.com/nikhilsoman/synlynk/issues/5236) (merge-block warning doesn't block), [`#5237`](https://github.com/nikhilsoman/synlynk/issues/5237) (untracked nested sub-dispatch), [`#5242`](https://github.com/nikhilsoman/synlynk/issues/5242) (gh-shim/push-auth gap) | All OPEN, none actioned this session |
| 12 | Prior ratified decisions this epic builds on | `dec-7a2b0e91` (authoritative master roadmap, Phase 1/2 paradigms), `dec-4a53a2ee` (autonomous fleet orchestrator / RSI machinery), `dec-9b41a7c3` / `dec-4e81b29a` (roadmap prioritization) — all in `project-docs/decisions/` | Ratified, referenced not re-derived |
| 13 | Current rendered roadmap | `project-docs/roadmap.md` (generated from `state.db`, do not hand-edit) | Tail state: v0.30.0 Fleet Expansion & Agent Studio shipped 2026-11-10 |

### 1.3 Repo state snapshot (as of 2026-11-13, this worktree)

- **Branch `chore/intent-based-engineering-drift-governance-spec` is 9 commits ahead, 3 commits behind `origin/main`.** The 3 commits it's missing from main are exactly the ones that shipped artifact #1's drift gate (`roadmap_drift.py`, the `pr_check.py` wiring, the `doctor.py` health check, and their tests) — this branch was cut before PRs #5240/#5241 merged. **This needs a rebase/`git pull` before any implementation work starts**, since artifact #10 (Approach C) is written as if that gate already exists in this tree, and it doesn't yet.
- `synlynk status`: 41 local worktrees (3 flagged stale), 27 active sentinels, fleet 6/7 attached, cost rates "never updated (hardcoded defaults)".
- Confirmed in code, not assumed: `evaluate_asimov_invariants()` (the Constitution spec's load-bearing prerequisite) is real and live at `synlynk/tpm_sweep.py:58`. `capability_scores` (the Approach C spec's VIEW precedent) is real and live at `synlynk/db_schema.py:643`. `synlynk/editions.py` does not exist yet — the Editions spec's registry is 100% unbuilt.

### 1.4 Open gaps the panel should be aware of (not yet actioned)

- **GOVERNS-linkage gap:** three of the four new specs (IBPD Phase 3, Constitution, Editions, and Approach C minus the one that already has a goal) have no GOVERNS goal or parent tracking issue yet — a direct instance of the standing `feedback_pm_session_governs_linkage_gap` pattern (create the linkage at spec-save time, not dispatch time). Issue #5230 tracks only the already-shipped gate, not this session's three follow-on specs. The panel's output should either be recorded against a new parent issue, or this gap should be closed before dispatch begins.
- **Branch currency** (1.3) — housekeeping, blocks nothing about this briefing, but blocks implementation.
- **Five side tickets (#5233/5234/5236/5237/5242)** remain open and unaddressed from an earlier triage pass this epic; not in scope for this panel unless it judges one of them a hard dependency for something in the proposed roadmap.

---

## Part 2 — Panel Agenda

**Convene with:** the four specs (artifacts #7–10 above) plus the already-shipped gate (artifact #1) as the full input set. Each panel member has repo file access when run headless — point at file paths rather than requiring content to be pasted inline.

1. **Calibration.** Read artifacts #1, #7, #8, #9, #10 in full, plus `project-docs/roadmap.md`'s tail (v0.26.10 onward) and `dec-7a2b0e91`. Do not re-litigate anything already ratified in those decisions — treat them as fixed ground.

2. **Cross-spec consistency check.** Artifact #10 explicitly retires artifact #1's just-merged drift gate ("there is no second copy left to drift against"). Was bundling detection-then-elimination into the same epic, sequenced as two separate specs, the right call — or should elimination (#10) have been proposed *before* detection (#1) was built, to avoid building something meant to be torn out in the same breath? Answer this before scoring anything else; it affects how much of #1's shipped work is sunk cost vs. reusable.

3. **Per-spec opinion — feasibility, viability, SWOT, architectural quality.** For each of #7, #8, #9, #10 individually (not a blended average):
   - Feasibility: can this be built with today's codebase and team composition, and in what order internally?
   - Viability: does the business/technical case still hold given what's shipped since the spec was written?
   - SWOT: strengths/weaknesses/opportunities/threats specific to *this* spec, not generic.
   - Architectural quality: schema soundness, migration risk, blast radius, test coverage plan — #10 in particular names its own biggest risk (the `cost_entries` FK-to-view problem and its backfill); the panel should independently assess whether that resolution is sound or whether it's missing something.

4. **Code proximity & dependency matrix.** Produce a table in the style of `dec-4e81b29a`'s Thematic Alignment & Code Proximity Matrix (Theme / Focus / Code Proximity % / Governing Specs / Active Story IDs) for artifacts #7–10, with artifact #1 included as the "already 100% mature" baseline row. Be explicit about hard blocking dependencies — e.g., #10 cannot land before #1's gate is retired without a dual-write period that violates #10's own two-step rollout; #9 (Editions) is purely additive registry code with zero dependency on #7/#8/#10 and could land independently at any point; #8 (Constitution)'s citation-gate reuses #1's observe/enforce pattern but has no other code dependency on #1, #9, or #10.

5. **Improvement opportunities / enhancements not yet in any spec.** Anything the panel sees across these four specs — individually or at their intersections — that should be added before implementation planning starts.

6. **Themed execution tracks + prioritization.** Propose named tracks (not necessarily one per spec — some specs may split across tracks, some tracks may bundle parts of multiple specs) with an explicit build order, justified against the dependency matrix from item 4 — not just effort/value.

7. **Edition rollout sequencing under the new Constitution.** Propose the incremental launch order for Core → Personal → Team → Enterprise, stating for each edition: which of #7–#10's capabilities must exist first, and which of #9's own Hosted bolt-ons (named concretely in that spec's Section 3 table) remain correctly blocked on Platform Vision Phase 1 regardless of this epic's internal sequencing. Tie this explicitly to the Constitution's (#8) RSI-gated Delivery Tier model — e.g., should an edition's launch gate on a law reaching a specific Delivery Tier (Prose/Cited/Injected), or is that orthogonal?

8. **Flag unresolved gaps.** Explicitly comment on the GOVERNS-linkage gap and branch-currency item from Part 1.4 — are either a hard blocker on the proposed roadmap, or can the roadmap proceed with them tracked as parallel housekeeping?

9. **Final synthesis.** One recorded decision: the prioritized, dependency-ordered roadmap with named tracks and the edition launch sequence, in a form suitable for `--record` and for `_generate_roadmap_md()` to eventually render.

---

## Suggested invocation (not yet run)

```bash
synlynk decide --panel claude,agy,codex,grok --record \
  "Review docs/superpowers/specs/2026-11-13-decide-panel-briefing-and-agenda.md in full (it points at four new specs plus the already-shipped drift gate). Work through its 9-item agenda: cross-spec consistency, per-spec feasibility/viability/SWOT/architecture, a code-proximity/dependency matrix, improvement opportunities, themed execution tracks with dependency-ordered prioritization, and an incremental Core/Personal/Team/Enterprise edition launch sequence under the new Constitution. Return a single prioritized roadmap as your final decision."
```
