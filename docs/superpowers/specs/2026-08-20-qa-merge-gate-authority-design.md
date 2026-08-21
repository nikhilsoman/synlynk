# qa Delegated Merge-Gate Authority — Design

**Date:** 2026-08-20
**Status:** Approved by Nikhil (brainstorm dialogue, this session) — amends `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md`
**Origin:** Explicitly deferred in `docs/superpowers/specs/2026-08-19-gh-write-broker-design.md` §9 Out of Scope, as its own follow-up PR.

## 1. Problem

The agent-roles-charters spec (§3.2) already splits PR lifecycle stages: **Review** and **Merge** sit with architect; **CI/CD gate + Deploy** sits with qa, "per qa's explicit charter." In practice this split is advisory only — nothing stops a PR from merging if qa's pipeline-health signal is red, because qa's charter ownership isn't wired into anything that can actually block a merge. "Delegated merge-gate authority" names the gap: qa owns CI/CD health in principle but has no mechanism to enforce it.

## 2. Decision

qa gets the ability to **block** a merge. qa does not get the ability to **click** merge. This is a narrowing of what "CI/CD gate" already meant in §3.2, not a transfer of architect's merge authority — architect remains the sole role that merges PRs into `main`.

This is deliberately the smallest of three options considered (see §6). The other two — qa merging a narrow class of PRs itself, and qa's own review satisfying the non-authoring-reviewer rule — are named as future modes (§5) rather than built now, because the stated reason to reach for them (architect and qa diverging in model tier/capability) doesn't hold today: both currently route to the same capability class. Building for that divergence before it exists would be speculative.

## 3. Gate verdict

The gate is **green** only if both hold for the PR's HEAD commit:

1. **CI matrix status** — the GitHub Actions test matrix (currently 3.8/3.10/3.12) reports success for the HEAD commit.
2. **No unresolved sentinel alert** — no currently-open FLATLINE, QUOTA_EXHAUSTED, or other sentinel-pattern alert against the repo, per the Support Engineer's existing telemetry monitoring (`synlynk/support_engineer.py`, `.synlynk/telemetry.json` → `sentinel.md`). This ties the gate to qa's actual ongoing charter (durable telemetry monitoring), not just to the PR's own isolated test run — a PR can have green CI and still be merging into a repo qa has flagged as unhealthy.

**No verdict is not the same as green.** If the gate cannot be computed — Support Engineer state unreachable, `sentinel.md`/telemetry unreadable, any transient error — the gate is treated as **red**, not skipped. An unverifiable claim of health is not a passing one. If this happens repeatedly (not a one-off transient blip), it escalates to Claude/architect to investigate qa's own infrastructure rather than being silently tolerated as routine.

**Scope:** every PR into `main`. No exceptions carved out for author identity (Claude-authored PRs are not exempt) — a uniform rule is simpler to implement, explain, and audit than one with carve-outs, and matches how PR Review Discipline already applies uniformly today.

## 4. Enforcement — two layers

1. **`synlynk pr check` (authoring surface).** Already run by every reviewer per PR Review Discipline, alongside the existing non-authoring-reviewer check. Extended to compute and surface the qa gate verdict inline during review, so architect sees it before deciding to merge.
2. **GitHub branch-protection required check (backstop).** A required status check on `main` mirrors the same verdict at the GitHub level, so the gate can't be bypassed by merging through `gh pr merge` or the web UI without ever running `synlynk pr check`. This closes the loophole the first layer alone would leave open — `synlynk pr check` is a convention, not something GitHub itself can force.

Both layers compute the same verdict from the same two inputs (§3); the branch-protection check is not a second, independently-designed gate — it's the same gate exposed at a second enforcement point.

## 5. Config toggle for future modes

`.synlynk/config.json` gains a `qa_gate_mode` field:

| Value | Behavior |
|---|---|
| `"block-only"` | **Default, this design.** qa gate can block, cannot merge. |
| `"merge-restricted-classes"` | For a defined narrow PR class (dependency bumps, CI config, docs-only, or any PR where qa is the assigned non-authoring reviewer and the gate is green), qa gets actual merge authority without waiting on architect. Architect stays required for anything touching application logic. |
| `"non-authoring-equivalent"` | qa's own review (when qa is the assigned reviewer) satisfies the non-authoring-reviewer requirement on its own — removes the need for a second reviewer, narrowing what "non-authoring" means rather than changing who clicks merge. |

Switching `qa_gate_mode` away from `"block-only"` is itself a "major decision" in the sense the roadmap strategy doc uses the term (`docs/strategy/road-to-autonomous-ops.md`) — it requires the same sign-off gate this spec went through (Nikhil approval via brainstorm dialogue), not a role granting itself broader authority through a config edit. The trigger condition named for reconsidering the mode is architect and qa diverging in model tier or capability — not a fixed calendar date, and not something to revisit speculatively before that divergence is real.

This spec defines the field and its three values; it does not implement `"merge-restricted-classes"` or `"non-authoring-equivalent"` logic. Only `"block-only"` is in scope for the implementation plan that follows this spec.

## 6. Alternatives considered

Presented to Nikhil as three options; option 1 was selected for now with the other two reserved as future `qa_gate_mode` values (§5):

1. **Block-only (selected).** qa's CI/CD gate becomes a hard blocking check; merge action itself stays with architect. Formalizes qa's existing charter as an enforced gate rather than an advisory signal. Lowest risk, smallest scope.
2. **qa merges a narrow class of PRs itself.** For CI-only/low-risk PRs (dependency bumps, CI config, docs-only) with qa as reviewer and green CI, qa gets real merge authority. Reserved as `"merge-restricted-classes"`.
3. **qa's review satisfies non-authoring-reviewer on its own.** Narrows what counts as a sufficient review rather than changing who clicks merge. Reserved as `"non-authoring-equivalent"`.

Option 1 was chosen because it requires no changes to who holds merge authority today, ties directly to qa's already-charter-defined responsibility (CI/CD gate + deploy, §3.2), and avoids granting new authority ahead of the condition (model-tier divergence) that would motivate it.

## 7. What does not change

- Architect remains the only role that merges PRs into `main`.
- The non-authoring-reviewer requirement in PR Review Discipline is unchanged.
- No behavioral change today: architect and qa currently run on the same model tier, so this is pure infrastructure — no PR that would merge today is blocked or unblocked by this design in practice, until the CI-status + sentinel-health wiring described in §3-4 is actually built.

## 8. Out of scope for this spec

- Implementing `"merge-restricted-classes"` or `"non-authoring-equivalent"` gate modes.
- Any change to how the non-authoring-reviewer rule works for roles other than qa.
- The broker-as-persistent-system-service question (separately deferred in the #865 spec's own §9, unrelated to this one).

## 9. Next step

A follow-up implementation plan (`docs/superpowers/plans/`) for the `"block-only"` gate: `synlynk pr check` verdict computation, the `qa_gate_mode` config field (single default value for now), and the GitHub branch-protection required-check wiring. Not written as part of this spec per the Design → Plan → Build sequence — plan work starts only after this spec is committed and reviewed.
