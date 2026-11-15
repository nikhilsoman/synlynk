# Autonomy Models: A Three-Axis Framework

**Date:** 2026-11-15
**Status:** Draft — framework only, no experiment design or implementation authorized
**Scope:** Cross-project. Applies to synlynk itself and all three externally-owned products under epic #5261 (Hitchcock, cc-videoreframing/VDOWRX, rxcc).
**Relationship to epic #5261:** Not filed as part of that epic. #5261's three merged specs (PRs #5262–#5265) each describe autonomy for one product without a shared vocabulary for *why* that autonomy exists or *who* is meant to operate it. This framework supplies that vocabulary retroactively and for future autonomy work, including any eventual autonomy work on synlynk's own operations.
**Explicitly deferred:** the concrete experiment design — which paradigm each product/pillar tests, what's measured, how results feed back into routing decisions. That is a separate, later brainstorm ("1 followed by 2 eventually," per the user).

---

## Context

While proposing where epic #5261's work should sit on synlynk's roadmap, the proposal implicitly treated "autonomy" as one undifferentiated thing. The user — as founder of all four products (synlynk, rxcc, VDOWRX, Hitchcock) — pointed out that the proposal actually smuggled in two distinct, unstated decisions:

1. **Why** autonomy is warranted at all in a given case.
2. **Who** operates it — the founder, within the boundary of their own business, versus delegating operation to synlynk as a third party.

Rather than guess at how these relate, the user asked for prior art before committing to a structure. Three independent, pre-existing bodies of research turned out to answer the structural question directly: don't force everything into one taxonomy or one matrix. Treat them as three separate axes that move independently, the same conclusion recent enterprise agentic-AI maturity research reaches when it finds that business scope, human oversight posture, and technology stack advance unevenly within the same organization rather than together.

## The Three Axes

An instance of autonomy — one pillar, one role, one recurring workflow — is positioned independently on all three axes below. None of the three determines the others.

### Axis 1 — Driver: why autonomy emerges

| Category | Definition | Prior art |
|---|---|---|
| **Structural / Deliberate** | Autonomy chosen in advance because scope, reach, scale, or adoption rate make manual operation a known, anticipated bottleneck. | Matches "scale" and "competitive pressure" as named drivers in the business-process-automation literature; corresponds to Mintzberg's *deliberate strategy*. |
| **Internally Emergent / Reactive** | Autonomy that crystallizes as a response to those same structural factors turning out adverse or insufficient — a pattern that emerges under strain rather than one chosen ahead of time. | Mintzberg's *emergent strategy* — the direct counterpart to deliberate strategy, not a separate invention. |
| **Regulatory** | Autonomy imposed by law, standard, or binding convention. | Directly named as a driver category across BPA/RPA adoption literature, especially in regulated sectors. |
| **Convenience / Philosophical** | No external pressure — chosen because recurring manual attention is inefficient, uninteresting, or philosophically preferred to be delegated. | The softer, discretionary end of the same literature's "efficiency" driver category; least formally codified of the four. |

A single real-world instance can shift categories over time (convenience-driven automation can later become structurally load-bearing), but is classified by its *current* dominant driver, not its origin story.

### Axis 2 — Operating Boundary: who runs it

Not a driver — a governance choice, directly modeled on Williamson's Transaction Cost Economics (make/buy/hybrid), where the deciding variable is **asset specificity**: how much hard-to-transfer, domain-specific judgment the work requires, plus uncertainty and frequency of the decisions involved.

| Category | Definition | Favored by |
|---|---|---|
| **Self-Operate ("Make")** | The founder/project retains full operating control over decisions. synlynk may provide infrastructure or tooling but does not make the operating calls. | High asset specificity (deep domain/regulatory knowledge), high uncertainty, or high-frequency judgment calls the founder is best positioned to make. |
| **Synlynk-Delegated ("Buy")** | synlynk's own roles/dispatch/charters run the operation end-to-end; the founder sets strategy and guardrails only, not individual decisions. | Low asset specificity — generic, portable operational work that doesn't depend on founder-specific knowledge. |
| **Hybrid** | Mechanical execution (dispatch, drafting, infra) runs through synlynk; the specific judgment calls (sign-off, compliance decisions, pricing) stay with the founder. | Mixed specificity — most real cases, including most of what #5261's three merged specs already describe (e.g. rxcc Pillar 2: agents draft compliance artifacts, a human signs off). |

### Axis 3 — Oversight Posture: how much human-in-the-loop

Independent of Axis 2. Who holds the operating boundary (self vs. synlynk) is a different question from how tightly a human must supervise a given action — and the current agentic-AI autonomy-levels literature is explicit that oversight should scale with the *risk* of the action, not with who nominally operates it. A synlynk-delegated workflow can still require tight human sign-off on its highest-risk step; a self-operated one can run most of its low-risk steps unsupervised.

Adapted from the Operator/Collaborator/Consultant/Approver/Observer role ladder used in recent autonomy-level research, ordered from most to least human involvement per action:

- **Operator** — a human does the action; AI assists.
- **Collaborator** — human and AI co-drive the action together.
- **Consultant** — AI acts, human is available on demand but not required per action.
- **Approver** — AI prepares the action; a human must sign off before it takes effect.
- **Observer** — AI acts fully autonomously; a human audits after the fact.

## Why These Stay Independent (Illustrative, Not Prescriptive)

The three merged specs already contain real instances that land at different points on all three axes — shown here only to demonstrate the axes move independently, not as a decision about how any of these should ultimately be run:

- **rxcc, Pillar 2 (compliance-prep drafting):** Regulatory driver × Hybrid boundary × Approver posture (agents draft, a human must sign off before ABDM/DPDP artifacts go anywhere).
- **rxcc, Pillar 1 (DERQ monthly eval cycle):** Structural driver × already synlynk-dispatched boundary × Consultant/Observer posture (capture→classify→dispatch→consolidate runs with minimal per-cycle human involvement).
- **Hitchcock, Tier C billing trigger:** Structural driver (billing unit designed in advance) × boundary not yet decided × low-risk action, naturally suited to Observer posture once trusted.
- **Hitchcock, Tier C legal/liability questions:** explicitly deferred in Pass 2's own spec — a case where Oversight Posture (Operator-level, a human/professional must act) is clear even though Driver and Operating Boundary remain open.
- **rxcc's overall dormancy** (noted in its own spec: "most of the platform is currently dormant, used only personally"): a case where the Driver is Internally Emergent — the founder's attention is one person spread across four products, and gaps in rxcc's operation emerged from that scarcity rather than being designed.

No project is assigned a single position across all its pillars — each pillar/role is classified on its own.

## How This Framework Gets Used

1. **Future autonomy specs state their axis positions explicitly.** Any new design spec for Hitchcock, VDOWRX, rxcc, or synlynk's own internal operations should name its Driver, Operating Boundary, and Oversight Posture per pillar/role, rather than leaving Operating Boundary implicit the way the original roadmap-placement proposal did.
2. **The deferred experiment design (next brainstorm) treats Axis 2 as its primary independent variable.** The user's explicit interest — testing self-operate vs. synlynk-delegated directly, as the founder of all four products — is a controlled variation along Axis 2, holding Driver and Oversight Posture constant where possible, to isolate what the Operating Boundary choice itself actually changes.
3. **Retrofitting #5262–#5265:** each of the three merged specs could be lightly annotated with their pillars' axis positions. This is a non-blocking follow-up, not required before any further work.

## Deferred (explicitly out of scope for this spec)

- **The concrete experiment design** across the four projects — which paradigm each pillar tests, what's measured (cost, quality, founder-time-saved, failure modes), and how results feed back into future routing decisions. Next brainstorm, per the user.
- **Numeric or formal scoring** for where a given instance sits on each axis (e.g., a quantified asset-specificity score). This spec defines the axes qualitatively; a scoring rubric is a future refinement only if the experiment design needs one.
- **Retrofitting PRs #5262–#5265** with explicit axis annotations — recommended as a lightweight follow-up, not performed here.
- **Any claim about which axis position is "better."** This framework is descriptive and classificatory. It does not recommend an Operating Boundary or Oversight Posture for any specific case — that judgment belongs to the founder, informed by the eventual experiment results.

## Validation Criteria

Before this framework is used to shape the deferred experiment design: confirm with the user that the three axes and their definitions hold up against their lived experience operating all four products — specifically, that no real instance of autonomy they've encountered resists classification on all three axes, or forces one axis to collapse into another.
