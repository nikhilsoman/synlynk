# Graphify Knowledge Graph Substrate

Graphify is a deterministic Abstract Syntax Tree (AST) code intelligence substrate integrated into Synlynk. It provides semantic code graphs, call-graph topologies, community clustering, and blast radius analysis across single-repo and multi-repo workspaces.

By extracting structural relationships directly from source code ASTs, Graphify enables an estimated **~20x context token reduction** (replacing 100k+ token brute-force codebase dumps with ~5k tokens of targeted symbol call-chains and community summaries).

---

## 1. Key Capabilities & Architecture

- **Deterministic AST Extraction:** Parses code across multiple languages (Python, TypeScript, JavaScript, Go, Rust, Java, C++, Ruby) using AST parsers without requiring LLM inference for code structure.
- **Topological Community Detection:** Groups tightly coupled functions, classes, and modules into modular community clusters via graph modularity algorithms.
- **Degree Centrality & "God Node" Detection:** Identifies critical hubs and high-in-degree architectural bottlenecks.
- **Commit Staleness Anchor:** Binds extracted graphs to git commit SHAs (`built_at_commit`) to detect and alert on code drift.
- **Vizor View 2 (Logical Tubemap) Embed:** Powers interactive D3 force-directed visual topologies with community cluster coloring in Synlynk Vizor.
- **Multi-Repo Fleet Knowledge Mesh:** Merges distributed microservices into a global federated mesh (`~/.synlynk/global-graph.json`) with cross-repo API link inference.
- **Process Isolation & Permissive Licensing:** Graphify is licensed under Apache-2.0. Synlynk invokes Graphify across external process boundaries (`uv tool run graphify`, CLI subcommands, or JSON-RPC) without vendoring or relicensing.

---

## 2. 1-Click FTUE Onboarding & Installation

Synlynk promotes Graphify as a recommended core tool during First-Time User Experience (FTUE) onboarding.

### Option A: 1-Click Web Onboarding via Vizor
When opening the Synlynk Onboarding Canvas (`synlynk viz` -> `/onboarding`):
1. Synlynk performs preflight detection using `is_tool_available("graphify")`.
2. If uninstalled, a prominent recommended tool card is displayed:
   ```text
   [x] Graphify AST Knowledge Graph (Recommended: ~20x token savings)
   ```
3. Clicking **1-Click Install** issues a POST request to `/tools/install`, executing the automated provisioning pipeline.

### Option B: CLI Installation
Install Graphify at any time using the Synlynk CLI:

```bash
synlynk tool install graphify
```

Under the hood, Synlynk detects your environment's package managers and executes in order of priority:
1. `uv tool install graphifyy` (Recommended: fast, isolated)
2. `pipx install graphifyy`
3. `pip install graphifyy`

> [!NOTE]
> The binary command is `graphify`, while the PyPI distribution package name is `graphifyy`. The Synlynk tool installer handles this mapping automatically.

---

## 3. AST Extraction & Workspace Discovery

### Deterministic Extraction
To index a repository without LLM API costs or token burn, Synlynk runs Graphify in deterministic `--code-only` mode:

```bash
graphify extract . --code-only --out .synlynk/graphify-out/
```

This generates three core artifacts inside `.synlynk/graphify-out/`:
- `graph.json`: Nodes (files, classes, functions), directed edges (calls, imports, inherits), community cluster IDs, and degree centrality scores.
- `manifest.json`: Metadata including `built_at_commit` (git HEAD SHA), extraction timestamp, file count, and language distribution.
- `graph.html`: Standalone interactive visual viewer.

### Workspace Discovery Integration
During `synlynk scan` or `synlynk start`:
- Synlynk inspects `.synlynk/graphify-out/` and enriches the workspace discovery model.
- Static discovery outputs node count, edge count, top central "god nodes", and detected community clusters.
- Agents receive structured architectural context in `.synlynk/context.md`.

---

## 4. Commit Staleness Invalidation Anchor

To ensure AI agents do not act upon outdated code topologies:
1. When `graph.json` is generated, the current git commit SHA is recorded as `built_at_commit`.
2. On every discovery scan or Vizor render, Synlynk executes:
   ```bash
   git rev-parse HEAD
   ```
3. If the current HEAD commit differs from `built_at_commit`:
   - The logical view is flagged as `stale = 1` in `state.db`.
   - Vizor View 2 displays an amber warning banner:
     ```text
     ⚠ Graph Stale (N commits behind HEAD) — [Refresh]
     ```
   - Agents are informed of staleness, prompting an incremental graph refresh (`graphify update .`).

---

## 5. Vizor View 2 (Logical Tubemap) Embed

Synlynk Vizor integrates Graphify output directly into View 2 (Logical View):
- **Graph Ingestion:** Nodes and edges from `.synlynk/graphify-out/graph.json` are projected into `workspace_view_nodes` and `workspace_view_edges` with `view = 'logical'` and `provenance = 'graphify'`.
- **Topological Clustering:** Community cluster IDs are assigned distinct stroke colors using a deterministic hash palette.
- **Centrality Scaling:** Node radii scale proportionally with degree centrality, immediately highlighting architectural hubs.
- **Graceful Fallback:** If `graph.json` is absent or malformed, Vizor falls back to native module directory walking without disruption.

---

## 6. Multi-Repo Fleet Knowledge Mesh

In distributed architectures with multiple repositories:
1. Initialize multi-repo extraction:
   ```bash
   graphify extract ../service-auth --code-only --as auth --global
   graphify extract ../service-billing --code-only --as billing --global
   ```
2. Individual graphs are aggregated into the global fleet mesh at `~/.synlynk/global-graph.json`.
3. Synlynk infers cross-boundary links:
   - REST / GraphQL route definitions in Service A $\leftrightarrow$ HTTP client calls in Service B.
   - Database schema declarations in Service A $\leftrightarrow$ ORM models in Service B.
4. Vizor renders the cross-repo service interaction graph in the multi-repo Tubemap.

---

## 7. Role-Specific Agent Skills

Synlynk equips autonomous harnesses (Claude, Codex, Agy, Grok) with targeted skills that query the Graphify substrate:

| Skill | Target Role | Primary Purpose |
| :--- | :--- | :--- |
| `skills/graphify-architecture-audit/` | `architect` | God node detection, community boundary analysis, and circular dependency checks. |
| `skills/graphify-pr-impact/` | `qa` / `dev` | Blast radius calculation and downstream symbol impact analysis for pull requests. |
| `skills/graphify-symbol-navigator/` | `dev` | Precise jump-to-definition, caller hierarchy, and callee traces. |
| `skills/graphify-domain-sweep/` | `pm` / `architect` | Domain cohesion auditing and modularity drift detection across subsystem boundaries. |

---

## 8. CLI Command Quick Reference

```bash
# Check tool status and install
synlynk tool install graphify

# Run static workspace discovery (includes Graphify overlay if present)
synlynk scan

# Deep discovery scan
synlynk scan --deep

# Launch Vizor with Onboarding & Logical View
synlynk viz
```

---

## 9. Troubleshooting & FAQ

**Q: `graphify: command not found` after running installation.**  
*A:* Ensure your package manager's bin directory is in your `PATH` (e.g. `~/.local/bin` for `uv` and `pipx`). Run `which graphify` to verify.

**Q: Why does the installer reference `graphifyy` with two y's?**  
*A:* On PyPI, the registered package name is `graphifyy`, which installs the executable CLI binary `graphify`. Synlynk handles this translation automatically.

**Q: Does Graphify send code or tokens to external LLM APIs?**  
*A:* No. Synlynk strictly runs Graphify with `--code-only`. Extraction is 100% local, offline, and deterministic using language ASTs.
