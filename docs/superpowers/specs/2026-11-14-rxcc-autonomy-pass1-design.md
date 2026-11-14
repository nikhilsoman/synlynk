# rxcc Autonomy Pass 1: Taking a Dormant Product to Market

**Date:** 2026-11-14
**Status:** Draft — Pass 1 (research/design only, no implementation authorized)
**Tracked under:** Epic #5261 ("[Epic] Autonomous-future planning: rxcc, cc-videoreframing (vdowrx), Hitchcock")
**Roadmap entry:** Third and final project in this epic's sequence, after Hitchcock (PRs #5262/#5263) and cc-videoreframing (PR #5264).

---

## Context

rxcc is a patient-centric AI health record service for India (ingests, extracts, and shares longitudinal medical data across providers) already built through v0.2 public soft launch and partway into v0.3/v0.4 — but, per the user, **most of the platform is currently dormant, used only personally.** The question for this spec is not "what ops are missing" (cc-videoreframing's framing) but "what does it take to autonomously take an already-built product to market."

rxcc carries regulatory weight the other two projects don't: DPDP Act 2023 and ABDM/ABHA compliance, patient health data, and a compliance sequencing roadmap already mapped (`roadmap.md`): #807 IP filings → ABDM sandbox registration (#32/#103, the long-pole) → security audit (#96) → dossier (#97) → pentest (#95) → go-live (#103). This weight is why the user explicitly scoped autonomy here as **engineering + compliance-prep drafting**, not compliance-decision autonomy — sign-off, submission, and the real pentest/audit stay human/professional actions.

Unlike Hitchcock and cc-videoreframing, rxcc already has substantial pre-existing design material for its growth/monetization gaps, which this spec reuses rather than re-derives:
- **E3 Growth Instrumentation** (#274) — spec drafted (`docs/superpowers/specs/2026-09-14-e3-growth-instrumentation-design.md`, PR #1201), includes channel attribution/UTM from day one (merged with E11's scope), **pending the user's sign-off**, not yet approved/planned.
- **E11 Paid Acquisition & Attribution / doctor monetization pricing** (#881) — spec done (`docs/superpowers/specs/2026-07-19-doctor-monetization-pricing-design.md`); doctor-facing Phase 1 channel/messaging already shipped via PR #954.
- **E1 Monetization v1 — Razorpay paywall + family tier** (#806) — deferred since 2026-07-15; `PAYWALL_ENABLED` stays `false`; payment blockers #857/#858 are open and unassigned.
- **LIVE-63 (#1129/#1202)** — root-caused 2026-09-14: Razorpay env vars/secrets are missing on the live `rxcc-api-dev` ECS task definition, so subscribe calls fail at Razorpay client init. Not yet fixed.

rxcc already dogfoods the same synlynk role substrate as cc-videoreframing (`.synlynk/roles.yaml`: `pm`/`architect`/`qa`/`dev`/`marketing`/`tpm`/`infra`), and already runs one autonomous recurring cycle in production: the DERQ (Data Extraction & Recognition Quality) monthly research/eval cycle, modeled on the #886→#963-971 GA4-audit pattern (#973, closed; first cycle DERQ-Jul26 fully landed).

**Decided with the user during brainstorming:**
- Autonomy scope is broad: "consider all functions of this product to be under autonomous execution" — engineering, compliance-prep drafting, growth/marketing, user acquisition funnel, and payment-integration production-readiness are **all** in scope for this one pass (no second pass reserved, unlike Hitchcock/cc-videoreframing's two-pass shape).
- Compliance stays human-gated for decisions and submissions; agents may draft artifacts but do not submit, register, or sign off.
- The growth/acquisition pillar follows the same shape the user specified for VDOWRX (cc-videoreframing Pass 1, PR #5264): a new dedicated role running a Google Ads + Google Analytics funnel — but here it builds on top of the already-drafted E3 instrumentation spec rather than starting blank.
- Razorpay/payments is explicitly called out as unfinished ("pending testing/production readiness"), distinct from cc-videoreframing's Paddle integration, which is already live.

---

## Section 1 — Approach

Reuse the already-adopted synlynk role substrate (same as cc-videoreframing) and the already-drafted E3/E11 specs rather than re-deriving growth/monetization design from scratch. This spec's job is sequencing and gap-filling across four pillars, not fresh design work for pillars that already have one.

## Section 2 — Pillar 1: Engineering Execution

The DERQ monthly research/eval cycle (#973 precedent) continues unchanged — it is already a working autonomous instance of capture→classify→dispatch→consolidate, same shape IB-PMEO Pass 2 generalizes. Backlog execution for E3 (#274) and any E11 (#881) follow-through dispatches through the existing `dev`/`architect`/`qa` roles once each spec clears its human sign-off gate (Section 3 below is the blocking step for E3 specifically).

## Section 3 — Pillar 2: Compliance-Prep Drafting (human-gated)

Agents draft compliance artifacts for human/professional review and action:
- ABDM/HIU compliance dossier (#97)
- Security-audit prep materials ahead of #96
- DPDP Act 2023 assessment documentation supporting #33 [F-5]

**Explicitly not autonomous:** ABDM sandbox registration/submission (#32/#103), the actual penetration test (#95), the actual security audit (#96), and go-live (#103) — these require human or licensed-professional action and carry legal accountability that drafting assistance does not remove. This mirrors Hitchcock Pass 2's identical deferral of Tier C legal/liability questions — drafting support is in scope, the decision/signature is not.

## Section 4 — Pillar 3: Growth/Marketing + User Acquisition Funnel

Same shape as cc-videoreframing's Pillar 1: a **new dedicated role** (harness resolved via the Empirical Capability Assessment Policy) running a Google Ads + Google Analytics acquisition/retention funnel, distinct from the existing `marketing`/Agy role's release-comms/docs/blog scope.

Unlike cc-videoreframing, this role does not start from zero — its first action is getting **E3 Growth Instrumentation (#1201) signed off** (currently pending the user's review, per `roadmap.md`), since E3 already includes the channel-attribution/UTM pipeline this role would otherwise need to build. Once #1201 ships, the growth role's job is running acquisition campaigns against that instrumentation, not building the instrumentation itself.

## Section 5 — Pillar 4: Razorpay Production Readiness

Unlike VDOWRX's Paddle integration (already live in production), rxcc's payment integration is explicitly **not** production-ready:
- #857/#858 payment blockers are open, unassigned
- LIVE-63/#1202: Razorpay secrets missing from the live `rxcc-api-dev` ECS task definition — subscribe calls fail at client init, not yet fixed
- `PAYWALL_ENABLED` stays `false`; E1 Monetization v1 (#806, Razorpay paywall + family tier) is deferred, not killed

This pillar closes #857/#858 and #1202, gets Razorpay tested end-to-end in a real production path, and only then flips `PAYWALL_ENABLED` — using E11's already-shipped doctor-facing pricing work (PR #954) as the pricing basis for the doctor side, with the family-tier patient-facing pricing still open per `roadmap.md`'s v0.3 table. This pillar can proceed in parallel with Pillar 3 rather than strictly behind it (contrast with cc-videoreframing, where pricing had no existing basis at all and had to wait on funnel data) — but flipping the paywall for real volume should wait until Pillar 3's funnel is live, so the business doesn't monetize an unmeasured acquisition channel.

---

## Deferred (explicitly out of scope for this spec)

- **Actual compliance submission, audit, pentest, and go-live** (#32/#103, #96, #95) — human/professional actions, not agent-executable regardless of drafting support (Section 3).
- **Family-tier patient-facing pricing numbers** — `roadmap.md`'s v0.3 table marks this not started; this spec does not set those numbers, only sequences the engineering (Pillar 4) that would carry them.
- **Exact harness assignment for the new growth role** — resolved later via the Empirical Capability Assessment Policy's ≥5-sample measurement, matching cc-videoreframing Pillar 1's identical deferral.
- **Channel + budget decision for paid acquisition** — `roadmap.md` already flags this as "pending founder input"; unchanged by this spec.
- **A second pass for rxcc** — the user explicitly scoped this as one comprehensive pass covering "all functions," not a two-pass split like Hitchcock/cc-videoreframing.

## Validation Criteria

Before any implementation plan is written against this design:
1. Confirm E3 Growth Instrumentation (#1201/#274) is reviewed and signed off by the user — Pillar 3's growth role has no instrumentation to build on until this happens.
2. Confirm #857/#858 and #1202 are each still accurately described as open/unfixed at implementation-plan time (this spec's recon is a snapshot; re-verify before sequencing Pillar 4 work).
3. Confirm with the user which compliance-prep artifacts (Section 3) are the highest-value starting point, given ABDM sandbox registration is already flagged as the roadmap's "real long-pole."
