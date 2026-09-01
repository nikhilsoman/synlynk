# Implementation Plan: Grant Administration:Write Permission to Merge Roles in GitHub App Manifests (#1295)

- **Issue:** [#1295](https://github.com/nikhilsoman/synlynk/issues/1295)
- **PR:** [#1303](https://github.com/nikhilsoman/synlynk/pull/1303)
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-09-01

---

## 1. Proposed Code Changes

### 1.1 `synlynk/team.py`
- Import `load_policy` from `synlynk.policy`.
- In `_build_app_manifest_url()`:
  - Query `merge_authority.can_merge` from policy (defaulting to `["qa"]`).
  - If `role in merge_roles`, set `manifest["default_permissions"]["administration"] = "write"`.

### 1.2 `tests/test_team.py`
- Add unit test `test_build_app_manifest_url_adds_administration_only_for_merge_roles` verifying `qa` receives `administration: write` and `dev` does not.

### 1.3 Documentation & Devlog
- Create blog post 150: `docs/blog/150-pr1303-qa-app-administration-permission.md`.
- Update `docs/blog/README.md`.
- Add decision note to `project-docs/memory.md`.
- Record entry in `project-docs/devlogs/nikhilsoman.md`.

---

## 2. Verification Plan
- `pytest tests/test_team.py -v` (1 passed)
- `pytest tests/test_identity_init_role.py -v` (12 passed)
- `pytest tests/test_synlynk.py -q` (506 passed)
- `python -m synlynk pr check`
- Dispatch non-authoring review to Codex (`job-...`).
