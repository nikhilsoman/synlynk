# Specification: Graphify Knowledge Graph Substrate, Multi-Repo Mesh & Reusable Spike Harness

**Status:** Proposed / Brainstormed  
**Date:** 2026-09-15  
**Author:** Agy (Antigravity) & Claude  
**Target Milestone:** `v0.22.0`  
**Decisions Referenced:** `dec-494eb4f5`, `dec-17f044f8`  
**License Compliance:** Apache-2.0 (Graphify) / MIT (Synlynk) — 100% Permissive, Commercially Safe  

---

## 1. Executive Summary & Problem Statement

### 1.1 The Context & Token Waste Problem in Autonomous Fleets
In autonomous multi-agent software engineering, context acquisition accounts for the single largest expenditure of tokens, wall-clock latency, and model errors. When an agent (Claude, Agy, Codex, Grok) is tasked with implementing a feature, fixing a bug, or reviewing a pull request, it typically engages in iterative, blind exploration:
1. Grepping regex patterns across the entire codebase.
2. Reading dozens of source files into the context window to trace callers and callees.
3. Consuming 30,000–50,000 tokens before writing a single line of code.
4. Hallucinating missing call sites due to dynamic imports or aliased functions.

### 1.2 The Empirical Breakthrough (PoC Findings)
In a live proof-of-concept on `synlynk` (~35,000 LOC, 368 Python code files), integrating an Abstract Syntax Tree (AST) Knowledge Graph via **Graphify** (`graphifyy`) produced empirical breakthroughs:
- **Zero-Cost Local Extraction:** Multi-threaded tree-sitter AST extraction completed in **14.2 seconds** with **$0.00 external token cost** and zero network calls.
- **Topological Mapping:** Mapped **6,932 nodes**, **13,637 call edges**, and **428 modular communities** with exact file and line-number citations.
- **13× to 32× Token Reduction:** Targeted call graph queries consumed **~350 to 1,200 tokens** compared to baseline grep-and-read exploration consuming **8,400 to 38,500 tokens** (a **95%+ token savings**).
- **Instant Blast Radius Calculation:** Upstream and downstream dependencies of any symbol or PR diff are resolved in <0.5 seconds.

### 1.3 Core Architectural Mission
This specification formalizes Graphify as a **Tier-1 Recommended Tool** in Synlynk, elevating it from a local discovery plugin into a **central architectural nervous system for the multi-agent fleet**. It delivers:
1. Single-repo and multi-repo onboarding with global fleet knowledge mesh.
2. Documented, role-specific skills injected into living agent charters.
3. Pre-emptive cached graph traversals that synthesize zero-grep, 1,500-token context packs for dispatched jobs.
4. High-leverage CLI commands: `synlynk impact`, `synlynk pack`, `synlynk graph`, and graph-backed PR attestation.
5. The Reusable Spike Evaluation Harness (`synlynk spike`) to standardize future tool, model, and harness evaluations.

---

## 2. Architecture & Ecosystem Positioning

### 2.1 The Recommended Stack Contract
Graphify is adopted into the **Synlynk Recommended Stack** alongside GitHub (`gh`) and Superpowers:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        User Experience Level                           │
│  "RECOMMENDED TOOL" — Promoted prominently in Onboarding, Docs, & CLI  │
│  • synlynk init prompts: [x] Graphify AST (Recommended: ~20x token savings) │
│  • 1-click automatic install via: synlynk tool install graphify        │
│  • Active by default when present                                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Runtime Architecture                            │
│  "GRACEFUL FALLBACK" — The bulletproof reliability contract            │
│  • If a developer is in an air-gapped VM, minimal Alpine container,   │
│    or hasn't installed uv yet: Synlynk STILL runs without crashing.   │
│  • Falls back to native synlynk/discovery.py standard AST scanner.    │
│  • Synlynk NEVER fails with a hard fatal crash due to a missing plugin │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.2 License Compatibility & Separation of Concerns
- **Graphify License:** Apache-2.0 (permissive, commercial-friendly, patent grant).
- **Synlynk License:** MIT (permissive, commercial-friendly).
- **Process Isolation:** Graphify is executed as an external process (`uv tool run graphify` or `graphify-mcp` daemon over stdio/HTTP). Synlynk does not vendor or relicense Graphify code; it interacts purely across clean CLI, JSON-RPC, and file manifest interfaces.

---

## 3. Pillar 1: Single-Repo & Multi-Repo Onboarding

### 3.1 1-Click Provisioning & Preflight
During `synlynk init` (interactive wizard or Vizor `/onboarding`):
1. **Preflight Check:** Probes if `graphify` is installed on `PATH`.
2. **1-Click Auto-Install:** If missing, user can select:
   ```bash
   synlynk tool install graphify
   ```
   Behind the scenes, Synlynk invokes `uv tool install graphifyy` (or `pipx install graphifyy`).
3. **Deterministic AST Extraction:** Runs:
   ```bash
   graphify extract . --code-only --out .synlynk/graphify-out/
   ```
   - Skips non-code files (images/markdown) to avoid unexpected LLM API calls.
   - Extracts all supported languages (Python, TypeScript, Go, Rust, Java, C++, Ruby, etc.).
   - Stores `graph.json`, `graph.html`, and `manifest.json` under `.synlynk/graphify-out/`.

### 3.2 Commit Staleness Invalidation Anchor
`graph.json` contains the exact `built_at_commit` SHA (e.g. `a88f49b3da`).
- On every CLI command or Vizor load, Synlynk compares `built_at_commit` with `git rev-parse HEAD`.
- If commits differ:
  - Vizor displays an amber badge: `⚠ Graph Stale (3 commits behind HEAD) — [Refresh]`.
  - Background daemon schedules an incremental re-index: `graphify update .`.
  - Prevents agents from acting on outdated architectural topologies.

### 3.3 Multi-Repo Fleet Knowledge Mesh
In multi-repo workspaces (e.g. `synlynk`, `rxcc`, `playblazer-ng`, `cc-videoreframing`):
1. When a workspace is initialized with multiple repositories (`synlynk init --multi` or `synlynk join <sibling-path>`):
2. Synlynk iterates through each registered repository:
   ```bash
   graphify extract ../rxcc --code-only --as rxcc --global
   graphify extract ../synlynk --code-only --as synlynk --global
   graphify extract ../playblazer-ng --code-only --as playblazer-ng --global
   ```
3. Graphify merges individual graphs into a federated **Fleet Mesh**: `~/.synlynk/global-graph.json`.
4. **Cross-Repo Edge Inferrer:** Synlynk identifies cross-boundary links:
   - Exported REST / GraphQL route in Repo A $\leftrightarrow$ Fetch / Axios call in Repo B.
   - Database table schema in Repo A $\leftrightarrow$ ORM query in Repo B.
5. **Vizor Fleet Tubemap:** View 2 renders the multi-repo service interaction graph, allowing engineers and agents to visualize distributed boundaries at a glance.

---

## 4. Pillar 2: Role-Specific Skills Injected into Agent Charters

Plugins must not exist in a vacuum; agents must have explicit charter capabilities to use them. Synlynk materializes 4 documented skills into `.synlynk/skills/` and binds them to living agent charters via `synlynk charters adapt`:

### 4.1 `skills/graphify-architecture-audit/` (Role: `architect` — Claude, Agy)
- **Charter Mandate:** Responsible for macro system design, modularity verification, and refactoring plans.
- **Available Tools:** `god_nodes(top_n=10)`, `get_community(id)`, `find_cycles()`.
- **Protocol:**
  - Before approving a spec, the Architect queries the top centrality hubs to ensure new features do not overload god nodes.
  - Checks import cycle graphs to maintain clean package boundaries.

### 4.2 `skills/graphify-pr-impact/` (Role: `verifier` / `qa` — Codex)
- **Charter Mandate:** Responsible for code review, verification gates, and merge authority.
- **Available Tools:** `get_pr_impact(pr_number)`, `shortest_path(source, target)`.
- **Protocol:**
  - During PR review, the Verifier executes `get_pr_impact` to obtain the mathematical list of all modified symbols and their downstream callers.
  - Verifies that every affected caller has an executed test in the verification suite before approving the PR.

### 4.3 `skills/graphify-symbol-navigator/` (Role: `builder` / `dev` — Codex, Agy)
- **Charter Mandate:** Responsible for feature implementation, bug fixes, and surgical edits.
- **Available Tools:** `get_neighbors(symbol)`, `query_graph(query, budget=1000)`.
- **Protocol:**
  - When assigned a task to modify a function, the Builder calls `get_neighbors` to retrieve exact line-number citations of callers instead of issuing multi-turn greps.
  - Never reads entire files when a 300-token subgraph slice provides the interface signatures.

### 4.4 `skills/graphify-domain-sweep/` (Role: `pm` — Claude)
- **Charter Mandate:** Responsible for market research, standards compliance (e.g. LOINC, HL7, OpenAPI, RFCs), and PRD authoring.
- **Available Tools:** `graphify extract <dir> --mode deep`, `query_graph(question)`.
- **Protocol:**
  - Ingests reference whitepapers, medical codes, or API specs into an isolated research worktree.
  - Queries the multi-modal graph to write evidence-cited specifications with exact source chapter/page references.

---

## 5. Pillar 3: Pre-Emptive Cached Graph Traversals & Context Packs

### 5.1 The 4 Canonical Pre-Emptive Traversals
During project initialization and post-commit hooks, Synlynk pre-computes and caches 4 foundational traversals in `.synlynk/cache/traversals/`:
1. **The Ingress $\to$ Ledger Pipeline:** Pre-computed BFS call path from external HTTP/CLI endpoints through business services to persistent state (`state.db`).
2. **The Authentication & Security Perimeter:** Pre-computed traversal of all role tokens, GitHub App authentication shims, and permission checks (`--requires-gh-write`).
3. **The Multi-Harness Dispatch Loop:** Pre-computed flow from task dispatch, capability matching, sandbox creation, process execution, to receipt logging.
4. **The Cross-Service Boundary Map:** Pre-computed contracts representing all inter-repo API calls and shared database dependencies.

### 5.2 Dynamic Task-Specific Context Pack Synthesis (`synlynk pack`)
When a task is dispatched:
```bash
synlynk dispatch codex --story story-1234 --task "Fix SQLite busy timeout during job state transitions"
```
1. **Intent Matching:** Synlynk's dispatcher matches keywords against pre-cached traversals (e.g. `SQLite`, `busy timeout`, `job state` $\to$ **Ingress $\to$ Ledger Pipeline**).
2. **Subgraph Slicing:** Extracts the localized subgraph (target nodes + 1-hop inbound/outbound edges) and caps the text representation at **1,200 tokens**.
3. **Context Injection:** Injects `.synlynk/context_pack.md` into the agent's turn-1 context header:
   ```markdown
   ## Task Context Pack (Generated via Knowledge Graph)
   Target Symbols:
   - record_job_superseded [synlynk/lineage.py:L70]
     - Callers:
       - test_lineage_concurrent_writes [tests/test_sqlite_concurrency.py:L110]
       - test_record_job_superseded_updates_schema_and_status [tests/test_worktree_lineage.py:L58]
   - SynlynkDaemon._run_loop [synlynk/daemon.py:L145]
     - Mutates: daemon_jobs (status, updated_at)
   ```
4. **Outcome:** Dispatched agents begin working with surgical, complete call-site awareness on **Turn 1**, saving an estimated 80%–90% of exploration tokens.

---

## 6. Pillar 4: New Synlynk CLI Commands & Roadmap Features

| Command | Syntax | Output & Purpose |
| :--- | :--- | :--- |
| **`synlynk impact`** | `synlynk impact <symbol\|file>` | Calculates exact blast radius: lists all upstream callers, downstream callees, and associated tests that must be run before editing. |
| **`synlynk pack`** | `synlynk pack <story-id>` | Synthesizes a standalone, portable 1,500-token markdown context pack for any registered story. |
| **`synlynk pr check --impact-attested`** | `synlynk pr check --impact-attested` | Extends PR gate: verifies that 100% of symbols touched in the PR git diff have corresponding test executions recorded in the CI matrix. |
| **`synlynk graph view`** | `synlynk graph view` | Launches Vizor directly at `/graph` displaying the interactive D3/Mermaid topological visualization. |
| **`synlynk graph export`** | `synlynk graph export --out docs/arch.md` | Generates a static Mermaid callflow diagram and exports it to documentation. |
| **`synlynk heal --cycles`** | `synlynk heal --cycles` | Detects circular import dependencies using `nx.simple_cycles` and creates prioritized refactoring stories in `state.db`. |

---

## 7. Pillar 5: The Reusable Spike Evaluation Harness (`synlynk spike`)

To standardize the empirical A/B evaluation methodology proven during the Graphify spike, Synlynk introduces the **Spike Evaluation Harness**.

### 7.1 Command Interface
```bash
synlynk spike eval <candidate-name> --scenario <scenario-name> [--baseline <baseline>]
```
*Examples:*
- `synlynk spike eval graphify --scenario exploration`
- `synlynk spike eval deepseek-harness --scenario plugin-lifecycle`
- `synlynk spike eval claude-3-7-sonnet --scenario complex-refactor`

### 7.2 Execution Pipeline
1. **Isolated Shadow Worktree:** Provisions a temporary worktree in `/tmp/synlynk-spike-<id>`.
2. **Condition A (Baseline Run):** Dispatches a benchmark task using the current control plane tools; captures token usage, round-trip turns, latency, and test exit code.
3. **Condition B (Candidate Run):** Dispatches the identical task with the candidate tool/model enabled; captures the identical telemetry.
4. **Empirical Receipt Generation:** Compiles a standardized evaluation document in `project-docs/spikes/YYYY-MM-DD-<candidate>-<scenario>.md`:
   ```markdown
   # Spike Evaluation Receipt: graphify (exploration)
   Date: 2026-09-15
   Baseline: Grep/Glob Native
   Candidate: Graphify AST Engine
   
   | Metric | Baseline | Candidate | Delta |
   | :--- | :--- | :--- | :--- |
   | Input Tokens | 38,500 | 1,200 | -96.8% (32.0x savings) |
   | Tool Turns | 9 | 1 | -88.9% |
   | Latency | 28.2s | 0.8s | -97.1% |
   | Call-site Recall | 80% | 100% | +20% |
   ```
5. **Panel Ingestion:** The generated receipt is automatically passed to `synlynk decide --panel ...` so architectural decisions are made on verifiable data rather than speculation.

---

## 8. Failure Modes, Security & Governance Guardrails

1. **Context Window Protection (The 2MB Trap):**
   Under no circumstances may an agent or CLI command dump the unindexed `graph.json` (7.3 MB) into prompt context. The MCP query server and context pack generator enforce a strict **2,000-token ceiling** (`_cut_lines_to_budget`) on all traversal payloads.
2. **Offline & Zero-Cost Guardrail:**
   Synlynk's automated onboarding and discovery commands will only invoke `graphify extract` with the `--code-only` flag. Deep multi-modal LLM extraction (`--mode deep`) requires explicit manual invocation by a PM agent and is never triggered in default loops.
3. **Deterministic Fallback Invariant:**
   If `graphify` is uninstalled, corrupted, or fails to parse a malformed repository, Synlynk logs a warning and falls back immediately to `synlynk/discovery.py` native standard library AST discovery. No core Synlynk command (`init`, `scan`, `dispatch`, `pr check`) is ever blocked by a Graphify failure.
4. **Permission & Token Discipline:**
   The `graphify-mcp` daemon is strictly read-only (`read:repo`). It is never granted write permissions or network access, preserving Synlynk's `--requires-gh-write` security fence.

---

## 9. Implementation Phasing

### Phase 1: Core AST Provider & Vizor Embed
- CLI auto-detection and 1-click install (`synlynk tool install graphify`).
- `synlynk/discovery.py` integration with commit-hash staleness check.
- Vizor View 2 (Logical Tubemap) D3 embedding (`graph.html`).
- Native fallback verification suite.

### Phase 2: Role-Specific Charter Skills & Context Packs
- Implement the 4 role skills in `.synlynk/skills/`.
- Wire `graphify-mcp` background daemon.
- Implement `synlynk pack` and dynamic context pack injection during dispatch.

### Phase 3: High-Leverage Commands & PR Attestation
- Implement `synlynk impact` (blast radius calculator).
- Implement `synlynk pr check --impact-attested`.
- Implement `synlynk heal --cycles`.

### Phase 4: Multi-Repo Knowledge Mesh & Spike Evaluation Harness
- Multi-repo onboarding hook (`synlynk init --multi`).
- Cross-repo global mesh aggregation (`~/.synlynk/global-graph.json`).
- Implement the `synlynk spike eval` benchmarking engine and receipt generator.

---

## 10. Verification Gate & Acceptance Criteria

1. **Deterministic Speed & Cost:** `graphify extract --code-only` on a 35K LOC codebase finishes in <20s with 0 tokens billed.
2. **Token Reduction Gate:** Dispatched tasks using `synlynk pack` or `graphify-mcp` demonstrate $\ge 70\%$ token reduction on multi-module navigation tasks compared to regex grep baselines.
3. **Zero-Failure Fallback:** Full repository test suite passes 100% green when `graphify` is completely missing from `PATH`.
4. **Staleness Accuracy:** Advancing `HEAD` by 1 commit triggers the stale badge in Vizor and incremental re-index.
5. **Cross-Repo Connectivity:** Sibling repositories registered in a multi-repo workspace resolve shared API endpoints in the global mesh.
