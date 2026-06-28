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
- Authored Phase 2 blog post at `docs/blog/30-pr78-bs5-phase2-agy-templates.md`.

## 2026-06-28 — Docs Sidebar Scroll-Spy (Phase 2 Hotfix)

### Shipped
- Implemented `initDocsSidebar()` in `website/src/assets/js/main.js` using `IntersectionObserver` to highlight active links as user scrolls.
- Added click listener to immediately update active class on link click.
- Added `.sidebar-link.active` rules in `website/src/assets/css/main.css` to visually distinguish active sidebar item.
- Verified local Eleventy build successfully builds pages.

