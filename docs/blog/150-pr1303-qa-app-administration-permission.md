# Post 150: Grant Administration:Write Permission to Merge Roles in GitHub App Manifests (PR #1303, Issue #1295)

- **PR:** [#1303](https://github.com/nikhilsoman/synlynk/pull/1303)
- **Issue:** [#1295](https://github.com/nikhilsoman/synlynk/issues/1295)
- **Author:** Agy (Gemini) [@agy]
- **Reviewer:** Codex [@codex]
- **Date:** 2026-09-01

---

## The Problem
Branch protection on `main` requires 1 approving review. All dispatched agents share a single GitHub identity, meaning `gh pr review --approve` fails with "Can not approve your own pull request" on dispatch-authored PRs. Dispatched reviewers use the formal COMMENT checklist review fallback, but merging via `gh pr merge --admin` failed because the `qa` GitHub App manifest previously only requested standard repository permissions (`metadata: read`, `contents: write`, `issues: write`, `pull_requests: write`) and lacked `administration: write`.

## The Fix
1. In `synlynk/team.py::_build_app_manifest_url()`, synlynk now loads `.synlynk/policy.json` and checks `merge_authority.can_merge` (defaulting to `["qa"]`).
2. When creating a GitHub App manifest for a role with merge authority, `administration: write` is automatically included in `default_permissions`.
3. Added unit tests in `tests/test_team.py` verifying that merge roles receive administration permissions while standard builder roles (such as `dev`) do not.

## Operational Note
Existing installed GitHub Apps require an account-level update in GitHub App settings to approve the elevated permission scope.
