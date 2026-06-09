# synlynk.com Features Page — Design Spec

**Date:** 2026-06-09  
**Status:** Approved — ready for implementation  
**Brainstorm visuals:** `docs/brainstorm/features-page/`

---

## Overview

A Features page system for synlynk.com consisting of four page types:

| URL | Purpose |
|---|---|
| `/features/` | Feature matrix with OS-layer / user-facing toggle, 3-version moving window |
| `/features/<slug>/` | Per-feature detail page (medium depth) |
| `/releases/` | Full release history index (footer link, all versions including archived) |
| `/releases/v0.X/` | Per-release detail page (changelog + install command) |

---

## 1. Feature Matrix Page (`/features/`)

### Release columns

- Columns = **minor versions** (v0.2.x, v0.3.x, v0.4.x) — patch releases do not get their own column.
- **Moving window of 3 minor versions** shown in the matrix at any time. When a new minor ships (e.g., v0.5.x), v0.2.x drops out of the matrix.
- The current (latest) release column is visually highlighted: teal left/right border, teal version label, **↓ install** pill + **changelog →** link in the column header.
- Older release columns within the window are greyed (no install pill). Archived releases (outside the window) are not shown in the matrix.
- All release column headers link to their `/releases/v0.X/` page.

### View toggle

Two views switchable via a toggle at the top of the page. Both use the same matrix table structure; only the row groupings differ.

**OS Layer view** — groups by kernel metaphor layer:
- Kernel — Context Engine
- Filesystem — State & Telemetry
- IPC — Agent Files & Coordination
- Scheduler — Dispatch
- Job Control *(v0.6.x+)*
- Open Context *(v0.8.x+)*

**User-Facing view** — groups by user goal:
- Context Management
- Cost & Visibility
- Agent Coordination
- Autonomy & Dispatch

### Matrix row anatomy

Each feature row contains:
- Feature name (links to `/features/<slug>/`)
- One-line subtitle description
- Checkmark (✓ teal) or dash (— light grey) per release column
- "new" badge (amber) on features introduced in the currently visible window

### Footer row

Below the table: `Older releases: View full release history →` linking to `/releases/`.

---

## 2. Per-Feature Pages (`/features/<slug>/`)

### Content (medium depth)

1. **What it does** — 2–3 sentence description of the feature's purpose.
2. **OS layer placement** — which layer this belongs to, why it lives there, and what it connects to (upstream and downstream features).
3. **Introduced in** — version badge + link to the release page where it landed.
4. **Usage** — one or two concrete `synlynk` command examples with expected output.
5. **Related features** — 2–4 linked feature names that are architecturally adjacent.
6. **Upgrade notes** — only if the feature changed behaviour across versions (e.g., a flag renamed, a file moved). Omit section if not applicable.

### Navigation

- Back link: `← All features` → `/features/`
- Breadcrumb in page header (not in the site nav)

---

## 3. Releases Index Page (`/releases/`)

- Listed in the site footer only (not in the main nav).
- Shows all minor releases in reverse chronological order, including those outside the 3-version matrix window.
- Each row: version badge, release date, 1-line theme summary, links to the release page and GitHub release.
- Archived releases (outside window) shown with a muted "archived" label but no install pill.

---

## 4. Per-Release Pages (`/releases/v0.X/`)

### Content

1. **Release headline** — version + theme (e.g., "v0.4.0 — The Autonomy Driver").
2. **Install command** — `pip install synlynk==0.4.0` or equivalent, with copy button. Only on current-window releases.
3. **What's new** — bulleted list of features introduced in this minor series, each linking to the feature page.
4. **Changelog** — a flat list of all patch releases in this minor (v0.4.0, v0.4.1…), each with a date and 1-line description, linking to the GitHub release tag.
5. **Related blog post** — link to the corresponding post in the "Building the OS" series if one exists.

### Navigation

- Back link: `← All releases` → `/releases/`
- The current-window releases also link back to the feature matrix.

---

## 5. Data Model

All feature and release data lives in 11ty global data files:

### `site/src/_data/features.json`

```json
[
  {
    "slug": "context-injection",
    "name": "Context injection",
    "subtitle": "Reads project-docs/ → .synlynk/context.md before each exec",
    "os_layer": "kernel",
    "user_theme": "context-management",
    "introduced": "0.1",
    "changelog": []
  }
]
```

`os_layer` values: `kernel` | `filesystem` | `ipc` | `scheduler` | `job-control` | `open-context`  
`user_theme` values: `context-management` | `cost-visibility` | `agent-coordination` | `autonomy-dispatch`  
`introduced`: the minor version string (e.g., `"0.3"`)

### `site/src/_data/releases.json`

```json
[
  {
    "minor": "0.4",
    "label": "v0.4.x",
    "theme": "The Autonomy Driver",
    "date": "2026-07-01",
    "current": true,
    "install_cmd": "curl -fsSL https://synlynk.com/install.sh | sh",
    "blog_post": "/blog/06-pr27-v0.4.0-autonomy-driver/",
    "patches": [
      { "version": "0.4.0", "date": "2026-07-01", "summary": "Trio Protocol + synlynk start" }
    ]
  }
]
```

`current: true` marks the latest release (install pill shown).  
Window = the 3 most recent entries where `archived: false` (or where `archived` is absent).  
Add `"archived": true` when a minor falls out of the window.

---

## 6. 11ty Template Structure

```
site/src/
  features/
    index.njk          ← /features/ (matrix page)
    feature.njk        ← /features/<slug>/ (per-feature, pagination over features.json)
  releases/
    index.njk          ← /releases/ (history index)
    release.njk        ← /releases/v0.X/ (per-release, pagination over releases.json)
  _data/
    features.json      ← feature definitions
    releases.json      ← release definitions
  _includes/
    base.njk           ← add "Features" to nav (between "How it works" and "Install")
```

The matrix view toggle is a small inline `<script>` (no framework) that swaps CSS display on the two `<tbody>` groups. No build step, no JS bundler — consistent with the zero-dependency site philosophy.

---

## 7. Nav & Footer Changes

**Nav** (`base.njk`): Add `Features` between `How it works` and `Install`.

```html
<a href="/features/">Features</a>
```

**Footer** (`base.njk`): Add `Releases` alongside Changelog, Discussions, MIT.

```html
<a href="/releases/">Releases</a>
```

---

## 8. Implementation Scope

**In scope:**
- All four page types with 11ty Nunjucks templates
- `features.json` and `releases.json` data files populated for all current releases (v0.1–v0.4)
- View toggle (inline JS, no framework)
- Nav + footer link additions
- CSS for matrix table, feature pages, and release pages (extend `main.css`)

**Out of scope:**
- Search/filter within the matrix
- Per-feature API reference or config option tables (upgrade to C-depth later)
- Dark mode toggle (inherits existing site theme)
- Automated generation of `features.json` from git history
