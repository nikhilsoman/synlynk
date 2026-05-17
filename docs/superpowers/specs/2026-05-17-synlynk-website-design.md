# synlynk.com — Website Design Spec

**Date:** 2026-05-17
**Version:** 1.0
**Status:** Approved

---

## Overview

A single-page landing site at synlynk.com with a blog section, hosted on GitHub Pages. The site serves as the public face of the synlynk project — communicating what it does, how to install it, and where the project is headed. The blog publishes one post per release plus origin story posts at launch.

---

## Architecture

### Repository structure

Website source lives inside the existing `nikhilsoman/synlynk` repo under `/site/`. Build output is deployed to a `gh-pages` branch via GitHub Actions.

```
synlynk/
  site/
    .eleventy.js          # 11ty config
    package.json          # 11ty + plugins (no runtime deps)
    src/
      index.njk           # Landing page template
      blog/
        index.njk         # Blog listing page
        posts/            # Markdown post files
          2026-05-10-why-i-built-synlynk.md
          2026-05-14-from-idea-to-v010.md
          2026-05-17-redesigning-for-v020.md
          2026-05-17-v020-release-deep-dive.md
      _includes/
        base.njk          # HTML shell (head, nav, footer)
        post.njk          # Blog post layout
      assets/
        css/
          main.css        # All styles, no framework
        js/
          copy.js         # Copy-to-clipboard for code blocks
        img/              # Logo assets copied via 11ty addPassthroughCopy from ../docs/img/logo/
    _site/                # 11ty output (gitignored)
  docs/                   # Project docs (unchanged)
  bin/                    # synlynk CLI (unchanged)
  CNAME                   # → synlynk.com (in gh-pages branch)
```

### Tech stack

| Layer | Choice | Reason |
|---|---|---|
| Static site generator | [11ty (Eleventy)](https://www.11ty.dev/) v3 | Full HTML/CSS control, Markdown posts, no framework lock-in |
| Templates | Nunjucks (`.njk`) | Ships with 11ty, clean syntax |
| Styles | Plain CSS (custom properties) | No build pipeline beyond 11ty |
| JS | Vanilla, single file | Copy-to-clipboard only; no bundler needed |
| Hosting | GitHub Pages (`gh-pages` branch) | Free, custom domain, zero infra |
| Deploy | GitHub Actions | Same pattern as existing CI workflow |
| Domain | synlynk.com via CNAME | Point DNS A records to GitHub Pages IPs |

### Deployment flow

1. Push to `main` triggers `site.yml` workflow
2. Actions: `cd site && npm ci && npx eleventy`
3. `_site/` contents pushed to `gh-pages` branch
4. GitHub Pages serves `gh-pages` with custom domain `synlynk.com`

Only changes under `site/` or `docs/img/logo/` trigger the site workflow (path filter).

---

## Visual Design System

### Palette

| Token | Value | Usage |
|---|---|---|
| `--bg-dark` | `#0E0E0F` | Hero, install band, footer background |
| `--bg-dark-elevated` | `#252526` | Code block fill |
| `--bg-dark-subtle` | `#1a1a1c` | Secondary code block, nav |
| `--bg-light` | `#ffffff` | Problem, features, blog sections |
| `--bg-light-alt` | `#fafafa` | How it works, roadmap sections |
| `--border-dark` | `#3a3a3c` | Code block border on dark bg |
| `--border-light` | `#f0f0f0` | Section dividers on light bg |
| `--accent-blue` | `#5B8DEF` | CTA button, step 1 number, "l" in wordmark |
| `--accent-purple` | `#A259F7` | "y" in wordmark, section labels |
| `--accent-teal` | `#2EC4A0` | Code text, "n" in wordmark, active states |
| `--text-primary` | `#1a1a1a` | Body text on light bg |
| `--text-secondary` | `#666` | Subtitles, descriptions |
| `--text-muted` | `#aaa` | Dates, minor labels |
| `--text-hero` | `#d4d4d4` | Wordmark on dark bg (not pure white) |
| `--text-hero-sub` | `#ccc` | Hero tagline |
| `--text-hero-body` | `#666` | Hero description paragraph |

### Typography

| Element | Font | Weight | Notes |
|---|---|---|---|
| Wordmark (hero) | Courier New, monospace | 500 | `-webkit-font-smoothing: antialiased` applied to hero section |
| Wordmark (nav, footer) | Courier New, monospace | 500 | Same |
| Code blocks | Courier New, monospace | 400 | `#2EC4A0` on dark, `#333` on light |
| Section labels | System UI | 600 | Uppercase, letter-spacing 3px, 11px |
| Body headings | System UI | 500–600 | |
| Body text | System UI | 400 | 13–14px, line-height 1.7 |
| Blog prose | System UI | 400 | Max-width 680px, 16px, line-height 1.8 |

### Wordmark colour rule

The "syn" and "k" characters use the contextual text colour. The three middle characters are always brand-coloured:

- `l` → `--accent-blue` (`#5B8DEF`)
- `y` → `--accent-purple` (`#A259F7`)
- `n` → `--accent-teal` (`#2EC4A0`)

### Icon border

The icon mark (terminal S-glyph) always renders with `stroke="#888" stroke-width` scaled to produce a ~2px visible border against any dark background. This prevents the dark icon body from blending into dark section backgrounds.

---

## Page Sections

### Navigation (sticky, dark)

- Left: wordmark lockup (icon + "synlynk" text)
- Right: "How it works" · "Install" · "Blog" (teal) · "GitHub ↗" (pill button)
- Transparent on hero, solidifies to `--bg-dark-subtle` on scroll
- Mobile: text links hidden below 640px except "Blog" and a GitHub icon (SVG octocat); no hamburger

### 1. Hero (dark, full-width)

**Background:** `#0E0E0F` with a subtle radial gradient (dark purple at top center → black) — `radial-gradient(ellipse at 50% 0%, #1a1040 0%, #0E0E0F 65%)`

**Content (centred):**
1. Logo lockup: 52px icon + 34px wordmark, `font-weight:500`, colour `#d4d4d4`, antialiased
2. Tagline: "Keep your AI tools in sync with your project." — 19px, `#ccc`
3. Body: "A single-file Python CLI that injects project context into every AI session — no lost state, no repeated setup, no invisible costs." — 13px, `#666`, max-width 520px
4. Primary code block (install command)
5. Secondary code block (no-install alternative)
6. CTA row: "Get started →" (blue filled) · "View on GitHub" (outline)
7. Requirement badges: "Python 3.8+ · stdlib only · MIT" — 11px, monospace, `#3a3a3c`

**Code block spec:**

| Property | Primary block | Secondary block |
|---|---|---|
| Background | `#252526` | `#1a1a1c` |
| Border | `1px solid #3a3a3c` | `1px solid #2a2a2c` |
| Border radius | 8px | 6px |
| Padding | 14px 56px 14px 20px | 10px 56px 10px 20px |
| Font size | 13px | 12px |
| Text colour | `#2EC4A0` | `#666` |
| Overflow | `white-space:nowrap; overflow:hidden; text-overflow:ellipsis` | same |
| Copy icon | 18px white SVG clipboard, absolute right 10px | 16px `#888` SVG clipboard |

**Copy button behaviour:**
- Copies full command string (not the truncated display text)
- Icon swaps to teal `✓` checkmark SVG for 1.5 seconds on success
- Hover: `rgba(255,255,255,0.1)` background pill
- Implemented in `assets/js/copy.js` as a `data-copy` attribute pattern — no inline JS in HTML

**Primary command:** `curl -sSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | bash`
**Secondary command:** `python3 bin/synlynk.py <command>`

### 2. Problem (white)

Centred prose, max-width 560px, no heading chrome — just the section label "THE PROBLEM" in purple uppercase, then one short paragraph at 20px:

> Every AI session starts from scratch. Switch from Claude to Gemini and it has no idea what you were building. Switch accounts and your task list evaporates. Costs accumulate invisibly.

### 3. How it works (light alt)

Section label "HOW IT WORKS" in blue uppercase. Four-column step grid, max-width 680px, centred:

| Step | Label | Description |
|---|---|---|
| 1 (blue) | init | Bootstrap project-docs/ and AI instruction files |
| 2 (purple) | exec | Run any AI CLI with context injected automatically |
| 3 (teal) | checkpoint | Archive completed tasks, refresh state, log telemetry |
| 4 (grey) | status | Dashboard: tasks, budget, alerts, watcher state |

Each step: numbered circle (dark bg, accent colour number) + bold label + 1-line description.

### 4. Features (white, 2×2 card grid)

Section label "FEATURES" in teal uppercase. Four cards, max-width 600px, centred:

| Glyph | Title | Description |
|---|---|---|
| ⟡ | Context injection | Shared project-docs/ directory every AI tool reads at session start |
| ◈ | Cost tracking | Budget limits with 80% warnings. Spend read from costs.md |
| ◎ | Watch daemon | Background process regenerates context.md as project-docs/ changes |
| ◬ | Sentinel alerts | Detects flatline failure loops — 3 consecutive failures of the same command |

Cards: 1px `#eee` border, 10px radius, 20px padding.

### 5. Install (dark band)

Section label "INSTALL" in `#888` uppercase. Centred code block with the install command (same spec as hero primary block). Secondary "no install" line below. Three requirement badges: "Python 3.8+" · "stdlib only" · "MIT license".

This section exists so a user who scrolls past the hero can still copy the install command without scrolling back up.

### 6. Roadmap (light alt)

Section label "ROADMAP" in purple uppercase. Three-column layout with a horizontal progress line. Each column: status dot + title + 2-line description.

| Stage | Dot | Title | Status |
|---|---|---|---|
| 1 | `#2EC4A0` filled | Solo edition | Current — v0.2.0 |
| 2 | `#333` with `#ddd` border | Team edition | Next |
| 3 | `#333` with `#ddd` border | Enterprise | Future |

Below: "Vote on what to build next →" linking to GitHub Discussions.

### 7. Blog — "From the build log" (light alt)

Section label "FROM THE BUILD LOG" in blue uppercase. Three most-recent posts listed, max-width 600px. Each post row:
- Date in monospace `#aaa`
- Title in 15px `#1a1a1a`
- Excerpt in 12px `#777`
- Bottom border `#eee`

"All posts →" link right-aligned, linking to `/blog/`.

### 8. Footer (dark, matches hero)

Single row: wordmark left · links right (GitHub · Discussions · Changelog). Below: version badge (pulled from `site/src/_data/site.json` → `version` field, updated each release) and "MIT" in `#444` monospace. No newsletter, no social beyond GitHub.

---

## Blog System

### Post format

Markdown files in `site/src/blog/posts/`. Front matter:

```yaml
---
title: "Why I built synlynk"
date: 2026-05-10
excerpt: "Three AI tools. Three separate contexts. Zero shared memory. There had to be a better way."
tags: [origin, story]
---
```

### Initial post set (launch)

| File | Date | Title |
|---|---|---|
| `2026-05-10-why-i-built-synlynk.md` | 2026-05-10 | Why I built synlynk |
| `2026-05-14-from-idea-to-v010.md` | 2026-05-14 | From idea to v0.1.0: the first working CLI |
| `2026-05-17-redesigning-for-v020.md` | 2026-05-17 | Redesigning for v0.2.0: watch daemon, checkpoint, and context compaction |
| `2026-05-17-v020-release-deep-dive.md` | 2026-05-17 | Release notes deep dive: v0.2.0 |

**Post content guidance:**

- *Why I built synlynk* — the original pain point: context loss across AI tools, invisible costs, no shared state. Personal, conversational tone.
- *From idea to v0.1.0* — what the first CLI was, what it got right, what it obviously missed. The minimal loop: init → exec → context.md.
- *Redesigning for v0.2.0* — what v0.1.0 made obvious: stale context, no archiving, no daemon. Design choices behind watch, checkpoint, sentinel. Why stdlib-only matters.
- *v0.2.0 release deep dive* — detailed walkthrough of every CHANGELOG entry. Each new function, what it does, why the interface is the way it is.

**Future posts:** one per release. Authored as a detailed CHANGELOG walkthrough. Linked from the GitHub release page.

### Blog index (`/blog/`)

List of all posts, newest first. Date · title · excerpt. Same light body background as landing page.

### Post layout

Max-width 680px prose, centred. No sidebar. Font: system UI 16px, line-height 1.8. Syntax highlighting via [Prism.js](https://prismjs.com/) (11ty plugin, dark theme to match brand). Back link to `/blog/` at top and bottom.

---

## Assets

### Existing (in repo)

| File | Usage |
|---|---|
| `docs/img/logo/icon.svg` | Favicon, og:image fallback |
| `docs/img/logo/lockup.svg` | README only (dark text on transparent — not used on website) |
| `docs/img/logo/synlynk-by-claude/03-terminal-s-glyph.svg` | Source of truth for icon geometry |

### New assets needed

| File | Description |
|---|---|
| `site/src/assets/img/og-image.png` | 1200×630 Open Graph image — dark hero bg, logo lockup centred |
| `site/src/assets/img/favicon.svg` | 32×32 icon mark only (no wordmark) |
| `site/src/assets/img/apple-touch-icon.png` | 180×180 icon mark on dark bg |

The OG image and favicons can be generated from `icon.svg` during the implementation phase.

---

## GitHub Pages & Custom Domain

1. Create `CNAME` file in `gh-pages` branch root containing `synlynk.com`
2. DNS: add four A records pointing to GitHub Pages IPs (185.199.108–111.153) plus AAAA records for IPv6
3. Enable "Enforce HTTPS" in repo Settings → Pages after DNS propagates
4. `www.synlynk.com` → CNAME to `nikhilsoman.github.io` (GitHub handles redirect to apex)

---

## Out of scope

- Analytics (can add later via Plausible or similar)
- Search
- Comments on blog posts (GitHub Discussions linked instead)
- Dark/light mode toggle (dark hero + light body reads well on both)
- RSS feed (can add as a future 11ty plugin)
