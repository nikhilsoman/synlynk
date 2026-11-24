<!-- generated - source of truth is state.db -->
---
decision_id: dec-4c89c11b
topic: "Maintainer full autonomy (re-review): docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md + docs/superpowers/plans/2026-11-24-maintainer-full-autonomy.md (14 tasks, goal-8248294f, tracking issue #5510) — revised to close all 5 defects from the 2026-11-24 conditional-approval panel (role-aware typed registry; dry-run/promotion boundary with audit+cap+dedupe; evidence-weighted proximal selection with config thresholds + recorded tier_provenance; generalized multi-source Proposal Studio data layer in synlynk/roadmap_studio.py with normalize_proposal_for_studio adapter; versioned taxonomy/domain-pack schemas with validate-or-fallback). grok excluded (402 balance exhausted), agy excluded (headless command timed out on prior attempt this session). Confirm all 5 defects are closed and re-approve for dispatch, or flag remaining gaps."
date: 2026-11-24
panel: [claude, codex]
status: approved
---

## Topic
Maintainer full autonomy (re-review): docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md + docs/superpowers/plans/2026-11-24-maintainer-full-autonomy.md (14 tasks, goal-8248294f, tracking issue #5510) — revised to close all 5 defects from the 2026-11-24 conditional-approval panel (role-aware typed registry; dry-run/promotion boundary with audit+cap+dedupe; evidence-weighted proximal selection with config thresholds + recorded tier_provenance; generalized multi-source Proposal Studio data layer in synlynk/roadmap_studio.py with normalize_proposal_for_studio adapter; versioned taxonomy/domain-pack schemas with validate-or-fallback). grok excluded (402 balance exhausted), agy excluded (headless command timed out on prior attempt this session). Confirm all 5 defects are closed and re-approve for dispatch, or flag remaining gaps.

## Panel Inputs

### claude
[model=sonnet; version=2.1.327 (Claude Code)]

**Verdict: all five defects are closed on paper. I'm approving for dispatch with two conditions.**

I read the spec and plan structure and grepped them. I did not read all 3,000 plan lines or run any code.

**Closure check**
1. **Role-aware typed registry.** Spec §5.2 and Task 4 cover it. The `FieldSpec` and `filter_schema` types are defined, and Task 13 renders its form controls from them.
2. **Dry-run/promotion boundary.** Spec §5.3a covers all five guards: audit entry, per-cycle cap, dedupe, rate limit, and no host-token fallback. The spec's tests include a forbidden-`gh` assertion in dry-run. Task 6 implements the audit log, the cap, and a dedupe against that log.
3. **Evidence-weighted proximal selection.** Thresholds come from config (`join_threshold`). Tie-breaking is deterministic. `tier_provenance` is returned by Task 5 and carried to proposals through the Task 13 Step 0 wiring.
4. **Proposal Studio data layer.** The correction in Task 14 is the strongest part of this revision. The adapter belongs in `synlynk/roadmap_studio.py`, which serves `/api/roadmap_studio`, not in the JS-shell module `synlynk/viz/roadmap_studio.py`. The plan says it verified this against the `server.py:305` import.
5. **Versioned schemas with fallback.** `schema_version` is validated in both loaders. An unknown version, bad JSON, or a missing file falls back to built-in defaults. Pack precedence is documented, and a bad pack is skipped whole rather than partially merged.

**Remaining gaps, to fix at or before dispatch**
- **Dedupe mismatch.** Spec §5.3a says dedupe searches existing open GitHub issues by finding signature. The Task 6 code I saw dedupes only against the local audit JSON. That misses issues opened by humans or by other runs. Either have Task 6 also query GitHub, or amend the spec to say local-only dedupe is the v1 scope. I recommend the first.
- **Spec/plan drift.** The spec says the audit log is `.jsonl` or the telemetry log, "decided at plan time". The plan uses `.synlynk/maintainer_promotion_audit.json`, which is read, appended, and rewritten whole. That is not concurrency-safe, and the GitHub Actions concurrency group only covers CI runs. Use append-only JSONL, or add a file lock.
- **Rate limit.** I found no rate-limit step in Task 6's promotion path. Confirm it exists or record it as deferred.

**Dispatch order**
The hold markers are right. Run the foundation wave (Tasks 1–4) and then Task 5. Hold Task 13 until Task 5 merges, and Task 14 until Tasks 1–6 merge. Dispatch should go through `synlynk dispatch` to codex and claude. Grok and agy are excluded for now.

**Position:** I approve the revised spec and plan for dispatch, starting with the foundation wave. Two of the gaps above, dedupe against GitHub and the audit-log concurrency, must be fixed in Task 6 before Task 6 is dispatched. The remaining items can be fixed in review.

### codex
[model=default; version=codex-cli 0.172.0]

The role-aware registry defect is substantially closed: Task 4 defines stable `<role>:<name>` IDs, role filtering, typed `FieldSpec`s, and unknown-config-key rejection. The Proposal Studio adapter direction is also correct: Task 14 normalizes TPM stories/backlog and merges Maintainer proposals in the served `synlynk/roadmap_studio.py` data path.

However, I cannot re-approve dispatch because the remaining plan does not implement several claimed safeguards. The promotion boundary is materially incomplete: Task 6 audits only once per promoted action and does so after the action runs; it caps actions rather than individual external writes; `_ensure_github_issue_for_story()` has neither finding-signature dedupe nor rate limiting; and dry-run stages stories without `github_issue`, contradicting the promised non-null proposal-story contract.

The proximal-selection implementation is not executable as written: it imports a nonexistent `read_traversal_cache()` helper, while the actual graph-cache module exposes traversal-path helpers rather than an `adjacency` map. It also collapses `reverse_doc_index`, `issues_and_prs`, and `code_references` into an inaccurate shared set, omits the separately configured evidence weights required by the spec, and lacks the promised fixtures for these signals.

The shared `Proposal` schema remains an ad-hoc JSON/dict convention: no shared schema module or validation boundary is planned, so source-specific records can drift despite the normalization adapter. Finally, taxonomy/domain-pack validation only checks JSON object/version; it does not validate required field shapes, string lists, or non-negative numeric weights as §6 requires, and therefore cannot reliably provide validate-or-fallback behavior.

My position: do not approve for dispatch yet. Approve only the foundation registry work if separately scoped; revise Tasks 1–2, 5–6, and 14 to close the above gaps, then re-run the decision panel.

## Synthesis
Both reviewers agree the registry and Proposal Studio adapter are sound. They disagree on dispatch readiness. I side with Codex on Tasks 5, 6 and 14, because its objections are concrete defects in the plan. Claude's approval was based on a lighter read, and it said it did not read the full plan or run code.

**Closure status of the five defects**
1. **Role-aware typed registry:** closed. Both reviewers confirm it (Task 4, stable `<role>:<name>` IDs, `FieldSpec`s, unknown-key rejection).
2. **Dry-run/promotion boundary:** not closed. Codex found that Task 6 writes the audit entry after the action runs, caps actions rather than external writes, and has no finding-signature dedupe or rate limit in `_ensure_github_issue_for_story()`. Claude independently found that dedupe is local-only and that the audit log is not concurrency-safe. Codex also noted that dry-run stories lack `github_issue`, which contradicts the proposal-story contract.
3. **Evidence-weighted proximal selection:** not closed. Task 5 imports a `read_traversal_cache()` helper that doesn't exist. It also merges three evidence signals into one set, leaves out the separately configured weights, and has no fixtures for these signals.
4. **Proposal Studio data layer:** the adapter placement in `synlynk/roadmap_studio.py` is correct. The shared `Proposal` schema is still an unvalidated dict convention, so source-specific records can drift.
5. **Versioned schemas with fallback:** only partly closed. Validation checks JSON-object shape and version, but not required fields, string lists or non-negative weights, as spec §6 requires. Validate-or-fallback therefore can't be relied on.

**Required revisions**
- **Task 6:**
  - Write the audit entry before each external write, in append-only JSONL.
  - Count the cap per external write.
  - Dedupe against open GitHub issues by finding signature, as well as against the audit log.
  - Add the rate limit.
  - Give dry-run stories a defined `github_issue` placeholder, or amend the contract.
- **Task 5:** use the real graph-cache API, keep the three evidence sources separate, apply the configured weights, and add fixtures for each signal.
- **Task 14:** add a shared `Proposal` schema module with a validation boundary.
- **Tasks 1–2:** validate field shapes and weight ranges, with fallback on failure.

**Dispatch**
- **Task 4:** it can go now as a separately scoped foundation task, since both reviewers accept it.
- **Tasks 1–3:** hold them until the Tasks 1–2 validation revision is in the plan.
- **Tasks 5, 6, 13 and 14:** hold them until the plan is revised.
- **Re-review:** re-run the panel after the revision. Grok and Agy are still excluded.

Decision: Do not approve the full plan for dispatch yet. Approve Task 4 alone for dispatch now. Revise Tasks 1–2, 5, 6 and 14 as listed above, then re-run the decision panel before dispatching anything else.

## Decision
Decision: Do not approve the full plan for dispatch yet. Approve Task 4 alone for dispatch now. Revise Tasks 1–2, 5, 6 and 14 as listed above, then re-run the decision panel before dispatching anything else.

> Signatures: see 2026-11-24-maintainer-full-autonomy-re-review-docs.json
