# BS-6 Brainstorm Agenda — Project Intelligence: OKF + Visualization

**Story:** story-f5513a93  
**Scheduled:** 2026-06-28 (tomorrow)  
**Pre-session action:** Dispatch Agy to produce `docs/okf_assessment.md` before the session starts

---

## Pre-Session: Dispatch Agy

Before opening the brainstorm, run:

```bash
synlynk dispatch agy --force-agent --context-mode none --task "Read the OKF spec at https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf (SPEC.md and README.md). Produce docs/okf_assessment.md — your assessment of: (1) what OKF is, (2) where synlynk's project-docs/ already aligns with OKF, (3) gaps, (4) what synlynk should adopt, (5) what synlynk surpasses. Be specific about frontmatter fields, bundle structure, index.md, log.md, and the viz.html approach. Compare against synlynk's generate_context(), context.md, project-docs/ schema, and relay layer. Max 600 words."
```

Consolidate `docs/okf_assessment.md` (Agy) with this agenda (Claude) before opening the session.

---

## Agy's Assessment (2026-06-26) — `docs/proposals/okf/okf_assessment.md`

**Key findings from Agy:**

- OKF is static data/systems cataloging; synlynk is dynamic agent coordination — **complementary, not competing**
- Google beat us only on the cataloging/metadata front; synlynk's runtime layer (daemon, relay, WAL, decide) is entirely out of OKF's scope
- Most actionable Agy recommendation: **OKF as ingestion format** — scan OKF-style directories into `generate_context()` under a `## System Reference Catalog` section. Coding agents can ingest OKF files (BigQuery schemas, API endpoints) without hallucinating.
- Agy warns against scope creep into data catalog features (validation, lineage, profiling) — stay focused on repo workflow orchestration
- Attribution layer: preserve OKF author metadata matching synlynk's `[@username]` convention when reading OKF context

**Agy's concrete action items:**
1. `generate_context()` / `scan.py` — identify OKF-style directories (has `index.md` + YAML frontmatter), append to context as `## System Reference Catalog`
2. Attribution preservation when reading OKF files
3. No `state.db` alteration — keep synlynk's execution engine authoritative

---

## Claude's Prior Assessment (2026-06-26) — Summary

### OKF in one sentence
A formal spec for markdown + YAML frontmatter knowledge bundles, git-native, vendor-neutral, with a built-in Cytoscape.js graph visualizer. Primary use case: data catalogs (BigQuery, APIs, playbooks).

### Where synlynk already converged on OKF independently
- `project-docs/` = OKF bundle (roadmap.md, todo.md, memory.md = OKF concepts)
- `devlogs/<user>.md` = OKF `log.md` pattern  
- Cross-doc references = OKF graph links
- `generate_context()` compaction = OKF `index.md` progressive disclosure
- Git-native, human + agent readable ✓

Nikhil's instinct is right: synlynk independently arrived at the same format intuitions. Google formalized what was already emerging practice.

### What OKF adds that synlynk lacks
- Formal YAML frontmatter: `type`, `title`, `description`, `resource`, `tags`, `timestamp` — semantic routing and tool interoperability
- `index.md` for progressive disclosure (explicit, not just dynamic)
- `log.md` change history convention
- `citations` body section
- **The viz.html**: self-contained Cytoscape.js HTML — force-directed graph, detail panel, backlinks, search, type filter, zero backend

### What synlynk surpasses OKF (its real moat)
- Dynamic context injection and scoping (task vs. full)
- Multi-agent dispatch, telemetry, sentinel, capability routing
- Shared context across agents (context.md, relay, HTTP API)
- Team coordination (join, decide, write-arbitration, token budgets)
- Identity + Ed25519 signing
- Real-time relay broadcast

### OKF's gap Nikhil correctly identified
OKF has **no concept** of shared context between agents or teams. It is a static format. Everything synlynk does at the coordination layer is intentionally out of scope for OKF by design.

### SWOT summary
- **Strength:** synlynk validated OKF's format intuitions independently; coordination layer is entirely beyond OKF's scope
- **Weakness:** `project-docs/` is not OKF-conformant today (no YAML frontmatter)
- **Opportunity:** OKF conformance costs one PR; Cytoscape.js viz is free inspiration for BS-6; "synlynk = OKF + coordination OS" is a clean positioning narrative
- **Threat:** Google could extend OKF with coordination primitives in v0.2+; if OKF wins as a standard and synlynk diverges, synlynk becomes a silo

---

## The Bigger Idea — Why This Matters for Adoption

Project visibility has always been stuck in engineering/code trees. A new developer joins a project and faces: a file tree, a README, and a git log. None of these answer the real questions:

- What does this product *do* for users?
- How do the pieces fit together conceptually?
- What does the infrastructure actually look like?

The answer isn't more documentation — it's **a different point of view**. Anybody can be a developer now (AI-assisted coding has lowered the floor enormously), but the cognitive barrier isn't syntax — it's *mental model formation*. A new dev with no prior context can be productive on day one if they can see the product as a user, then zoom into the component they need to touch.

That's the thesis for BS-6: `synlynk viz` as a first-class onboarding tool and project intelligence surface.

---

## Brainstorm Agenda

### 1. OKF Alignment (30 min)
- Review consolidated assessments (Agy + Claude) — full notes above
- **Ingestion story (Agy's rec):** `generate_context()` gains OKF scanner — detects `index.md` + YAML frontmatter directories, appends as `## System Reference Catalog`. Lets agents read enterprise data catalogs without hallucinating endpoints.
- **Output story (Claude's rec):** Add OKF YAML frontmatter to `project-docs/` init templates — one PR, near-zero cost, conformant from day 1
- Decide: `synlynk export --okf` for portability? (future, v1.x)
- Positioning: "synlynk project-docs is an OKF-conformant knowledge bundle; synlynk is the coordination OS that runs on top"
- Anti-scope-creep gate: no data catalog features (validation, lineage, profiling) — stay focused on repo workflow orchestration

### 2. Visualization Architecture (45 min)
Three views for `synlynk viz`:

**Product view**
- Consumer-centric UX screen graph
- Static map of screens/features linking to each other
- Source: inferred from routes, page components, navigation structure
- Audience: new devs, PMs, designers, anyone onboarding

**Logical view**
- High-level component breakdown
- Service boundaries, module dependencies, data flow
- Source: file tree + source scan (`synlynk scan` already produces this)
- Audience: engineers understanding the architecture

**Infra view**
- Network and cloud stack
- Services, queues, databases, CDN, external APIs
- Source: infra-as-code (Pulumi/Terraform), Dockerfile, docker-compose
- Audience: DevOps, new engineers, technical leadership

**Key questions:**
- How is each view generated? Static analysis vs. agent-produced vs. human-authored OKF concepts?
- Self-contained HTML (viz.html approach) vs. daemon-served UI?
- How do the three views link to each other? (a screen in product view links to the component in logical view, which links to the service in infra view)
- Where does this live in the synlynk command surface? `synlynk viz [--view product|logical|infra]`?

### 3. New Developer Onboarding POV (20 min)
- Who is the "new developer" in 2026? (AI-assisted, no traditional CS background, product-first thinking)
- What is the first 30 minutes of joining a synlynk-instrumented project?
- How does `synlynk viz` + `synlynk doctor` + `synlynk join` form a complete onboarding flow?
- "Anybody can be a dev now" — what does that actually mean for the UI/UX of the viz?

### 4. Technical Approach (20 min)
- Adopt OKF's Cytoscape.js viz.html pattern: self-contained HTML, no backend, shareable as artifact
- `synlynk viz --view product --out viz.html` — generate and open in browser
- Data source: `state.db` stories + source scan + agent-authored OKF concepts
- Three separate HTML templates or one with view toggle?
- Commit viz.html to `docs/` in the repo? (OKF does this for bundles)

### 5. Release Scope Decision (10 min)
- Does `synlynk viz` ship with OKF frontmatter in init? Or separately?
- Which version: v0.9.8 standalone, or bundle into a larger v0.10.0 "Project Intelligence" release?

---

## Related
- Claude OKF assessment: this file (above)
- Agy OKF assessment: `docs/okf_assessment.md` (to be created pre-session)
- OKF spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf
- BS-5: website redesign (story-048f5fe5)
- synlynk source scan: `synlynk/__init__.py` `_check_scan_cache()`, `_format_source_architecture()`
- Cytoscape.js: https://js.cytoscape.org/
