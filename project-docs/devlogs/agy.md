# Agy Devlog

## 2026-06-28 — Homepage Sections 1, 3, 4, 5 & CSS Design System (Phase 2)

### Shipped
- Modularized repeated card components into Nunjucks macros (`website/src/_includes/macros.njk`).
- Implemented Section 1 (Tagline Hero) porting layout from `hero-v4.html` with class-based colors (no inline styles).
- Implemented Section 3 (Relief Section) using cards and the distributed cost savings callout.
- Implemented Section 4 (How It Works) command flow using cards.
- Implemented Section 5 (Features spotlight) 2x2 grid with commands and keyword tags.
- Extended `website/src/assets/css/main.css` to add support for all new visual components (buttons, gradients, cards, and terminal window styling).
- Fixed the footer docs link in `base.njk` to point to the absolute `/#docs` path.
- Verified successful Eleventy build in the worktree.
- Authored Phase 2 blog post at `docs/blog/30-pr-bs5-phase2-website-redesign.md`.

## 2026-07-03 — Architect Map (Task 5 of BS-21 Vizor)

### Shipped
- Implemented `generate_tube_html(data, port)` in `synlynk/viz.py`.
- Implemented centered setup-prompt card matching spec if `tube_config` is None, using premium CSS styles.
- Implemented custom SVG generation in Python when `tube_config` is present:
  - Generates line segments from coordinate lists.
  - Generates station circle elements with radius based on connection count: `r = 4 + (segs * 2)`.
  - Computes station connections dynamically based on lines list.
  - Generates multi-color interchange hub rings dynamically using segmented stroke-dasharray/stroke-dashoffset circles.
  - Generates assignment badges for agents (Claude, Agy, Codex, Grok) at `y - r - 10`.
  - Supports custom label alignments (top, bottom, left, right) and multi-line label rendering (split by newline).
  - Integrates hover tooltips showing station name and description from config.
  - Supports zoom-in and zoom-out operations on the SVG canvas.
- Added comprehensive unit tests in `tests/test_viz.py` for both setup-prompt and configured states.
- Verified successful cache generation with `python3 bin/synlynk.py viz --generate`.

## 2026-08-03 — PR #683 Review & Merge (docs: blog post for PR #676)

### Shipped
- Reviewed PR #683 (`docs: blog post for PR #676 — worktree audit/clean command group`).
- Confirmed `synlynk pr check` passed cleanly.
- Verified `gh pr diff 683` touched strictly one file (`docs/blog/96-pr676-worktree-audit-clean.md`) with zero code changes.
- Merged PR #683 via `gh pr merge 683 --squash`.
- Verified test suite (`pytest tests/test_agent_quota_tracking.py`).

