# Design Spec: Grant Administration:Write Permission to Merge Roles in GitHub App Manifests (#1295)

- **Issue:** [#1295](https://github.com/nikhilsoman/synlynk/issues/1295)
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-09-01
- **Status:** APPROVED

---

## 1. Context & Problem Statement

Branch protection on `main` requires `required_approving_review_count: 1`. In synlynk's dispatched autonomous workflow:
1. All dispatched agents share a single GitHub identity (`nikhilsoman`-owned tokens per #423). Consequently, GitHub rejects self-approval with `Can not approve your own pull request` on dispatch-authored PRs.
2. Dispatched reviewers use a sanctioned fallback: posting a formal COMMENT review with an explicit approval checklist.
3. The `qa` role is granted merge authority in `.synlynk/policy.json` (`merge_authority.can_merge: ["qa"]`).
4. However, GitHub App manifests created via `synlynk identity init <role>` previously only requested `metadata: read`, `contents: write`, `issues: write`, and `pull_requests: write`.
5. Because the `qa` App lacks `administration: write` on the repository, `gh pr merge --admin` fails with:
   `At least 1 approving review is required by reviewers with write access.`

This creates a structural block preventing dispatched `qa` review/merge jobs from completing autonomously.

---

## 2. Proposed Architecture

### 2.1 Dynamic Permission Request in GitHub App Manifest
In `synlynk/team.py::_build_app_manifest_url()`:
- Load the workspace policy via `load_policy()`.
- Check `policy.get("merge_authority", {}).get("can_merge", ["qa"])`.
- If the role being provisioned is in `can_merge` (e.g., `qa`), add `"administration": "write"` to the manifest's `default_permissions`.
- For other roles (e.g. `dev`, `architect`), do not request `administration: write`.

### 2.2 Scope & Operational Boundaries
- **Code-level:** Dynamically requests `administration: write` for roles holding `merge_authority.can_merge`.
- **Account-level:** For existing installations, elevated permissions require an owner confirmation in GitHub App settings (`github.com/settings/apps/<app_slug>`).

---

## 3. Testing & Verification

- Unit test in `tests/test_team.py` (`test_build_app_manifest_url_adds_administration_only_for_merge_roles`):
  - Asserts `qa` manifest contains `"administration": "write"`.
  - Asserts `dev` manifest does not contain `"administration"`.
- Verify full test suite passes (`pytest tests/test_synlynk.py -q`).
- Verify `python -m synlynk pr check` passes.
