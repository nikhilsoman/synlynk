# Hitchcock Autonomy Pass 2: Business/Ops Layer

**Date:** 2026-11-14
**Status:** Draft — Pass 2 of 2 (research/design only, no implementation authorized)
**Tracked under:** Epic #5261 ("[Epic] Autonomous-future planning: rxcc, cc-videoreframing (vdowrx), Hitchcock")
**Roadmap entry:** Second of two Hitchcock autonomy specs, sequenced after Pass 1 (`docs/superpowers/specs/2026-11-14-hitchcock-agent-staffed-creative-roles-design.md`, PR #5262) per the user's explicit "roles first then ops" decision. Fills `project-docs/roadmap.md`'s literal unfilled "Positioning" and "Business Goals" placeholders.

---

## Context

Pass 1 designed how an AI agent occupies one of Hitchcock's twelve creative roles (DIRECTOR, SCREENWRITER, CINEMATOGRAPHER, PRODUCTION_DESIGNER, COSTUME_DESIGNER, COMPOSER, SOUND_DESIGNER, VFX_SUPERVISOR, EDITOR, PRODUCER, MARKETING, VISUALIZER) via `CollaborationManager`'s existing invite/join flow, dispatched through IB-PMEO Pass 2's intent pipeline. This spec answers the question Pass 1 explicitly deferred: who pays Hitchcock, for what, and how.

Prior to this spec, `project-docs/roadmap.md` had no answer at all — "Positioning" and "Business Goals" were literal `[Describe what hitchcock is building toward]` / `[Define outcomes here with synlynk goal create...]` placeholders, confirmed during recon.

**A related, already-approved spec exists but is deliberately not reused as this spec's structure:** `docs/superpowers/specs/2026-11-13-intent-based-product-development-design.md` defines Master Roadmap Phase 3's three-tier ladder (Self-Serve → Assisted Self-Serve → Fully Managed) for synlynk's own software-delivery business. During brainstorming, the user explicitly chose **independent tiering for Hitchcock** over instantiating that same ladder — film production's trust/revenue dynamics don't track software delivery's linearly (a brand may want fully-managed service for one campaign and self-serve for another, not a graduated trust climb). This spec's three tiers are named and justified on their own terms; any structural resemblance to Phase 3's ladder is coincidental, not inherited.

**Decided with the user during brainstorming:**
- All three customer segments (B2C creators, B2B agencies/brands, fully-managed) are in scope — not a single starting segment (Section 1).
- Each tier gets its own billing unit, not one unit forced across all three (Section 2).
- Tier↔billing mapping confirmed explicitly: Tier A=subscription, Tier B=per-production contract, Tier C=per-finished-minute outcome billing.

---

## Section 1 — Positioning

**Positioning statement:** *"Hitchcock turns a brief into a finished film — direct it yourself, bring your own studio, or hand us the brief."*

One underlying product (the autonomous render pipeline that already ships, plus Pass 1's agent-staffed creative roles) serves three distinct customer relationships, differentiated by **who holds the creative roles**, not by different software. This directly fills `roadmap.md`'s "Positioning" placeholder.

## Section 2 — Three-Tier Structure

| Tier | Who holds creative roles | Billing unit | Customer |
|---|---|---|---|
| **A — Creator Self-Serve** | Customer (human or their own agent picks, per Pass 1's registry) holds all 12 roles | Subscription with usage caps (rendered minutes/month) | Individual creators, indie filmmakers, YouTubers |
| **B — Agency/Brand** | Customer's team holds senior creative roles (DIRECTOR, SCREENWRITER); synlynk's agent fleet holds mechanical/production-design roles (CINEMATOGRAPHER, COSTUME_DESIGNER, PRODUCTION_DESIGNER, COMPOSER, VFX_SUPERVISOR, EDITOR) via Pass 1 dispatch | Per-production contract, negotiated against finished-output complexity | Production companies, marketing agencies, brands |
| **C — Fully-Managed** | synlynk's agent fleet holds all 12 roles via Pass 1; customer supplies only a brief | Per-finished-minute outcome billing, tied directly to compute cost | Any customer wanting zero creative-production involvement |

**Why Tier B splits roles by seniority rather than by discipline:** DIRECTOR and SCREENWRITER carry the creative-authorship decisions (scene intent, narrative structure) a brand/agency customer typically wants to retain control over; the remaining roles are execution-layer (camera, wardrobe, sets, score, VFX, pacing) and delegate cleanly to Pass 1's agent fleet without surrendering the customer's creative voice. This mirrors real agency practice — an agency's own creative director stays in the loop while production vendors are swapped freely.

**Why Tier C is billed per-finished-minute, not per-production:** unlike Tier B's negotiated contract (where a human sits across the table to agree a price), Tier C has no negotiation step — the customer submits a brief and expects a price before committing. Per-finished-minute billing ties price directly to Hitchcock's own compute cost (generation + QC + render), which is measurable and quotable up front without a human sales cycle.

## Section 3 — MARKETING Role as the Production/Business Boundary

Pass 1's MARKETING role (`release`-stage, per IB-PMEO Pass 1's taxonomy: transmedia export/distribution) is the one creative role whose output *is* this spec's concern, not Pass 1's:

- **For Tier C**, MARKETING's completed activity (the exported, distributed deliverable) *is* the billable outcome — its activity-completion event in Pass 2's pipeline (IB-PMEO's `ActivityResult`) is the natural trigger for issuing the per-finished-minute invoice.
- **For Tiers A/B**, MARKETING's activity log (how many finished exports, at what length) is the usage record that subscription caps (Tier A) and contract-complexity negotiation (Tier B) meter against.

This means Pass 1's role registry and this spec's billing layer share one event stream rather than needing a separate usage-tracking mechanism — MARKETING's dispatch/await/consolidate lifecycle (already specified in Pass 1 Section 3) is reused as-is; this spec adds no new instrumentation to Pass 1's design, only a consumer of its existing output.

## Section 4 — Business Goals

This section fills `roadmap.md`'s "Business Goals" placeholder:

1. **First goal: one Tier C pilot engagement**, run manually/semi-manually (synlynk's fleet producing one real film from one real brief, billed per-finished-minute by hand) before any Tier A/B infrastructure is built. This mirrors the already-approved IBPD spec's own validation pattern ("run 1–3 pilot engagements manually... before building scale infrastructure") — reused here as precedent, not re-derived.
2. **Second goal: validate Tier C pricing** against this spec's compute-cost-tied billing unit using the pilot's actual `cost_entries` data, before quoting a second Tier C customer.
3. **Third goal (sequenced after 1-2): build Tier A's subscription/usage-metering infrastructure** — explicitly the most infrastructure-heavy tier (recurring billing, usage caps, self-serve onboarding) and therefore the last tier built, not the first, despite being the highest-volume target segment long-term.
4. **Tier B is opportunistic** — pursued if/when an agency/brand customer is identified, using Tier C's already-proven agent-role dispatch machinery (Pass 1) with a negotiated-contract billing wrapper; no dedicated infrastructure goal precedes it the way Tier A's does.

---

## Deferred (explicitly out of scope for this spec)

- **Exact pricing numbers** (per-minute rate, subscription tiers/caps, contract pricing bands) — a future commercial/pricing exercise once pilot cost data exists (Business Goal 2 above).
- **Legal/liability model for Tier C** — who is accountable when a fully-managed production ships a defect or rights-clearance issue. Mirrors the identical open deferral in the IBPD spec's Tier 3 (`docs/superpowers/specs/2026-11-13-intent-based-product-development-design.md` Section 6) — flagged as a blocker for actually *launching* Tier C, not for this spec.
- **Go-to-market/customer acquisition motion** — how the first Tier C pilot customer is actually found. Out of scope for a business-model design spec.
- **Tier A/B billing infrastructure build** — explicitly sequenced last per Business Goal 3; this spec establishes the billing unit, not the metering/invoicing system.
- **Rights/licensing for generated creative assets** (music, voice, likeness) across any tier — a legal question this spec does not attempt to resolve, related to but broader than the Tier C liability deferral above.

## Validation Criteria

Before any implementation plan is written against this design: complete Business Goal 1 (one real Tier C pilot, billed by hand) and confirm its actual `cost_entries` data supports a per-finished-minute price that covers compute cost with margin. If the pilot's economics don't support that unit at any reasonable price, this spec's Section 2 billing-unit choice for Tier C needs revision before Tier A/B infrastructure work begins.
