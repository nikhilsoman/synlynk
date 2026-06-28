---
title: "PR — BS-5 Phase 2: Grok Terminal Carousel + JS Interactions"
date: 2026-06-28
series: "Building the OS for Multi-Agent Development"
post: 31
pr: "TBD (BS-5 Phase 2)"
merged: TBD
---

## The Broader Goal at the End of the Previous PR
At the end of Phase 1 (scaffold + tokens) and Agy's parallel Phase 2 work on Sections 1/3/4/5 + the CSS design system, the homepage had a complete visual language and most of the marketing surface in place. The remaining critical interactive piece was Section 2 — the live terminal carousel demonstrating the four primary commands (init, join, dispatch, status) — plus the install-bar copy affordance that makes "getting started" feel instant.

## Strategic Shifts in This PR
No major strategic shift; pure execution handoff. The split of responsibilities (Agy: content + layout + macros + CSS system; Grok: carousel markup fidelity + vanilla JS behaviors + copy button) mirrors the "design-first, beyond functional" mandate of BS-5. We kept the carousel purely presentational + behavioral (no framework, no build step for the site JS).

## What This PR Shipped
- Replaced the `#carousel` placeholder shell in `website/src/index.njk` with full markup ported from `hero-v4.html`:
  - Four `.terminal-slide` panes (init wizard, `join --scan`, parallel dispatch, `status` with Budget Pulse table).
  - Command pill row (`.cmd-pill`): init · join · dispatch · status with `.active` state.
  - Dot navigation (`.slide-dot` ×4).
- Added dedicated carousel CSS in `website/src/assets/css/main.css` (`.section-carousel`, `.carousel-*`, `.cmd-pill`, `.slide-nav`/`.slide-dot`, absolute-positioned fade slides using `.terminal-slide.active` + `opacity` transition + slide-in feel).
- Created `website/src/assets/js/carousel.js`:
  - Auto-advance every 4200ms.
  - Clicking pill or dot pauses the timer and switches the slide.
  - Hover on container pauses; mouseleave resumes.
  - Keyboard arrows when focused; tiny debug API on `window.__synlynkCarousel`.
  - Pure vanilla, data-* driven, no inline handlers.
- Created `website/src/assets/js/main.js`:
  - On DOMContentLoaded finds every `.copy-btn[data-copy]`.
  - Uses `navigator.clipboard.writeText`, graceful fallback to execCommand.
  - 1.5s "Copied!" label + `.copied` class, restores original innerHTML (svg friendly).
- Wired both scripts in `website/src/_includes/base.njk` before `</body>` using absolute `/assets/js/...` paths (passthrough copied by Eleventy).
- Build verified: `cd website && npm run build` emits clean `_site/index.html` containing the four slides, controls, copy button, and both script tags.

The carousel uses the same terminal chrome (`.t-dots`, `.t-body`, token classes `.t-cmd`/`.t-arg`/`.t-ok` etc.) that Agy's step cards already styled.

## Brainstorm Visuals Used
- `docs/brainstorm/bs5-website-redesign/hero-v4.html` — exact source for markup structure, slide copy, terminal chrome, pill + dot nav, color accents, and the original inline JS reference implementation.

## What This Achieved on the Path to Autonomy
The live carousel is the first "show, don't tell" surface that lets a visitor instantly grasp the four core user actions that turn isolated CLIs into a coordinated workgroup. The copy button lowers friction to the exact first command. Together they turn the website from a brochure into a working demonstration of the OS layer. This is table stakes for the later "Agent Autonomy Bridge" and public launch narrative.

## Strategic Note: The Goal at the End of This PR
With Sections 1–5 + vision shell + interactive carousel complete, the homepage is now feature-complete for the current phase of BS-5. Remaining work (per the implementation plan) is Phase 3 details: vision motherboard canvas, docs cards, waitlist form, blog integration, and any sub-pages. The next user-visible milestone is pointing a real domain + CloudFront/S3 (or equivalent) at the built site and driving traffic from the CLI `--doctor` / `synlynk.com` mentions.
