<!-- generated - source of truth is state.db -->
---
decision_id: dec-16e77e5c
topic: "Maintainer full autonomy: docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md + docs/superpowers/plans/2026-11-24-maintainer-full-autonomy.md (14 tasks, goal-8248294f, tracking issue #5510) — review architecture (generic MaintainerActionRegistry, taxonomy-as-config, dual-graph proximal selection, Role Operations Panel, Proposal Studio generalization) before any task is dispatched for implementation. (grok excluded this run: 402 Grok Build usage balance exhausted)"
date: 2026-11-24
panel: [claude, agy, codex]
status: approved
---

## Topic
Maintainer full autonomy: docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md + docs/superpowers/plans/2026-11-24-maintainer-full-autonomy.md (14 tasks, goal-8248294f, tracking issue #5510) — review architecture (generic MaintainerActionRegistry, taxonomy-as-config, dual-graph proximal selection, Role Operations Panel, Proposal Studio generalization) before any task is dispatched for implementation. (grok excluded this run: 402 Grok Build usage balance exhausted)

## Panel Inputs

### claude
[model=sonnet; version=2.1.327 (Claude Code)]

**Panel position: proceed, with four changes before dispatch.** (Grok is excluded from this panel.)

I read spec §5–6 and the plan's task list. I did not read the 2,131-line plan in full.

**What's sound**
- Taxonomy-as-config (T1–T3) and the Domain Pack schema (T2) are correctly first. They are low-risk and unblock everything else.
- The registry (T4) is the right seam. Its value depends on `run_fn` having a strict contract.
- The three-tier proximal selection degrades gracefully, and keyword clustering stays as the fallback.
- Defaulting every action to `dry_run` is the right safety posture for "full autonomy".

**Concerns**
1. **The registry is over-generic for one consumer.** `filter_schema` is a loose dict that's meant to auto-generate UI cards. Either define it as a typed field spec (name, type, default, label) or hand-write the three cards for now. Otherwise T13 ends up reverse-engineering untyped schemas. I recommend typed specs. Registry-driven UI is also what makes the panel reusable by other roles.
2. **Promote mode needs a structural guard.** The spec says `promote` closes GitHub issues and rebuilds the graph. The `maintainer_autonomy` config is the only thing gating that. It should need an explicit per-action opt-in recorded with an audit event (as with gh:#1992), and a per-cycle cap on side effects such as at most N issue closes. That follows the "invariants always hold" principle, because a mis-set filter in promote mode can bulk-close issues.
3. **Auto-opening GitHub issues for orphan findings (§5.3) can flood the tracker.** It needs dedupe against existing issues and a per-cycle rate cap. It also needs a defined `qa`-identity failure path: if no role App token exists, stage nothing rather than fall back to a host token.
4. **Dual-graph proximity is the biggest unknown.** Two graph dependencies with unspecified distance thresholds make behavior hard to test. T5 should ship with a thresholds-in-config setting and a fixture-based test that shows the tier-1/2/3 resolution order. It should also record which tier matched on each proposal, so the Studio can show why a finding joined.
5. **Ordering.** T14 (Studio generalization) changes shared UI and has the largest blast radius. Gate it behind the alias and keep T13 and T14 as separate PRs. Combine T10 and T11, since both are thin trigger wrappers.
6. **Governance.** The plan's goal and tracking issue exist (goal-8248294f, #5510). Generate the stories before dispatch, as the Design → Plan → Build rule says. Route the implementer and reviewer through different harnesses and models, with Grok out this round.

**Recommendation:** approve the architecture. Amend the spec for the typed `filter_schema`, the promote guard and cap, the issue-creation dedupe and rate limit, and the tier-provenance field. Then dispatch T1–T4 first as the foundation wave. Hold T5 until the thresholds are specified, and T13–T14 until the registry contract is proven.

### agy
[model=default; version=1.5.16]

**Last completed task:** Charter v3: fix yaml_subset empty-collection round-trip (`story-efbff7ae`)  
**Next task from `todo.md`:** Maintainer autonomy Task 1: create `synlynk/maintainer_taxonomy.py` + `.synlynk/maintainer_taxonomy.json` (`story-3dba5237`)

---

### Architectural Review: Maintainer Full Autonomy (Goal `goal-8248294f`, Issue #5510)

The architecture specified in [2026-11-24-maintainer-full-autonomy-design.md](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+claude+maintainer-full-autonomy-spec/docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md) and planned in [2026-11-24-maintainer-full-autonomy.md](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+claude+maintainer-full-autonomy-spec/docs/superpowers/plans/2026-11-24-maintainer-full-autonomy.md) soundly elevates Platform Maintainer to parity with TPM through five well-decoupled pillars:

1. **`MaintainerActionRegistry` & Settings Decoupling:** Factoring action discovery and execution into `maintainer_registry.py` separates loop coordination from domain tasks (`sentinel_triage`, `backlog_burndown`, `mesh_sweep`). Enforcing `dry_run` by default and configuring per-action filters directly fixes `scheduler.py`'s discarded triage return values without introducing breaking side effects.
2. **Taxonomy-as-Config & Domain Packs:** Externalizing cluster keywords and remediation topics to `.synlynk/maintainer_taxonomy.json` with a layered loader in `.synlynk/domain_pack.json` removes hardcoded software heuristics. This ensures synlynk-managed repositories in non-code or specialized domains (e.g. rxcc, vdowrx, Hitchcock) can customize vocabulary without upstream code edits.
3. **Dual-Graph Proximal Selection:** The tiered fallback resolution (Code-graph → Doc-graph → Keyword fallback) is an elegant design. When AST signals are sparse, leveraging `docgraph.py` reverse indices ensures proposals group naturally around shared specs and decision records rather than fragmenting into orphaned stories.
4. **Role Operations Panel & Proposal Studio Generalization:** Refactoring `roadmap_studio.py` into a multi-source `proposal_studio.py` (while maintaining backwards-compatible route aliases) and introducing `role_ops_panel.py` provides a reusable control plane for both Agent Studio and the Overview page. The severity-flagged lane for critical sentinel alerts cleanly bypasses clustering volume thresholds.
5. **Execution Plan Rigor:** The 14-task progression strictly follows TDD, pairs every new module with comprehensive unit tests, and correctly sequences registry dependencies before scheduler and UI hooks.

### Recommendation & Position

**Position: APPROVE without reservations.** The proposed architecture is robust, eliminates long-standing operational silos, preserves full backward compatibility, and establishes a portable reference model for subsequent role autonomy efforts. Implementation can proceed with Task 1 immediately.

### codex
[model=default; version=codex-cli 0.172.0]

The direction is sound, but the design is not ready to dispatch unchanged. The main architectural risk is that “generic” components remain Maintainer-shaped in the plan. `MaintainerActionRegistry` hardcodes the `maintainer_autonomy` config namespace and has no `role_slug`, schema validation, persistence contract, or stable action identity; it should instead be a role-aware autonomous-action registry before becoming the reference pattern.

The dual-graph concept is the right portability mechanism, but its planned implementation does not meet the stated design. The proposed code only detects direct code adjacency and shared `reverse_code_index` documents; it omits distance-two traversal, `reverse_doc_index`, and issue/PR evidence. Define one normalized finding/proposal-evidence model, deterministic scoring/tie-breaking, and persisted provenance before implementation.

There is also a critical semantics conflict: dry-run is described as side-effect-free, while proposal staging requires opening a GitHub issue when none exists. Split local staging from promotion, or explicitly classify issue creation as a separately authorized promotion step. GitHub Actions additionally needs least-privilege permissions, concurrency/idempotency controls, and a clear writer identity path—not merely a reference to the QA route.

Proposal Studio needs a data-layer generalization, not only an HTML-function rename. Its current queries and mutation endpoints are `release_proposal`-specific; source, severity, lifecycle, and approval behavior require a shared proposal schema/API or an adapter boundary. Similarly, taxonomy/domain packs need versioned schemas, validation, documented precedence, and safe fallback behavior.

My position: **do not dispatch the 14 tasks yet. Approve the strategic architecture conditionally after revising the spec and plan to establish role-aware registry contracts, complete evidence-based proximal selection, enforce dry-run/promotion boundaries, and generalize the proposal data/API layer first.**

## Synthesis
**Synthesis.** Three panelists took part, and Grok was excluded because its balance is exhausted. Agy approved without reservations. Claude approved with four amendments. Codex said not to dispatch yet. Agy's review didn't test the plan against the code. Claude and Codex raised specific defects, and those are the ones I'm acting on. Claude read the spec but not the full plan. Codex's concerns come from checking the planned implementation against the stated design.

**Where the panel agrees**
- The strategic direction is sound. That covers taxonomy-as-config and Domain Packs, a registry seam, tiered proximal selection with a keyword fallback, and a generalized Studio.
- T1–T3 (taxonomy and Domain Pack schema) are low-risk and correctly first.

**Defects to fix before any implementation dispatch**
1. **Registry contract (Claude and Codex).** `MaintainerActionRegistry` is Maintainer-shaped. It hardcodes the `maintainer_autonomy` namespace and has no `role_slug`, stable action ID or persistence contract. `filter_schema` is an untyped dict. Make it a role-aware autonomous-action registry with typed field specs (name, type, default, label) and schema validation. The Role Operations Panel renders from those specs.
2. **Dry-run and promotion boundary (Codex and Claude).** Dry-run is described as side-effect-free, but staging opens a GitHub issue when none exists. Split local staging, which is free of side effects, from promotion. Issue creation and issue closes belong to promotion only. That step needs an explicit per-action opt-in recorded in the audit log, a per-cycle cap on side effects, dedupe against existing issues, and a rate limit. If no `qa` role App token exists, the action stages nothing and does not fall back to a host token. This matches the standing rule that invariants always hold. GitHub Actions also needs least-privilege permissions, concurrency and idempotency controls, and a named writer identity.
3. **Proximal selection (Codex and Claude).** The planned T5 code doesn't match the spec's design. It omits distance-two traversal, `reverse_doc_index` and issue/PR evidence. Define one normalized finding/evidence model with deterministic scoring and tie-breaking. Put the thresholds in config. Record which tier matched on every proposal. Add a fixture test for tier 1/2/3 resolution order.
4. **Proposal Studio data layer (Codex).** Today's queries and mutation endpoints are specific to `release_proposal`. T14 needs a shared proposal schema and API, or an adapter boundary, covering source, severity, lifecycle and approval. Doing only an HTML rename isn't enough.
5. **Taxonomy and Domain Pack schemas (Codex).** Add versioned schemas, validation, documented precedence and a safe fallback.

**Sequencing changes**
- Fold the registry, promotion-guard and proposal-schema contracts into the spec and plan first.
- Then dispatch T1–T4 as the foundation wave.
- Hold T5 until the thresholds and evidence model are specified.
- Keep T13 and T14 as separate PRs, with T14 behind the route alias. Hold both until the registry contract has been proven.
- Merge T10 and T11, since both are thin trigger wrappers.
- Generate the GOVERNS-linked stories for the revised plan before any dispatch.
- Reviewers must differ from the implementer in harness and model. Grok is out until its balance is restored.

I'd also run the revised spec through `synlynk decide --record` again. I haven't done that or edited the spec or plan yet.

Decision: Approve the architecture conditionally, and do not dispatch any of the 14 tasks yet. First revise the spec and plan to cover five things. These are the role-aware registry with typed `filter_schema`, the split between side-effect-free staging and guarded promotion, the evidence-based proximal-selection model with config thresholds and recorded tier provenance, the generalized proposal data layer, and versioned taxonomy schemas. After the revision, dispatch T1–T4 as the foundation wave. Hold T5 until its thresholds and evidence model are specified. Hold T13–T14 until the registry contract is proven.

## Decision
Decision: Approve the architecture conditionally, and do not dispatch any of the 14 tasks yet. First revise the spec and plan to cover five things. These are the role-aware registry with typed `filter_schema`, the split between side-effect-free staging and guarded promotion, the evidence-based proximal-selection model with config thresholds and recorded tier provenance, the generalized proposal data layer, and versioned taxonomy schemas. After the revision, dispatch T1–T4 as the foundation wave. Hold T5 until its thresholds and evidence model are specified. Hold T13–T14 until the registry contract is proven.

> Signatures: see 2026-11-24-maintainer-full-autonomy-docs-superpower.json
