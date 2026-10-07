# README Capability Evidence Copy Plan

**Design:** `docs/superpowers/specs/2026-10-07-readme-capability-evidence-design.md`
**Issue:** #2098

## Scope findings

- `README.md:15` says the router selects the best-measured harness after a minimum sample size, but leaves the threshold and interim behavior unnamed.
- The source `website/` tree has no equivalent external capability claim in its README or product copy.
- The policy defines a minimum of five merged jobs and explicitly marks `task_allocation` as an interim default. The capability policy article explains that the report generator is not shipped yet and that fleet-wide reporting depends on #1926/#1993.

## Tasks

1. Replace the current README capability sentence with the approved wording from the design spec, preserving the surrounding product description.
2. Link to `docs/blog/244-chore-empirical-capability-policy.md` and `.synlynk/policy.json` using repository-relative Markdown links.
3. Inspect the README and source `website/` copy for equivalent overclaims. Update any match only if it is the same product claim and remains within the design scope.
4. Verify both links resolve, inspect the final README paragraph, and search the README and website source for the old “best-measured”/“live capability ledger” claim forms.
5. Draft the required blog post in `docs/blog/` for the PR, commit it on this branch, and include the PR number once known.
6. Open a PR referencing #2098. The PR body will describe the copy correction, rationale, markdown/link verification, documentation-only scope, and whether a deploy or migration is needed.

## Verification

- Run a small script or shell check to confirm each target exists and each relative path is correct from `README.md`.
- Review the Markdown diff and the searched README/website copy.
- No behavior tests are required for this documentation-only change.

## Review and merge

- Assign a non-authoring reviewer through the role-scoped harness flow.
- Reviewer runs `synlynk pr check` inside the PR worktree.
- Require cross-harness and cross-model review per policy. The reviewer alone merges after the merge-authority check succeeds.
