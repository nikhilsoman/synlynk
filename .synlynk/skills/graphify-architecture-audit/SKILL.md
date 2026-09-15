---
name: graphify-architecture-audit
description: Audit macro system architecture, query god nodes and high-centrality hubs, inspect modular community boundaries, and detect cyclic dependencies using the Graphify knowledge graph substrate.
---

# Graphify Architecture Audit

## Charter Mandate & Overview
- **Primary Role:** `architect`
- **Supported Harnesses:** Claude, Agy
- **Mission:** Maintain system-wide architectural integrity, prevent architectural erosion (god nodes, community entanglement, circular imports), and verify macro modularity before approving feature specifications.

Architectural reviews must be grounded in mathematical AST topology rather than subjective inspection. By querying Graphify's directed graph substrate, the Architect evaluates centrality, community clustering, and dependency cycles with zero external token cost.

---

## Available Tools & CLI Commands

### MCP Tools (`graphify-mcp`)
- `god_nodes(top_n: int = 10)`: Identifies top in-degree and PageRank centrality nodes in the AST graph. Highlights functions, classes, and modules bearing disproportionate blast radius.
- `get_community(id: str | int)`: Returns the modular Louvain/Leiden community partition for a given identifier, listing closely coupled symbol clusters and their external boundary edges.
- `find_cycles()`: Executes Johnson's or Tarjan's elementary cycle detection algorithm (`nx.simple_cycles`) over the directed dependency graph to surface import cycles.

### Companion CLI Commands
- `synlynk heal --cycles`: Scans the workspace graph for circular dependencies and automatically creates prioritized refactoring stories in `state.db`.
- `synlynk graph export --out docs/arch.md`: Exports static Mermaid topological diagrams documenting macro component interactions.
- `synlynk graph view`: Launches the Vizor interactive D3/Mermaid topological visualization at `/graph`.

---

## Execution Protocol

### Step 1: Centrality & God Nodes Inspection
Before approving a new feature design or structural refactoring:
1. Run `god_nodes(top_n=10)` via MCP or CLI query.
2. Examine the returned hub symbols (classes, shared utilities, dispatchers).
3. **Guardrail Check:** Ensure the proposed changes do NOT add new inbound or outbound responsibilities to top-tier god nodes (nodes with degree centrality $> 3\sigma$ above repository mean). If a proposed feature touches a god node, mandate extraction of an adapter, façade, or sub-module.

### Step 2: Community Boundary Verification
1. Identify the target domain or package for the feature.
2. Query `get_community(id)` for the relevant module.
3. Review external boundary cross-edges:
   - Confirm that cross-community calls flow strictly through public contracts or service interfaces.
   - Flag any tight coupling or accidental leaky abstractions between decoupled domains (e.g. direct storage engine access from presentation layers).

### Step 3: Cyclic Dependency Detection
1. Execute `find_cycles()` to detect any directed import or call cycles:
   ```bash
   synlynk heal --cycles
   ```
2. If cycles are detected:
   - Block architectural approval until circular dependencies are eliminated.
   - Propose dependency inversion (interfaces/protocols) or extract shared leaf types into a dedicated common leaf module.

### Step 4: Architectural Attestation & Spec Sign-off
1. Document the topology audit in the design specification under `docs/superpowers/specs/`:
   - List top affected hubs and their baseline vs. projected centrality.
   - Confirm 0 cycles introduced.
   - Confirm community boundary compliance.
2. Commit spec with architectural attestation.

---

## Safety & Governance Guardrails
1. **Context Window Protection (2,000-token ceiling):** Never ingest the entire raw `graph.json`. Always filter queries using `top_n`, specific `community_id`, or localized subgraphs.
2. **Deterministic Fallback:** If `graphify-mcp` is unavailable, fall back to `synlynk/discovery.py` native static AST discovery. Do not block emergency architectural fixes on tool unavailability.
3. **Read-Only Scope:** The architecture audit skill is strictly diagnostic and analytical. Refactoring implementations must be executed by `builder` (`Codex` / `Agy`) in isolated worktrees.
