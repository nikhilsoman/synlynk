# BS-5: synlynk.com Website Redesign — Design Spec
**Date:** 2026-06-27  
**Status:** Phase 1 complete — approved for implementation  
**Next:** Implementation plan (session 2, ~1 week)

---

## Goal

Replace the current documentation-dump homepage with a product-story-led experience that converts solo developers and engineering teams into synlynk users and waitlist signups for synlynk.com account management.

**Long-arc goal:** synlynk.com becomes the coordination OS dashboard — account management, team workspaces, hosted dispatch. The site must be designed to accommodate that future while shipping a useful MVP now.

---

## Audience

| Primary | Secondary |
|---------|-----------|
| Solo developer already using 1–2 AI CLIs | Engineering team lead evaluating multi-agent tooling |
| Pain: not knowing workgroups are possible | Pain: no shared context or cost visibility across agents |
| Hook: "you could be running a workgroup" | Hook: "your team's agents could share project state" |

---

## Narrative Arc: C → D → A

- **C (Reveal hook):** "Most developers use one agent at a time." — not framed as pain, framed as a gap most people haven't noticed.
- **D (Unlock):** "synlynk lets you run a workgroup." — the product is the solution.
- **A (Vision):** synlynk as a coordination OS — the layer that schedules, routes, monitors, and accounts for every agent in your org.

**Token economics as sub-hook:** distributing work across agents is cheaper (lower effective $/tok) and richer (model diversity). This is woven into the relief section, not the headline.

---

## Site Architecture

**Stack:** 11ty (Eleventy) v3, Nunjucks, GitHub Pages, plain CSS, vanilla JS. No build dependencies beyond 11ty.

**Hybrid mode:** Static marketing + waitlist stub now. Account management / team invites are stubbed as a waitlist CTA (`synlynk.com` coming soon).

**OSS contributor strategy:** Handled separately as a GitHub-native epic (README, Issues, Polls, Project Boards). Not part of this spec.

---

## Visual System

| Token | Value |
|-------|-------|
| Background dark | `#0E0E0F` |
| Background light | `#f5f5f7` (Apple-inspired) |
| Blue | `#5B8DEF` |
| Purple | `#A259F7` |
| Teal | `#2EC4A0` |
| Orange (Claude) | `#D97757` |
| Google Blue (Gemini) | `#4285F4` |

**Alternation:** dark → dark → light → dark → light → dark → light → dark

**Logo:** S-glyph SVG (`docs/img/logo/synlynk-by-claude/03-terminal-s-glyph.svg`) — two Bézier paths (blue, purple) + vertical teal stem + endpoint circles.

**Typography:**
- Display: Inter 800, `clamp(32px, 4vw, 52px)`, letter-spacing `-1.8px`
- Body: Inter 400, 16px
- Code/terminal: JetBrains Mono

**Direction:** Bolder Brand — gradient headline, dark substrate, accent-bordered cards, terminal aesthetics throughout.

---

## Page Sections (8)

### 1. Tagline (dark, 100vh)
- **Byline (problem):** "Most developers use one agent at a time." — 20px, muted
- **Headline (unlock):** "synlynk lets you run a workgroup." — 52px max, purple-blue gradient on "synlynk"
- **Sub:** "Spread the work, spread the cost. Different models, different strengths, one shared project state."
- **CTAs:** "Install synlynk" (blue primary) + "Read the docs" (ghost)
- **Persistent install bar:** `curl -fsSL install.synlynk.com | bash` with copy button — always visible below CTAs
- **Agent chips:** Claude · Gemini · Grok · Codex with brand icons

### 2. Terminal Carousel (dark)
- Full-width section, one slide visible at a time (fade transition, 4.2s auto-advance)
- Command pills (init / join / dispatch / status) + dot indicators
- **Slide 1 — `synlynk init`:** Onboarding wizard questions → created project-docs/, CLAUDE.md, config
- **Slide 2 — `synlynk join --scan`:** Repo scan → infers stack, generates memory.md, detects teammates
- **Slide 3 — `synlynk dispatch`:** Sends 3 background jobs to claude/agy/codex with context injection
- **Slide 4 — `synlynk status`:** Job table from state.db with token counts, cost, budget pulse

### 3. Relief (light)
- Headline: "You're not limited to one agent. You just needed a harness."
- 3 cards: Context injection · Unified cost tracking · Sentinel monitoring
- Token economics callout: ~60% cheaper effective rate when distributed across 3 agents

### 4. How It Works (dark)
- 4 steps: Install → Init → Exec → Dispatch
- Each with a code block and concise description

### 5. Features (light)
- 2×2 grid: Dispatch · Context Injection · Sentinel Monitoring · Agent Profiles
- Each with command example, description, tags

### 6. OS Vision (dark, dramatic)
- Left: headline "synlynk is becoming a coordination OS for AI workgroups." + stats (4 agents · 0 deps · MIT)
- Right: **Isometric motherboard diagram** (canvas animation)
  - Central NPU chip (synlynk) with S-glyph, die grid, purple glow
  - 4 CPU stacks at corners: Claude (Opus/Sonnet/Haiku), Gemini (Pro/Flash), Grok (3/mini), Codex (o3/o4-mini/GPT-4.1)
  - London Tube-style metro lines connecting each stack to NPU via L-shaped routes
  - Interchange station circles: dispatch · relay · profiles · state
  - Animated data packets traveling along routes

### 7. Docs Download (light)
- 3 document cards with thumbnails: Quick Start Guide · Command Reference · The Manual

### 8. Waitlist (dark) + Blog teasers + Footer
- Email signup for synlynk.com early access
- 3 blog teasers (most recent posts from `docs/blog/`)
- Footer: GitHub · Docs · Blog · Changelog · Privacy

---

## Key Assets

| Asset | Location |
|-------|----------|
| S-glyph SVG | `docs/img/logo/synlynk-by-claude/03-terminal-s-glyph.svg` |
| Full page mockup | `docs/brainstorm/bs5-website-redesign/hero-v4.html` |
| Isometric diagram (standalone) | `docs/brainstorm/bs5-website-redesign/diagram-isometric.html` |
| Compact motherboard | `docs/brainstorm/bs5-website-redesign/diagram-motherboard-compact.html` |
| Agy diagram directions | `docs/brainstorm/bs5-website-redesign/diagram-directions.html` |
| Quick Start style reference | `docs/synlynk-quickstart-apple.html` |

---

## Deferred / Phase 2

- OSS Maintainer autopilot agent — separate epic (GitHub-native: README, Issues, Polls, Boards)
- Account management / team workspaces UI — stub as waitlist for now
- Grok image gen dispatch (CLI `--single` flag issue unresolved — separate fix needed)
- Blog series page (index + full post view)
- Mobile responsive pass

---

## Decisions Log

| Decision | Rationale |
|----------|-----------|
| Reveal hook over pain hook | Most devs don't feel pain from single-agent; they don't know workgroups exist |
| Persistent install bar over CTA modal | Always discoverable, lower friction than a hidden copy component |
| Isometric motherboard for OS Vision | Most distinctive; CPU-stack-per-harness metaphor maps to model tier hierarchy |
| London Tube routing (L-shaped) | Matches PCB orthogonal routing conventions; readable as metro map |
| No carousel peek element | Looked visually disconnected floating at bottom of hero |
| OSS epic split out | GitHub-native tools (Issues, Polls, Boards) don't belong in the site redesign epic |
