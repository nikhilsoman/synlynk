# Implementation Plan: Autonomous Growth & Marketing Engine

**Spec:** `docs/superpowers/specs/2026-09-02-autonomous-growth-and-marketing-engine-design.md`  
**Date:** 2026-09-02  

---

## Tasks

- [ ] **Task 1: Per-PR Blog Quality Gate & Automation**
  - Implement `validate_blog_post_frontmatter(path)` in `synlynk/marketing.py` to enforce required YAML frontmatter fields (`title`, `author`, `date`, `pr`, `version`, `tags`).
  - Wire blog index updater into `synlynk pr check` and QA merge workflow.
  - Add unit tests in `tests/test_marketing.py`.

- [ ] **Task 2: Automatic Living Documentation Sync Hook**
  - Integrate `scripts/generate_command_docs.py` into `synlynk instructions update` and `synlynk init` pre-commit hooks to prevent command documentation drift.
  - Add unit tests in `tests/test_docs_sync.py`.

- [ ] **Task 3: Social & Changelog Snippet Extraction**
  - Implement `extract_social_changelog_snippets(blog_post_path)` storing structured announcement snippets in `.synlynk/social_drafts.json`.
  - Add unit tests in `tests/test_marketing.py`.

- [ ] **Task 4: Media & Visual Asset Generator (`synlynk media generate`)**
  - Add `synlynk media generate` CLI command in `synlynk/cli.py` and `synlynk/taxonomy.py` for rendering SVG architecture diagrams and OpenGraph preview cards.
  - Add unit tests in `tests/test_media.py`.

- [ ] **Task 5: Documentation, Blog Post, and Verification**
  - Author blog post `docs/blog/164-pr1347-autonomous-growth-engine.md` and index in `docs/blog/README.md`.
  - Ensure all pytest tests pass.
