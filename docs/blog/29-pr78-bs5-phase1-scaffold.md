---
title: "PR #78 — BS-5 Phase 1: Standalone Website Scaffold"
date: 2026-06-28
series: "Building the OS for Multi-Agent Development"
post: 29
pr: "#78"
merged: 2026-06-28
---

## The Broader Goal at the End of the Previous PR
At the end of v0.9.8 (health pulse + lifecycle commands), the CLI was hardened for clean onboarding, exit, repair, and observability. The understood next step was shifting focus toward public launch preparation — making the project discoverable and understandable to new users beyond the GitHub repo and internal docs.

## Strategic Shifts in This PR (if any)
BS-5 is the first concrete step toward a real synlynk.com. This moves synlynk from "CLI tool with project-docs" to "product with a face". The website/ directory is a standalone 11ty v3 site (parallel to legacy site/) explicitly scoped as design-first. Phase 1 (Grok) delivers the scaffold, tokens, structure, and handoff surface so that Phase 2 (Agy) can focus on content fidelity, full visual system, and subpages without fighting structural or specificity problems.

## What This PR Shipped

<figure class="brainstorm-visual">
  <iframe src="/assets/brainstorm/bs5-website-redesign/visual-direction.html" title="Visual direction study" loading="lazy" frameborder="0"></iframe>
  <figcaption>Visual direction study</figcaption>
</figure>

<figure class="brainstorm-visual">
  <iframe src="/assets/brainstorm/bs5-website-redesign/page-structure-bs5.html" title="Page structure plan" loading="lazy" frameborder="0"></iframe>
  <figcaption>Page structure plan</figcaption>
</figure>

- `website/` 11ty v3 project:
  - `package.json` (eleventy ^3, scripts for build/serve)
  - `.eleventy.js` with passthrough, dateFilter, stub collections
  - `src/_includes/base.njk`: fixed nav, font preconnects, footer stub, content slot
  - `src/index.njk`: 8 section shells with correct IDs (#top #carousel #relief #how #features #vision #docs #waitlist)
  - `src/assets/css/main.css`: design tokens from spec/hero-v4, reset, nav, primitive section rules, responsive
  - S-glyph logo (from brainstorm `03-terminal-s-glyph.svg`) placed at `src/assets/img/logo/s-glyph.svg` and used in nav
- Dark/light alternation primitives and typography stack (Inter + JetBrains Mono) matching the visual system
- Clean agent role split demonstrated: Grok authored scaffold + structure + build; no content fidelity beyond shells
- Addressed all R1 Claude review findings in this branch:
  - Scoped `section p` muted color only to dark sections (`#top p, ...`)
  - Converted ID rules (`#top, #...`) to `.section-dark` / `.section-light` classes + applied classes to sections in index.njk
  - Stripped every inline `style=` attribute from the entire #top hero section (hero-headline / hero-byline classes preserved as pure hooks)
  - Replaced onclick `getElementById('waitlist')` button with `<a href="/#waitlist">` link (crash-proof on subpages)
  - Removed duplicate `@import` Google Fonts line from main.css (base.njk `<link>` + preconnect is sufficient)
  - Fixed `dateFilter` to force local-day parsing for ISO date strings (`date + 'T00:00:00'`)
- Blog post (this file) per CLAUDE.md convention

`cd website && npm install && npm run build` produces a working `_site/` with nav + all 8 sections.

## Brainstorm Visuals Used
- `docs/brainstorm/bs5-website-redesign/hero-v4.html` (hero, layout, tokens, color/alternation direction)
- Supporting logo and diagram assets referenced in `docs/superpowers/specs/2026-06-27-bs5-website-redesign-design.md`

## What This Achieved on the Path to Autonomy
This PR puts the multi-agent workflow on public display: different agents (Grok scaffold/animations, Agy templates+CSS+copy, Claude reviewer) collaborate on a real product artifact with clear ownership boundaries and clean handoff contracts. The specificity and style-stripping fixes ensure Agy can own the design system in Phase 2 without cascade fights or `!important`. The site itself is the external manifestation of "the OS for multi-agent development" — the thing a new visitor lands on and immediately understands the value of workgroups, shared state, and model diversity.

## Strategic Note: The Goal at the End of This PR
Phase 1 complete: runnable 11ty build, correct tokens and structure, Phase 2 handoff surface ready. New goalpost: Agy fills the 8 sections with full content and micro-copy, implements the complete CSS design system (cards, components, states, responsive details), adds the blog index + subpages (docs, features, changelog, about), wires any interactive shells (carousel etc.), and ensures visual parity with the hero-v4 reference. Then full review + merge to unblock the rest of the launch arc.
