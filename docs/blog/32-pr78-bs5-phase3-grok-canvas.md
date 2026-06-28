---
title: "PR — BS-5 Phase 3: Grok Isometric Motherboard Canvas (OS Vision)"
date: 2026-06-28
series: "Building the OS for Multi-Agent Development"
post: 32
pr: "#78"
merged: TBD
---

## The Broader Goal at the End of the Previous PR
Phase 2 (Agy + Grok) delivered the Tagline Hero, Relief, How-It-Works, Features spotlight, full terminal carousel for the four core commands, copy affordance, CSS design system (cards, terminals, buttons, labels), and macros. The homepage had a complete marketing surface and interactive "show don't tell" demo. The single remaining dramatic centerpiece specified in the BS-5 design was Section 6 — the OS Vision canvas that literally draws the "coordination OS" story.

## Strategic Shifts in This PR
None. Pure implementation of the Section 6 spec handed off from the design doc. The isometric motherboard metaphor (NPU as synlynk core + four harness CPU stacks + London Tube L-shaped metro routing) was locked in the brainstorm and spec; this PR simply ported it faithfully into the live 11ty site.

## What This PR Shipped

<figure class="brainstorm-visual">
  <iframe src="/assets/brainstorm/bs5-diagram-impl/diagram-motherboard.html" title="Motherboard diagram design" loading="lazy" frameborder="0"></iframe>
  <figcaption>Motherboard diagram design</figcaption>
</figure>

- Replaced the `#vision` placeholder shell in `website/src/index.njk` with the exact two-column layout from the task:
  - Left: `.section-label.dark` ("The coordination layer"), `.section-title`, `.section-body`, and `.vision-stats` row (4 / agents, 0 / deps, MIT / license) using `.stat-item > .stat-value + .stat-label`.
  - Right: `.vision-canvas-wrap` containing `<canvas id="motherboard-canvas" width="520" height="460">`.
- Added the full CSS block (`.section-vision`, `.vision-inner` grid `1fr 1fr`, responsive mobile flip with `order:-1`, stat typography) directly after the features section in `website/src/assets/css/main.css`.
- Created `website/src/assets/js/motherboard.js`:
  - Complete port of the isometric + metro animation from `docs/brainstorm/bs5-website-redesign/diagram-isometric.html` (615-line reference).
  - All elements: board grid + traces + vias, central NPU with S-glyph (purple/blue/teal), four corner CPU stacks labeled Claude (#D97757), Gemini (#4285F4), Grok (#A259F7), Codex (#888), L-shaped tube lines with 5 routes (incl. teal trunk), interchange station circles at dispatch/relay/profiles/state + ctx points, animated particles (packets) traveling via requestAnimationFrame.
  - HUD (COORD-OS + "4 AGENTS · 0 DEPS · MIT") and bottom-right legend drawn on-canvas.
  - Encapsulated in IIFE; only `window.__synlynkMotherboard` debug handle.
  - Pause on `prefers-reduced-motion`, `visibilitychange` (tab hidden), and `IntersectionObserver` (start when canvas enters view). Self-starts on DOMContentLoaded.
- Wired the new script in `website/src/_includes/base.njk` immediately before `</body>`.
- `cd website && npm run build` verified clean (1 njk + passthrough assets).

The canvas projection constants (TW/TH/ZS/OX/OY) were tuned for the 520×460 target while preserving the exact visual language and painter order from the reference.

## Brainstorm Visuals Used
- `docs/brainstorm/bs5-website-redesign/diagram-isometric.html` — primary full source for every drawing primitive, particle system, iso projection math, NPU die, S-glyph bezier, tube styling, CPU stack labeling, and animation loop.
- `docs/brainstorm/bs5-website-redesign/diagram-motherboard-compact.html` — secondary reference for sizing/legend density on a ~460px-tall canvas.
- `docs/superpowers/specs/2026-06-27-bs5-website-redesign-design.md` — Section 6 requirements (stats copy, label "The coordination layer", exact canvas id + two-col grid, color assignments).

## What This Achieved on the Path to Autonomy
Section 6 is the emotional and narrative payoff of the homepage. Visitors now see the "coordination OS" rendered live: agents as swappable CPU stacks on a shared motherboard, data flowing over explicit metro routes through dispatch/relay/state hubs, with the synlynk NPU at the center emitting the S-glyph. It makes the abstract OS-layer claim concrete and ownable in a way no bullet list can. This directly supports the long-arc goal of autonomous multi-agent dispatch by telling the story of a single substrate that every agent (Claude, Gemini/Agy, Grok, Codex) plugs into.

## Strategic Note: The Goal at the End of This PR
With the vision canvas live, the core marketing narrative (hero → demo carousel → features → OS vision) is complete. Remaining BS-5 work per the plan and active tasks is finishing the light docs and waitlist sections, any final polish, wiring the blog index, and cutting over a real domain/CF/S3 (or GitHub Pages) so `install.synlynk.com` and CLI doctor can point at it. Next major user-visible milestone after this is external launch of the redesigned site + the BS-6 visualization and BS-7 interop sessions.
