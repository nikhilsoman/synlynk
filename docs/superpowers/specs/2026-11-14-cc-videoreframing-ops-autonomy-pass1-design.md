# cc-videoreframing (VDOWRX) Autonomy Pass 1: Business/Ops Layer

**Date:** 2026-11-14
**Status:** Draft — Pass 1 of 2 (research/design only, no implementation authorized)
**Tracked under:** Epic #5261 ("[Epic] Autonomous-future planning: rxcc, cc-videoreframing (vdowrx), Hitchcock")
**Roadmap entry:** First of two cc-videoreframing autonomy specs, per the user's explicit "ops-finish first then expansion" decision. Pass 2 (the deeper EDIT-vertical / VDOWRX Expansion 1 technical design) is a separate, later spec, gated on this spec's Pillar 4 producing a "go" Decision Recommendation.

---

## Context

Earlier light recon (from the IB-PMEO Pass 2 cross-industry validation) characterized cc-videoreframing as "a fully automated 9-stage batch pipeline with one CLI entrypoint, zero human roles." Deeper recon for this spec found that picture significantly out of date: the project has grown into a near-complete multi-tenant SaaS product (branded **VDOWRX**) with its own API (`api/`: FastAPI, Alembic migrations, `plans`/`accounts`/`api_keys`/`subscriptions`/`jobs` tables), dashboard (`dashboard/`: Next.js), background workers (`lambda/`), and Pulumi-managed cloud infra (`infra/`: ALB, ECS Fargate, RDS Aurora, SQS, Batch, CloudFront). It also already dogfoods synlynk's own 7-role architecture (`pm`/`architect`/`qa`/`dev`/`marketing`/`tpm`/`infra`, `.synlynk/roles.yaml`, commit `5b75190`/PR #213) for its own engineering delivery — distinct from VDOWRX's end-customer-facing product.

This discrepancy was surfaced to the user explicitly before brainstorming proceeded, rather than designing against the stale picture.

`Plan_SAAS.md` is a detailed, substantially-already-implemented hand-written SaaS conversion plan. One part of it is stale: it drafted Stripe as the payment platform, but **Paddle is already live in production** (`api/.../paddle_service.py`, `tests/api/test_billing.py`, `docs/paddle-sandbox-testing.md`, a shipped `docs/superpowers/plans/2026-04-17-paddle-compliance-pages.md`). `story-13266171` ("finalize pricing and seed plans table") targets Paddle, not Stripe.

`docs/vdowrx_strategy.md` already contains a complete, unused **Idea Evaluation Framework** (Sections 0–8: Idea Brief → Problem/Opportunity → Market Sizing → Personas → Product Definition → Competitive Landscape → Technical Plan → Go-to-Market → Decision Recommendation) plus an Opportunity Register and Seed List — this spec's Pillar 4 runs the EDIT vertical / "VDOWRX Expansion 1" opportunity through it rather than inventing a new prioritization method. `docs/research/vdowrx-expansion-1/` already holds three un-consolidated cross-agent research docs (Codex backend feasibility, Grok frontend/infra, Agy content/marketing) that are the direct input to that framework pass.

**Decided with the user during brainstorming:**
- Two passes, not one: Pass 1 = business/ops autonomy (this spec); Pass 2 = deeper EDIT-vertical technical design, gated on Pass 1's Pillar 4 outcome.
- Pass 1 covers four pillars, in this priority order: (1) growth/marketing, (2) support/incident-response, (3) billing/pricing finalization, (4) product-research-and-expansion's business/prioritization layer.
- The priority order is load-bearing, not just a dispatch preference: Pillar 3 (billing) is sequenced *behind* Pillar 1 (growth) because final pricing numbers come from the growth funnel's acquisition/retention data, not from compute-cost data alone.
- Growth/marketing (Pillar 1) is a **new dedicated role**, not an extension of the existing `marketing`/Agy role (which stays scoped to release comms/docs/blogs).
- Support/incident-response (Pillar 2) covers **both** the engineering-defect track (extending the existing LIVE-issue SOP to be autonomous for a defined band) and a **new** customer-facing track (account/billing/usage support), which does not exist today.
- Billing/pricing finalization (Pillar 3) means **revisiting** `Plan_SAAS.md`'s drafted tier numbers, not adopting them as final.
- Approach: extend the already-adopted synlynk role substrate (dispatch/GOVERNS/cost-tracking) rather than building a separate ops-automation system, matching Hitchcock Pass 1's choice to reuse `CollaborationManager` instead of inventing a bypass.

---

## Section 1 — Approach

Extend cc-videoreframing's already-adopted synlynk role substrate to run all four ops pillars. This is the one of the three projects (Hitchcock, cc-videoreframing, rxcc) already fully bought into dispatch/GOVERNS/cost-tracking for its own engineering — the autonomy story here is "reuse what's proven," not "invent new infrastructure." Two new roles are added (growth, support); two pillars (billing, product-research) route through existing `pm`/`architect` roles with new task content.

## Section 2 — Pillar 1: Growth/Marketing (priority 1)

A **new dedicated role** (harness resolved via the Empirical Capability Assessment Policy, not hand-picked) designs and runs a user acquisition & retention funnel on **Google Ads + Google Analytics**. This is distinct from the existing `marketing` role (Agy), which stays scoped to release communications, documentation compilation, and build-diary blogs — funnel/acquisition work is a different discipline and is not folded into that role's existing charter.

Requires real engineering bandwidth, not just agent dispatch:
- GA4/GTM tagging across the Next.js dashboard, Google Ads conversion tracking, UTM/campaign attribution
- Server-side conversion events tied to monetization milestones (signup → first job → paid conversion → retained usage), wired against the existing `jobs`/`subscriptions`/`accounts` tables
- This pillar has the highest build cost of the four and is explicitly a **prerequisite for Pillar 3** (Section 4), not a parallel independent track — this is why it is priority 1.

## Section 3 — Pillar 2: Support & Incident-Response (priority 2)

Two tracks, both in scope:

- **Engineering-defect track:** extend the existing LIVE-issue SOP (declare → investigate → RCA → action-tickets → resolution) to run without the PM/human triage gate for a defined severity/confidence band — e.g., Sev3 and Sev2-with-clear-root-cause dispatch straight to `dev`/`qa` roles; Sev1 or ambiguous-root-cause still escalates to a human. `story-issue-98`/`story-issue-104` (LIVE-5's `_duration_tolerance()` boundary bug, LIVE-6's ffprobe CSV trailing-delimiter bug) are the worked precedent for what "clear root cause" looks like.
- **Customer-facing track (new):** no account/billing/usage support system exists today. Modeled as a new `support` role (harness resolved via the Empirical Capability Assessment Policy) that triages incoming customer tickets, answers usage/billing/quota questions directly from `jobs`/`subscriptions`/`accounts` table state, and escalates anything touching money or data loss to a human.

## Section 4 — Pillar 3: Billing/Pricing Finalization (priority 3)

Payment rails are not the blocker — Paddle is already live in production; `story-13266171`'s seed-plans-table work targets Paddle. The actual blocker is data: pricing cannot be finalized without acquisition/retention signal, so **this pillar is sequenced after Pillar 1's funnel is live and producing data**. Final tier numbers (revisiting, not adopting, `Plan_SAAS.md`'s drafted Starter/Pro/Enterprise/Overage figures) come from real CAC/LTV/willingness-to-pay evidence the growth role surfaces via Google Ads + Analytics, not from compute-cost data alone. The `pm`/`architect` roles consume that funnel output and set final numbers before `story-13266171` ships.

## Section 5 — Pillar 4: Product Research & Expansion — Business/Prioritization Layer

Not a new prioritization method — **running the EDIT vertical / "VDOWRX Expansion 1" opportunity through the existing Idea Evaluation Framework** in `docs/vdowrx_strategy.md` (Sections 0–8). The three existing un-consolidated research docs in `docs/research/vdowrx-expansion-1/` (Codex backend feasibility, Grok frontend/infra, Agy content/marketing — the subject of the already-queued `story-8f79e79d` consolidation task) are the direct input, dispatched to `pm`/`architect` roles to fill the framework's Sections 1–8 and produce a go/no-go Decision Recommendation.

## Section 6 — Boundary with Pass 2

Pass 1 ends at Pillar 4's Decision Recommendation and the four pillars' operational autonomy (Sections 2–4). Pass 2 begins only if Pillar 4's framework output is "go," and covers the EDIT vertical's actual technical design — explicitly deferred, not touched here.

---

## Deferred (explicitly out of scope for this spec)

- **Pass 2's technical design for the EDIT vertical** — gated on this spec's Pillar 4 producing a "go" Decision Recommendation.
- **Exact harness assignment for the new `growth` and `support` roles** — resolved later via the Empirical Capability Assessment Policy's ≥5-sample measurement, not hand-picked here.
- **Exact GA4/GTM/Google Ads implementation details** (tag plan, conversion event schema, attribution model) — an implementation-plan concern once this design is approved.
- **Exact revised pricing numbers** — explicitly blocked on Pillar 1's funnel producing real data; this spec establishes the sequencing, not the numbers.
- **Legal/compliance review of the customer-facing support track** (e.g., what support agents may say about billing disputes/refunds) — a future concern, not resolved here.
- **`project-docs/roadmap.md`'s stray placeholder content** (found during recon to contain only an unrelated "I need your permission to write..." artifact string) — out of scope for this spec; noted for separate cleanup.

## Validation Criteria

Before any implementation plan is written against this design:
1. Confirm Pillar 1's growth role charter and Pillar 2's support role charter are each addable to `.synlynk/roles.yaml` without conflicting with an existing role's scope.
2. Confirm Pillar 4's framework pass (Sections 1–8 of `vdowrx_strategy.md`, fed by the three existing `docs/research/vdowrx-expansion-1/` docs) can be dispatched and produce a Decision Recommendation before Pass 2 is started.
3. Confirm with the user that Pillar 3's billing-numbers work is blocked (not merely deprioritized) until Pillar 1's funnel is live, before any dispatch sequencing is finalized in an implementation plan.
