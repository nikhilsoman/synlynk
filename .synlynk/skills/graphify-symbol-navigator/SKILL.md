---
name: graphify-symbol-navigator
description: Perform zero-grep surgical code navigation, query 1-hop neighbor subgraphs, inspect interface signatures, and synthesize token-efficient context packs.
---

# Graphify Symbol Navigator

## Charter Mandate & Overview
- **Primary Role:** `builder` / `dev`
- **Supported Harnesses:** Codex, Agy
- **Mission:** Execute surgical code implementations, bug fixes, and refactorings with minimal token consumption, zero hallucinated call sites, and instant AST symbol navigation.

Blind grepping across dozens of files wastes tens of thousands of tokens and clutters model context. The Builder leverages Graphify's AST neighbor queries to inspect symbol definitions, interface signatures, and inbound callers in precise 300-to-1,000-token slices.

---

## Available Tools & CLI Commands

### MCP Tools (`graphify-mcp`)
- `get_neighbors(symbol: str)`: Returns the localized 1-hop subgraph around a specific symbol (function, method, class, or constant). Delivers incoming callers, outgoing calls, defined-in file/line numbers, and interface parameters.
- `query_graph(query: str, budget: int = 1000)`: Executes semantic and topological sub-queries against the AST graph, returning an optimized token-capped markdown summary within the specified token budget.

### Companion CLI Commands
- `synlynk pack <story-id>`: Synthesizes a standalone, portable 1,500-token markdown context pack for an assigned story, pre-assembling target symbols and their direct dependencies.
- `synlynk impact <symbol>`: Quickly prints the immediate callers and callees of a target symbol before making changes.

---

## Execution Protocol

### Step 1: Pre-Implementation Context Acquisition
When assigned a development task or bug fix:
1. Identify the primary function, class, or symbol referenced in the story.
2. Check for an injected `.synlynk/context_pack.md` or invoke:
   ```bash
   synlynk pack <story-id>
   ```
3. If investigating an individual function, query `get_neighbors(symbol)`:
   - Identify exact file path and line number (e.g. `synlynk/lineage.py:L70`).
   - Identify all active callers across the codebase.
   - Review interface arguments, return types, and default values.
4. **Discipline Rule:** Never issue whole-directory grep commands or read 500+ lines of untouched code when a targeted neighbor query yields the required interface boundaries.

### Step 2: Interface Signature Inspection
1. Call `query_graph(query, budget=800)` for specific architectural questions:
   - Example: `"Where is JobReceipt constructed and what fields does it require?"`
2. Extract the minimal type contract required to implement the fix.

### Step 3: Test-Driven Surgical Edit (TDD)
1. Locate connected unit and integration tests from the neighbor query:
   - Identify which test files directly exercise the target symbol.
2. Write a failing reproduction or unit test targeting the expected behavior.
3. Apply surgical edits to the implementation file:
   - Preserve existing function signatures whenever possible to avoid breaking upstream callers.
   - If a signature must change, use `get_neighbors` to update every identified caller in the same changeset.

### Step 4: Verification & Hand-off
1. Run local verification commands:
   ```bash
   python3 -m pytest <connected_tests> -v
   ```
2. Verify zero regressions across the immediate 1-hop blast radius.
3. Commit with required trailers and submit PR for verifier review.

---

## Safety & Governance Guardrails
1. **Token Window Conservation:** Always respect the token budget parameter (default $\le 1,000$ tokens). Do not expand neighbor depth beyond 1 hop unless specifically tracing an indirect crash.
2. **Deterministic Fallback:** If Graphify daemon is stopped, use standard Python AST discovery (`synlynk/discovery.py`) or targeted `find_by_name` / `grep_search` on specific files.
3. **Branch Isolation:** Always work inside a dedicated git worktree (`git worktree add ../feat+<name> feat/<agent-prefix>/<name>`).
