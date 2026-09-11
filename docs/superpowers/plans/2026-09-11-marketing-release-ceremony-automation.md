# Marketing Release Ceremony Automation — Implementation Plan

- **Spec:** `docs/superpowers/specs/2026-09-11-marketing-release-ceremony-automation-design.md`
- **Branch:** `feat/agy/marketing-release-ceremony`
- **Goal:** `goal-85656c82`, `goal-0c4e96ff`

---

## User Review Checkpoint
> [!IMPORTANT]
> This plan implements automated synchronization of `README.md`, `website/` metadata, and canonical Synlynk Docs bundles (`docs/*.html` and `.pdf`) during every named release, satisfying the final requirement of Milestone v0.20.0 Cluster A.

---

### Task 1: Core Marketing Ceremony Engine (`synlynk/release_marketing.py`)

**Files:**
- Create: `synlynk/release_marketing.py`
- Test: `tests/test_release_marketing.py`

**Interfaces:**
- Consumes: `synlynk.release_readme.sync_readme_for_release`, `collect_pytest_test_count`
- Produces: `execute_release_ceremony`, `sync_docs_bundles`, `mirror_docs_pdfs_to_website`, `update_website_metadata`, `verify_website_build`

- [ ] **Step 1: Write the failing tests**
  Add unit tests in `tests/test_release_marketing.py`:
  - `test_sync_docs_bundles_updates_version_and_date()`
  - `test_mirror_docs_pdfs_to_website()`
  - `test_update_website_metadata()`
  - `test_execute_release_ceremony_dry_run()`
  - `test_execute_release_ceremony_live()`

- [ ] **Step 2: Run tests to verify they fail**
  Run: `pytest tests/test_release_marketing.py` (Expected: ModuleNotFoundError)

- [ ] **Step 3: Implement `synlynk/release_marketing.py`**
  - Implement `sync_docs_bundles` replacing `v0.X.Y` and dates in the 3 HTML guides.
  - Implement `mirror_docs_pdfs_to_website` copying PDFs to `website/src/assets/docs/`.
  - Implement `update_website_metadata` updating `website/src/_data/release.json`.
  - Implement `verify_website_build` calling `npx @11ty/eleventy` or `npm run build` when available.
  - Implement `execute_release_ceremony`.

- [ ] **Step 4: Run tests to verify they pass**
  Run: `pytest tests/test_release_marketing.py` (Expected: all pass)

- [ ] **Step 5: Commit**
  ```bash
  git add synlynk/release_marketing.py tests/test_release_marketing.py
  git commit -m "feat(marketing): implement core marketing release ceremony engine"
  ```

---

### Task 2: CLI Plumbing & Release Engine Hook

**Files:**
- Modify: `synlynk/cli.py`
- Modify: `synlynk/__init__.py`
- Test: `tests/test_release_marketing.py`

**Interfaces:**
- Produces: `synlynk marketing ceremony` CLI command
- Connects: `cmd_release()` to `execute_release_ceremony()`

- [ ] **Step 1: Write the failing test**
  - `test_cmd_marketing_ceremony_cli()`
  - `test_cmd_release_invokes_marketing_ceremony()`

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest tests/test_release_marketing.py -k "cli or release"`

- [ ] **Step 3: Implement CLI and release hooks**
  - Add `marketing_parser` with `ceremony` subcommand in `synlynk/cli.py`.
  - Add `cmd_marketing_ceremony` in `synlynk/__init__.py`.
  - Update `cmd_release` in `synlynk/__init__.py` to invoke `execute_release_ceremony`.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_release_marketing.py` (Expected: all pass)

- [ ] **Step 5: Commit**
  ```bash
  git add synlynk/cli.py synlynk/__init__.py tests/test_release_marketing.py
  git commit -m "feat(marketing): add marketing ceremony CLI verb and release engine hook"
  ```

---

### Task 3: Full Verification, Documentation Sync, and PR Review

- [ ] **Step 1: Run full test suite regression**
  Run: `pytest tests/test_release_marketing.py tests/test_agent_cli.py tests/test_viz*.py`
- [ ] **Step 2: Update project-docs (roadmap, devlog, costs, memory)**
- [ ] **Step 3: Open PR, dispatch QA review to Codex, and merge into main**
