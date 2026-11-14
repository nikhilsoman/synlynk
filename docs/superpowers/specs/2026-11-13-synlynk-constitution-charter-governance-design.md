# The Synlynk Constitution: Charter Governance & RSI-Gated Instruction Effectiveness

**Date:** 2026-11-13
**Status:** Approved
**Audience:** Internal governing law only — not a customer-facing document.
**Roadmap entry:** Resolves the "full Synlynk Constitution/Charter" item deferred in `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md`'s Deferred section. That spec's "Semantic Laws Seed Doc" (Asimov Laws 0–3 + Intent-Based Engineering invariant) was designed but never written to disk at `docs/strategy/synlynk-constitution.md` — confirmed absent via `ls`, `cat`, and `git log --all` for that path. **This spec is that seed doc, upgraded to a full governance design** — it supersedes the never-written stub rather than leaving it to be written separately.

---

## Context

Three things already exist and must not be re-derived here:

- **The four Asimov Laws are already implemented in code**, not just designed: `evaluate_asimov_invariants()` in `synlynk/tpm_sweep.py` (lines 58–90) checks Law 0 (Secrets/System Integrity, via forbidden-pattern match), Law 1 (Human Sovereignty, via required role attribution), Law 2 (Evidence Over Assertions), and Law 3 (Metered Self-Preservation, a 200k-token estimate ceiling) at every TPM-sweep dispatch-readiness check. This spec promotes them from code-only enforcement to canonical written law, cited by name and number everywhere downstream.
- **The organizational/operational layer is already fully specified**: `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` owns the 8-role org chart, role→harness dispatch policy, GOVERNS integration, and the 4-phase Agent-vs-Harness roadmap (Terminology → Agent manifest → Memory+gated learning → Capability registry → Portability). **This spec does not re-specify any of that.** The Constitution is the *normative law* layer; the 2026-08-09 spec is the *organizational* layer it governs.
- **The RSI/Harness² machinery is already ratified for a different purpose**: `docs/superpowers/specs/2026-11-10-autonomous-fleet-orchestrator-and-organogram-designer-design.md` (ratified via `dec-4a53a2ee`, 3 Binding Amendments, target v0.31.0) defines Google Research's Harness² — **Propose → Probe → Compose** — an RSI Reliability Engine, an L1→L2→L3 agent-autonomy ladder, and (Binding Amendment 3) a **Non-Self-Interested Ledger**: autonomy promotion/demotion is measured strictly by Sentinel/Inspector, never agent self-report, and promotion is never self-granted. This spec **reuses that methodology**, applied to a different scored entity (see Section 3) — it does not duplicate or modify the agent-autonomy RSI score itself.

**Naming note:** this spec's "laws" are numbered Law 0–3, matching `evaluate_asimov_invariants()`'s existing numbering exactly, so citation tags introduced in Section 2 need no renumbering of already-shipped code.

---

## 1. The Constitution as Source of Truth

The Constitution (this document) is the single canonical source for:

- **Law 0 — Secrets & System Integrity.** No artifact, harness output, or dispatched job may expose secrets, credentials, or system-integrity-breaking content. Enforced today via forbidden-pattern matching in `evaluate_asimov_invariants()`.
- **Law 1 — Human Sovereignty.** Every dispatched unit of work carries required role attribution back to an accountable identity; no anonymous or unattributed autonomous action. Enforced today via required-attribution checks in the same function, and structurally via the Hardened PR Review Policy's prohibition on personal-GitHub-token use by any agent/harness.
- **Law 2 — Evidence Over Assertions.** A claim of completion, verification, or success must be backed by directly-checked evidence (a diff, a test run, a `gh pr view --json`), never inferred from a status label or a harness's own self-report. This is the same principle already operating informally throughout `[[feedback]]` (job-status false-negative RCA, PR-review discipline) — the Constitution makes it a named, numbered law rather than scattered practice.
- **Law 3 — Metered Self-Preservation.** Autonomous execution is cost-bounded; a 200k-token estimate ceiling gates dispatch readiness today, extensible to other budget/circuit-breaker signals (`TOKEN_CIRCUIT_BREAKER_TRIPPED`, the 2x-consecutive-failure demotion trigger already defined in `dec-4a53a2ee`).
- **The Intent-Based Engineering invariant** (not a numbered law — a standing design invariant): every unit of dispatched work traces to a captured human intent (a GOVERNS goal/story), never to an un-sourced ad hoc instruction. This is the normative backing for the existing "100% GOVERNS adherence" gate.

Both **Harness Instructions** (`CLAUDE.md`, `GEMINI.md`, `AI_INSTRUCTIONS.md`, per-harness sections) and **Agent Charters** (the 8 role charters from the 2026-08-09 spec) are now *governed artifacts*: every clause in either must trace to one of the four laws or the Intent-Based Engineering invariant. Clauses that trace to nothing, and laws nothing traces to, are both drift — Section 2 builds the mechanism that detects this the same way `check_pr_roadmap_gate` already detects roadmap drift.

## 2. Generation Pattern — Approach C (Hybrid)

Two delivery mechanisms, matched to stakes, not one uniform mechanism for every law:

**Highest-stakes laws → generated bearings block.** A short, single-sourced, byte-identical block — the exact mechanism already being built for gh:#5233 (naming `tpm wake`/`tpm sweep`, `dispatch --as-agent <role>`, "PR findings = dispatched review, not a fix menu") — generalized so its *source* is this Constitution document, not an ad hoc hand-written card. Injected at session/job start the same way a role charter already is. Reserved for laws that have, or are likely to have, real-world miss-rate (Section 3 makes this a measured decision, not a one-time editorial choice).

**Everything else → citation + drift-gate.** Every Harness Instruction clause and Agent Charter field carries a citation to the law/invariant it implements (a frontmatter tag or inline marker, e.g. `<!-- constitution: law-1 -->`). A new gate — architecturally identical to `check_pr_roadmap_gate`, reusing its `observe|enforce` phase-in pattern via a new `constitution_authority.require_citation_mode` key in `.synlynk/policy.json` — flags two drift conditions on every PR touching `CLAUDE.md`/charter files: **orphaned laws** (a law/invariant no artifact cites) and **orphaned clauses** (a clause citing nothing). Starts in `observe` mode, same discipline as every other gate introduced this way.

## 3. RSI-Gated Instruction Effectiveness

This is the extension the user's most recent instruction requires: Harness Instruction and Agent Charter content must itself be subject to Recursive Self-Improvement, using Sentinel triage and RCAs as the evidence base — reusing Harness²'s methodology, not inventing a parallel one.

**A second, distinct ladder** — the **Delivery Tier** of a law's instantiation — modeled on but independent of the agent L1→L2→L3 autonomy ladder:

| Tier | Mechanism | When assigned |
|---|---|---|
| 1 — Prose | Mentioned in Harness Instruction/Charter text only | Default for every law/invariant at authoring time |
| 2 — Cited | Citation tag, checked by the Section 2 drift-gate | Default once the gate goes live; nearly all clauses live here |
| 3 — Injected | Baked into the generated bearings block | Reserved for laws with measured real miss-rate (below) |

**Evidence base — Sentinel triage + RCAs, never self-report.** This reuses `dec-4a53a2ee`'s Binding Amendment 3 Non-Self-Interested Ledger invariant exactly: measurement is done by Sentinel (`check_sentinel_patterns`'s pattern alerts, written to `sentinel.md`) and by Inspector-role review (independent, non-authoring), never by the harness or agent whose instruction is in question. Two existing artifact types gain one new field each — not a new artifact type:

- **Sentinel triage alerts** (`sentinel.md` entries) gain: `constitution_law: <Law N | invariant-name | none>`.
- **Sev1 RCA docs** (`docs/rca/YYYY-MM-DD-LIVE-N-<slug>.md`) gain a line in their root-cause section naming which law/invariant (if any) the incident's root cause traces to — exactly the kind of tagging the #5233 RCA already did informally (three missing bearings-card behaviors) without a formal field for it.

**Propose → Probe → Compose, applied to instruction text:**
- **Propose** — a law's rolling miss-count (tagged Sentinel alerts + RCAs over a window) crosses a threshold → a tier-promotion candidate surfaces (Prose→Cited or Cited→Injected). Symmetrically, a Tier-3 law with zero misses over a long window surfaces as a **demotion candidate**, for cost containment — the bearings card must stay short, per the #5233 RCA's own constraint, and this gives that constraint a quantitative trigger instead of leaving it to editorial judgment alone.
- **Probe** — the candidate is reported, not applied, starting in `observe` mode — same phase-in discipline as every other gate in this repo. Verification stays strictly on the non-self-interested ledger: a harness that was the subject of a miss cannot self-clear it.
- **Compose** — the actual instruction-text edit (or bearings-card regeneration) is drafted but **never auto-applied**. Promotion (and demotion) require explicit human or acting-PM-role confirmation — mirroring the agent-autonomy ladder's own invariant that promotion is never self-granted.

**Numeric thresholds are deferred to the implementation plan**, not fixed here — this spec establishes the mechanism and the non-self-interested measurement discipline, not the exact miss-count that triggers a Propose event.

## 4. Relationship to the 2026-08-09 and 2026-11-10 Specs

- **vs. 2026-08-09 (Agent Roles & Charters):** unchanged. This spec adds governance *over* charter content; it does not touch the role roster, dispatch policy, or GOVERNS integration that spec already owns.
- **vs. 2026-11-10 (Autonomous Fleet Orchestrator / Harness²):** this spec borrows the RSI *methodology* (non-self-interested ledger, human-confirmed promotion, automatic-but-flagged demotion) and applies it to a **different scored entity** — an instruction clause's delivery tier, not an agent's autonomy level. The two RSI instances are parallel, not merged: an agent's L1/L2/L3 score and a law's Prose/Cited/Injected tier are tracked independently, in different tables, and a change to one never silently changes the other.
- **Open question, explicitly flagged and not resolved here:** how the 2026-11-10 spec's 6 universal archetypes (orchestrator/strategist/director/creator/inspector/custodian) relate to the 2026-08-09 spec's 8 named roles (pm/architect/tpm/dev/designer/qa/marketing/synlynk-bot) — most likely the named roles are synlynk's own SWE-domain Domain Profile Pack instantiation of the universal archetypes, but this belongs to the 2026-11-10 spec's own rollout sequencing, not to this Constitution spec.

## 5. Reconciliation With Existing Policy

- **Drift-governance spec:** this spec supersedes its never-written "Semantic Laws Seed Doc" stub entirely — no separate `docs/strategy/synlynk-constitution.md` file is needed; this document *is* the seed, upgraded.
- **Hardened PR Review Policy / GOVERNS:** unchanged and reinforced — Law 1 (Human Sovereignty) and the Intent-Based Engineering invariant are the normative backing for the personal-GitHub-token prohibition and the 100% linked-goal gate, which were previously enforced by policy alone, without a named law to cite.
- **Empirical Capability Assessment Policy:** unaffected — that policy scores harness×task-type routing from `capability_ratings`/`cost_entries`; this spec's RSI mechanism scores instruction-clause delivery tier from Sentinel/RCA tags. Different inputs, different outputs, no shared table.

## 6. Deferred / Explicitly Out of Scope

- **Full prose drafting of each law beyond the one-paragraph summaries in Section 1** — the summaries here are sufficient to seed citation tags; expanded prose (if needed) is an implementation-plan task.
- **The citation-tag drift-gate's code** (`constitution_authority.require_citation_mode`, the `check_pr_roadmap_gate`-pattern implementation) — separate plan/PR, not built in this spec.
- **The Sentinel-alert and RCA-template schema changes** (`constitution_law` field) — separate small PR.
- **Numeric miss-count thresholds for tier promotion/demotion** — deferred to the implementation plan; this spec fixes the mechanism, not the numbers.
- **The 6-archetype vs. 8-role relationship** (Section 4's open question) — belongs to the 2026-11-10 spec's rollout, not here.
- **SFIA/APQC/NAICS taxonomic grounding** — already scoped to the 2026-11-10 spec; this spec does not extend it.

## 7. Validation Criteria

Before building the citation drift-gate or the Sentinel/RCA schema changes: confirm on at least one already-filed RCA (e.g. gh:#5233's own RCA) that retroactively tagging it with a `constitution_law` value is unambiguous — i.e., the law/invariant it traces to is obvious without forcing a fit. If retroactive tagging is ambiguous on real RCAs, the law definitions in Section 1 need sharper boundaries before the mechanism is built, not after.

---

## Deferred (explicitly out of scope for this spec)

- Full expanded prose per law (Section 6).
- Citation drift-gate implementation (Section 6).
- Sentinel/RCA schema changes (Section 6).
- Numeric promotion/demotion thresholds (Section 6).
- 6-archetype vs. 8-role reconciliation (Section 4, Section 6).
- SFIA/APQC/NAICS taxonomic grounding (Section 6).
