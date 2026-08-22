# qa Merge-Restricted-Classes — Design

**Date:** 2026-08-22
**Status:** Approved by Nikhil (brainstorm dialogue, this session) — implements the `"merge-restricted-classes"` value reserved (not built) in `docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md` §5.
**Origin:** Named as a future `qa_gate_mode` value in the block-only spec, explicitly deferred because its stated trigger condition — architect and qa diverging in model tier/capability — didn't hold at the time. Revisited this session; see §1.

## 1. Why now, if the trigger condition hasn't changed

Asked directly during the brainstorm: the original trigger condition (architect/qa model-tier divergence) still does not hold — architect and qa still run on the same model tier. The motivation for building this now is different: **throughput**, not capability divergence. Every PR, including a pure docs change, currently waits on architect to click merge even when qa's gate is already green and there is nothing for a second reviewer to meaningfully judge. That's a bottleneck the block-only design didn't address (it only added a block, not a fast path).

This is named explicitly because the block-only spec (§5) treated "switching `qa_gate_mode` away from `block-only`" as requiring the same sign-off gate it went through, tied to a specific trigger condition. That condition is unchanged; the actual justification here is different and is being surfaced to Nikhil as such, not silently substituted.

## 2. Decision

`qa_gate_mode` gains a second live value: `"merge-restricted-classes"`. In this mode, PRs matching a narrow, explicitly-defined class can be merged by qa directly — without waiting on architect — provided the block-only gate (§3 of the block-only spec: CI matrix green + no unresolved sentinel alert) is also green. All other PRs still require architect, exactly as under `block-only`.

**v1 scope: docs-only PRs only.** The block-only spec's own examples named three candidate classes — dependency bumps, CI config, docs-only. This design builds **only the docs-only class** for v1, not all three. Dependency bumps and CI config changes can affect runtime behavior in ways a file-pattern check can't fully rule out (a CI config change can quietly disable a check; a dependency bump can introduce a supply-chain risk) — docs-only is the one class where "touches no code" is both easy to verify mechanically and sufficient to make the risk of an unattended merge genuinely low. Widening to the other two classes is a future increment, not blocked by anything in this design, but deliberately not attempted in the same PR.

## 3. What counts as "docs-only"

A PR is docs-only if every file it touches matches one of:

- `docs/**`
- `*.md` at any path (covers root-level files like `README.md`, `CLAUDE.md`, `CHANGELOG.md`)
- `project-docs/**` (excluding `project-docs/.synlynk_config.json`, which is config, not prose)

Any file outside these patterns — including `.github/workflows/**`, anything under `synlynk/`, `bin/`, `tests/`, `.synlynk/config.json`, or `scripts/` — disqualifies the PR from this class entirely, even if it's the only non-doc file changed. No partial credit: one non-doc file means the PR falls back to requiring architect, same as any other PR under `block-only`.

## 4. Enforcement — CI-native, no agent dispatch

This is a **mechanical** decision: a deterministic file-pattern match against the PR's changed-files list, computed the same way `merge-restricted-classes` eligibility is checked as the block-only gate itself (extending `synlynk pr check` and the `qa-gate` CI job, not a new pipeline). No LLM judgment, no dispatched agent, no semantic reasoning — that is deliberately out of scope for this design (it's a separate concern, covered by the qa completion tracker design, `docs/superpowers/specs/2026-08-22-qa-completion-tracker-design.md`, which is non-blocking and semantic; this design stays blocking and mechanical).

**Why CI-native and not dispatched:** the decision is pure pattern matching over `git diff --name-only` — no reasoning is needed, so routing it through an agent dispatch would add latency and cost for no accuracy gain. This also sidesteps the GitHub-identity limitation entirely (§5).

Two layers, mirroring block-only's enforcement (§4 of that spec):

1. **`synlynk pr check`** computes docs-only eligibility alongside the existing gate verdict, and if both are green, performs the merge directly (`gh pr merge --squash`) instead of leaving it for architect to click.
2. **GitHub branch-protection backstop.** Because merge-restricted-classes changes *who* can merge, not just what blocks a merge, the backstop here is different in kind from block-only's: there is no required-check equivalent for "auto-merge if docs-only," since GitHub's branch protection can require checks but can't itself decide to merge. The backstop instead is that the underlying `block-only` gate (§3 of that spec) still applies unconditionally — if CI or sentinel health is red, the docs-only fast path never fires, regardless of file pattern. A docs-only PR with a red gate still waits for a human, same as any other PR.

## 5. GitHub identity — resolved as a non-issue for this design

The `#423` identity caveat (all dispatched agents share one `gh` login, so GitHub can't verify a distinct reviewer identity) was raised as a likely blocker going into this brainstorm. Checked directly against `main`'s live branch protection (`gh api repos/nikhilsoman/synlynk/branches/main/protection`):

```
required_pull_request_reviews: null
restrictions: null
```

**`main` has no required-review-approval rule at all** — only required status checks (`test (3.8)`, `test (3.10)`, `test (3.12)`, `qa-gate`). The `#423` caveat specifically blocks `gh pr review --approve` (GitHub refuses self-approval); it does not block `gh pr merge`, which has no self-restriction under GitHub's model. Since this design's `qa`-initiated merge never calls `gh pr review --approve` — it calls `gh pr merge` directly once the gate is green — the shared-identity limitation does not apply here. No per-role GitHub App identity work (PR #517) is needed for this design to function.

If `main`'s branch protection later gains a required-review-approval rule, this fast path would need to be revisited at that time — noted here so it isn't silently invalidated by an unrelated future change.

## 6. Alternatives considered

1. **All three named classes at once (dependency bumps, CI config, docs-only) — rejected for v1.** Wider surface area, more failure modes to reason about per class, no reason to ship them together when docs-only alone addresses the throughput complaint that motivated this. Narrowing to docs-only first, widening later, keeps this PR reviewable and keeps risk contained to the class where "safe" is easiest to argue.
2. **Dispatching an agent to make the merge decision — rejected.** Considered whether qa's merge decision itself should run through `synlynk dispatch` (matching the GitHub-write-routing table's default of routing GitHub writes to Grok). Rejected because the decision requires no judgment — it's a file-pattern match — so dispatching an agent would add cost and latency without adding accuracy. CI-native keeps this fast and cheap.
3. **Provisioning per-role GitHub App identity first — rejected as unnecessary.** PR #517's identity work would let qa merge under a visibly distinct GitHub identity. Confirmed via §5 that this isn't required for the merge action itself given main's actual branch-protection settings; deferred as unneeded scope for this design specifically (it may still matter for other design goals, just not this one).

## 7. What does not change

- Architect still merges every PR outside the docs-only class — no broader authority transfer.
- The block-only gate (CI + sentinel health) still applies unconditionally to every merge, including docs-only fast-path merges.
- PR Review Discipline's non-authoring-reviewer rule is unaffected for any PR that doesn't qualify for the docs-only fast path.
- Nothing about this design updates Vizor or performs semantic verification — that's the separate qa completion tracker design.

## 8. Out of scope for this spec

- Dependency-bump and CI-config PR classes (future increment, §2).
- Any semantic/LLM-based judgment of PR content (that's the qa completion tracker design, unrelated mechanism).
- Per-role GitHub App identity provisioning (§5, §6.3 — not needed here).
- Revisiting `main`'s branch protection to add a required-review-approval rule (out of scope; §5 just notes the dependency).

## 9. Next step

A follow-up implementation plan (`docs/superpowers/plans/`) covering: the docs-only file-pattern matcher (shared logic between `synlynk pr check` and the `qa-gate` CI job), the `qa_gate_mode: "merge-restricted-classes"` config value and mode-dispatch logic, and the `gh pr merge` call path guarded by the existing block-only gate. Not written as part of this spec per the Design → Plan → Build sequence.
