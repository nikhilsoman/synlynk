# BS-5: synlynk.com Website Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:brainstorming (if visuals needed), superpowers:writing-plans (already used), then subagent-driven-development or executing-plans for impl. Steps use checkbox (`- [ ]`) syntax. Claude reviews only — never authors.

**Date:** 2026-06-28  
**Story:** BS-5 (story-048f5fe5)  
**Target:** Stand up redesigned synlynk.com as the canonical marketing site ahead of v0.10.0 Dev Preview.  
**Spec:** `docs/superpowers/specs/2026-06-27-bs5-website-redesign-design.md`  
**Visuals:** `docs/brainstorm/bs5-website-redesign/hero-v4.html` (full page), `diagram-isometric.html`, `diagram-motherboard-compact.html`, logo `docs/img/logo/synlynk-by-claude/03-terminal-s-glyph.svg`

---

## Goal

Replace the current documentation-dump homepage (`site/`) with a product-story-led experience (C → D → A narrative) that converts solo devs and team leads. The site is static marketing + waitlist stub today; designed to evolve into the coordination OS dashboard later without full rewrite.

**Success criteria (Definition of Done for the epic):**
- 8 homepage sections match spec + hero-v4 visual/animation fidelity (within responsive + browser variance).
- All listed additional pages (blog, docs, features, changelog, about) exist with consistent visual system, shared nav/footer.
- Isometric motherboard canvas (Section 6) and terminal carousel (Section 2) are live, smooth, and match reference diagrams.
- Blog teaser cards pull hero images via the extraction pipeline (or documented fallback).
- Zero build deps beyond Eleventy v3. `npm run build` in `website/` produces production-ready `_site/`.
- GitHub Pages workflow updated; site deploys cleanly to synlynk.com (or staged path until cutover).
- The capability scoring test matching this brainstorm passes with no new failures.
- All PRs reviewed by Claude before merge.

---

## Architecture & Constraints

**Stack (locked):** 11ty v3, Nunjucks, GitHub Pages, plain CSS, vanilla JS. No Tailwind, no React, no bundlers.

**Output:** New top-level `website/` directory (parallel to existing `site/`). Old `site/` remains until explicit cutover (Phase 4 or later chore PR).

**Visual system (from spec):**
- Dark base `#0E0E0F`, light `#f5f5f7`
- Accents: `--blue:#5B8DEF`, `--purple:#A259F7`, `--teal:#2EC4A0`, `--orange:#D97757`, gemini `#4285F4`
- Typography: Inter (display 800, body 400), JetBrains Mono for terminals/code. Use Google Fonts import or system fallback for zero-asset.
- Alternating sections: dark → dark → light → dark → light → dark → light → dark
- Logo: inline the S-glyph SVG (terminal variant). Support 28px nav, 64px, 40px scales.

**Data & content:**
- Homepage is static Nunjucks (index.njk).
- Blog posts continue to live in `docs/blog/*.md` (single source of truth). Website consumes them.
- CHANGELOG.md rendered for /changelog.
- Features can be data-driven or hardcoded to match homepage Section 5 cards.
- No server-side form handling for waitlist in v1 — UI stub only.

**Agent split (locked by query):**
- **Grok owns:** Initial 11ty scaffold + build pipeline, terminal carousel JS (Sec 2), all canvas/interactive/animated components (esp. isometric motherboard in Sec 6), any shared JS utilities.
- **Agy owns:** All Nunjucks templates + partials, full CSS design system (tokens + layout + dark/light + components), static content for sections 1,3,4,5,7,8 + copy, blog/docs/changelog/features/about pages, blog image extraction pipeline.
- **Claude:** Reviewer only on every PR. Observations + suggestions only. No direct commits or code changes on feature branches.

---

## Branch Strategy & Workflow

- Plan file lives on `chore/bs5-impl-plan` (this branch).
- Main implementation branch: `feat/bs5-website-redesign` (cut from main after plan merge).
- Parallel agent work:
  - Grok works in worktree or dedicated slice branch `feat/bs5-grok-animations` (stacks on feat/bs5-website-redesign).
  - Agy works in `feat/bs5-agy-templates` (or direct on shared when non-conflicting).
- PR discipline: small, agent-owned slices. Each PR includes:
  - Summary bullets.
  - Visual reference links (the brainstorm HTMLs).
  - Screenshot of built page (local or deploy preview).
  - "Claude review requested" label.
- Merge only after Claude +1 (comment) + green build.
- Do not touch `site/` files in this epic unless a migration step is explicitly approved.
- At cutover (Phase 4): update `.github/workflows/site.yml` publish_dir + any root links. Old `site/` can be archived or removed in a follow-up chore.

**Worktree usage:** Before any heavy implementation sessions, invoke the using-git-worktrees skill (or manual `git worktree add .worktrees/feat+bs5-website-redesign -b feat/bs5-website-redesign`).

---

## Phase Breakdown

### Phase 1: Scaffold & Foundations (Grok owns, ~1 session)

**Status:** ✅ Complete (2026-06-28, committed on feat/bs5-website-redesign)

**Goal:** Runnable 11ty project in `website/` that produces a shell matching nav + hero layout from hero-v4.html. No content fidelity required beyond structure.

**Dependencies:** None.

**Tasks:**

- [ ] **Grok:** Create `website/` directory + standard 11ty layout:
  - `website/package.json` (name: "synlynk-website", scripts: build/serve, devDep @11ty/eleventy@^3.0.0)
  - `website/.eleventy.js` (passthrough for assets + logo, basic dateFilter, collection setup for blog later)
  - `website/src/_includes/base.njk` (minimal head, nav from mock, footer stub, slot for content)
  - `website/src/index.njk` (empty shell with correct section ids: #top, #carousel, #how, #features, #docs, #waitlist etc.)
  - `website/src/assets/css/main.css` (root with tokens from spec/hero-v4; reset; basic nav + section padding)
  - `website/.gitignore` (node_modules, _site, .cache)
- [ ] **Grok:** Copy/inline the S-glyph SVG into assets (or keep as static file + passthrough). Ensure `src/assets/img/logo/` or direct embed. Add to nav in base.
- [ ] **Grok:** Implement basic dark/light section primitives + typography (clamp headlines, Inter stack, mono for code). Match hero-v4 CSS custom properties exactly where listed.
- [ ] **Grok:** Add `npm run serve` dev server on port 8081 (to not collide with old site). `npm run build` outputs to `website/_site`.
- [ ] **Grok:** Verify zero extra deps: `cd website && npm install --no-audit --no-fund && npm run build`.
- [ ] Add root-level convenience (optional): `package.json` workspace hint or root script `website:build`, but keep website self-contained.
- [ ] Document in `website/README.md`: "This is the BS-5 redesign. Deploy via updated gh-pages workflow. Old site/ coexists."

**Definition of Done (Phase 1):**
- `cd website && npm run build` succeeds with _site/index.html containing nav + at least 3 section shells.
- Visual tokens match spec (can diff against hero-v4.css vars).
- Logo renders in nav at correct size.
- No new top-level files outside website/ except this plan.
- Local serve works.

**Review Checkpoint 1:** Open PR from chore or early slice → Claude reviews scaffold fidelity to spec + visual system. Do not proceed to Phase 2 content until Claude approval comment.

**Estimated sessions:** 1 (Grok)

---

### Phase 2: Homepage Core Narrative Sections + Terminal Carousel (Agy primary + Grok JS, ~1–1.5 sessions)

**Dependencies:** Phase 1 scaffold merged + reviewed.

**Tasks:**

**Agy:**
- [ ] Port exact Section 1 (tagline, 100vh) from hero-v4: hook-label, hero-byline, .hero-headline with .grad1 gradient, hero-sub, CTAs, install-bar (with working copy JS stub or handoff), agent-chips (Claude/Gemini/Grok/Codex with simple svgs or emoji).
- [ ] Section 3 (Relief, light bg): headline, 3 relief-cards (Context injection, Unified cost tracking, Sentinel monitoring), cost-callout (~60% cheaper).
- [ ] Section 4 (How It Works, dark): 4 step-cards (Install → Init → Exec → Dispatch) with code snippets and body copy from spec/mock.
- [ ] Section 5 starter (Features light): 2x2 grid skeleton + 4 feat-cards with accent borders, titles, bodies, feat-code, tags (content can be placeholder text matching spec intent).
- [ ] Full CSS extraction / system: buttons (primary/secondary/teal), cards, terminal chrome (t-dots, t-body etc.), responsive grids (start mobile-friendly but full polish deferred).
- [ ] Shared layout: persistent nav (fixed blur), footer stub. Use Nunjucks macros for cards/buttons where it helps.

**Grok:**
- [ ] Section 2 (Terminal Carousel, full dark): full markup + JS from hero-v4.
  - 4 slides exactly (init / join --scan / dispatch / status) with terminal formatting (prompts, t-ok, t-cmd, t-arg, t-val, t-out, t-flag).
  - Auto-advance every ~4.2s (fade).
  - Command pills row + dot nav (slide-dot).
  - Clickable pills/dots that pause auto + switch .active.
  - Pure vanilla — no deps. Put logic in `src/assets/js/carousel.js` (or inline if <60 lines) and import via script tag.
- [ ] Copy button on install-bar in hero: full working `navigator.clipboard` + visual "copied" state (match the inline handlers in mock).
- [ ] Any small interactions for Phase 2 sections.

**Shared:**
- [ ] Ensure dark/light alternation and spacing from mock (96px/80px/120px paddings etc.).
- [ ] Wire internal anchors (#how, #features etc.).
- [ ] Build + manual visual spot-check vs hero-v4.html (open both side-by-side).

**Definition of Done (Phase 2):**
- Homepage scroll produces C→D→A arc with correct section backgrounds.
- Carousel cycles 4 slides, manual nav works, content is verbatim from mock.
- Install bar copy works. Agent chips present.
- No console errors. Lighthouse or manual perf note (canvas not yet).
- CSS is one coherent main.css (tokens at top).

**Review Checkpoint 2:** PR(s) for Phase 2 → Claude reviews narrative flow + carousel behavior + design token consistency. Signoff required before Phase 3.

**Estimated sessions:** 1.5 (Agy leads content/CSS; Grok owns JS animation)

---

### Phase 3: OS Vision (Canvas), Remaining Sections, Subpages, Blog Pipeline (Grok canvas + Agy everything else, ~2 sessions)

**Dependencies:** Phase 2 merged + reviewed.

**Grok tasks (canvas + interactives):**
- [ ] Section 6 (OS Vision, dramatic dark): two-column (text + stats on left, diagram container on right).
  - Stats: "4 agents · 0 deps · MIT" (or current from spec).
  - Headline + body copy from spec.
  - Embed the motherboard: port full working canvas + animation from `diagram-isometric.html` (and use compact as reference).
    - Iso projection, board, CPU stacks (Claude/Gemini/Grok/Codex with model tiers), NPU with S-glyph + glow.
    - London Tube metro lines (L-routes), interchange stations (dispatch/relay/profiles/state), animated packets (use requestAnimationFrame, traveling dots or short path segments).
    - Legend, HUD (COORD-OS v0.9.x, 4 harnesses...).
    - Keep colors exact (claude orange, gemini blue, grok purple, codex gray, trunk teal).
    - Encapsulate in `src/assets/js/motherboard.js` + canvas element. Make it self-starting on load. Optional: pause on reduced-motion or tab hidden.
  - Deliverable must animate packets and look like the reference (test in browser).
- [ ] Any other Phase 3 interactive (e.g. waitlist copy or stats counters if desired — keep minimal).
- [ ] Ensure canvas is responsive or fixed-aspect with media query note (mobile deferred).

**Agy tasks (content + pages + pipeline):**
- [ ] Complete Section 5: 2×2 (or 3×2) feat-cards using exact feature names + command examples + tags from spec.
- [ ] Section 7 (Docs Download, light): 3 doc-cards (Quick Start Guide, Command Reference, The Manual) with thumbs (use existing pngs from `site/src/assets/img/docs/` or new gradients; link to real PDFs in docs/ or raw github).
- [ ] Section 8 + Blog teasers + Footer:
  - Waitlist form (styled input + btn-teal). Action stub: preventDefault, show "Thanks — you're on the list. (synlynk.com account portal coming soon)".
  - 3 blog teaser cards (most recent from docs/blog). Title, date, short excerpt. Use gradient banner or placeholder. Link to full post (or /blog/ later).
  - Footer links: GitHub, Docs, Blog, Changelog, Privacy.
- [ ] **Blog index + post pages:**
  - Configure 11ty (or _data + template) to surface `docs/blog/*.md` posts (use 11ty's `addGlobalData` + fs read or add passthrough + collection via before/after hooks. Avoid new npm deps).
  - `/blog` grid of cards (title, date, excerpt, hero image slot).
  - `/blog/<slug>` individual post view. Reuse typography. Hero image at top.
- [ ] **Blog image extraction pipeline (Agy):**
  - Create `website/scripts/` (or root `website/extract-heroes.js`).
  - For MVP: a documented flow + small script (Node fs only, no puppeteer to stay zero-dep) that:
    - Maintains a `website/src/_data/blogHeroes.json` map: `{ "26-pr68-...": "assets/blog-heroes/pr68-v0.9.8.png" }`
    - Instructions: "To set hero: open docs/brainstorm/<topic>/xxx.html in browser, use DevTools → Capture node screenshot or external tool (e.g. browser's save as image), place in assets/blog-heroes/ with matching name, update manifest."
  - Fallback in template: if no hero, render gradient banner + post number / version (as in spec).
  - In blog cards and post, use the manifest + 11ty url filter.
  - Later enhancement (post-BS5): optional lightweight screenshot step if 11ty plugin or separate allowed.
- [ ] **Additional pages (full reskin, shared base.njk):**
  - `/docs` (section nav sidebar, JetBrains code blocks on dark substrate, pull from existing content or stub with spec language).
  - `/features` (grid consistent with homepage Sec 5).
  - `/changelog` (render root CHANGELOG.md or parsed versioned sections; use badges, Added/Fixed/Changed tags in brand colors).
  - `/about` (mission + OS layer framing from decisions; roster humans + agents Claude/Gemini/Grok/Codex; links to blog series).
- [ ] Update base.njk nav/footer to link all pages. Add active states if simple.
- [ ] Ensure blog posts pull frontmatter (title, date, excerpt) — extend 11ty config minimally.

**Shared:**
- [ ] Dark/light sections continue correctly on subpages.
- [ ] All links internal or correct external.
- [ ] Build succeeds. Manual click-through of nav/blog.

**Definition of Done (Phase 3):**
- Full homepage (all 8 sections) matches visual + interaction intent of references.
- Canvas animates data packets along metro routes; CPU stacks + NPU + legend visible and correct.
- /blog lists ≥3 posts; clicking opens styled post; at least one hero image or clean fallback present.
- /changelog, /features, /docs, /about exist and share visual language (no old site styles leaking).
- Blog pipeline documented in website/README.md or a docs/ note.

**Review Checkpoint 3:** Larger PR or split PRs (Grok canvas PR separate from Agy pages PR recommended). Claude reviews visuals (screenshots + live local), code cleanliness of canvas/JS, and content fidelity. Must pass before Phase 4.

**Estimated sessions:** 2 (Grok canvas heavy lift; Agy templates + pipeline + 4 pages)

---

### Phase 4: Polish, Cutover, Deploy, Final Verification (~0.5–1 session)

**Dependencies:** Phase 3 complete + Claude signoff.

**Tasks (mix Grok/Agy, joint ownership):**

- [ ] **Polish pass (Agy lead, Grok assists on JS):**
  - Typography, spacing, hover states, focus rings, button consistency across pages.
  - Code blocks use proper mono + dark substrate everywhere.
  - Accessibility basics (alt on images, aria on carousel if interactive, contrast).
  - Reduce any layout shift; ensure install bar and CTAs prominent.
- [ ] **Deploy integration (Grok lead):**
  - Update `.github/workflows/site.yml`:
    - Add paths trigger for `website/**`
    - Change build dir to `website`
    - Change `publish_dir: ./website/_site`
    - Keep cname.
  - (Optional) Add a build matrix or separate job if parallel deploys desired during transition. For now, switch primary.
  - Verify workflow syntax (dry-run via dispatch later).
- [ ] **Cutover / coexistence notes:**
  - Add a deprecation banner or note on old site? Or leave as-is until separate PR.
  - Update root README.md links from "site" references if any point to old.
  - Ensure `docs/img/logo` passthrough still works (already referenced in old config).
- [ ] **Docs & meta:**
  - `website/README.md` full usage + hero extraction instructions + "How to add a new blog hero".
  - Update project-docs/todo.md / roadmap.md? (only if natural; plan itself is the artifact).
  - Add a small "Built with 11ty + vanilla" footer credit if fits tone.
- [ ] **Verification commands (run locally):**
  ```bash
  cd website
  npm ci
  npm run build
  # serve and spot-check
  npx @11ty/eleventy --serve   # (in bg or separate)
  ```
  Open http://localhost:8081 , scroll full page, click carousel, inspect canvas animation.
  ```bash
  # From repo root
  python -m pytest tests/test_capability_scoring.py -k 'bs5_brainstorm__standalone_synlynk_websi' -v
  ```
- [ ] Commit any final tweaks on the feature branch. Tag the PRs.

**Definition of Done (Phase 4 + Epic):**
- Deploy preview (via workflow_dispatch or merge to main) shows the new site at synlynk.com (or the action target).
- All DoD items from prior phases + this phase.
- No regressions to existing tests (the targeted capability test + full suite).
- Blog hero extraction instructions are actionable for future posts.
- Old `site/` untouched (except workflow if shared paths).

**Estimated sessions:** 0.5–1 (mostly verification + one deploy PR)

---

## Open Questions & Risks

- **Blog sourcing without extra deps:** 11ty can read Markdown outside src via custom collections + fs + frontmatter parsing (manual or using built-in markdown lib). If too painful, copy recent posts into `website/src/blog/` as a bootstrap step (Agy). Document the choice.
- **Hero image assets:** Real screenshots will add bytes. Use aggressive compression + WebP if simple (but keep PNG for compatibility). Fallbacks must be first-class.
- **Waitlist real backend:** Out of scope. Formspree / Buttondown / custom later when synlynk.com accounts land (post v0.10+). Current is visual + thank-you only.
- **Mobile / responsive:** Explicitly Phase 2 deferred per spec. Add `viewport` + basic media queries; full pass after launch.
- **Font loading:** @import Google Fonts for Inter/JetBrains is acceptable for marketing site (old site already does similar). Self-host only if perf budget requires.
- **Canvas perf / accessibility:** requestAnimationFrame + visibility check. Provide reduced-motion pause. Alt text or description for the diagram.
- **Two sites during transition:** Risk of drift. Mitigate by cutting over in Phase 4 PR and removing/redirecting old quickly after.
- **Content drift vs spec:** Use the hero-v4.html + diagram files as the source of truth for copy/animation during implementation. Update spec only via follow-up if needed.
- **Version in data:** Pull current version from root pyproject or synlynk/__init__.py for badges? Keep simple static or add a small data transform.
- **OSS section:** Per spec, OSS contributor story is GitHub-native only — do not build special page here.

---

## Verification & Success Metrics

1. Build: `cd website && npm run build` → clean _site with index + subpages.
2. Visual: Side-by-side browser render of localhost vs the three key brainstorm HTMLs.
3. Animation: Terminal carousel advances + accepts input. Motherboard shows traveling packets on all 5 lines.
4. Test: `pytest ... -k 'bs5_brainstorm__standalone_synlynk_websi' -v` → all matched pass, no new failures.
5. Deploy: After merge + workflow, curl or browser visit to synlynk.com shows new design (or confirm action logs).
6. PR hygiene: Every slice has Claude review + visual evidence.

---

## File Map (high level)

| Path | Owner | Notes |
|------|-------|-------|
| `website/package.json` | Grok | 11ty only |
| `website/.eleventy.js` | Grok | filters, passthroughs, blog collection |
| `website/src/_includes/base.njk` | Agy | shared shell + nav/footer |
| `website/src/index.njk` + partials | Agy + Grok | homepage sections |
| `website/src/assets/css/main.css` | Agy | all tokens + components |
| `website/src/assets/js/carousel.js` | Grok | Sec 2 |
| `website/src/assets/js/motherboard.js` | Grok | Sec 6 full port + anim |
| `website/src/assets/img/...` | Agy/Grok | logos, doc thumbs, blog-heroes/ |
| `website/src/blog/` (or data) | Agy | index + post templates |
| `website/src/features/`, `docs.njk`, `about.njk`, `changelog.njk` | Agy | subpages |
| `website/scripts/extract-heroes.js` (or manifest) | Agy | pipeline + docs |
| `.github/workflows/site.yml` | Grok | Phase 4 update |
| `docs/superpowers/plans/2026-06-28-bs5-website-implementation-plan.md` | Grok (this) | committed on chore branch |

---

## Timeline Sketch (weekend + follow-up)

- This session: write + commit this plan (chore/bs5-impl-plan)
- Next: merge plan → cut `feat/bs5-website-redesign`
- Phase 1+2 this weekend (parallel Grok/Agy worktrees)
- Phase 3 Sunday/Mon
- Phase 4 + PRs + Claude reviews + deploy early next week
- v0.10.0 batch includes the live site

---

**End of plan.** When executing, mark checkboxes in this file as work progresses. Update status in project-docs/todo.md and memory.md at natural pauses (attribution `[@grok]` or `[@agy]`).

Commit message convention for slices: `feat(bs5): <section> <owner>` e.g. `feat(bs5): terminal carousel (grok)`, `feat(bs5): relief + how sections + tokens (agy)`.

Ready for implementation after Claude review of the plan itself (if required).