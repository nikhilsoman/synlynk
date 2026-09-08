# Positioning Messaging Reconciliation

**Scenario:** general / advanced difficulty

## Conflict

Two statements currently compete for the product's identity:

- **Platform statement:** synlynk is an “OS for multi-agent development” or a
  hybrid workgroup that coordinates where AI work happens.
- **Arbitration statement:** synlynk is the measurement and arbitration layer
  for heterogeneous coding agents: it routes work, verifies outcomes, and
  keeps shared project state truthful.

The first is an approachable operating metaphor, but it puts synlynk in the
same category as agent IDEs and execution runtimes. The second identifies the
durable differentiator: evidence-backed coordination across vendors. Treating
both as equal taglines leaves users unsure whether synlynk is an agent, a
harness, or the system that governs them.

## Reconciled message

Use the arbitration statement as the canonical positioning:

> **synlynk keeps heterogeneous coding agents honest:** it routes work using
> capability and cost signals, verifies outcomes from project history, and
> preserves shared state across the fleet. It coordinates and measures work
> performed by external harnesses; it is not itself a harness or agent vendor.

The platform statement may appear as supporting atmosphere copy, provided the
canonical idea is present on the same surface:

> One human, multiple AI harnesses, shared project state — a hybrid workgroup
> that stays in sync.

Do not use “OS,” “native harness,” or “standalone execution runtime” as the
primary product category. A future native-runner experiment can remain an
implementation detail or research proposal without changing the positioning.

## Application rule

- Homepage, README hero, release pitches, and competitive material lead with
  measurement, arbitration, routing evidence, and verified job truth.
- Onboarding and day-in-the-life examples may use the hybrid-workgroup
  metaphor, but never without the arbitration explanation nearby.
- New features expand the trust and coordination capabilities of the
  arbitration layer; feature velocity does not promote the metaphor into a
  competing category.

## Completed-feature status update

- Dispatch reconciliation now preserves jobs with real exit markers or
  completed work instead of misclassifying them as zombies.
- Daemon job claims are released and committed safely, while uncertain
  follow-up reads fail closed for a later reconciliation attempt.
- The resulting job truth supports synlynk's arbitration promise by keeping
  operator status and verification evidence aligned under concurrent load.
