# #2799 — Dual-tracking drift between project docs and state.db

## Question

Review the drift risk between `project-docs/*.md` and `state.db`, including whether Synlynk should collapse to `state.db` only.

## Verdict

**Single-author assessment.** Synlynk should keep `state.db` as the sole mutation authority, but “state.db-only” should not mean eliminating reviewable human-readable projections. The verified failure mode is competing or non-deterministic write paths: generated Markdown is useful as an inspectable export, but it should be reproducible from canonical state, drift-checked, and never described as a transactional backup.

## Findings

- The approved generated-docs design names `state.db` as the sole mutation point and routes the four generated ledgers through a shared generator path.
- Repository instructions prohibit hand-editing `todo.md` and direct status changes through the story commands, confirming the intended authority boundary.
- The October 5 review praised Git-visible Markdown for inspectability and durability, while the five-POV review recommended making Markdown a generated export instead of write-through.
- The October 16 architecture review resolves that tension: keep revisioned projections/exports, but do not equate tracked write-through Markdown with a complete or transactional recovery backup.
- Whether every current writer obeys the sole-mutation rule is **not verified** by this docs-only review.

## Recommended follow-ups

- **New ticket: No. Proposed title:** “Make project-docs ledgers deterministic state.db projections.” Track the authority and projection contract in #2799.
- **New ticket: Yes. Proposed title:** “Add a drift and reproducibility check for generated project-docs projections.” The check should compare regenerated output with tracked projections without making observation commands mutate state.
- **New ticket: Yes. Proposed title:** “Document recovery guarantees for state.db and generated Markdown exports.” State explicitly which artifacts provide backup, recovery, and human review.

## Sources

- [GitHub issue #2799](https://github.com/nikhilsoman/synlynk/issues/2799)
- `docs/superpowers/specs/2026-09-25-generated-docs-lock-and-write-through-design.md`
- `docs/reviews/2026-10-05-three-lens-strategic-review.md`
- `docs/strategy/2026-10-02-five-pov-review.md`
- `docs/reviews/2026-10-16-frontier-lab-architecture-review.md`
