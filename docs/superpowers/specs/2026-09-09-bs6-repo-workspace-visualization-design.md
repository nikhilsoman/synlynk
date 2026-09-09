# BS-6: Repo / Workspace Visualization — Product · Logical · Infra
## Design Spec

**Date:** 2026-09-09
**Session:** BS-6 continuation (PM/Architect; Grok away-worker)
**Status:** Drafted for review — design only; not approved for implementation until Home Harness / Nikhil sign-off
**Story:** story-f5513a93 (original) · this dispatch: story-adhoc-1788972982
**Related:**
- Agenda: `docs/superpowers/specs/bs6-project-intelligence-okf-viz-agenda.md`
- Vizor: `docs/superpowers/specs/2026-07-03-bs21-vizor-design.md`
- Architect Map v2: `docs/superpowers/specs/2026-07-11-vizor-architect-map-v2-design.md`
- Deep scan: `docs/superpowers/specs/2026-07-03-bs20-deep-scan-design.md`
- State engine (workspace_edges / symbol tables): `docs/superpowers/specs/2026-07-20-state-engine-tiered-design.md`
- SCIP research (deferred for v1): `docs/superpowers/specs/2026-09-04-scip-code-graph-research.md`
- OKF assessment: `docs/proposals/okf/okf_assessment.md`
- UX 1.0 / uxcore: `docs/superpowers/specs/2026-08-05-synlynk-ux-1.0-design.md`

---

## 1. Problem statement

A new contributor (human or dispatched agent) still meets a synlynk workspace as a file tree, a README, and a git log. Vizor (BS-21) solved *operational* ambient awareness — Gantt, cost, efficiency, live jobs — but not *mental-model* formation.

Three questions remain unanswered in one place:

1. **Product** — what does a user actually walk through (screens, routes, journeys)?
2. **Logical** — how do modules and packages fit together inside a repo?
3. **Infra** — what runs where (containers, queues, CDNs, cloud resources, CI deploy targets)?

Today those questions are split and incomplete:

| Need | What shipped | Gap |
|---|---|---|
| Product | Vizor Journeys tab, hand-authored `docs/journeys/*.md` | Empty unless someone writes markdown; no route/page inference |
| Logical | Architect Map File Tree from `source_symbols` | Directory listing only; Architect Map v2 explicitly deferred intra-repo graphs |
| Workspace topology | Architect Map Graph from `cfg["repos"]` + `.synlynk/vizor-workspace-map.json` | Repo-to-repo edges only; typed edges still discipline-maintained JSON |
| Infra | `synlynk scan` stack fingerprints (`Dockerfile`, `Pulumi.yaml`, compose files) | Presence bits, not a topology |

BS-6 originally bundled OKF conformance with this visualization. This spec **separates** those tracks. OKF remains an ingestion/interop opportunity (`generate_context()` System Reference Catalog). It is not the visualization architecture. Cytoscape.js as a CDN-backed `viz.html` is rejected: Vizor already requires self-contained HTML with no external CDN.

---

## 2. User value

### Primary users

| User | First 30 minutes | What the three views must answer |
|---|---|---|
| New developer (often AI-assisted, product-first) | `synlynk join` → `synlynk doctor` → `synlynk viz` | "What does the product do, which module owns the screen I need, which service deploys it?" |
| PM / designer | Open Vizor without a terminal archaeology session | Screen graph, not import graph |
| Implementing agent (Agy/Grok/Codex) | Task-scoped context plus a clickable map | Jump from a journey step to files, from a module to the deployable |
| TPM / DevOps | Incident or onboarding | Infra graph with provenance, not a guessed architecture slide |

### Value proposition

`synlynk viz` becomes the onboarding and orientation surface, not only the retention dashboard. Gantt/Observatory stay "what is moving." Product/Logical/Infra become "what exists and how it is shaped."

Success is a contributor pointing at one node in each view and following a cross-link to the other two without opening a second tool.

### Non-goals (locked)

- Full OKF export, YAML frontmatter on `project-docs/`, or `synlynk export --okf` (separate track; do not block these views).
- SCIP / tree-sitter / Glean indexers in v1 (research doc #1396 remains the later upgrade path for *agent context*, not for this dashboard).
- Automatic inference of *cross-repo relationship types* (`api-call`, `shared-db`) — still Architect Map v2 out of scope.
- Replacing Gantt, Effort, Efficiency, or Observatory.
- Public hosting, cloud sync, or a second dashboard product.
- Real-time websocket graphs. Refresh stays generate-and-poll.
- Data-catalog features (lineage, profiling, schema validation).
- Hand-drawn tube-map revival.

---

## 3. Approaches considered

### A. Three first-class Vizor views on a shared projection (recommended)

Add Product, Logical, and Infra as Vizor nav entries. One generator pass writes JSON snapshots consumed by self-contained HTML, same as Gantt/Architect Map. Data lives in `state.db` (and write-through JSON only as a cache). Reuses `synlynk viz --serve`, `viz-cache/manifest.json` polling, local token auth, and uxcore as the read chokepoint.

**Trade-offs:** grows Vizor IA; must not collide with Journeys and Architect Map. Generation must stay under the existing ~2s budget for typical workspaces.

### B. Standalone `synlynk viz --view product|logical|infra` emitting committed `docs/viz-*.html`

Closest to the original OKF `viz.html` idea. Shareable as a git artifact, no daemon.

**Trade-offs:** a second command surface next to already-shipped Vizor; committed HTML goes stale the same way `vizor-tube.json` did; agents still need a live local tab.

### C. CDN graph library (Cytoscape / D3) inside a one-off HTML file

Fastest pretty graph.

**Trade-offs:** violates Vizor's no-CDN rule; offline-unready; not stdlib.

**Decision:** Approach A. Architect Map remains the *workspace-repo* graph. Journeys remain the *authored* product overlay and become one input to Product view, not a competing tab forever (see §8 phase 2 for the merge).

---

## 4. Information architecture

### 4.1 How the three views sit next to what shipped

Vizor left nav today (`synlynk/viz.py` `generate_index_html` nav_items):

Gantt · Journeys · Architect Map · Effort & Cost · Observatory · Efficiency

Target nav after this work:

Gantt · **Product** · **Logical** · Architect Map · **Infra** · Effort & Cost · Observatory · Efficiency

Rules:

- **Product** supersedes Journeys as the default product tab. Existing `docs/journeys/*.md` keep working as authored sources. The Journeys nav entry is removed in the same PR that ships Product, with a redirect from `journeys.html` to `product.html` so old bookmarks do not 404.
- **Logical** is intra-repo (modules, packages, entrypoints). It is *not* a third Architect Map sub-view. Architect Map v2 stays workspace-level (repos + typed edges + file tree).
- **Infra** is the reserved "future third Architect Map sub-view" from Architect Map v2 §6, promoted to a top-level tab because it has a different audience and a different data source (IaC, not `cfg["repos"]`).
- Architect Map File Tree remains a debug/browse sub-view, not the logical architecture.

### 4.2 Cross-view linking

Every node has a stable ID. Drawers expose `implements` / `implemented_by` / `deploys_to` / `deployed_as` links that switch the iframe the same way Architect Map already posts `vizor-navigate` to Gantt.

```
product:repo/synlynk-website:route:/pricing
    implements → logical:repo/synlynk-website:module:src/pricing
        deploys_to → infra:repo/synlynk-website:resource:cloudfront:synlynk-site
```

If a link target is missing, the drawer shows an explicit empty state ("no implementing module recorded") rather than hiding the control.

---

## 5. Data sources and model

### 5.1 Provenance

Borrowed from the state-engine spec's Graphify note, applied here as a required field on every node and edge:

| Provenance | Meaning | Example |
|---|---|---|
| `authored` | Human or agent wrote it on purpose | `docs/journeys/*.md` steps; future `synlynk workspace-map add-edge` |
| `extracted` | Deterministic parse of a file that exists | Next.js `app/` route; compose `services:` key; Dockerfile `FROM` |
| `inferred` | Heuristic join between extracted facts | "this Next.js route is served by the `web` compose service because the Dockerfile copies `website/`" |

Render inferred edges dashed; extracted solid; authored bold. Never silently promote inferred → extracted.

### 5.2 Canonical store

`state.db` is the mutation point. Vizor HTML never parses the repo at request time.

New tables (names locked for the implementation plan; SQLite, stdlib only):

```sql
-- One row per viewable node across the three views.
CREATE TABLE workspace_view_nodes (
    id TEXT PRIMARY KEY,            -- "product:<repo>:<kind>:<key>"
    view TEXT NOT NULL,             -- product | logical | infra
    repo TEXT NOT NULL,
    kind TEXT NOT NULL,             -- route, screen, journey, module, entrypoint,
                                    -- service, image, queue, bucket, cdn, workflow, host
    label TEXT NOT NULL,
    attrs_json TEXT NOT NULL DEFAULT '{}',
    provenance TEXT NOT NULL,       -- authored | extracted | inferred
    source_path TEXT,               -- file that justified this node, if any
    scanned_at TEXT NOT NULL,
    head_sha TEXT
);

CREATE TABLE workspace_view_edges (
    id TEXT PRIMARY KEY,
    view TEXT NOT NULL,             -- product | logical | infra | cross
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    kind TEXT NOT NULL,             -- navigates_to, includes, imports,
                                    -- implements, deploys_to, depends_on, publishes
    provenance TEXT NOT NULL,
    attrs_json TEXT NOT NULL DEFAULT '{}',
    scanned_at TEXT NOT NULL,
    FOREIGN KEY (from_id) REFERENCES workspace_view_nodes(id),
    FOREIGN KEY (to_id) REFERENCES workspace_view_nodes(id)
);

CREATE TABLE workspace_view_meta (
    view TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    head_sha TEXT,
    source_counts_json TEXT NOT NULL DEFAULT '{}',
    duration_ms INTEGER NOT NULL DEFAULT 0,
    stale INTEGER NOT NULL DEFAULT 0
);
```

Write-through cache (optional, same shape Architect Map already uses for edges):

- `.synlynk/vizor-workspace-views.json` — snapshot of nodes, edges, meta for the last successful generate. Disposable. Header comment: generated, do not hand-edit.

Do **not** extend `.synlynk/vizor-workspace-map.json` with intra-repo or infra edges. That file stays the workspace-repo relationship document (and should still become a projection of `workspace_edges` when state-engine PR2 lands). Mixing scopes in one JSON is how the tube map went stale.

### 5.3 Product view sources (priority order)

1. **Authored journeys** — existing parser in `generate_viz_data()._load_journeys()` (`docs/journeys/*.md`: H1 name, `## Screen` + `route:` / `desc:` / `agent:` / `stage:`).
2. **Extracted routes / pages**, first language/frameworks that scan already fingerprints:
   - Next.js App Router: `app/**/page.{tsx,jsx,js}` → URL path.
   - Next.js Pages Router: `pages/**/*.{tsx,jsx,js}` minus `_app` / `_document`.
   - 11ty/Nunjucks: `website/src/**/*.njk` (this repo's marketing site).
   - Static HTML entrypoints under `website/` or `docs/` only when a `*.njk`/`page.tsx` scan is empty.
3. **Nav structure** — links between extracted pages from in-file `href` / `Link` targets *within the same repo*, capped (default 200 edges) so marketing sites do not explode.

CLI-only / library repos with no routes show the Product empty state: "No user-facing routes detected. Add `docs/journeys/` or mark `vizor.has_ux: false`." That reuses the existing FTUE `has_ux` / `second_view` signal.

### 5.4 Logical view sources

v1 uses **already-shipped** `synlynk scan --deep` output, not a new parser family:

- `source_symbols` (file + symbol_count) via `_query_repo_file_tree()` / `_scan_full_repo()`.
- Top-level packages and well-known roots: `synlynk/`, `tests/`, `website/src/`, `bin/`, language-idiomatic `src/`, `pkg/`, `internal/`, `app/`, `lib/`.
- Entrypoints: `synlynk/__main__.py`, `bin/synlynk.py`, `package.json` `"bin"` / `"main"`, `cmd/` in Go.
- Edges in v1 are **directory/package containment plus same-package file adjacency**, plus a conservative import edge when both ends are Python and the import is a relative or in-repo absolute module that scan already visited. No cross-language import graph. No SCIP.

If `source_symbols` is empty, Logical shows "run `synlynk scan --deep`" — the same prompt Architect Map File Tree already uses.

### 5.5 Infra view sources

Heuristic, file-presence first (scan already knows these names):

| File | Nodes | Edges |
|---|---|---|
| `Dockerfile` / `Dockerfile.*` | image, base `FROM` | `FROM` → image |
| `docker-compose.yml` / `.yaml` | service, image, volume, network | `depends_on`, `image` |
| `Pulumi.yaml` / `.yml` plus `**/*pulumi*.py` / `*.ts` **names only** | stack label; resource names are inferred only from obvious `aws.s3.Bucket`, `aws.cloudfront`, `aws.ecs` string matches, marked `inferred` | none unless a compose/Dockerfile node shares a name |
| `.github/workflows/*.yml` | workflow | `inferred` `publishes` to image/service when a job name or `deploy` keyword matches a compose service |
| `fly.toml`, `render.yaml`, `vercel.json`, `netlify.toml` | host/platform | `deploys` the current repo |

v1 does **not** execute Pulumi/Terraform, does **not** call cloud APIs, and does **not** require credentials. A workspace with no IaC files gets a truthful empty state, not a fake three-tier diagram.

### 5.6 Read path

`uxcore` grows three read functions so TUI/Vizor/BYOUX do not re-parse:

- `get_product_view(repo=None) -> WorkspaceView`
- `get_logical_view(repo=None) -> WorkspaceView`
- `get_infra_view(repo=None) -> WorkspaceView`

`WorkspaceView` is a typed dataclass: `{view, generated_at, head_sha, stale, nodes, edges, warnings[]}`.

`synlynk/viz.py` `generate_viz_data()` calls these instead of growing more inline loaders. Product view replaces the current `_load_journeys()` list as the journeys payload (journeys become a subset of product nodes with `kind=journey` / `kind=screen`).

### 5.7 Write / rebuild path

A single builder, `synlynk.workspace_views.build_workspace_views(root, repos)`, runs from:

1. `synlynk viz` / `synlynk viz --generate` (always; must tolerate missing scan by emitting empty Logical + warning).
2. `synlynk scan --deep` after `source_symbols` write (Logical becomes fresh in the same command).
3. Future `synlynk workspace-views refresh` as an explicit alias; not required for v1 if (1)+(2) exist.

Rebuild is per-repo then unioned. Failures in one repo (unreadable compose YAML) record a warning on `workspace_view_meta` and skip that source; they do not fail Vizor generation.

---

## 6. View design

Shared chrome: existing Vizor shell, theme tokens, local token, 60s manifest poll, note pencil on nodes (reuse `.synlynk/viz-notes.json` keyed by node id).

Layout for all three: graph canvas + right drawer (Architect Map idiom). No new JS library. Deterministic circle-seeded spring embedder already used for Architect Map, with a 200-node cap: if a view exceeds the cap, cluster by package/service and put overflow behind "expand cluster."

### Product

- Nodes: journeys, screens/routes.
- Authored journey sequence as directed `navigates_to` edges.
- Extracted routes without a journey sit in an "Unmapped routes" cluster.
- Drawer: route, source file, implementing logical module (if linked), stage/agent from journey markdown when present.

### Logical

- Nodes: packages/modules (size by file or symbol count), entrypoints highlighted.
- Containment drawn as parent grouping, not as extra edge clutter.
- Drawer: path, symbol_count, tests path if `tests/test_<module>.py` exists, infra deployable if linked.

### Infra

- Nodes: images, services, queues, buckets, CDNs, workflows, hosts.
- Legend by kind, not by repo (repo is a badge).
- Drawer: source file + line-ish path, provenance, "open file" is out of scope for v1 (show path as copyable text).

Empty, stale, and warning banners are mandatory in all three (see §7).

---

## 7. Refresh and observability

### 7.1 Freshness model

A view is **fresh** when `workspace_view_meta.head_sha` equals the repo HEAD that was scanned *and* `stale=0`.

A view is **stale** when any of:

- HEAD moved since `generated_at`.
- An IaC or journey source file mtime is newer than `generated_at` (infra/product).
- `source_symbols` is empty for Logical while the repo has source files.

Vizor status bar (existing `updated N min ago`) gains a per-view chip: `Product · live` / `Logical · stale (scan --deep)` / `Infra · empty`. Clicking a stale chip runs no command; it tells the operator which command to run. Auto-rebuild inside the HTTP server is out of scope (generation can exceed request time).

`viz-cache/manifest.json` grows:

```json
{
  "updated_at": "2026-09-09T22:00:00Z",
  "version": "0.2",
  "views": {
    "product": {"generated_at": "...", "head_sha": "...", "stale": false, "node_count": 12},
    "logical": {"generated_at": "...", "head_sha": "...", "stale": true, "node_count": 0},
    "infra": {"generated_at": "...", "head_sha": "...", "stale": false, "node_count": 4}
  }
}
```

Existing 60s poll stays; the reload banner already fires when `updated_at` changes. Stale chips update only after regenerate.

### 7.2 Generation budget

Keep Vizor's "under 2 seconds for 10 dreams / 100 tasks" spirit:

- Product+Logical+Infra rebuild target: **≤ 1.5s extra** on the synlynk repo itself after a warm `source_symbols` table.
- If rebuild would exceed 3s, skip inferred import edges and inferred Pulumi name-matching, record `warnings: ["degraded_inference"]`, still show extracted nodes.
- Do not walk `node_modules`, `.venv`, `worktrees/`, or `_SCAN_SKIP_DIRS`.

### 7.3 Sentinel and observatory

New sentinel code **`WORKSPACE_VIEW_STALE`** (severity INFO unless viz `--serve` is up, then WARN):

- Fires when any of the three views is stale for more than `vizor.view_stale_after_minutes` (default 180) *and* a Vizor server is recorded in `.synlynk/viz-meta.json`.
- Does not fire on workspaces that never opened Vizor.
- Clears on the next successful `build_workspace_views`.

Observatory snapshot (`synlynk/observatory.py`) gains a `workspace_views` rollup:

```json
{
  "workspace_views": {
    "product": {"nodes": 12, "edges": 18, "stale": false, "duration_ms": 40},
    "logical": {"nodes": 9, "edges": 11, "stale": false, "duration_ms": 120},
    "infra": {"nodes": 4, "edges": 3, "stale": false, "duration_ms": 15}
  }
}
```

This is read-only telemetry already on disk; no extra network.

### 7.4 Config

Extend the existing `vizor` object in `.synlynk/config.json`:

```json
{
  "vizor": {
    "has_ux": true,
    "default_view": "gantt",
    "product_unmapped_cluster": true,
    "logical_max_nodes": 200,
    "infra_parse_pulumi_names": true,
    "view_stale_after_minutes": 180
  }
}
```

`has_ux` defaults from the existing FTUE path (`second_view` journeys vs tube). No new interactive prompt in v1.

---

## 8. Staged implementation

Each stage is a mergeable PR. Do not start stage N+1 until stage N's acceptance tests are green on main.

### Stage 0 — Projection and rebuild (no new Vizor tabs)

- Schema + migration for the three tables.
- `build_workspace_views()` for authored journeys + compose/Dockerfile extraction + package clustering from `source_symbols`.
- `uxcore.get_*_view()`.
- `synlynk viz --generate` writes `.synlynk/vizor-workspace-views.json` and meta even if HTML is unchanged.
- Tests: fixture repo with one journey, one compose service, one Python package; assert node/edge counts and provenance.

### Stage 1 — Product tab

- `product.html` generator; nav swap Journeys → Product; `journeys.html` redirect.
- Extracted routes for Next.js app/pages + 11ty `*.njk`.
- Unmapped-routes cluster; empty state for CLI-only.
- Tests: render contains authored screen titles; missing journeys dir does not crash generate.

### Stage 2 — Logical tab

- `logical.html`; package nodes; entrypoint highlight; scan-empty prompt.
- Conservative Python import edges only when both files are in `source_symbols`.
- Tests: synlynk-like fixture shows `synlynk` and `tests` as separate modules; skip dirs never appear.

### Stage 3 — Infra tab

- `infra.html`; Dockerfile + compose + workflow nodes; Pulumi name-match behind `infra_parse_pulumi_names`.
- Degraded_inference path if over budget.
- Tests: compose `depends_on` becomes an extracted edge; invalid YAML yields warning, not exception.

### Stage 4 — Cross-links, freshness, sentinel

- `implements` / `deploys_to` joins (inferred, always dashed).
- Manifest `views` block; status-bar chips; `WORKSPACE_VIEW_STALE`; observatory rollup.
- Tests: HEAD change marks stale; rebuild clears sentinel; drawer JSON includes cross IDs.

**Harness split (when implementation is dispatched):** Grok for canvas/HTML views; Codex for schema, uxcore, scan join, sentinel; Agy for empty-state copy and any CSS polish. Claude remains PM/review. No implementation in this PR.

---

## 9. Acceptance criteria

The feature is done when all of the following are true:

1. `synlynk viz --generate` produces `product.html`, `logical.html`, and `infra.html` in `.synlynk/viz-cache/` without network access and without CDN URLs in the HTML.
2. A fixture with `docs/journeys/onboarding.md`, `website/src/index.njk`, `synlynk/cli.py`, and `docker-compose.yml` yields at least one node in each view, with provenance `authored` or `extracted` as specified in §5.
3. CLI-only fixture (no journeys, no `app/`/`pages/`/`website/`, no IaC) generates successfully and each view shows its documented empty state.
4. Architect Map still renders repo nodes from `cfg["repos"]` and still reads `.synlynk/vizor-workspace-map.json` only for *inter-repo* edges.
5. `uxcore.get_product_view()` / `get_logical_view()` / `get_infra_view()` return the same node IDs the HTML embeds (single read path).
6. Stale detection: after generating, rewriting a tracked source file or advancing HEAD, the next generate (or a cheap meta check) sets `stale=true` on the affected view; a full rebuild sets `stale=false`.
7. Sentinel `WORKSPACE_VIEW_STALE` appears only when Vizor has been served and staleness exceeds the configured window; tests cover the negative case (never served → no alert).
8. Generation of the three views on the fixture stays under 3s in CI; degraded inference is recorded rather than timeout.
9. Notes saved on a product/logical/infra node round-trip through `.synlynk/viz-notes.json` using the node id as key.
10. No OKF catalog features, no SCIP dependency, no new PyPI dependency.

---

## 10. Testing strategy

- Unit tests around `build_workspace_views` with tmp fixtures (compose YAML, njk page, fake `source_symbols` rows). Do not require a live browser for graph layout.
- Vizor HTML tests follow `tests/test_viz.py`: generate into tmp `.synlynk/viz-cache/`, assert filenames, nav labels, and JSON blobs (`window.PRODUCT_NODES` etc.) rather than screenshotting canvas.
- Sentinel tests follow `tests/test_sentinel.py` patterns: write meta + viz-meta, assert code present/absent.
- Do not use a pytest `-k` selector derived from the brainstorm title; collect the new test module(s) by path.

This spec change itself is guarded by `tests/test_bs6_workspace_views_spec.py`, which asserts the spec file exists and contains the locked sections so a later edit cannot drop acceptance criteria or staging by accident.

---

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Vizor nav overload (8+ tabs) | High | Operators ignore Product/Logical/Infra | Product replaces Journeys; Infra is not nested under Architect Map; default tab stays Gantt |
| Heuristic infra looks authoritative and is wrong | High | Bad mental model, worse than empty | Provenance badges; inferred dashes; no cloud API; empty state preferred to fiction |
| Logical view becomes an unreadable import hairball | High | Tab is unused | 200-node cap, package clustering, Python-only imports in v1 |
| Rebuild blows the 2s Vizor budget | Medium | `synlynk viz` feels broken | Degraded inference; skip dirs; rebuild Logical from DB not from a fresh walk when symbols exist |
| Collision with Architect Map v2 "file tree" and state-engine PR2 `workspace_edges` | Medium | Two sources of truth | Separate tables; do not stuff intra-repo edges into `vizor-workspace-map.json` |
| SCIP research lands mid-implementation and forks the model | Medium | Rework | v1 schema stores provenance + source_path so a later indexer can *replace extracted logical edges* without a new UI |
| Journeys markdown and extracted routes disagree | Medium | Duplicate screens | Same route key coalesces; authored label wins; extracted-only goes to Unmapped |
| `WORKSPACE_VIEW_STALE` noise | Medium | Sentinel fatigue | Default 180 minutes; only if Vizor was served |
| Scope creep into OKF catalogs | Low | This spec never ships | Non-goal; ingestion is a different spec |

---

## 12. Command surface

No new top-level command required for v1.

```
synlynk viz              # rebuild projections + HTML, open default
synlynk viz --generate   # rebuild, do not open
synlynk viz --serve      # existing local server
synlynk scan --deep      # refreshes Logical sources, then builder
```

Optional later (not v1): `synlynk viz --view product` to open with that iframe selected (query param on `index.html`). Do not add `synlynk viz --out viz.html` committed artifacts.

---

## 13. Relationship to OKF (explicitly not this release)

Agy's 2026-06-26 assessment stands: ingest OKF directories into `generate_context()` as `## System Reference Catalog`; do not turn synlynk into a data catalog. Product/Logical/Infra may later *read* OKF concept files as `authored` nodes if a directory has `index.md` + YAML `type:`. That adapter is a follow-up spec, not a stage of this one.

---

## 14. Open questions closed in this draft

These were the agenda's "key questions." They are resolved so an implementation plan can start after sign-off without a second brainstorm:

| Question | Resolution |
|---|---|
| Static analysis vs agent-produced vs human-authored? | Hybrid: authored journeys + extracted routes/IaC + inferred joins, all provenance-tagged |
| Self-contained HTML vs daemon-served UI? | Existing Vizor generate + local serve; no new daemon |
| How do views link? | Stable IDs + `implements` / `deploys_to` drawer navigation |
| Command surface? | Existing `synlynk viz`; no parallel git-connectome CLI |
| Three templates or one toggle? | Three HTML files + shared shell, matching current Vizor |
| Commit viz.html to `docs/`? | No |
| Ship with OKF frontmatter in init? | No |

Reserved approval gate: Nikhil / Home Harness spec sign-off. This document does not authorize implementation or a writing-plans session until that gate passes.
