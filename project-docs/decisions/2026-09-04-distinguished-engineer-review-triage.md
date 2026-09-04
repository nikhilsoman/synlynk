<!-- PM-authored triage note (Claude), not a multi-agent `synlynk decide` panel record -->

# Triage: 2026-09-04 Distinguished Engineer Architectural Review

**Author:** Claude (PM/review role)
**Source:** `docs/reviews/2026-09-04-synlynk-architectural-review-and-muse-platform-fit.md` (branch `docs/distinguished-engineer-review`, commit `eaf7061b`, authored by Agy — not yet merged)
**Status:** decided

## Disposition of the review doc itself

Merge as-is via PR, not revised for tone or content. It's an external point-in-time opinion; editing it to flatter ourselves would defeat its value as an outside data point. A non-authoring reviewer (Codex, since Agy wrote it) does a light factual sanity-check against the codebase before merge — specifically the concrete numbers it cites (test count, cost-reduction estimate) — but the recommendation sections are left untouched regardless of whether the reviewer agrees with them.

## The five epics already opened (all linked to `docs/reviews/2026-09-04-...`)

All five of the review's architectural gaps already have an Epic + Research story + Brainstorm story + linked goal. This note adds sequencing/priority perspective and connects each to prior project work, so a future reader isn't re-deriving context this review already had available.

### 1. #1389 — Monorepo & Virtualized VCS Workspace Support (EdenFS/Sapling/sparse checkouts)
**Gap A. Genuinely new — no prior spec or issue addressed this.**
Scoping: this is a real cost at *enterprise monorepo* scale, but synlynk today operates on this repo's own single, non-monorepo checkout and a handful of sister-project repos of similar size. There is no current evidence (job telemetry, sentinel findings, user complaint) that worktree-per-dispatch cost is actually hurting anyone yet — the review is extrapolating from a hypothetical "5-10 parallel worktrees on a multi-gigabyte monorepo" scenario, not an observed one. Recommend the Research story (`story-ebdc2894`) start by checking `synlynk jobs --all` telemetry for worktree-creation latency/disk-usage signal before investing in EdenFS/Sapling integration design — validate the premise against this project's own dogfooding data first. Lowest near-term priority of the five; natural home is the existing **Post-GA / v1.2.0 Enterprise Workspace** horizon, not before.

### 2. #1392 — Enterprise Containerized & Kernel-Level Agent Sandboxing (eBPF/Bubblewrap/microVMs)
**Gap C. Reinforces already-tracked work — sequence behind it, don't parallel it.**
Connects directly to:
- `#577` (B2 Codex sandbox / GH-write routing) — closed as investigation-complete 2026-08-13, root-caused Codex's `workspace-write` sandbox blocking `api.github.com` egress structurally. Recommended a "B2-A fail-closed routing design" that was never implemented as code.
- `docs/superpowers/specs/2026-08-23-gh-write-identity-hardening-design.md` and `2026-08-29-codex-direct-gh-write-network-access-design.md` — the identity/network-layer sandbox work already in flight.
- The `#423` identity-sharing caveat and `#1264` (worktree-aware token path resolution) in `docs/harness-parity-reference.md`.
- PR #1375 (post [171](../../docs/blog/171-pr1375-codex-review-network-access-regression.md)) — the most recent concrete example of how fragile the current per-vendor-flag sandbox config already is (one fix silently broke another).

Scoping: the review's recommendation (OS-level jailing via bubblewrap/sandbox-exec/microVM) is a *deeper* layer than what's currently unresolved. It doesn't make sense to design kernel-level sandboxing before the simpler, already-scoped identity/network fail-closed routing (B2-A) actually ships — that unfinished work is more likely to surface requirements the OS-level design needs anyway. Recommend the Brainstorm story (`story` under this epic) explicitly block on B2-A landing, or at minimum open by restating B2-A's unimplemented recommendation as its starting requirement rather than starting from a blank slate.

### 3. #1395 — SCIP & Tree-sitter Semantic Code Knowledge Graph Integration
**Gap B. Genuinely new — no prior spec or issue addressed this.**
Current state for context: `synlynk/context.py` (markdown concatenation) and `synlynk/scan.py` (static AST scan) are both real, shipped, and doing their originally-scoped job — this isn't a gap in what was promised, it's a ceiling the review is pointing at for a codebase size synlynk hasn't operated on yet. Scoping: same "validate before building" concern as #1389 — recommend the Research story (`story` under this epic) start by sampling *this repo's own* dispatched-job failure telemetry for a "missing context / wrong file touched" failure signature before scoping a SCIP/Tree-sitter integration. If that signal doesn't exist yet in a single-repo ~30-file-python-module codebase, the case for it strengthens once/if synlynk is dispatched against a genuinely large or multi-language target. Not urgent; good candidate to sit in the same Post-GA horizon as #1389.

### 4. #1398 — High-Concurrency Speculative Rebase & Semantic Conflict Resolution
**Gap E. Reinforces an already-*observed* problem — elevate above #1389/#1395.**
Connects directly to:
- Project memory `feedback_dispatch_stacking_pr_proliferation.md` — two four-task dispatch plans on 2026-08-22 produced 8+ PRs and 16 worktrees needing manual cleanup. This isn't hypothetical; it already happened on this repo.
- `feedback_branch_creation_from_stale_local_main.md` — a related but distinct concurrency hazard (branching from stale local main silently inherits unrelated commits).

Scoping: unlike #1389/#1395, this gap has real incident evidence already in project memory, which makes it the strongest near-term candidate of the three "new-ish" items. Recommend the Research story (`story-issue-1399`) cite both memory incidents as primary source material directly, rather than starting from external literature on 3-way AST merge — the actual failure mode observed here so far has been *PR/worktree proliferation from dispatch stacking*, which may turn out to need a lighter fix (stacking semantics, `--base` discipline) before anything as heavy as automated AST-aware semantic merge resolution is justified. Keep the epic's ambition (speculative rebase trees) as the long-run target, but don't let it skip past the cheaper diagnosis.

### 5. #1401 — Enterprise Team Workspace State Synchronization & Multi-Tenant Billing
**Gap D. Reinforces already-planned roadmap milestones — this epic is early scoping for work already on the roadmap.**
Connects directly to:
- Roadmap `v1.1.0 — Cross-Workgroup (Team Level)` (target Q4 2026: relay → community server, cross-workgroup epics, agent entitlements) and `v1.2.0 — Enterprise Workspace` (target Q1 2027: cross-team, org-level governance agents, enterprise entitlements) in `.synlynk/project-docs/roadmap.md`.
- The existing stub fields (`org`, `team`, `sync_endpoint`) already present in `.synlynk/config.json`, confirming this was anticipated, just not built.
- `docs/archive/agy-synlynk-opportunity-arch-review.md` — an earlier, also-Agy-authored architecture review that raised overlapping enterprise ideas (DLP context-scrubbing gatekeeper, SSO/Entra ID identity bindings) not reflected in this new review; worth folding into the same Research story so the two reviews' enterprise thinking isn't split across two untracked documents.

Scoping: this epic is not really a new initiative — it's early scoping work *for* v1.1.0/v1.2.0, which already exist as roadmap targets with a real date horizon (Q4 2026 is the nearer one). Recommend treating this epic's Research/Brainstorm stories as the actual design-phase work for v1.1.0's "relay → community server" line, rather than a separate future track — i.e., pull it *into* the existing milestone's scope instead of tracking it as a parallel epic that could drift out of sync with it.

## Overall sequencing recommendation (relative priority, not calendar commitment)

1. **#1398** (merge-conflict/dispatch-stacking) — real observed pain, cheapest to start diagnosing (telemetry + memory already exists).
2. **#1401** (enterprise team sync) — already has a roadmap slot and target date; this epic should merge into that existing work rather than run alongside it.
3. **#1392** (sandboxing) — real and already partially scoped, but should sequence *after* the already-open B2-A fail-closed routing work ships, not before.
4. **#1389** and **#1395** (monorepo VCS scaling, semantic code graph) — both genuinely new, both currently unvalidated against synlynk's own actual usage pattern. Recommend their Research stories open by checking for the failure signature in existing telemetry before any design investment; if the signal isn't there, these stay parked at Post-GA horizon.

## Book question (deferred, no action taken)

The review's scorecard (9.2/10 architecture, etc.) is a reasonable small addendum candidate for the Part Four competitive-scorecard chapter and the closing market-sizing chapter, as independent external validation. Not urgent — no chapter edit made as part of this triage. Revisit once/if the review doc itself is merged (so the book can cite a real, landed source rather than an open branch).
