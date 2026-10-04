# PR Check Linked Story Provenance Plan

Issue: follow-up to the provenance failure observed on PR #2026; policy contract from #1991.

## Behavior

- Keep the existing direct `capability_ratings.pr_number` implementation lookup as the preferred path.
- If absent, resolve the PR's GitHub closing-issue references and map them to story IDs (`stories.gh_issue` and the canonical `story-issue-<number>` ID).
- Use cost/job metadata for the unique matching implementation story; continue to fail closed if no story, job, review job, or complete harness/model identity is available.
- Recognize review jobs that refer to the PR by its GitHub `/pull/<number>` URL as well as `PR #<number>` text.
- Do not mutate the ledger during the check or relax the cross-harness/model equality rule.

## Implementation and verification

1. Add a read-only PR closing-issue resolver and fallback implementation lookup in `synlynk/db.py`.
2. Add tests for provenance recovery without a capability rating, plus fail-closed ambiguity and existing direct-link behavior.
3. Run focused cross-harness and PR-check tests.
