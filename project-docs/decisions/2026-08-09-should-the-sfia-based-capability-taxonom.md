---
decision_id: dec-fd8d09d7
topic: "Should the SFIA-based capability taxonomy (synlynk/taxonomy_standards.py SFIA_CODES, synlynk/capability_sweep.py) play a role in defining synlynk's new 8-role org chart (pm, architect, tpm, dev, designer, qa, marketing + synlynk-bot infra identity)? Evaluate specifically across five angles and give a recommendation for each: (1) Could SFIA help set up workspace-specific roles better -- i.e. help a new project pick which of the 8 roles it actually needs and how to scope them for its domain? (2) Could SFIA help define role charters better -- giving each role's responsibilities a grounded, standard vocabulary instead of ad-hoc prose? (3) Could SFIA help identify role-specific tools and services -- inferring what tools/integrations a role needs by picking up on SFIA skill-category conventions even where SFIA itself doesn't explicitly define tooling? (4) Could SFIA help measure a given agent+harness combination (e.g. Claude+Sonnet, Codex+gpt, Grok) and adapt that role's behavior/tool-agent choice over time based on measured capability drift, reusing capability_sweep.py's existing calibration mechanism? (5) Would grounding roles in SFIA make a workspace's roles portable/valuable as reusable execution agents in OTHER workspaces -- i.e. is this a meaningful building block toward the future Tokq cross-repo agent marketplace? For each angle give a clear yes/no/partial and a one-sentence justification, then give one overall recommendation: should this spec incorporate SFIA now, defer it, or reject it as unnecessary."
date: 2026-08-09
panel: [claude, agy, codex]
status: approved
---

## Topic
Should the SFIA-based capability taxonomy (synlynk/taxonomy_standards.py SFIA_CODES, synlynk/capability_sweep.py) play a role in defining synlynk's new 8-role org chart (pm, architect, tpm, dev, designer, qa, marketing + synlynk-bot infra identity)? Evaluate specifically across five angles and give a recommendation for each: (1) Could SFIA help set up workspace-specific roles better -- i.e. help a new project pick which of the 8 roles it actually needs and how to scope them for its domain? (2) Could SFIA help define role charters better -- giving each role's responsibilities a grounded, standard vocabulary instead of ad-hoc prose? (3) Could SFIA help identify role-specific tools and services -- inferring what tools/integrations a role needs by picking up on SFIA skill-category conventions even where SFIA itself doesn't explicitly define tooling? (4) Could SFIA help measure a given agent+harness combination (e.g. Claude+Sonnet, Codex+gpt, Grok) and adapt that role's behavior/tool-agent choice over time based on measured capability drift, reusing capability_sweep.py's existing calibration mechanism? (5) Would grounding roles in SFIA make a workspace's roles portable/valuable as reusable execution agents in OTHER workspaces -- i.e. is this a meaningful building block toward the future Tokq cross-repo agent marketplace? For each angle give a clear yes/no/partial and a one-sentence justification, then give one overall recommendation: should this spec incorporate SFIA now, defer it, or reject it as unnecessary.

## Panel Inputs

### claude
This is a code-review/decision-panel style analysis, not creative work, so brainstorming doesn't apply here. I'll answer directly.

**(1) Workspace-specific role scoping — Partial.** SFIA's skill categories (e.g., "Systems design," "Data management," "Quality assurance") give a checklist to sanity-check whether a workspace even needs a `designer` or `qa` role, but the 8-role split is already coarser than SFIA's ~120 skills, so SFIA can prune/justify roles more than it can *generate* new scoping logic.

**(2) Role charter vocabulary — Yes.** This is SFIA's actual design purpose — standardized skill descriptions at defined proficiency levels — so mapping each of the 8 roles to a cluster of SFIA codes replaces ad-hoc prose with an externally auditable definition, and it's low-effort since `SFIA_CODES` already exists in-repo.

**(3) Tooling inference — No.** SFIA is explicitly tool-agnostic by design (it describes skills and responsibility levels, not implementations), so inferring "this role needs Playwright vs. Selenium" from an SFIA code requires a synlynk-authored mapping layer sitting *outside* SFIA — SFIA gives no signal here beyond category names.

**(4) Capability drift measurement — Partial.** `capability_sweep.py` already does empirical calibration against real task outcomes; SFIA proficiency levels (1-7) could give that calibration a normalized *reporting* scale ("this Codex+gpt combo is currently SFIA level 3 on role X"), but SFIA itself has no mechanism for measuring agent/harness drift — the sweep mechanism would still be doing all the actual work.

**(5) Cross-workspace portability / Tokq marketplace — Yes.** This is the strongest case: an externally-recognized standard (vs. synlynk's own prose) is exactly the kind of common vocabulary a marketplace needs so a "pm" role defined in one workspace is legible and comparable in another, which directly serves the Tokq agent-marketplace direction already in memory.

**Recommendation: defer, not reject.** The clear win (#2 charters, #5 portability) is real but not urgent for the initial 8-role org chart — ship the org chart with plain-prose charters now, and revisit SFIA-grounding as a follow-up PR once Tokq's cross-repo marketplace work actually starts (that's when #5's payoff materializes and justifies the mapping effort for #2 and #4). Incorporating it now adds scope to a spec that doesn't yet need external standardization to function.

### agy
**Last completed task:** Perform structured technical code review of PR #51 (Codex Headless Dispatch)  
**Next task:** Refine decision flow templates for agents  

### Evaluation of SFIA in Synlynk's 8-Role Org Chart

1. **Workspace-Specific Role Selection & Scoping:** **Yes.** SFIA's standardized skill codes and responsibility levels (Levels 1–7) allow new projects to programmatically select and bound the exact subset of the 8 roles required for their domain context.
2. **Role Charters & Vocabulary:** **Yes.** Grounding role charters in SFIA skill definitions provides an authoritative, industry-standard vocabulary that eliminates prompt ambiguity and prevents responsibility drift.
3. **Role-Specific Tools & Services Inference:** **Partial.** While SFIA skill categories (e.g., `PROG`, `TEST`, `DESN`) provide logical domain groupings, inferring exact API and CLI tool bindings still requires a secondary metadata overlay.
4. **Agent Performance Measurement & Calibration:** **Yes.** Reusing `capability_sweep.py` against SFIA competency levels enables continuous benchmarking of agent-harness pairings (e.g., Claude+Sonnet, Codex+gpt, Grok) to dynamically optimize role dispatch based on measured capability drift.
5. **Cross-Repo Agent Portability (Tokq Marketplace):** **Yes.** Grounding roles in SFIA establishes a standardized capability schema, making agent execution profiles portable, composable, and verifiable across external workspaces and repositories.

### Recommendation
**Incorporate SFIA now.** Grounding the 8-role org chart (`pm`, `architect`, `tpm`, `dev`, `designer`, `qa`, `marketing`, `synlynk-bot`) in the SFIA taxonomy provides immediate structural clarity for agent charters and runtime benchmark sweeps while establishing the foundational protocol needed for future Tokq cross-repo marketplace portability. Deferring SFIA would lead to ad-hoc prompt charters that must be rewritten and re-calibrated later.

### codex
1. **Workspace-specific role selection: Partial.** SFIA can expose capability areas a project needs (e.g., `ARCH`, `PROG`, `TEST`, `DEPL`), but it does not determine staffing: project topology, lifecycle, risk, domain, and desired autonomy must also be inferred.

2. **Role charters: Partial.** SFIA supplies useful, grounded vocabulary for responsibilities, but its competency labels are not complete charters; roles also need decision rights, deliverables, boundaries, collaboration rules, and workspace-specific outcomes.

3. **Role-specific tools/services: No, except as a weak input.** SFIA categories describe capabilities, not integrations. `METL`, `DEPL`, or `SCTY` may suggest tool classes, but selecting GitHub, Figma, CI, cloud, CRM, or observability services requires stack, workflow, permissions, and domain evidence. Existing `stack_tags` and workspace scanning are better signals.

4. **Measuring agent+harness combinations: Partial, with a promising foundation.** `capability_sweep.py` already provides independently verified calibration, cost guardrails, model-versioned ratings, and decay toward organic evidence. However, it currently tests only `PROG`, `TEST`, and `REQM`; calibration tasks are not role-specific, the loop does not visibly bind the selected model into dispatch, and seeded rows do not establish meaningful per-role behavior. It should evolve into role/task/stack-specific evaluation before driving adaptation.

5. **Portability to other workspaces: Partial.** SFIA codes make capability evidence more comparable across repositories and agents, which is useful for a future Tokq marketplace. But portable execution agents require versioned charters, tool contracts, permission profiles, identity, domain overlays, and trustworthy performance evidence—not merely taxonomy labels.

**Overall recommendation: defer SFIA as a defining dependency, but retain it as an optional capability vocabulary and measurement dimension.** The eight roles should first be specified around stable charters, inputs/outputs, permissions, tools, and workspace composition. Then SFIA can annotate those contracts and strengthen capability-sweep calibration. Making the new org chart SFIA-native now would overstate what the current taxonomy and sweep can support, while discarding them would waste a useful interoperability and measurement foundation.

## Synthesis
Decision: Incorporate SFIA now, but scoped narrowly — as a role-charter vocabulary layer (#2) and an optional annotation dimension for `capability_sweep.py` calibration (#4), not as the mechanism for role scoping (#1), tool inference (#3), or marketplace portability (#5), which all need synlynk-authored logic SFIA can't supply.

All three reviewers converge on the same shape once you net out the disagreement: Agy's "yes across the board" collapses under Codex's and my own scrutiny — SFIA is explicitly tool-agnostic and non-generative (no staffing logic, no tool bindings, no charter completeness), so #1, #3, and #5 are at best partial inputs that still require a synlynk-built mapping/overlay layer to do the real work. But #2 is a genuine, low-cost win right now: `SFIA_CODES` already exists in-repo, and replacing ad-hoc prose charters with SFIA-grounded vocabulary is cheap and immediately auditable — no reason to defer it. #4 is the more interesting case: `capability_sweep.py` already does real empirical calibration (Codex correctly notes it currently only covers PROG/TEST/REQM and isn't yet role-bound), so SFIA can't drive the adaptation logic, but tagging sweep results with SFIA proficiency levels gives the *existing* calibration a normalized reporting scale for free — worth wiring in alongside charters rather than as a separate future effort. #1, #3, and #5 should be explicitly deferred: write the 8-role org chart with plain scoping logic and tool bindings now, note SFIA-annotation as a stated future enhancement, and revisit #5's marketplace-portability case when Tokq's cross-repo work actually starts, since that's the point where an external standard's payoff (comparability across independently-authored roles) materializes — building it in now would be speculative scope on a spec that doesn't yet have a second workspace to be portable *to*.

## Decision
Decision: Incorporate SFIA now, but scoped narrowly — as a role-charter vocabulary layer (#2) and an optional annotation dimension for `capability_sweep.py` calibration (#4), not as the mechanism for role scoping (#1), tool inference (#3), or marketplace portability (#5), which all need synlynk-authored logic SFIA can't supply.

> Signatures: see 2026-08-09-should-the-sfia-based-capability-taxonom.json
