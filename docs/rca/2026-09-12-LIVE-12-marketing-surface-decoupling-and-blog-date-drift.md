# LIVE-12: Marketing Surface Decoupling, Blog Post Date Drift, and Stale Collateral

**Date:** 2026-09-12  
**Severity:** Sev2 (Major public positioning degraded; production workaround verified)  
**Status:** Investigated / RCA Recorded  
**Related Specs & Issues:**
- `docs/superpowers/specs/2026-09-02-autonomous-growth-and-marketing-engine-design.md`
- `docs/superpowers/specs/2026-09-11-marketing-release-ceremony-automation-design.md`
- PR #938, PR #1430, PR #1550, PR #1557

---

## Executive Summary

On 2026-09-12, visual inspection of `synlynk.com` revealed three critical public-facing anomalies:
1. **Features Matrix Stagnation:** `synlynk.com/features/` displays `v0.13.1` as the active release, with comparison columns spanning `v0.13.0` down to `v0.10.0`. Core architectural additions from releases `v0.14.0` through `v0.20.0` (unattended loop, GitHub App broker, policy gates, dual-ledger sync) are completely absent.
2. **Blog Post Date Homogenization & Badge Fallback:** Every recent blog card on `synlynk.com/blog/` displays the date **`Sep 11, 2026`** and placeholder badge **`#00`**, sorted in erratic non-chronological order (e.g. post 97, 98, 94).
3. **Stale Documentation & Book Formats:** Downloadable documentation PDFs (`synlynk-quickstart-guide.pdf`, `synlynk-official-reference.pdf`, `synlynk-command-reference.pdf`) and the book manuscript (`the-supervised-machine-v0.5-DRAFT.pdf/.epub`) are not compiled during release ceremonies, resulting in stale binary assets distributed via `synlynk.com/docs`.
4. **Missing Autonomous Trigger on PR Merge:** Routine feature PRs (e.g. PR #1556–#1560) merge without triggering blog post creation, README updates, or site rebuilds.

---

## Timeline

- **2026-07-16 (PR #298):** `website/src/features.njk` created and refreshed through `v0.12.0`.
- **2026-08-14 (PR #938):** `website/src/features.njk` manually updated to `v0.13.1`. This was the last time the file was edited in git history.
- **2026-09-02 (PR #1347):** Spec for Autonomous Growth & Marketing Engine written (`synlynk/marketing.py`), introducing frontmatter validation functions, but not attached to any PR lifecycle gate or daemon hook.
- **2026-09-05 (PR #1430):** Book default outputs expanded to include EPUB (`the-supervised-machine-v0.5-DRAFT.epub`), but compilation remained a manual CLI recipe.
- **2026-09-11 21:05 (PR #1557):** Marketing Release Ceremony Automation landed (`synlynk/release_marketing.py`), adding `synlynk marketing ceremony` CLI verb and linking it to named release command `synlynk release`. Several unquoted YAML keys in `docs/blog/` were fixed to unblock Eleventy builds.
- **2026-09-11 21:10:** Push to `main` triggered GitHub Actions `.github/workflows/site.yml`. The Eleventy build copied all 220 files from `docs/blog/` into `website/src/blog/posts/`. 61 historical posts lacking YAML frontmatter received the runner's filesystem timestamp (`Sep 11, 2026`), bubbled to the top of `synlynk.com/blog/`, and rendered with `#00` badges.
- **2026-09-12 07:05:** Operator reported visual anomalies via browser screenshots. Root cause investigation initiated.

---

## Root Causes

### 1. Blog Post Frontmatter Absence & Eleventy Timestamp Leak
- **The Defect:** 61 out of 220 blog markdown files in `docs/blog/` lacked YAML frontmatter (`--- ... ---`) entirely. An additional 2 files had incomplete frontmatter (`docs/blog/34-pr82-bs14-harness-compatibility.md` lacked `date:` and `title:`; `docs/blog/165-pr1348-cross-harness-event-relay.md` lacked `post:` and `pr:`).
- **The Mechanism:** `website/.eleventy.js` copies `../docs/blog/*.md` to `src/blog/posts/` using `fs.copyFileSync`. In Eleventy, if a template lacks `date:` in frontmatter, it falls back to the file's `mtime`/`ctime`. On the GitHub Actions Ubuntu runner, every newly checked-out and copied file received an `mtime` of `2026-09-11`.
- **The Consequence:** Because real historical posts had dates in June, July, and August 2026, all 61 un-frontmattered posts evaluated to `Sep 11, 2026`—newer than the legitimate posts. The collection sort `dateB - dateA` pushed all 61 to the front page of the blog. Furthermore, since `post.data.post` was undefined, `website/src/blog/index.njk` evaluated `post.data.post or '00'`, rendering `#00` on every card.

### 2. Features Page Hardcoded HTML & Lack of Release Pipeline Integration
- **The Defect:** `website/src/features.njk` is 683 lines of completely hardcoded HTML.
- **The Mechanism:** Unlike `release.json` (which receives version stamps during release ceremony), `features.njk` had no data-driven model (`website/src/_data/features.json`), no schema, and no update hooks in `synlynk/release_marketing.py`.
- **The Consequence:** Releases `v0.14.0`, `v0.15.0`, `v0.16.0`, `v0.17.0`, `v0.18.0`, `v0.19.0`, and `v0.20.0` shipped code, documentation, and tests without anyone updating the features matrix.

### 3. Decoupled PR Lifecycle and Absence of Event Triggers
- **The Defect:** While `synlynk/marketing.py` contained validation and snippet extraction methods, nothing called them during everyday development.
- **The Mechanism:**
  - `synlynk pr check` verified model version attestation and git context, but contained zero assertions on blog posts or documentation sync.
  - No webhook, post-merge GitHub Action, or daemon event listener was wired to run `synlynk marketing` on PR merge events.
  - The `marketing` role was registered as a durable agent in `agent_store`, but had no active entry in `.synlynk/config.json`'s `roles` table.

### 4. Release Ceremony Not Run Following Cluster Merges
- Milestone `v0.20.0` was completed across Clusters A, B, C, and D (PRs #1556–#1560), bringing the suite to 2,795 tests.
- However, the ceremony command (`synlynk marketing ceremony --version v0.20.0` or `synlynk release v0.20.0`) was not triggered. Consequently, `README.md` remained on `v0.19.0` (2,734 tests) and `website/src/_data/release.json` was never written.

### 5. Stale PDF and EPUB Compilation in Releases
- `synlynk/release_marketing.py` mirrored existing PDF files via `shutil.copy2`, but did not invoke compilation tools (Headless Chrome for HTML->PDF; Pandoc for HTML->EPUB).
- The 3 canonical documentation guides (`synlynk-quickstart-guide`, `synlynk-official-reference`, `synlynk-command-reference`) and book manuscript (`the-supervised-machine`) had their HTML text updated, but the binary PDF and EPUB files remained frozen at older revisions.

---

## Architectural Remediation Plan

The remediation is structured across four comprehensive phases:

### Phase 1: Immediate Surface Remediation
1. **Frontmatter Backfill:** Prepend valid YAML frontmatter blocks (`title`, `author`, `date`, `post`, `pr`, `series`, `tags`) to all 61 un-frontmattered blog posts and fix the 2 partial posts, using canonical metadata from `docs/blog/README.md`.
2. **Features Matrix Refresh:** Update `website/src/features.njk` to feature `v0.20.0` as current, alongside `v0.19.0`, `v0.18.0`, `v0.17.0`, and `v0.16.0`, incorporating all shipped capabilities.
3. **v0.20.0 Marketing Release Ceremony:** Run `synlynk marketing ceremony --version v0.20.0` to synchronize `README.md` (2,795 tests, v0.20.0 hero release summary), compile `website/src/_data/release.json`, and verify clean Eleventy static builds.

### Phase 2: CI & Preflight Quality Gate Hardening
1. **Pre-Merge Validation:** Add `validate_all_blog_posts("docs/blog")` into `tests/test_marketing.py` and `synlynk pr check`. Fails closed if any blog post in `docs/blog/` lacks valid YAML frontmatter.
2. **Defensive Eleventy Timestamp Fallback:** Update `website/.eleventy.js` to extract dates from `docs/blog/README.md` or filename convention (`YYYY-MM-DD`) if a template lacks frontmatter, preventing raw filesystem `mtime` leakage.

### Phase 3: Autonomous PR Marketing Trigger & Two-Tier Blog Architecture
1. **Two-Tier Blog Architecture (`synlynk.com/blog`):**
   - **Tier 1 (Strategic Named Release Posts):** Featured prominently at the top of the blog, containing consolidated strategic reviews, evolutionary architectural trends, and visual assets (terminal simulations, vizor architecture maps, and metric charts).
   - **Tier 2 (Per-PR Engineering Diary):** Clean grid of incremental per-PR posts detailing specifically what shipped, why, and how it was verified.
2. **Autonomous PR Sync:**
   - Implement `synlynk marketing sync-pr <pr-number>` in `synlynk/marketing.py`.
   - Add GitHub Actions workflow `.github/workflows/marketing-pr-sync.yml` on PR closed/merged to draft/validate the incremental post and update `docs/blog/README.md`.

### Phase 4: Automated PDF & EPUB Compilation Engine
1. **Headless Chrome PDF Compilation:** Automatically compile `docs/synlynk-quickstart-guide.pdf`, `docs/synlynk-official-reference.pdf`, `docs/synlynk-command-reference.pdf`, and `docs/book/the-supervised-machine-v0.5-DRAFT.pdf` from their respective single-file HTML sources during release ceremonies.
2. **Pandoc EPUB Compilation:** Automatically compile `docs/book/the-supervised-machine-v0.5-DRAFT.epub` using Pandoc with `epub-metadata.yaml` and `epub.css`.
3. **Release Pipeline Integration:** Wire these compilation steps directly into `synlynk/release_marketing.py` so every named release regenerates and mirrors updated binaries to `website/src/assets/docs/`.

---

## Action Items & Ownership

| Action | Owner | Target | Status |
| :--- | :--- | :--- | :--- |
| Prepend YAML frontmatter to 61 blog posts + fix #34 & #165 | Agy | `docs/blog/` | Planned (Phase 1) |
| Refresh `features.njk` to v0.20.0 with recent capability matrix | Agy | `website/src/features.njk` | Planned (Phase 1) |
| Run v0.20.0 release ceremony and verify website build | Agy | Root & `website/` | Planned (Phase 1) |
| Add frontmatter assertions to `synlynk pr check` & tests | Codex | `synlynk/marketing.py` | Planned (Phase 2) |
| Implement two-tier blog view on `website/src/blog/index.njk` | Agy | `website/` | Planned (Phase 3) |
| Implement `synlynk marketing sync-pr` and GitHub Action | Codex | `synlynk/`, `.github/` | Planned (Phase 3) |
| Automate Chrome PDF & Pandoc EPUB generation in ceremony | Agy/Codex | `synlynk/release_marketing.py` | Planned (Phase 4) |
| Update Marketing Agent Charter with dual-treatment mandates | PM/Agy | `agent_store` & `agent_cli.py` | In Progress |
