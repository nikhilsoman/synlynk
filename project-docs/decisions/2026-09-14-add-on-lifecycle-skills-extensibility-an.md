<!-- generated - source of truth is state.db -->
---
decision_id: dec-494eb4f5
topic: "Add-on Lifecycle, Skills Extensibility, and Graphify AST Integration"
date: 2026-09-14
panel: [claude, agy]
status: approved
---

## Topic
Add-on Lifecycle, Skills Extensibility, and Graphify AST Integration

## Panel Inputs

### claude
Add-on Lifecycle, Skills Extensibility, and Graphify AST Integration — panel input:

**Framing.** This bundles three concerns that should be evaluated on different axes: (1) add-on lifecycle is a distribution/trust problem, (2) skills extensibility is a capability/composability problem, (3) Graphify AST integration is a technical-risk problem (parsing correctness across languages, staleness of the graph vs. live code). Treating them as one workstream risks scope creep — the kind that's already bitten this project (the 24-PR backlog, the harness-fence standardization gaps). I'd want each to ship as its own themed PR cluster, not one mega-feature.

**Add-on lifecycle.** The install/update/uninstall path needs the same rigor as the GitHub App naming/role work just shipped (#1570) — versioned manifests, a clear compatibility contract against synlynk core versions, and explicit deprecation/removal semantics. Given the repo's existing pattern of "capability isn't static, reassess on a cadence" (harness capability baseline protocol), add-ons should get an analogous reassessment cadence rather than install-and-forget.

**Skills extensibility.** synlynk already treats Agent vs. Harness as a first-class distinction; skills-as-extensibility should slot into that model rather than becoming a third parallel concept. Recommend: skills are declarative capability grants scoped to a role/charter, not arbitrary code — keeps the security surface bounded and matches the existing opt-in-at-init, nothing-breaks-without-agents design principle already on record.

**Graphify AST.** Highest technical risk of the three. AST-based codebase graphing is valuable for Vizor's Architect Map, but only if kept in sync — a stale graph that looks authoritative is worse than no graph (echoes the "job-status alone isn't sufficient evidence" lesson from #1377/#1436). Needs a clear invalidation trigger (file-save, git hook, or explicit refresh) and a "confidence/last-updated" indicator in the UI so users don't trust stale data.

**Recommendation:** Sequence as three separate specs under Brainstorm-First Policy, in this order: skills extensibility first (it's foundational and low external risk), add-on lifecycle second (depends on skills model being settled), Graphify AST last (highest implementation risk, benefits from the other two being stable). Do not attempt a combined design doc — the three have different failure modes and reviewers.

## Synthesis
## Synthesis: Add-on Lifecycle, Skills Extensibility, and Graphify AST Integration

The panel input converges on a single structural point: these three items share a name ("extensibility") but not a risk profile, and bundling them invites the same scope creep this project has already paid for (24-PR backlog, harness-fence drift, #1436-style half-authorized fixes). Each needs its own spec under Brainstorm-First Policy, not a combined design doc, because they fail differently — add-on lifecycle fails as a trust/versioning problem, skills fail as a security-surface problem, Graphify fails silently as stale-but-authoritative data (the same class of failure as #1377/#1436, where a green status hid a real gap).

Sequencing matters and should follow dependency, not urgency: skills extensibility first, since it's foundational, lowest external risk, and maps cleanly onto the Agent-vs-Harness distinction already established in the glossary — skills should be declarative, role-scoped capability grants, not arbitrary code, consistent with the opt-in-at-init / nothing-breaks-without-agents principle on record. Add-on lifecycle second, since its manifest/versioning/compatibility contract depends on the skills model being settled — and it should inherit the same "reassess on a cadence, don't install-and-forget" discipline as the harness capability baseline protocol. Graphify AST last, as the highest-risk item technically: it must ship with an explicit invalidation trigger and a visible confidence/last-updated indicator, or it becomes exactly the kind of unverifiable-but-trusted signal this project has been burned by before.

**Decision:** Split this into three separate specs under Brainstorm-First Policy — skills extensibility, add-on lifecycle, and Graphify AST integration — sequenced in that order, each gated on the prior one's spec being committed and approved before the next starts. No combined design doc, no combined PR cluster. Skills extensibility must define capability grants as declarative and role/charter-scoped. Add-on lifecycle must define versioned manifests, a core-version compatibility contract, deprecation semantics, and a periodic reassessment cadence. Graphify AST must define its invalidation trigger and ship a staleness/confidence indicator in the UI before it's considered mergeable.

## Decision
**Decision:** Split this into three separate specs under Brainstorm-First Policy — skills extensibility, add-on lifecycle, and Graphify AST integration — sequenced in that order, each gated on the prior one's spec being committed and approved before the next starts. No combined design doc, no combined PR cluster. Skills extensibility must define capability grants as declarative and role/charter-scoped. Add-on lifecycle must define versioned manifests, a core-version compatibility contract, deprecation semantics, and a periodic reassessment cadence. Graphify AST must define its invalidation trigger and ship a staleness/confidence indicator in the UI before it's considered mergeable.

> Signatures: see 2026-09-14-add-on-lifecycle-skills-extensibility-an.json
