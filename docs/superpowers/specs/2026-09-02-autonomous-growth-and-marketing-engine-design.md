# Design Spec: Autonomous Growth & Marketing Engine

**Date:** 2026-09-02  
**Status:** In Review  
**Role Owner:** `marketing` (Marketing Intern / Growth Agent)  
**Authors:** [@nikhilsoman], [@agy], [@claude]  
**Relates to:** `goal-0c4e96ff`, `goal-9ef9a965`, #859  

---

## 1. Objective & Scope

Establish an autonomous, continuous **Growth and Promotion Engine** operated by the `marketing` workspace agent (`f2039c38-37ef-4380-ae97-9954f0f7ed36`) across 5 external public surfaces:
1. Product Website & Interactive Canvas (`synlynk.dev`)
2. Per-PR Blog Posts & Public Blog Series (`docs/blog/`)
3. Living Documentation & Command Reference Sync (`docs/reference/commands.md`, `README.md`)
4. Generated Media & Architecture Visuals (SVG diagrams, social cards, book illustrations)
5. Telemetry Analytics & Growth Signal Feedback (`goal-0c4e96ff`)

---

## 2. Architectural Design

```
                               ┌──────────────────────────────────────────────┐
                               │           MARKETING AGENT ENGINE             │
                               └──────────────────────┬───────────────────────┘
                                                      │
         ┌──────────────────────────────┬─────────────┴────────────────┬──────────────────────────────┐
         ▼                              ▼                              ▼                              ▼
 ┌───────────────┐              ┌───────────────┐              ┌───────────────┐              ┌───────────────┐
 │ Website &     │              │ Blog Engine   │              │ Living Docs   │              │ Media & Visual│
 │ Canvas Sync   │              │ (Per-PR Post) │              │ Auto-Gen      │              │ Generator     │
 ├───────────────┤              ├───────────────┤              ├───────────────┤              ├───────────────┤
 │ Updates hero, │              │ Drafts, checks│              │ Regenerates   │              │ Builds SVG    │
 │ install bar & │              │ frontmatter & │              │ reference docs│              │ diagrams &    │
 │ canvas demo   │              │ indexes posts │              │ on CLI change │              │ social cards  │
 └───────────────┘              └───────────────┘              └───────────────┘              └───────────────┘
```

### A. Per-PR Blog Post Automation & Quality Gate
- **Trigger:** On PR creation or update by any implementer agent.
- **Action:**
  - Validates `docs/blog/NN-prN-<slug>.md` exists and conforms to YAML frontmatter schema (`title`, `author`, `date`, `pr`, `version`, `tags`).
  - Automatically updates `docs/blog/README.md` index table.
  - Extracts tweet/changelog summary snippet into `.synlynk/social_drafts.json`.

### B. Living Documentation Synchronization
- **Trigger:** On modification to `synlynk/taxonomy.py` (`COMMAND_TAXONOMY`) or `synlynk/cli.py`.
- **Action:**
  - Executes `scripts/generate_command_docs.py` automatically.
  - Keeps `docs/reference/commands.md` and `README.md` command tables byte-for-byte in sync with real CLI parsers.

### C. Website & Interactive OS Canvas Maintenance
- **Surface:** `docs/brainstorm/bs5-website-redesign/` and production static distribution.
- **Action:**
  - Syncs version numbers and install instructions (`pipx install synlynk`).
  - Updates feature spotlight cards when new core capabilities ship.
  - Refreshes the SVG/HTML5 coordination OS vision canvas.

### D. Media & Visual Asset Generator (`synlynk media generate`)
- **Action:**
  - Automated generation of high-resolution architectural SVG flowcharts and sequence diagrams from Mermaid definitions.
  - Generates OpenGraph (OG) image cards for blog posts and release announcements.

### E. Telemetry & Readership Analytics Loop
- **Action:**
  - Tracks anonymous CLI installation ping counts, documentation page views, and blog readership.
  - Feeds readership conversion metrics back into `goal-0c4e96ff` (*Grow readership of book & blog series*).

---

## 3. Test Strategy
- Unit tests in `tests/test_marketing.py` asserting blog post frontmatter validation, command docs generator consistency, and social draft exports.
