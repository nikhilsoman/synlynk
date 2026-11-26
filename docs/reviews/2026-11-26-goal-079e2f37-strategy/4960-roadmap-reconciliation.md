# #4960 — Roadmap reconciliation

## Question

Confirm or amend the proposed release sequence and explicitly disposition safety/authority, truth, attribution, cost, state, containment, surfaces, distribution, onboarding, journey evidence, and deferred scope.

## Verdict

**Derived from the recorded synthesis.** Preserve the truth-to-reliability-to-autonomy-to-distribution arc, with authority moved no later than daemon reliability, containment made an explicit pre-autonomy gate, and onboarding evidence moved before or alongside marketplace distribution. Keep swarms, gateway, capability-crawler, and later GTM consolidation post-preview until journey-level evidence clears the earlier gates.

## Findings

### Recorded panel synthesis (verbatim)

> All three panelists converge on the same structural judgment: truth (completion, cost, attribution, state) must be load-bearing before authority/autonomy is granted, and autonomy must be proven before distribution and swarms. The disagreements are about exactly where charter/authority enforcement sits (v0.26.1 vs. pulled forward into v0.25.3–v0.26.0) and whether onboarding gates or follows marketplace distribution. Codex's point is the sharpest architecturally: granting workspace-agent authority (v0.26.1) *after* a daemon-reliability release (v0.26.0) that has no enforceable authority underneath it repeats exactly the failure class this reconciliation exists to prevent — authority should not sit downstream of a release that runs autonomously without it. Claude and Agy both treat this as an amendment-worthy gap but don't go as far as resequencing; Codex does, and the underlying repo history (LIVE-17 nested-writer deadlock, #1377 completion-truth cascade) supports pulling enforceable authority earlier rather than later. On onboarding vs. distribution, Agy and Codex agree onboarding/first-win evidence must gate before or alongside public listing; Claude's "swap or co-gate" lands in the same place. Containment is flagged by Claude and Codex as a gate with no current home — that must be made explicit rather than folded silently into charter work. State consolidation (#1926/#1831) is named by Claude and implied by Codex's "durable outbox/projections" — it belongs explicitly inside v0.25.4, not assumed.
>
> Decision: Confirm the overall release arc (v0.25.x truth → v0.26.x reliability/authority/autonomy → v0.27.x surfaces/distribution/onboarding → v0.28.x+ swarms/gateway/GTM, deferred post-preview) with four amendments: (1) fold state.db/document-truth consolidation (#1926, #1831) explicitly into v0.25.4's scope rather than leaving it implicit; (2) pull enforceable workspace-agent authority/credential checks forward so they land no later than v0.26.0, ahead of or concurrent with daemon-reliability work, rather than deferred to v0.26.1 — no autonomous daemon release ships without enforceable authority already underneath it; (3) add an explicit containment exit gate (egress/credential disclosure, not just worktree isolation) before v0.26.2's supervised autonomy; (4) make onboarding/first-win journey evidence a co-gate with, or predecessor to, v0.27.1 marketplace distribution rather than a strict successor. v0.28.0 (safe swarms/universal gateway) remains gated on clean v0.26.2 supervised-autonomy telemetry, and v0.28.1/v0.29.0 stay post-preview as scope-deferred. No Dev Preview date is committed; it is set only after the v0.25.x truth gates and v0.26.x authority/reliability gates pass with journey-level (not unit-test) evidence.

- `docs/reviews/2026-10-16-deep-review-against-goals.md`, cited by the issue, is absent on this branch; its contents are **not verified** here.

## Recommended follow-ups

- **New ticket: No. Proposed title:** “Make state/document truth explicit in the v0.25.4 exit gate.” Amend the existing release epic.
- **New ticket: No. Proposed title:** “Land enforceable workspace-agent authority no later than v0.26.0.” Amend the existing authority/reliability epics.
- **New ticket: Yes. Proposed title:** “Define the egress and credential-containment exit gate for supervised autonomy.”
- **New ticket: No. Proposed title:** “Co-gate marketplace distribution on onboarding and first-win journey evidence.” Amend the existing distribution/onboarding epics.
- **New ticket: No. Proposed title:** “Keep v0.28+ swarms, gateway, crawler, and GTM evidence post-preview.” Record explicit deferral gates.

## Sources

- [GitHub issue #4960](https://github.com/nikhilsoman/synlynk/issues/4960)
- `docs/reviews/2026-10-16-frontier-lab-architecture-review.md`
- `docs/reviews/2026-10-16-decide-recommendation-ledger.md`
- `docs/strategy/2026-10-17-dev-preview-roadmap-and-competitive-synthesis.md`
- Cited but absent: `docs/reviews/2026-10-16-deep-review-against-goals.md`
