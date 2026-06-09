# Features Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a four-page feature matrix system for synlynk.com — `/features/` (matrix with dual-view toggle), `/features/<slug>/` (per-feature detail), `/releases/` (history index), and `/releases/v0.X/` (per-release changelog).

**Architecture:** 11ty v3 Nunjucks site. Global data files (`features.json`, `releases.json`) are the single source of truth. The matrix page loops over data in two groupings (OS layer, user-facing theme) and toggles between them with 20 lines of inline JS. Per-feature and per-release pages use 11ty pagination over those same data files. No build step beyond what already exists.

**Tech Stack:** 11ty v3, Nunjucks, vanilla CSS, inline JS (no framework). Dev server: `cd site && npx @11ty/eleventy --serve` (port 8080).

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `site/src/_data/features.json` | All feature definitions — slug, name, description, OS layer, user theme, introduced version |
| Create | `site/src/_data/releases.json` | All release definitions — minor version, window status, patches, install command, blog link |
| Modify | `site/src/_includes/base.njk` | Add Features to nav; add Releases to footer |
| Modify | `site/.eleventy.js` | Add `featureAvailable` and `windowReleases` filters |
| Create | `site/src/features/index.njk` | Feature matrix page with dual-view toggle |
| Create | `site/src/features/feature.njk` | Per-feature detail page (11ty pagination) |
| Create | `site/src/releases/index.njk` | Full release history index |
| Create | `site/src/releases/release.njk` | Per-release changelog page (11ty pagination) |
| Modify | `site/src/assets/css/main.css` | Matrix table, feature page, release page styles |

---

## Task 1: Data files

**Files:**
- Create: `site/src/_data/features.json`
- Create: `site/src/_data/releases.json`

- [ ] **Step 1: Create `features.json`**

```json
[
  {
    "slug": "context-injection",
    "name": "Context injection",
    "subtitle": "Reads project-docs/ into .synlynk/context.md before each exec",
    "description": "Before every `synlynk exec` call, the harness reads `project-docs/memory.md`, `roadmap.md`, and `todo.md` into a single `.synlynk/context.md` file that is prepended to the agent's prompt. This ensures every AI session starts with current project state — no repeated setup, no lost context.",
    "os_layer": "kernel",
    "user_theme": "context-management",
    "introduced": "0.1",
    "usage": [
      {
        "cmd": "synlynk exec claude",
        "note": "Generates .synlynk/context.md then spawns claude with context prepended"
      }
    ],
    "related": ["flatline-detection", "parametric-init"],
    "changelog": []
  },
  {
    "slug": "flatline-detection",
    "name": "Flatline detection",
    "subtitle": "Alerts and halts when the last 3 runs share identical command + non-zero exit",
    "description": "synlynk tracks the last 100 exec invocations in `.synlynk/telemetry.json`. If the most recent 3 entries share the same command and all exited non-zero, the harness prints a flatline warning and blocks the next run. This prevents silent looping where an agent repeatedly fails at the same step without human review.",
    "os_layer": "kernel",
    "user_theme": "context-management",
    "introduced": "0.1",
    "usage": [
      {
        "cmd": "synlynk exec gemini",
        "note": "After 3 consecutive failures: FLATLINE ALERT — same command, 3 non-zero exits"
      }
    ],
    "related": ["context-injection", "telemetry-log"],
    "changelog": []
  },
  {
    "slug": "cost-tracking",
    "name": "Cost tracking",
    "subtitle": "Appends per-session token counts and $ cost to project-docs/costs.md",
    "description": "After each `synlynk exec` run, the harness scrapes token counts from captured AI CLI stdout using format-specific regex patterns, computes cost at hardcoded rates ($0.003/1K input + $0.015/1K output), appends a row to `project-docs/costs.md`, and prints a Budget Pulse summary to the terminal.",
    "os_layer": "filesystem",
    "user_theme": "cost-visibility",
    "introduced": "0.1",
    "usage": [
      {
        "cmd": "synlynk exec claude",
        "note": "Prints: Budget Pulse | session: $0.24 | total: $3.12 | 14 runs"
      }
    ],
    "related": ["budget-enforcement", "telemetry-log"],
    "changelog": []
  },
  {
    "slug": "budget-enforcement",
    "name": "Budget enforcement",
    "subtitle": "Blocks exec when cumulative cost or request count exceeds configured limits",
    "description": "Before spawning any AI subprocess, `check_budgets()` reads `.synlynk/config.json` for `limit_usd` and `limit_requests`, then compares against totals in `.synlynk/telemetry.json`. If either limit is exceeded, the exec is blocked with a clear message. Limits are project-specific and set at `synlynk init` time.",
    "os_layer": "filesystem",
    "user_theme": "cost-visibility",
    "introduced": "0.1",
    "usage": [
      {
        "cmd": "synlynk exec claude",
        "note": "If over budget: Budget limit exceeded ($50.00). Run synlynk reset to continue."
      }
    ],
    "related": ["cost-tracking"],
    "changelog": []
  },
  {
    "slug": "telemetry-log",
    "name": "Telemetry log",
    "subtitle": "Rolling 100-entry log of every exec — duration, exit code, cost, command",
    "description": "Every `synlynk exec` invocation appends a structured JSON record to `.synlynk/telemetry.json`, keeping only the last 100 entries. Each record includes: timestamp, command, duration_seconds, exit_code, input_tokens, output_tokens, and estimated_cost_usd. This log powers both flatline detection and budget enforcement.",
    "os_layer": "filesystem",
    "user_theme": "cost-visibility",
    "introduced": "0.1",
    "usage": [
      {
        "cmd": "cat .synlynk/telemetry.json | python3 -m json.tool | tail -30",
        "note": "Inspect last 100 exec records"
      }
    ],
    "related": ["cost-tracking", "flatline-detection", "budget-enforcement"],
    "changelog": []
  },
  {
    "slug": "gh-cli-identity",
    "name": "gh CLI identity",
    "subtitle": "Resolves verified GitHub login as the canonical session actor for devlog attribution",
    "description": "When attributing devlog entries, `get_username()` calls `gh api user --jq .login` first, falling back to `git config user.name` only if gh is unavailable or unauthenticated. The GitHub login is a verified identity tied to a real account, unlike git config which can be set to any value. This is the v0.2.x approximation of the full Ed25519 identity stack planned for v0.5.0.",
    "os_layer": "ipc",
    "user_theme": "agent-coordination",
    "introduced": "0.2",
    "usage": [
      {
        "cmd": "synlynk exec claude",
        "note": "Devlog entry attributed to authenticated GitHub user (e.g. nikhilsoman)"
      }
    ],
    "related": ["polyglot-agent-files"],
    "changelog": []
  },
  {
    "slug": "polyglot-agent-files",
    "name": "Polyglot agent files",
    "subtitle": "Generates CLAUDE.md, GEMINI.md, and AGENTS.md from a single parameterised template",
    "description": "`synlynk init` generates three agent instruction files — `CLAUDE.md` (Claude Code), `GEMINI.md` (Gemini CLI), and `AGENTS.md` (Codex/OpenAI CLI) — from `_build_templates(org, repo, project_id)`. All three files contain the same session protocol, live issues SOP, git worktree policy, and GitHub Projects v2 GraphQL block. This ensures every agent in the workgroup receives identical constraints from a single source of truth.",
    "os_layer": "ipc",
    "user_theme": "agent-coordination",
    "introduced": "0.3",
    "usage": [
      {
        "cmd": "synlynk init --agents claude,gemini,codex --project-id PJ_kwDO...",
        "note": "Generates CLAUDE.md, GEMINI.md, AGENTS.md with live GraphQL blocks"
      }
    ],
    "related": ["gh-cli-identity", "parametric-init"],
    "changelog": []
  },
  {
    "slug": "parametric-init",
    "name": "Parametric init",
    "subtitle": "Four --flags fill project-specific values into all generated files at init time",
    "description": "`synlynk init` accepts `--agents`, `--mode`, `--org`, `--repo`, and `--project-id` flags. The `--project-id` flag is the most consequential: it fills the GitHub Projects v2 node ID (`PJ_kwDO…`) into live GraphQL mutation blocks in all agent instruction files, making them immediately executable rather than containing placeholder text.",
    "os_layer": "kernel",
    "user_theme": "context-management",
    "introduced": "0.3",
    "usage": [
      {
        "cmd": "synlynk init --mode team --org acme --repo api --project-id PJ_kwDOA1234",
        "note": "All agent files generated with org, repo, and project ID filled in"
      }
    ],
    "related": ["polyglot-agent-files"],
    "changelog": []
  },
  {
    "slug": "trio-protocol",
    "name": "Trio Protocol",
    "subtitle": "Routes tasks through an Architect → Builder → Verifier pipeline by capability score",
    "description": "The Trio Protocol assigns each task to one of three roles — Architect (design and planning), Builder (implementation), Verifier (testing and review) — based on per-agent capability scores accumulated from past performance. Cold-start uses round-robin assignment to generate initial score data. Scores are recency-weighted: recent performance has more influence than older runs, so improvements surface in routing within 3–4 jobs.",
    "os_layer": "scheduler",
    "user_theme": "autonomy-dispatch",
    "introduced": "0.4",
    "usage": [
      {
        "cmd": "synlynk dispatch --story 42",
        "note": "Routes story 42 to the highest-scoring available agent for its required role"
      }
    ],
    "related": ["board-management"],
    "changelog": []
  },
  {
    "slug": "board-management",
    "name": "Board management",
    "subtitle": "synlynk start moves GitHub Projects v2 board items autonomously via GraphQL",
    "description": "`synlynk start <issue-number>` reads cached field IDs from `.synlynk/config.json`, calls the GitHub Projects v2 GraphQL API to move the item to In Progress, sets the Agent field to the current executor, and begins the Trio Protocol dispatch sequence. This is the first autonomous action the harness takes on behalf of the user — no manual board updates required.",
    "os_layer": "scheduler",
    "user_theme": "autonomy-dispatch",
    "introduced": "0.4",
    "usage": [
      {
        "cmd": "synlynk start 42",
        "note": "Moves issue #42 to In Progress on GitHub Projects v2 board, sets Agent field"
      }
    ],
    "related": ["trio-protocol", "gh-cli-identity"],
    "changelog": []
  }
]
```

- [ ] **Step 2: Create `releases.json`**

```json
[
  {
    "minor": "0.3",
    "label": "v0.3.x",
    "theme": "The Multi-Agent Foundation",
    "date": "2026-06-03",
    "current": true,
    "in_window": true,
    "install_cmd": "curl -sSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | bash",
    "blog_post": "/blog/05-pr26-v0-3-0-multi-agent-foundation/",
    "patches": [
      { "version": "0.3.0", "date": "2026-06-03", "summary": "Polyglot agent files (AGENTS.md), parametric init flags, _build_templates() refactor" }
    ]
  },
  {
    "minor": "0.2",
    "label": "v0.2.x",
    "theme": "The Kernel",
    "date": "2026-05-20",
    "current": false,
    "in_window": true,
    "install_cmd": null,
    "blog_post": "/blog/02-pr1-v0-2-0-the-kernel/",
    "patches": [
      { "version": "0.2.2", "date": "2026-05-20", "summary": "gh CLI identity resolution, upgrade check via gh API" },
      { "version": "0.2.1", "date": "2026-05-17", "summary": "Token extraction correctness, test suite reliability" },
      { "version": "0.2.0", "date": "2026-05-17", "summary": "Initial kernel: context injection, cost tracking, telemetry, flatline detection, budget enforcement" }
    ]
  },
  {
    "minor": "0.1",
    "label": "v0.1.x",
    "theme": "Proof of Concept",
    "date": "2026-05-01",
    "current": false,
    "in_window": false,
    "install_cmd": null,
    "blog_post": null,
    "patches": [
      { "version": "0.1.0", "date": "2026-05-01", "summary": "Single-file CLI skeleton, exec wrapper, basic context injection" }
    ]
  }
]
```

- [ ] **Step 3: Commit**

```bash
git add site/src/_data/features.json site/src/_data/releases.json
git commit -m "feat: add features.json and releases.json data files"
```

---

## Task 2: 11ty filters

**Files:**
- Modify: `site/.eleventy.js`

- [ ] **Step 1: Add `featureAvailable` and `windowReleases` filters**

Open `site/.eleventy.js` and replace the existing content with:

```javascript
module.exports = function(eleventyConfig) {
  // Filters
  eleventyConfig.addFilter("dateFilter", (date) => {
    return new Date(date).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "2-digit"
    });
  });

  // Returns true if a feature (introduced at `introduced` minor) is available in release `minor`
  // Both are strings like "0.3". Compares as floats — works for 0.1–0.9 range.
  eleventyConfig.addFilter("featureAvailable", (introduced, minor) => {
    return parseFloat(introduced) <= parseFloat(minor);
  });

  // Returns only the releases where in_window is true, in array order
  eleventyConfig.addFilter("windowReleases", (releases) => {
    return releases.filter(r => r.in_window);
  });

  // Returns items from arr where item[key] === value
  eleventyConfig.addFilter("filterBy", (arr, key, value) => {
    return arr.filter(item => item[key] === value);
  });

  // Returns first item from arr where item[key] === value, or null
  eleventyConfig.addFilter("findBy", (arr, key, value) => {
    return arr.find(item => item[key] === value) || null;
  });

  // Passthrough copies
  eleventyConfig.addPassthroughCopy("src/assets");
  eleventyConfig.addPassthroughCopy({"../docs/img/logo": "assets/img/logo"});

  return {
    dir: {
      input: "src",
      output: "_site",
      includes: "_includes",
      data: "_data"
    },
    templateFormats: ["njk", "md", "html"],
    htmlTemplateEngine: "njk",
    markdownTemplateEngine: "njk"
  };
};
```

- [ ] **Step 2: Verify filters load**

```bash
cd /Users/nikhilsoman/dev/synlynk/site && npx @11ty/eleventy --dryrun 2>&1 | head -20
```

Expected: no errors, `Wrote 0 files` or similar dry-run output.

- [ ] **Step 3: Commit**

```bash
git add site/.eleventy.js
git commit -m "feat: add featureAvailable, windowReleases, groupBy filters to 11ty"
```

---

## Task 3: Nav and footer

**Files:**
- Modify: `site/src/_includes/base.njk`

- [ ] **Step 1: Add Features to nav and Releases to footer**

Replace `site/src/_includes/base.njk` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} | {{ site.name }}</title>
    <link rel="stylesheet" href="/assets/css/main.css">
</head>
<body class="{{ bodyClass }}">
    <nav class="sticky-nav">
        <div class="container nav-container">
            <a href="/" class="wordmark">
                <img src="/assets/img/logo/icon.svg" alt="Synlynk Icon" class="nav-icon">
                <span class="syn">syn</span><span class="l">l</span><span class="y">y</span><span class="n">n</span><span class="k">k</span>
            </a>
            <div class="nav-links">
                <a href="#how-it-works">How it works</a>
                <a href="/features/">Features</a>
                <a href="#install">Install</a>
                <a href="/blog/" class="teal-link">Blog</a>
                <a href="{{ site.github_url }}" class="github-btn">GitHub ↗</a>
            </div>
        </div>
    </nav>

    <main>
        {{ content | safe }}
    </main>

    <footer class="site-footer">
        <div class="container footer-container">
            <div class="footer-left">
                <div class="wordmark">
                    <span class="syn">syn</span><span class="l">l</span><span class="y">y</span><span class="n">n</span><span class="k">k</span>
                </div>
                <div class="version">v{{ site.version }}</div>
            </div>
            <div class="footer-right">
                <a href="{{ site.github_url }}">GitHub</a>
                <a href="{{ site.github_url }}/discussions">Discussions</a>
                <a href="{{ site.github_url }}/blob/main/CHANGELOG.md">Changelog</a>
                <a href="/releases/">Releases</a>
                <span class="license">MIT</span>
            </div>
        </div>
    </footer>

    <script src="/assets/js/copy.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add site/src/_includes/base.njk
git commit -m "feat: add Features to nav, Releases to footer"
```

---

## Task 4: CSS additions

**Files:**
- Modify: `site/src/assets/css/main.css` (append to end of file)

- [ ] **Step 1: Append features page and release page styles**

Append the following to the end of `site/src/assets/css/main.css`:

```css
/* ============================================================
   Features Page
   ============================================================ */

.features-page {
    padding: 80px 0 120px;
}

.features-header {
    text-align: center;
    margin-bottom: 48px;
}

.features-header h1 {
    font-size: 36px;
    margin-bottom: 12px;
}

.features-header p {
    font-size: 15px;
    color: var(--text-secondary);
    max-width: 480px;
    margin: 0 auto 28px;
}

/* View toggle */
.view-toggle {
    display: flex;
    justify-content: center;
    gap: 8px;
    margin-bottom: 40px;
}

.view-toggle button {
    padding: 7px 20px;
    border-radius: 20px;
    border: 1px solid var(--border-light);
    background: var(--bg-light);
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
}

.view-toggle button.active {
    background: var(--accent-teal);
    border-color: var(--accent-teal);
    color: #fff;
}

/* Matrix table */
.feature-matrix-wrapper {
    overflow-x: auto;
}

.feature-matrix {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    min-width: 560px;
}

.feature-matrix thead tr {
    border-bottom: 2px solid var(--border-light);
}

.feature-matrix th {
    padding: 16px 12px;
    font-weight: 500;
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    vertical-align: bottom;
    min-width: 110px;
}

.feature-matrix th.feature-col {
    text-align: left;
    min-width: 260px;
    padding-left: 0;
}

.feature-matrix th.current-col {
    background: #f9fffe;
    border-left: 2px solid var(--accent-teal);
    border-right: 2px solid var(--accent-teal);
    color: var(--accent-teal);
    font-weight: 700;
    font-size: 13px;
}

.release-label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 8px;
}

.release-label.muted {
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 500;
}

.release-label.archived-label {
    color: #ccc;
    font-size: 11px;
    font-weight: 400;
}

.release-meta {
    font-size: 10px;
    color: var(--text-muted);
    margin-bottom: 8px;
    display: block;
}

.release-actions {
    display: flex;
    gap: 6px;
    justify-content: center;
    flex-wrap: wrap;
}

.install-pill {
    font-size: 10px;
    background: var(--accent-teal);
    color: #fff;
    padding: 3px 10px;
    border-radius: 10px;
    text-decoration: none;
    white-space: nowrap;
}

.changelog-link {
    font-size: 10px;
    color: var(--accent-teal);
    text-decoration: none;
}

.changelog-link:hover {
    text-decoration: underline;
}

/* Section header rows */
.matrix-section-header td {
    padding: 10px 0 6px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    color: var(--text-muted);
    text-transform: uppercase;
    background: var(--bg-light-alt);
    border-top: 1px solid var(--border-light);
}

/* Feature rows */
.feature-matrix tbody tr:not(.matrix-section-header) {
    border-bottom: 1px solid #f5f5f5;
    transition: background 0.1s;
}

.feature-matrix tbody tr:not(.matrix-section-header):hover {
    background: #fafafa;
}

.feature-matrix td {
    padding: 12px;
    vertical-align: middle;
    text-align: center;
}

.feature-matrix td.feature-name-cell {
    text-align: left;
    padding-left: 0;
}

.feature-matrix td.current-col {
    background: #f9fffe;
    border-left: 2px solid var(--accent-teal);
    border-right: 2px solid var(--accent-teal);
}

.feature-name-cell a {
    color: var(--text-primary);
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    display: block;
}

.feature-name-cell a:hover {
    color: var(--accent-teal);
}

.feature-name-cell .feature-subtitle {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
    display: block;
}

.check-yes {
    color: var(--accent-teal);
    font-size: 16px;
    font-weight: 600;
}

.check-no {
    color: #e0e0e0;
    font-size: 16px;
}

.badge-new {
    display: inline-block;
    font-size: 9px;
    background: #fff3cd;
    color: #856404;
    padding: 1px 6px;
    border-radius: 8px;
    margin-left: 6px;
    font-weight: 600;
    vertical-align: middle;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.matrix-footer {
    padding: 14px 0;
    font-size: 12px;
    color: var(--text-muted);
    border-top: 1px solid var(--border-light);
    margin-top: 4px;
}

.matrix-footer a {
    color: var(--text-muted);
    text-decoration: none;
}

.matrix-footer a:hover {
    color: var(--accent-teal);
}

/* ============================================================
   Per-Feature Pages
   ============================================================ */

.feature-detail {
    padding: 80px 0 120px;
    max-width: 680px;
}

.feature-detail-header {
    margin-bottom: 48px;
}

.feature-detail-header .back-link {
    display: inline-block;
    font-size: 13px;
    color: var(--accent-teal);
    text-decoration: none;
    margin-bottom: 20px;
}

.feature-detail-header .back-link:hover {
    text-decoration: underline;
}

.feature-detail-header h1 {
    font-size: 32px;
    margin-bottom: 12px;
}

.feature-detail-header .feature-lead {
    font-size: 17px;
    color: var(--text-secondary);
    line-height: 1.6;
}

.feature-section {
    margin-bottom: 40px;
}

.feature-section h2 {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 16px;
}

.feature-section p {
    font-size: 15px;
    line-height: 1.75;
    color: var(--text-primary);
    margin-bottom: 16px;
}

.os-layer-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border: 1px solid var(--border-light);
    border-radius: 6px;
    font-size: 13px;
    margin-bottom: 12px;
}

.os-layer-badge .layer-label {
    font-weight: 600;
    color: var(--accent-teal);
}

.introduced-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text-secondary);
}

.introduced-badge a {
    color: var(--accent-teal);
    text-decoration: none;
}

.introduced-badge a:hover {
    text-decoration: underline;
}

.usage-block {
    background: #f5f5f5;
    border-radius: 6px;
    padding: 16px 20px;
    margin-bottom: 12px;
}

.usage-block code {
    font-family: 'Courier New', monospace;
    font-size: 13px;
    color: var(--accent-teal);
    display: block;
    margin-bottom: 6px;
}

.usage-block .usage-note {
    font-size: 12px;
    color: var(--text-muted);
}

.related-features {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.related-features a {
    font-size: 13px;
    color: var(--accent-teal);
    text-decoration: none;
    border: 1px solid var(--border-light);
    padding: 4px 12px;
    border-radius: 16px;
    transition: border-color 0.15s;
}

.related-features a:hover {
    border-color: var(--accent-teal);
}

/* ============================================================
   Releases Index Page
   ============================================================ */

.releases-page {
    padding: 80px 0 120px;
    max-width: 720px;
}

.releases-header {
    margin-bottom: 60px;
}

.releases-header h1 {
    font-size: 32px;
    margin-bottom: 12px;
}

.releases-header p {
    font-size: 15px;
    color: var(--text-secondary);
}

.release-row {
    display: flex;
    gap: 32px;
    padding: 32px 0;
    border-bottom: 1px solid var(--border-light);
    align-items: flex-start;
}

.release-row-meta {
    min-width: 100px;
    padding-top: 4px;
}

.release-version-badge {
    font-family: monospace;
    font-size: 13px;
    font-weight: 700;
    color: var(--text-primary);
    display: block;
    margin-bottom: 4px;
}

.release-version-badge.current {
    color: var(--accent-teal);
}

.release-row-date {
    font-size: 11px;
    color: var(--text-muted);
}

.release-row-body h2 {
    font-size: 18px;
    margin-bottom: 8px;
}

.release-row-body h2 a {
    color: var(--text-primary);
    text-decoration: none;
}

.release-row-body h2 a:hover {
    color: var(--accent-teal);
}

.release-row-body p {
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 12px;
}

.release-row-links {
    display: flex;
    gap: 12px;
    align-items: center;
}

.release-row-links .install-pill {
    font-size: 12px;
    padding: 4px 14px;
}

.release-row-links a {
    font-size: 13px;
    color: var(--accent-teal);
    text-decoration: none;
}

.release-row-links a:hover {
    text-decoration: underline;
}

.archived-tag {
    font-size: 10px;
    color: var(--text-muted);
    border: 1px solid var(--border-light);
    padding: 2px 8px;
    border-radius: 8px;
    font-family: monospace;
}

/* ============================================================
   Per-Release Pages
   ============================================================ */

.release-detail {
    padding: 80px 0 120px;
    max-width: 720px;
}

.release-detail-header {
    margin-bottom: 48px;
}

.release-detail-header .back-link {
    display: inline-block;
    font-size: 13px;
    color: var(--accent-teal);
    text-decoration: none;
    margin-bottom: 20px;
}

.release-detail-header .back-link:hover {
    text-decoration: underline;
}

.release-detail-header .release-version {
    font-family: monospace;
    font-size: 13px;
    color: var(--accent-teal);
    font-weight: 700;
    margin-bottom: 8px;
    display: block;
}

.release-detail-header h1 {
    font-size: 32px;
    margin-bottom: 16px;
}

.release-install-block {
    background: var(--bg-dark-elevated);
    border: 1px solid var(--border-dark);
    border-radius: 8px;
    padding: 14px 48px 14px 20px;
    font-family: monospace;
    font-size: 13px;
    color: var(--accent-teal);
    position: relative;
    margin-bottom: 48px;
    max-width: 560px;
}

.release-section {
    margin-bottom: 48px;
}

.release-section h2 {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 20px;
}

.whats-new-list {
    list-style: none;
    padding: 0;
    margin: 0;
}

.whats-new-list li {
    padding: 10px 0;
    border-bottom: 1px solid #f5f5f5;
    font-size: 14px;
}

.whats-new-list li a {
    color: var(--accent-teal);
    text-decoration: none;
    font-weight: 500;
}

.whats-new-list li a:hover {
    text-decoration: underline;
}

.whats-new-list li .feature-note {
    color: var(--text-secondary);
    margin-left: 6px;
}

.patch-list {
    list-style: none;
    padding: 0;
    margin: 0;
}

.patch-item {
    display: flex;
    gap: 20px;
    padding: 12px 0;
    border-bottom: 1px solid #f5f5f5;
    font-size: 13px;
    align-items: baseline;
}

.patch-version {
    font-family: monospace;
    font-weight: 600;
    min-width: 60px;
    color: var(--text-primary);
}

.patch-date {
    color: var(--text-muted);
    min-width: 90px;
    font-size: 12px;
}

.patch-summary {
    color: var(--text-secondary);
    flex: 1;
}

.release-blog-link {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: var(--accent-teal);
    text-decoration: none;
    border: 1px solid var(--border-light);
    padding: 10px 16px;
    border-radius: 6px;
    transition: border-color 0.15s;
}

.release-blog-link:hover {
    border-color: var(--accent-teal);
}
```

- [ ] **Step 2: Commit**

```bash
git add site/src/assets/css/main.css
git commit -m "feat: add CSS for features matrix, per-feature, and release pages"
```

---

## Task 5: Feature matrix page

**Files:**
- Create: `site/src/features/index.njk`

- [ ] **Step 1: Create the matrix page**

```
site/src/features/index.njk
```

```njk
---
layout: base.njk
title: Features
---

{% set windowRels = releases | windowReleases %}

{% set osSections = [
  { key: "kernel",     label: "Kernel — Context Engine" },
  { key: "filesystem", label: "Filesystem — State & Telemetry" },
  { key: "ipc",        label: "IPC — Agent Files & Coordination" },
  { key: "scheduler",  label: "Scheduler — Dispatch" }
] %}

{% set userSections = [
  { key: "context-management",  label: "Context Management" },
  { key: "cost-visibility",     label: "Cost & Visibility" },
  { key: "agent-coordination",  label: "Agent Coordination" },
  { key: "autonomy-dispatch",   label: "Autonomy & Dispatch" }
] %}

<div class="container features-page">

  <header class="features-header">
    <div class="section-label" style="color: var(--accent-teal)">Capabilities</div>
    <h1>Features</h1>
    <p>Everything synlynk provides across releases — from context injection to autonomous dispatch.</p>

    <div class="view-toggle">
      <button id="btn-os" class="active" onclick="setView('os')">OS Layer view</button>
      <button id="btn-user" onclick="setView('user')">User-facing view</button>
    </div>
  </header>

  <div class="feature-matrix-wrapper">

    {# ── OS LAYER VIEW ── #}
    <table class="feature-matrix" id="view-os">
      <thead>
        <tr>
          <th class="feature-col">Feature</th>
          {% for rel in windowRels %}
            <th class="{% if rel.current %}current-col{% endif %}">
              <span class="release-label {% if not rel.current %}muted{% endif %}">{{ rel.label }}</span>
              {% if rel.current %}
                <div class="release-actions">
                  <a href="/releases/v{{ rel.minor }}/" class="install-pill">↓ install</a>
                  <a href="/releases/v{{ rel.minor }}/" class="changelog-link">changelog →</a>
                </div>
              {% else %}
                <a href="/releases/v{{ rel.minor }}/" class="changelog-link" style="font-size:10px">changelog →</a>
              {% endif %}
            </th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for section in osSections %}
          <tr class="matrix-section-header">
            <td colspan="{{ windowRels.length + 1 }}">{{ section.label }}</td>
          </tr>
          {% for feature in features %}
            {% if feature.os_layer == section.key %}
              <tr>
                <td class="feature-name-cell">
                  <a href="/features/{{ feature.slug }}/">
                    {{ feature.name }}
                    {% if feature.introduced == windowRels[0].minor %}<span class="badge-new">new</span>{% endif %}
                  </a>
                  <span class="feature-subtitle">{{ feature.subtitle }}</span>
                </td>
                {% for rel in windowRels %}
                  <td class="{% if rel.current %}current-col{% endif %}">
                    {% if feature.introduced | featureAvailable(rel.minor) %}
                      <span class="check-yes">✓</span>
                    {% else %}
                      <span class="check-no">—</span>
                    {% endif %}
                  </td>
                {% endfor %}
              </tr>
            {% endif %}
          {% endfor %}
        {% endfor %}
      </tbody>
    </table>

    {# ── USER-FACING VIEW ── #}
    <table class="feature-matrix" id="view-user" style="display:none">
      <thead>
        <tr>
          <th class="feature-col">Feature</th>
          {% for rel in windowRels %}
            <th class="{% if rel.current %}current-col{% endif %}">
              <span class="release-label {% if not rel.current %}muted{% endif %}">{{ rel.label }}</span>
              {% if rel.current %}
                <div class="release-actions">
                  <a href="/releases/v{{ rel.minor }}/" class="install-pill">↓ install</a>
                  <a href="/releases/v{{ rel.minor }}/" class="changelog-link">changelog →</a>
                </div>
              {% else %}
                <a href="/releases/v{{ rel.minor }}/" class="changelog-link" style="font-size:10px">changelog →</a>
              {% endif %}
            </th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for section in userSections %}
          <tr class="matrix-section-header">
            <td colspan="{{ windowRels.length + 1 }}">{{ section.label }}</td>
          </tr>
          {% for feature in features %}
            {% if feature.user_theme == section.key %}
              <tr>
                <td class="feature-name-cell">
                  <a href="/features/{{ feature.slug }}/">
                    {{ feature.name }}
                    {% if feature.introduced == windowRels[0].minor %}<span class="badge-new">new</span>{% endif %}
                  </a>
                  <span class="feature-subtitle">{{ feature.subtitle }}</span>
                </td>
                {% for rel in windowRels %}
                  <td class="{% if rel.current %}current-col{% endif %}">
                    {% if feature.introduced | featureAvailable(rel.minor) %}
                      <span class="check-yes">✓</span>
                    {% else %}
                      <span class="check-no">—</span>
                    {% endif %}
                  </td>
                {% endfor %}
              </tr>
            {% endif %}
          {% endfor %}
        {% endfor %}
      </tbody>
    </table>

  </div>

  <div class="matrix-footer">
    Older releases: <a href="/releases/">View full release history →</a>
  </div>

</div>

<script>
function setView(v) {
  document.getElementById('view-os').style.display = v === 'os' ? '' : 'none';
  document.getElementById('view-user').style.display = v === 'user' ? '' : 'none';
  document.getElementById('btn-os').className = v === 'os' ? 'active' : '';
  document.getElementById('btn-user').className = v === 'user' ? 'active' : '';
}
</script>
```

- [ ] **Step 2: Build and check**

```bash
cd /Users/nikhilsoman/dev/synlynk/site && npx @11ty/eleventy --dryrun 2>&1 | grep -E "(features|error|Error)" | head -20
```

Expected: `site/features/index.html` appears in output, no errors.

- [ ] **Step 3: Commit**

```bash
git add site/src/features/index.njk
git commit -m "feat: add feature matrix page /features/ with OS-layer and user-facing toggle"
```

---

## Task 6: Per-feature pages

**Files:**
- Create: `site/src/features/feature.njk`

- [ ] **Step 1: Create the per-feature template**

```
site/src/features/feature.njk
```

```njk
---
layout: base.njk
pagination:
  data: features
  size: 1
  alias: feature
permalink: "/features/{{ feature.slug }}/"
eleventyComputed:
  title: "{{ feature.name }} — Feature"
---

{% set featureRelease = releases | findBy("minor", feature.introduced) %}

{% set osSectionLabels = {
  "kernel": "Kernel — Context Engine",
  "filesystem": "Filesystem — State & Telemetry",
  "ipc": "IPC — Agent Files & Coordination",
  "scheduler": "Scheduler — Dispatch"
} %}

<div class="container feature-detail">

  <header class="feature-detail-header">
    <a href="/features/" class="back-link">← All features</a>
    <h1>{{ feature.name }}</h1>
    <p class="feature-lead">{{ feature.subtitle }}</p>
  </header>

  <div class="feature-section">
    <h2>What it does</h2>
    <p>{{ feature.description }}</p>
  </div>

  <div class="feature-section">
    <h2>OS Layer</h2>
    <div class="os-layer-badge">
      <span class="layer-label">{{ osSectionLabels[feature.os_layer] }}</span>
    </div>
  </div>

  <div class="feature-section">
    <h2>Introduced in</h2>
    <div class="introduced-badge">
      <a href="/releases/v{{ feature.introduced }}/">v{{ feature.introduced }}.x</a>
      {% if featureRelease %}— {{ featureRelease.theme }}{% endif %}
    </div>
  </div>

  {% if feature.usage.length > 0 %}
  <div class="feature-section">
    <h2>Usage</h2>
    {% for item in feature.usage %}
    <div class="usage-block">
      <code>$ {{ item.cmd }}</code>
      <span class="usage-note">{{ item.note }}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if feature.related.length > 0 %}
  <div class="feature-section">
    <h2>Related features</h2>
    <div class="related-features">
      {% for slug in feature.related %}
        {% for f in features %}
          {% if f.slug == slug %}
            <a href="/features/{{ f.slug }}/">{{ f.name }}</a>
          {% endif %}
        {% endfor %}
      {% endfor %}
    </div>
  </div>
  {% endif %}

  {% if feature.changelog.length > 0 %}
  <div class="feature-section">
    <h2>Upgrade notes</h2>
    {% for note in feature.changelog %}
    <p><strong>v{{ note.version }}:</strong> {{ note.note }}</p>
    {% endfor %}
  </div>
  {% endif %}

</div>
```

- [ ] **Step 2: Build and check**

```bash
cd /Users/nikhilsoman/dev/synlynk/site && npx @11ty/eleventy --dryrun 2>&1 | grep "features/" | head -20
```

Expected: 10 lines like `Writing site/features/context-injection/index.html`.

- [ ] **Step 3: Commit**

```bash
git add site/src/features/feature.njk
git commit -m "feat: add per-feature detail pages /features/<slug>/"
```

---

## Task 7: Releases index page

**Files:**
- Create: `site/src/releases/index.njk`

- [ ] **Step 1: Create the releases index**

```
site/src/releases/index.njk
```

```njk
---
layout: base.njk
title: Releases
---

<div class="container releases-page">

  <header class="releases-header">
    <div class="section-label" style="color: var(--accent-purple)">History</div>
    <h1>All releases</h1>
    <p>Every synlynk release — including older versions outside the active download window.</p>
  </header>

  <div class="release-list">
    {% for rel in releases %}
    <article class="release-row">
      <div class="release-row-meta">
        <span class="release-version-badge {% if rel.current %}current{% endif %}">{{ rel.label }}</span>
        <span class="release-row-date">{{ rel.date | dateFilter }}</span>
        {% if not rel.in_window %}
          <span class="archived-tag" style="display:block;margin-top:6px">archived</span>
        {% endif %}
      </div>
      <div class="release-row-body">
        <h2><a href="/releases/v{{ rel.minor }}/">{{ rel.theme }}</a></h2>
        <p>{{ rel.patches[0].summary }}</p>
        <div class="release-row-links">
          {% if rel.current %}
            <a href="/releases/v{{ rel.minor }}/" class="install-pill">↓ install</a>
          {% endif %}
          <a href="/releases/v{{ rel.minor }}/">Release notes →</a>
          {% if rel.blog_post %}
            <a href="{{ rel.blog_post }}">Blog post →</a>
          {% endif %}
        </div>
      </div>
    </article>
    {% endfor %}
  </div>

</div>
```

- [ ] **Step 2: Build and check**

```bash
cd /Users/nikhilsoman/dev/synlynk/site && npx @11ty/eleventy --dryrun 2>&1 | grep "releases" | head -10
```

Expected: `Writing site/releases/index.html`.

- [ ] **Step 3: Commit**

```bash
git add site/src/releases/index.njk
git commit -m "feat: add releases history index /releases/"
```

---

## Task 8: Per-release pages

**Files:**
- Create: `site/src/releases/release.njk`

- [ ] **Step 1: Create the per-release template**

```
site/src/releases/release.njk
```

```njk
---
layout: base.njk
pagination:
  data: releases
  size: 1
  alias: release
permalink: "/releases/v{{ release.minor }}/"
eleventyComputed:
  title: "v{{ release.minor }}.x — {{ release.theme }}"
---

{% set relFeatures = features | filterBy("introduced", release.minor) %}

<div class="container release-detail">

  <header class="release-detail-header">
    <a href="/releases/" class="back-link">← All releases</a>
    <span class="release-version">{{ release.label }}</span>
    <h1>{{ release.theme }}</h1>

    {% if release.current and release.install_cmd %}
    <div class="release-install-block">
      {{ release.install_cmd }}
    </div>
    {% endif %}
  </header>

  {% if relFeatures.length > 0 %}
  <div class="release-section">
    <h2>What's new</h2>
    <ul class="whats-new-list">
      {% for feature in relFeatures %}
      <li>
        <a href="/features/{{ feature.slug }}/">{{ feature.name }}</a>
        <span class="feature-note">— {{ feature.subtitle }}</span>
      </li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}

  <div class="release-section">
    <h2>Changelog</h2>
    <ul class="patch-list">
      {% for patch in release.patches %}
      <li class="patch-item">
        <span class="patch-version">v{{ patch.version }}</span>
        <span class="patch-date">{{ patch.date | dateFilter }}</span>
        <span class="patch-summary">{{ patch.summary }}</span>
      </li>
      {% endfor %}
    </ul>
  </div>

  {% if release.blog_post %}
  <div class="release-section">
    <h2>From the build log</h2>
    <a href="{{ release.blog_post }}" class="release-blog-link">
      Read the blog post →
    </a>
  </div>
  {% endif %}

  <div class="release-section">
    <a href="/features/" style="font-size:14px;color:var(--accent-teal);text-decoration:none">← Back to feature matrix</a>
  </div>

</div>
```

- [ ] **Step 2: Build full site and verify**

```bash
cd /Users/nikhilsoman/dev/synlynk/site && npx @11ty/eleventy 2>&1 | tail -20
```

Expected output includes:
- `Writing site/features/index.html`
- `Writing site/features/context-injection/index.html` (and 9 more feature pages)
- `Writing site/releases/index.html`
- `Writing site/releases/v0.3/index.html` (and 2 more release pages)
- No error lines.

- [ ] **Step 3: Spot check output files exist**

```bash
ls /Users/nikhilsoman/dev/synlynk/site/_site/features/ && echo "---" && ls /Users/nikhilsoman/dev/synlynk/site/_site/releases/
```

Expected: `context-injection/`, `flatline-detection/`, etc. under `features/`; `v0.1/`, `v0.2/`, `v0.3/` under `releases/`.

- [ ] **Step 4: Commit**

```bash
git add site/src/releases/release.njk
git commit -m "feat: add per-release pages /releases/v0.X/"
```

---

## Task 9: Smoke test and push

- [ ] **Step 1: Start dev server**

```bash
cd /Users/nikhilsoman/dev/synlynk/site && npx @11ty/eleventy --serve --port 8080
```

- [ ] **Step 2: Verify these URLs in the browser**

Open each and confirm it renders with nav + footer:

| URL | What to check |
|---|---|
| `http://localhost:8080/features/` | Matrix renders, both view toggle buttons work, ✓ and — appear correctly, latest col is teal-highlighted |
| `http://localhost:8080/features/trio-protocol/` | Feature detail page renders, OS layer badge shows Scheduler, Usage block shows command |
| `http://localhost:8080/features/context-injection/` | No changelog section (empty array) |
| `http://localhost:8080/releases/` | All 3 releases listed, v0.1.x shows "archived" tag, v0.3.x shows install pill |
| `http://localhost:8080/releases/v0.3/` | Install command block visible, What's new shows polyglot-agent-files + parametric-init |
| `http://localhost:8080/releases/v0.1/` | No install block (current: false), What's new shows 5 core features |

- [ ] **Step 3: Check nav link works from homepage**

Load `http://localhost:8080/` — click "Features" in nav, confirm it navigates to `/features/`.

- [ ] **Step 4: Final commit and push**

```bash
git add -A
git status  # confirm only expected files
git push origin main
```

Expected: GitHub Actions triggers on `site/**` changes, deploys to synlynk.com within ~60 seconds.

- [ ] **Step 5: Verify live site**

After deploy, open `https://synlynk.com/features/` — confirm matrix renders and view toggle works.
