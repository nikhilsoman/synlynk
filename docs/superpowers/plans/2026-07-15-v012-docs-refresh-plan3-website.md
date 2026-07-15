# v0.12.0 Docs Refresh — Plan 3: Website (synlynk.com) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the synlynk.com docs page (`website/src/docs.njk`) so its command coverage matches the v0.12.0 CLI surface, organized by journey stage, and confirm the 11ty build still succeeds.

**Architecture:** Pure content edit to one Nunjucks template. `website/src/changelog.md` is a build artifact auto-generated from root `CHANGELOG.md` at build time (via `website/.eleventy.js` lines 55-94) — it needs **no manual edit**, only a build-time regeneration check.

**Tech Stack:** Nunjucks (`.njk`), 11ty (Eleventy) static site generator, Node.js.

---

This plan is one of 4 independent, parallel-dispatchable plans derived from `docs/superpowers/specs/2026-07-15-v0.12.0-docs-onboarding-refresh-design.md`. It touches only `website/src/docs.njk` — disjoint from the other 3 plans' files (README.md / docs/*.html+pdf / docs/blog/*.md).

### Task 1: Rewrite the command reference block in `website/src/docs.njk`

**Files:**
- Modify: `website/src/docs.njk:46-49` (the `docs-quick-ref` block at the bottom of the file)

- [ ] **Step 1: Read current state**

Run: `cat website/src/docs.njk`

Confirm the file still matches this 49-line structure: a `base.njk` layout front-matter, a hero header, a `docs-pdf-grid` with 3 `doc-card` divs (Quick Start, Command Reference, The Manual — each linking to `/assets/docs/*.pdf`), and a `docs-quick-ref` block at the bottom containing only an "Install" heading with a `curl` one-liner. There is currently no command-list content on this page at all — only the PDF cards and the install line.

- [ ] **Step 2: Cross-check the command surface against `synlynk/cli.py`**

Run: `grep -n 'add_parser(' synlynk/cli.py` and read each `help="..."` string (multi-line ones need `sed -n 'N,N+5p' synlynk/cli.py` to see the full text). This is the source of truth — do not invent command descriptions.

- [ ] **Step 3: Replace the `docs-quick-ref` block** (lines 46-49) with an expanded block that keeps the existing Install section and adds a journey-staged command quick-reference plus the Upgrading callout. Preserve the existing `docs-quick-ref` class wrapper and `<pre><code>` install snippet exactly as-is; append new content after it:

```html
<div class="docs-quick-ref">
  <h3>Install</h3>
  <pre><code>curl -fsSL install.synlynk.com | bash</code></pre>
</div>

<div class="docs-quick-ref">
  <h3>Getting Started</h3>
  <pre><code>synlynk init --wizard
synlynk doctor
synlynk exec claude
synlynk status</code></pre>
</div>

<div class="docs-quick-ref">
  <h3>Daily Use</h3>
  <pre><code>synlynk dispatch codex --task "..." --force-agent
synlynk jobs --watch
synlynk logs --job &lt;id&gt;
synlynk checkpoint</code></pre>
</div>

<div class="docs-quick-ref">
  <h3>Team / PM</h3>
  <pre><code>synlynk join
synlynk team status
synlynk story create ...
synlynk schedule --execute</code></pre>
</div>

<div class="docs-quick-ref">
  <h3>Advanced / Operate</h3>
  <pre><code>synlynk agent run &lt;name&gt;
synlynk local doctor
synlynk scan --deep
synlynk viz --serve</code></pre>
</div>

<div class="docs-quick-ref">
  <h3>Upgrading?</h3>
  <p>If you installed synlynk before 2026-07, here's what's new: <code>synlynk schedule</code> (fleet batch dispatch), <code>synlynk cost log</code> (manual cost entries), the <code>local</code> agent (5th dispatch target, zero-cost on-device inference), a <code>RATES</code> line in <code>synlynk status</code>, and <code>synlynk viz</code> (local web HUD).</p>
  <pre><code>synlynk upgrade
synlynk doctor</code></pre>
</div>
```

Use the class name `docs-quick-ref` for each new block since that's the existing convention in this file — do not invent a new class unless a check of `website/src/` CSS shows `docs-quick-ref` styling won't reasonably extend to multiple stacked blocks (check with `grep -rn "docs-quick-ref" website/src/ website/*.css website/src/**/*.css 2>/dev/null`). If the CSS only expects one instance of this block and stacking looks visually broken in a local build preview, keep the class name but confirm via Step 5's build check rather than guessing.

- [ ] **Step 4: Verify the 11ty build succeeds**

Run:
```bash
cd website && npm run build
```
Expected: build completes with no errors, and `website/src/changelog.md` is regenerated (confirm via `head -5 website/src/changelog.md` showing the current root `CHANGELOG.md`'s top version — should show `v0.12.0` since that's already the top entry in `CHANGELOG.md`). Do not hand-edit `website/src/changelog.md` — it is fully derived from root `CHANGELOG.md` via `website/.eleventy.js`.

- [ ] **Step 5: Self-verify — grep every command name mentioned in the rewritten block against `cli.py`**

Run:
```bash
grep -oE 'synlynk [a-z][a-z-]*' website/src/docs.njk | sed 's/synlynk //' | sort -u
```
For each name, confirm a matching `add_parser("<name>"` in `synlynk/cli.py`. Fix any orphan before committing.

- [ ] **Step 6: Commit**

```bash
cd website && git add src/docs.njk
git commit -m "docs(website): journey-staged command reference on docs page for v0.12.0"
```

Note: do not `git add` `website/src/changelog.md` even though the build regenerates it locally — it should already be untracked or gitignored as a build artifact; verify with `git status website/src/changelog.md` before committing and do not stage it if it shows as a tracked-and-modified file unexpectedly (that would indicate it's meant to be committed, which contradicts the design spec's finding — flag this to the reviewer rather than silently committing it).
