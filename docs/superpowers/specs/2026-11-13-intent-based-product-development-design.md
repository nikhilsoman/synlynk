# Intent-Based Product Development & Master Roadmap Phase 3

**Date:** 2026-11-13
**Status:** Approved
**Roadmap entry:** Resolves the "Intent-Based Product Development" item deferred in `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md`'s Deferred section, and the "Outsource to synlynk outcome-based delivery" item deferred in both that spec and `docs/superpowers/specs/2026-11-13-synlynk-editions-boundary-and-opt-in-gating-design.md`.

---

## Context

Two specs already touch adjacent ground without covering this one:

- **The drift-governance spec** defines the 2a/2b classification test for synlynk's *own* roadmap phases: "2a (full-stack builder — one person or Wingman, intent to shipped product, solo) is what Personal **is**. 2b (autonomous product org — PM/Ops delegated to a fleet) is what GOVERNS + Agent Studio become once load-bearing across Team/Enterprise." It explicitly deferred the broader question this spec answers: what Intent-Based Product Development means as a cross-industry concept, and its PM/Ops-as-a-service implications.
- **`project-docs/decisions/2026-11-07-authoritative-roadmap-for-public-release-and-two-paradigms.md`** (`dec-7a2b0e91`, approved by a 4-harness decide panel) is synlynk's **authoritative master roadmap**, independent of and using different phase numbering than the Platform Vision spec's infra Phase 0–5. It commits to: **Phase 1 — The Full-Stack Builder** (v0.29.0 Developer Preview, validates Paradigm 2a: hermetic packaging, zero-cost public release, 15-minute onboarding) and **Phase 2 — The Autonomous Organisation** (v1.0.0+, validates Paradigm 2b: multi-tenant workspace sync, remote swarm runners, policy-driven autonomous goal execution).

This spec adds **Master Roadmap Phase 3** to that same numbering — sequenced after Phase 2, not altering Phase 1/2 scope or version targets — and is the resolution of the "outsource to synlynk" thread both other specs flagged as deferred rather than a new deferral.

**Naming note:** "Phase 3" here means the *next master-roadmap phase* after `dec-7a2b0e91`'s Phase 1/Phase 2. It is unrelated to the Platform Vision spec's Phase 0–5, which numbers synlynk.com's own infrastructure build-out (GitHub Pages migration, Accounts, Hosted Workstation, Hosted Relay, Swarm Gateway, Community). Where this spec depends on a Platform Vision phase, it names it explicitly as "Platform Vision Phase N" to avoid collision.

---

## 1. Executive Thesis — What "Intent-Based Product Development" Is

Intent-Based Product Development (IBPD) is the claim that the fundamental unit of work in software delivery is shifting from *"a written spec handed to a delivery team"* to *"captured intent, governed by policy and executed by a swappable lattice of specialized roles (PM, Architect, TPM, Dev, QA), with verification gates substituting for traditional management oversight."*

This is broader than synlynk's own Intent Capture Layer (already designed and approved in the drift-governance spec) — that layer is the internal *mechanism* synlynk uses to turn a human's intent into GOVERNS goals/stories for its own engineering. IBPD is the industry-wide *claim* that this mechanism generalizes beyond synlynk's own dogfooding.

Legacy IT/SWE delivery — staff-aug consultancies, offshore development shops, traditional in-house PM/engineering organizations — carries high fixed overhead (headcount, management layers, cross-team communication latency) to translate a stated intent into shipped software. IBPD's position is that this overhead is **structural, not essential**: once intent capture, role charters, verification gates, and harness-agnostic execution exist as a substrate, the team performing delivery can be synthetic, swappable, and billed by verified outcome rather than headcount-time.

## 2. Synlynk as Proof-of-Concept — Mapping onto `dec-7a2b0e91`

The master roadmap's two paradigms are themselves two successive proofs of the IBPD thesis, and this spec's Phase 3 is the third:

- **Paradigm 2a (Master Roadmap Phase 1 — The Full-Stack Builder):** proves IBPD at individual scale. One human operator, directing a synthetic team through explicit charters and verification contracts, replaces a small dev team for their *own* product.
- **Paradigm 2b (Master Roadmap Phase 2 — The Autonomous Organisation):** proves IBPD at organizational scale. A policy-governed fleet (multi-tenant workspace sync, swarm runners, autonomous goal execution) replaces the PM/Ops layer for the operator's *own* product, now at Team/Enterprise load.
- **Master Roadmap Phase 3 (this spec):** proves IBPD **as a service**. The identical fleet-plus-governance substrate that 2a and 2b already built, pointed at a **third party's** intent and codebase instead of the operator's own, is the commercial instantiation of the thesis. Phase 3 introduces no new core technology beyond what Phase 2 already requires (multi-tenant GOVERNS, dispatch isolation, cost ledger per tenant) — it is a go-to-market and business-model layer on top of infrastructure the master roadmap already commits to building.

## 3. Master Roadmap Phase 3: Self-Serve Tiered Delivery Ladder

Phase 3 is **one substrate, three commercial tiers**, forming a trust ladder. A customer moves up the ladder without a platform migration — only a change in *whose* GOVERNS policy and *whose* fleet executes against their repo.

| Tier | Who drives | Who executes | Revenue model |
|---|---|---|---|
| **1 — Self-Serve** | Customer | Customer's own fleet, own harness credentials, own GOVERNS policy | Subscription (today's Personal/Team/Enterprise editions, unchanged) |
| **2 — Assisted Self-Serve** | Customer | Customer's fleet, augmented by synlynk role-charter playbooks and one-off `synlynk decide --panel` consulting sessions | Professional-services line items on top of the subscription |
| **3 — Fully Managed** | Customer (reviewer/approver role only) | Synlynk's own operator-controlled fleet, under synlynk's own GOVERNS policy and role charters | Outcome-based or consumption-based billing (per shipped/verified story, or a delivery-capacity retainer) |

**Tier 1** is exactly today's product — no new work, included here only to anchor the ladder.

**Tier 2** sells synlynk's accumulated operating knowledge (charter templates tuned to a domain/stack, strategic `decide --panel` sessions) without synlynk's fleet ever touching the customer's repo directly. Bounded, billable, lowest trust requirement to adopt.

**Tier 3** is the literal "outsource to synlynk" instantiation flagged deferred in both prior specs: the customer supplies only a brief, a backlog, or an existing codebase; synlynk's own fleet performs PM, architecture, implementation, QA, and deployment end-to-end, with the customer in a review/approval role rather than a driving one.

## 4. The AI-Transformation Pitch

Phase 3's target market is the long tail of legacy IT shops, internal engineering organizations, and traditional outsourced-delivery relationships (offshore dev shops, staff-augmentation, systems integrators) that currently bill by headcount-time. Tier 3 substitutes a verifiable, policy-governed, outcome-billed delivery model for that billing structure.

The pitch is deliberately **not** "an AI pair programmer" — that category is already commoditized by per-seat AI coding assistants aimed at augmenting an existing team's individual engineers. Phase 3's differentiated claim is **"replace your delivery org's PM/Ops layer, not just your individual engineers"** — the PM/Ops-as-a-service framing this spec is built around, and the thing no per-seat coding-assistant competitor is positioned to offer, because their unit of sale is the individual contributor, not the organizational structure around them.

## 5. Reconciliation With Existing Specs

This spec introduces no contradiction with prior decisions:

- **`dec-7a2b0e91` (authoritative master roadmap):** Phase 3 is additive and sequenced strictly after Phase 2 (v1.0.0+) lands. It does not change Phase 1 or Phase 2's scope, sequencing, or version targets. Tier 3's premise — synlynk's own fleet executing against a third party's repo under synlynk's own multi-tenant policy — structurally depends on Phase 2's multi-tenant workspace sync and policy-driven autonomous goal execution already being in place.
- **Platform Vision spec (Phase 0–5 infra numbering):** Tier 3 is the first concrete paying use case for **Platform Vision Phase 1** (Accounts/Entitlements — needed to represent a customer Account distinct from synlynk's own operator Account) and **Platform Vision Phase 2** (Hosted Workstation — the execution environment a managed engagement runs in). This spec adds no new Platform Vision phase; it gives two already-planned phases their first commercial driver.
- **Editions spec (Core/Opt-in/Hosted cost-bearer classification):** Tier 1 is today's editions, unchanged. Tier 2's consulting line items and Tier 3's managed delivery are both `category: "hosted"` capabilities under the existing classification rule (synlynk bears the marginal cost of running the engagement) — no new category is needed to represent Phase 3.
- **Drift-governance spec's Deferred section and Editions spec's Deferred section** both list "Outsource to synlynk outcome-based delivery" as deferred, not resolved. This spec is that resolution, not a third deferral.
- **GOVERNS / `.synlynk/policy.json`'s `merge_authority`, cross-harness+model review requirement, 100% linked-goal adherence, personal-GitHub-token prohibition:** Tier 3 engagements run under synlynk's **own** policy (not the customer's), so every existing Hardened PR Review Policy guarantee applies unchanged to managed-delivery work. This is presented to customers as a selling point — auditable, non-bypassable governance over who touches their code and how — not as a gap this spec needs to fill.

## 6. Deferred / Explicitly Out of Scope

- **Pricing mechanics** — exact rate cards, margin model, and retainer structures are deferred to a future commercial/pricing spec. This spec establishes the three-tier structure and cost-bearer classification only.
- **Legal/liability model for Tier 3** — who is accountable when a fully-managed engagement ships a defect is deferred, and is flagged as a blocker for actually *launching* Tier 3 (not a blocker for this spec, which is the product/business-model thesis).
- **Fixed harness/role roster for Tier 3 engagements** — deferred entirely to the Empirical Capability Assessment Policy's measured routing (`capability_ratings`/`cost_entries`). Phase 3 commits to whichever harness mix that policy currently judges best for a given task type, never a hand-picked roster.
- **Go-to-market and sales motion** for reaching legacy IT/SWE buyers — explicitly out of scope. This spec is the product/business-model thesis; marketing and sales planning are separate future work.

## 7. Validation Criteria

Before committing material engineering to Platform Vision Phase 1/2 specifically on Tier 3's behalf, run **1–3 Tier-3-shaped pilot engagements** manually or semi-manually: synlynk's own fleet, dispatched against a willing third party's actual repository, operating under synlynk's own GOVERNS policy, with no dedicated multi-tenant infrastructure built yet. This mirrors how Paradigm 2a was proven out before 2b's infrastructure was built — the operating model must be shown to work before the platform is built to scale it.

---

## Deferred (explicitly out of scope for this spec)

- Pricing mechanics, rate cards, and retainer structures (Section 6).
- Legal/liability model for managed (Tier 3) engagements (Section 6).
- Fixed harness/role roster for Tier 3 — defers to the Empirical Capability Assessment Policy (Section 6).
- Go-to-market/sales motion for the legacy IT/SWE target market (Section 6).
- Platform Vision Phase 1/2 implementation details — this spec establishes that Phase 3 depends on them; it does not re-specify them.
