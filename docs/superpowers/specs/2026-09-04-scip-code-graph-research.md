# Research Notes: Code Intelligence & Symbol Graph Representations for Context Assembly in Synlynk

**Date:** 2026-09-04  
**Status:** In Review / Research Specification  
**Issue:** Closes [#1396](https://github.com/nikhilsoman/synlynk/issues/1396)  
**Authors:** [@nikhilsoman], [@agy]  
**Relates to:** `story-4949989b`, `goal-abecd18c`, #1255, #1306  

---

## 1. Executive Summary & Objective

Autonomous software engineering agents (such as the Synlynk fleet: Claude, Agy, Codex, Grok) depend heavily on the quality, relevance, and density of the context injected into their prompts. Currently, Synlynk's codebase inspection relies on:
1. Heuristic regex pattern matching (`synlynk/scan.py: _extract_symbols()`) capped at 300 lines per file.
2. Flat git log recency scoring (`_score_source_files()`).
3. Textual devlog and memory concatenation (`synlynk/context.py: _generate_task_context()`).

While lightweight and dependency-free, this baseline has no semantic understanding of code structure: it cannot resolve cross-file symbol definitions, determine call graphs or callers/callees, detect type inheritance hierarchies, or identify which tests exercise a modified code path. Consequently, agents either hallucinate cross-module signatures, suffer from costly context blowups by loading entire unneeded files, or fail to modify interdependent modules in multi-file refactors.

This research paper evaluates three primary paradigms of code intelligence:
- **SCIP (Sourcegraph Code Intelligence Protocol)** indexers (`scip-python`, `scip-typescript`, `scip-go`, etc.) for compiler-grade, cross-file semantic indexing.
- **Tree-sitter Symbol Graphs** for sub-millisecond, dependency-free, error-tolerant AST parsing and lexical graph construction in dirty, mid-edit worktrees.
- **Glean-Compatible Code Intelligence** (Meta's relational Datalog/Angle fact graph architecture) for structured querying of code facts, caller/callee subgraphs, and test-impacted scopes.

Finally, this document specifies a **Tri-Tier Hybrid Code Intelligence Engine** and token-budgeted context assembly pipeline tailored directly to Synlynk's single-file, zero-heavy-daemon runtime requirements.

---

## 2. Problem Statement: The Agent Context Assembly Bottleneck

When Synlynk dispatches an agent into an ephemeral worktree (`.worktrees/job-<id>`), the agent faces the "needle-in-a-haystack" problem within strict context token budgets (typically 2,000 to 12,000 tokens allocated for code context).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CURRENT DEFICIT IN SYNLYNK                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Regex Fragility:                                                         │
│    Regexes miss multiline signatures, decorators, nested classes, and async │
│    closures; fail silently on complex metaprogramming and type annotations. │
│ 2. Blind Call Hierarchies:                                                  │
│    When refactoring `synlynk.dispatch.dispatch_agent()`, the agent cannot   │
│    know what calls it across `cli.py`, `jobs.py`, or `daemon.py` without   │
│    blindly grepping and consuming hundreds of lines of irrelevant tokens.   │
│ 3. Whole-File Token Bloat:                                                  │
│    Loading entire files (e.g. `synlynk/__init__.py` at ~4,000 lines or      │
│    `synlynk/jobs.py` at ~3,000 lines) exhausts token windows and triggers   │
│    hallucination loops (#1073 cost ratio sentinel incidents).               │
│ 4. Dirty Worktree Volatility:                                               │
│    Agents work in dirty trees during active refactoring. Compiler-based     │
│    typecheckers break completely on syntax errors; indexers must degrade    │
│    gracefully and parse partial code states.                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Deep Evaluation of Technologies

### A. Sourcegraph Code Intelligence Protocol (SCIP)

#### Protocol & Ecosystem Overview
SCIP is an open, language-agnostic protocol defined via Protocol Buffers (`index.scip`), created by Sourcegraph as the next-generation successor to LSIF (Language Server Index Format). SCIP indexes emit deterministic, package-qualified symbol strings:
```
scip: <scheme> ' ' <package> ' ' <version> ' ' <descriptor>
Example:
scip-python python synlynk 0.19.0 synlynk/dispatch/dispatch_agent().
```

Official and community SCIP indexers include:
- `scip-python`: Built on Pyright (Microsoft's static type checker).
- `scip-typescript` / `scip-javascript`: Built on TypeScript Compiler API.
- `scip-go`: Built on `golang.org/x/tools/go/packages`.
- `scip-rust`: Built on `rust-analyzer`.
- `scip-java` / `scip-clang`: Built on semantic compilers (Clang LibTooling, javac).

#### Architectural Strengths
1. **Compiler-Grade Semantic Accuracy:**
   Because `scip-python` executes Pyright, it accurately resolves type inference, class inheritance, method overriding, imported aliases (`from .foo import bar as baz`), and typing overloads.
2. **Deterministic Cross-File Linking:**
   References in `synlynk/cli.py` to `synlynk.dispatch.dispatch_agent()` bind to the exact same symbol ID as the declaration in `synlynk/dispatch.py`. There is zero ambiguity with identically named symbols in different modules.
3. **Decoupled Offline Serving:**
   The index is generated once into `index.scip`. Queries (`get_definition`, `find_references`, `get_hover`) execute in microseconds by querying the serialized protobuf or SQLite conversion without running a language server process.

#### Vulnerabilities & Trade-offs for Synlynk
1. **Strict Environment & Dependency Requirements:**
   `scip-python` requires project virtual environments with all dependencies installed. If external wheels or stub types are missing, cross-library type resolution fails. In sandboxed agent dispatch environments with denied network egress (`codex` without `requires_gh_write`), indexers cannot download missing packages.
2. **Cold Indexing Latency:**
   Running `scip-python` or `scip-typescript` on a 50,000 LOC repository takes between 10s and 60s. Running a full SCIP re-index before every agent turn or prompt injection would cause unacceptable latency.
3. **Binary Serialization Overhead:**
   Consuming `index.scip` requires Protobuf bindings or invoking the `scip` CLI binary. Integrating binary execution into Synlynk's pure-Python standard-library philosophy introduces external binary dependency hurdles.

---

### B. Tree-sitter Symbol Graphs & AST Navigation

#### Architecture Overview
Tree-sitter is an incremental parsing system built in C with bindings across Python (`tree-sitter`, `tree-sitter-languages`), Node, Rust, and WASM. It generates concrete syntax trees (CSTs) from source code using GLR parsing grammars.

#### Key Mechanics: Tree-sitter Queries (`.scm`)
Tree-sitter uses S-expression pattern matching to extract syntax nodes declaratively:
```lisp
;; python-symbols.scm
(function_definition
  name: (identifier) @symbol.name
  parameters: (parameters) @symbol.params
  body: (block) @symbol.body) @symbol.def

(class_definition
  name: (identifier) @class.name
  superclasses: (argument_list)? @class.super) @class.def

(call
  function: [
    (identifier) @call.identifier
    (attribute attribute: (identifier) @call.method)
  ]) @call.site
```

#### Architectural Strengths
1. **Sub-Millisecond Incremental Parsing:**
   Tree-sitter does not re-parse entire files upon edit. When an agent edits 5 lines in a 3,000-line file, Tree-sitter updates the syntax tree in under **0.5 milliseconds** via syntax node reuse.
2. **Rock-Solid Error Recovery (Dirty-Tree Resilience):**
   Unlike static compilers which abort on syntax errors, Tree-sitter contains robust error-recovery heuristics. If an agent writes an incomplete `def test_something(` without closing parentheses or indents, Tree-sitter isolates the `ERROR` node and continues parsing the remainder of the file flawlessly.
3. **Zero Build Dependencies / Zero Host Toolchain:**
   Tree-sitter requires no virtual environments, no compilers, no node_modules, and no network access. It operates purely on raw file buffers.
4. **Symbol Graph & PageRank Skeletons (The Repomap Pattern):**
   By extracting symbol definitions and call sites per file, Synlynk can build an in-memory bipartite graph ( = (V_{files}, V_{symbols}, E_{calls})$). Running PageRank on this graph surfaces the most architecturally central symbols relevant to the user's task prompt.

#### Vulnerabilities & Trade-offs for Synlynk
1. **Syntactic Scope Only (No Type Inference):**
   Tree-sitter knows that `x.do_work()` is a method call on identifier `x`, but without a type checker, it cannot resolve whether `x` is an instance of `WorkerA` or `WorkerB` if both define `do_work()`.
2. **Ambiguity with Dynamic Dispatch:**
   In highly dynamic Python or JavaScript code, method calls on generic objects cannot be resolved to a specific file target without heuristic ranking.

---

### C. Glean-Compatible Code Intelligence (Relational Fact Graphs)

#### Overview & Meta Architecture
Glean is Meta's open-source code intelligence engine, used internally to power code search, code review navigation, and developer tools across Facebook's monorepos. Glean models code as an **immutable relational knowledge graph** expressed in a Datalog-derived schema language called **Angle**:
```
# Glean Angle Schema Example
schema python.1 {
  predicate Declaration:
    {
      name: string,
      container: maybe Entity,
      file: src.File,
      span: src.ByteSpan,
    }

  predicate CallSite:
    {
      caller: Declaration,
      callee: Declaration,
      file: src.File,
      line: nat,
    }
}
```

#### Architectural Strengths
1. **Relational Query Expressiveness:**
   Unlike flat symbol lists or point-to-point LSP requests, Glean's fact model enables complex recursive graph queries:
   - *"Find all tests that transitively call `synlynk.dispatch.dispatch_agent` within 3 call hops."*
   - *"Find all classes implementing interface `HarnessAdapter` that override `execute_command`."*
   - *"Find the topological dependency order of modules affected by a diff in `synlynk/db.py`."*
2. **Fact Immutability & Delta Ingestion:**
   Facts are stored as indexed tuples. Unchanged files retain identical fact hashes; commit deltas only append new facts and link existing stable entity hashes.
3. **Subgraph Extraction for Agent Prompts:**
   Instead of injecting complete files, Glean can emit an exact **569Xhop neighborhood subgraph**: the target function, its direct caller signatures, its direct callee interfaces, and the type definitions of its parameter types.

#### Vulnerabilities & Trade-offs for Synlynk
1. **Massive Engine Complexity:**
   The full Meta Glean system requires a Haskell server, RocksDB storage, Angle query compiler, and dedicated indexer daemons—wholly incompatible with Synlynk's zero-bloat, single-tool CLI deployment.
2. **Glean-*Compatible* Adaptation:**
   Synlynk does not need the heavy Glean server. Instead, Synlynk can implement the **Glean Fact-Relational Paradigm** directly inside SQLite (`state.db` or `.synlynk/code_graph.db`) using relational tables and Recursive Common Table Expressions (CTEs).

---

## 4. Technology Comparison Matrix

| Evaluation Dimension | SCIP Indexers | Tree-sitter Symbol Graphs | Glean Relational Facts |
| :--- | :--- | :--- | :--- |
| **Semantic Precision** | **Compiler-Grade (Exact)** | Syntactic / Heuristic | **Exact to High (Relational)** |
| **Type Inference** | Full (via Pyright/tsc/rustc) | None | Dependent on Extractor |
| **Incremental Parsing Speed** | Slow (	ext{s} - 60	ext{s}$) | **Ultra-Fast ($<1	ext{ms}$)** | Fast (	ext{ms} - 50	ext{ms}$ per file) |
| **Dirty / Broken Code Tolerance** | Fails on syntax/type errors | **Excellent (Error-Recovery AST)** | Good (when fed by Tree-sitter) |
| **External Toolchain Dependencies** | Heavy (Venvs, Compilers) | **Zero (C/WASM / pure Python)** | Low (Embedded SQLite / pure Python) |
| **Graph Query Flexibility** | Low (Point-to-point symbols) | Medium (In-memory networkx/graph) | **Maximum (Recursive CTEs/Datalog)** |
| **Storage & Memory Footprint** | Protobuf file (`index.scip`, ~5-50MB)| Ephemeral CST in memory | Relational SQLite (~2-10MB) |
| **Best Role in Synlynk Fleet** | Background CI / Release Index | **Per-Turn Dirty Tree Context** | **Structural Context Subgraphs** |

---

## 5. Proposed Architecture: Synlynk Tri-Tier Code Intelligence Engine

To maximize accuracy while respecting Synlynk's strict performance and dependency constraints, Synlynk should adopt a **Tri-Tier Hybrid Code Architecture**:

```
                       ┌────────────────────────────────────────────────────────┐
                       │               SYNLYNK CONTEXT ASSEMBLER                │
                       │           (synlynk/context.py & dispatch.py)           │
                       └───────────────────────────┬────────────────────────────┘
                                                   │
                ┌──────────────────────────────────┼──────────────────────────────────┐
                ▼                                  ▼                                  ▼
   ┌───────────────────────────┐      ┌───────────────────────────┐      ┌───────────────────────────┐
   │          TIER 1           │      │          TIER 2           │      │          TIER 3           │
   │  Tree-sitter Fast AST &   │      │ Glean-Compatible Relational│      │     SCIP Static Index     │
   │      Repomap Engine       │      │   Fact Graph (SQLite)     │      │   (Optional Compiler CI)  │
   ├───────────────────────────┤      ├───────────────────────────┤      ├───────────────────────────┤
   │ • Sub-millisecond CST     │      │ • `code_entities` table   │      │ • Full type resolution    │
   │ • Dirty-tree error tolerant│     │ • `code_facts` table      │      │ • Cross-repo packages     │
   │ • File skeletonization    │      │ • Recursive CTE queries   │      │ • Ingested via CI/daemon  │
   │ • Fast PageRank ranker    │      │ • Caller/callee/test hops │      │ • Background update only  │
   │ • Zero host dependencies  │      │ • Transitive impact map   │      │ • Falls back to Tier 2    │
   └───────────────────────────┘      └───────────────────────────┘      └───────────────────────────┘
```

### Tier 1: Real-Time Tree-Sitter AST & Skeletonization (Active Worktrees)
- **Role:** Generates instant symbol outlines and skeletonized file views during active agent edits.
- **Execution:** Runs in-process in $<50	ext{ms}$ on touched files.
- **Output:** Strips function bodies, preserving signatures, type annotations, and docstrings (`def foo(x: int) -> str: ...`).

### Tier 2: Glean-Compatible Relational Fact Graph in SQLite (Project Core)
- **Role:** Answers graph queries: callers, callees, class hierarchies, and test associations.
- **Execution:** Backed by `state.db` (or `.synlynk/code_graph.db`) using standard SQLite.
- **Incremental Sync:** Synchronized during `synlynk scan` and git post-commit hooks via git commit SHA / tree hashing.

### Tier 3: SCIP Semantic Pipeline (High-Precision Ambient Layer)
- **Role:** Provides deep type resolution for complex, multi-package repositories.
- **Execution:** Run optionally in CI or background daemon (`synlynk daemon`). Emits `index.scip`, which is converted into Tier 2 SQLite facts. If SCIP is unavailable, the system operates seamlessly on Tiers 1 and 2.

---

## 6. Detailed SQLite Schema for Glean-Compatible Code Facts

To operationalize the Glean relational model within Synlynk without adding external dependencies, the following schema extends Synlynk's `state.db`:

```sql
-- 1. Code Entities (Declarations, Definitions, Modules)
CREATE TABLE IF NOT EXISTS code_entities (
    entity_id TEXT PRIMARY KEY,          -- sha256(head_sha:file:qualified_name:kind)
    head_sha TEXT NOT NULL,              -- Git commit SHA
    file_path TEXT NOT NULL,             -- Relative repo path
    language TEXT NOT NULL,              -- python, typescript, go, rust
    kind TEXT NOT NULL,                  -- function, class, method, variable, interface
    name TEXT NOT NULL,                  -- Symbol identifier
    qualified_name TEXT NOT NULL,        -- e.g. synlynk.dispatch.dispatch_agent
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    signature TEXT,                      -- e.g. (story_id: str, role: str) -> dict
    docstring TEXT,                      -- Extracted docstring / header comment
    is_exported BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL
);

-- 2. Code Facts (Relational Predicates & Cross-References)
CREATE TABLE IF NOT EXISTS code_facts (
    fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    head_sha TEXT NOT NULL,
    subject_id TEXT NOT NULL,            -- Source entity_id
    predicate TEXT NOT NULL,             -- 'calls', 'defines', 'inherits', 'imports', 'tests'
    object_id TEXT,                      -- Target entity_id (if resolved)
    target_symbol TEXT,                  -- Target symbol name (if unresolved / external)
    file_path TEXT NOT NULL,             -- Occurrence file
    line INTEGER NOT NULL,
    confidence REAL DEFAULT 1.0,         -- 1.0 = SCIP/Compiler, 0.8 = AST, 0.5 = Heuristic
    FOREIGN KEY(subject_id) REFERENCES code_entities(entity_id)
);

-- Indexes for lightning-fast graph traversal
CREATE INDEX IF NOT EXISTS idx_code_entities_head_file ON code_entities(head_sha, file_path);
CREATE INDEX IF NOT EXISTS idx_code_entities_qname ON code_entities(qualified_name);
CREATE INDEX IF NOT EXISTS idx_code_facts_subject ON code_facts(subject_id, predicate);
CREATE INDEX IF NOT EXISTS idx_code_facts_object ON code_facts(object_id, predicate);
CREATE INDEX IF NOT EXISTS idx_code_facts_target ON code_facts(target_symbol);
```

### Recursive CTE Query Example: 2-Hop Call Graph Expansion
```sql
WITH RECURSIVE call_tree(entity_id, qualified_name, depth) AS (
    -- Anchor: The target symbol being modified by the story
    SELECT entity_id, qualified_name, 0
    FROM code_entities
    WHERE qualified_name = 'synlynk.dispatch.dispatch_agent'
      AND head_sha = :current_head

    UNION

    -- Recursive step: Find callers and callees up to 2 hops
    SELECT e.entity_id, e.qualified_name, ct.depth + 1
    FROM call_tree ct
    JOIN code_facts f ON (f.subject_id = ct.entity_id AND f.predicate = 'calls')
                      OR (f.object_id = ct.entity_id AND f.predicate = 'calls')
    JOIN code_entities e ON (e.entity_id = f.object_id OR e.entity_id = f.subject_id)
    WHERE ct.depth < 2
)
SELECT DISTINCT qualified_name, depth FROM call_tree ORDER BY depth;
```

---

## 7. Context Assembly Strategy & Token Budgeting

Rather than dumping monolithic files into an agent prompt, the context assembler executes a strict 4-stage pruning pipeline:

```
Raw Project Code (100k+ tokens)
  │
  ▼ [Stage 1: Focus File Discovery via Git Diff & Story Metadata]
Focused Files & Symbols (15k tokens)
  │
  ▼ [Stage 2: Graph Expansion via 1-Hop Caller/Callee CTE]
Target Subgraph (8k tokens)
  │
  ▼ [Stage 3: Tree-sitter Skeletonization (Fold Bodies -> ...)]
Interface Skeletons + Full Focus Bodies (2.5k tokens)
  │
  ▼ [Stage 4: Token Budget Enforcer (< 3,500 tokens)]
Optimized Context Injection Block (.synlynk/contexts/job-<id>.md)
```

### Context Injection Output Format
Injected into `.synlynk/contexts/job-<id>.md` under `## Relevant Code Intelligence`:
```markdown
## Code Intelligence: Architectural Subgraph (Focus: synlynk.dispatch.dispatch_agent)

### Direct Callers (1-Hop Upstream)
- `synlynk.cli.main()` [synlynk/cli.py:1450]
- `synlynk.daemon.worker_loop()` [synlynk/daemon.py:320]

### Direct Callees (1-Hop Downstream)
```python
# synlynk/probe.py (Interface Skeleton)
def probe_harness_capabilities(harness_name: str) -> dict: ...

# synlynk/approval_gate.py (Interface Skeleton)
def check_dispatch_approval(story: dict, agent: str) -> tuple[bool, str]: ...
```

### Associated Unit & Integration Tests
- `tests/test_dispatch.py::test_codex_dispatch_workspacewrite_sandbox`
- `tests/test_agent_cli.py::test_cli_dispatch_as_agent_without_explicit_harness`
```

---

## 8. Implementation & Rollout Roadmap

### Phase 1: Pure-Python Tree-sitter AST & Skeletonizer (Milestone 1)
- Introduce `tree-sitter` parser wrapper in `synlynk/ast_parser.py` (with fallback to regex parser when tree-sitter C/binary extensions are absent).
- Replace `synlynk/scan.py: _extract_symbols()` with AST symbol extraction (classes, functions, async methods, arguments, return type annotations).
- Add skeletonization utility: render files with function bodies replaced by `...`.

### Phase 2: Glean Fact Schema Migration in `state.db` (Milestone 2)
- Add `code_entities` and `code_facts` migration to `synlynk/db.py: _migrate_db()`.
- Update `synlynk scan` to populate relational facts during cold and incremental runs.
- Implement recursive CTE queries in `synlynk/code_graph.py` for caller/callee and test impact resolution.

### Phase 3: Context Assembler Integration (Milestone 3)
- Update `synlynk/context.py: _generate_task_context()` to query the code fact graph for story target symbols.
- Integrate token budgeting: dynamically prune the graph to fit inside a configurable ceiling (`max_code_context_tokens: 3000`).

### Phase 4: Optional SCIP Ambient Ingester (Milestone 4)
- Add `synlynk index --scip` command to run `scip-python` / `scip-typescript` if installed on host.
- Ingest `index.scip` protobuf output into `code_entities` and `code_facts` with confidence score `1.0`.

---

## 9. Verification & Conclusion

This research demonstrates that relying solely on SCIP introduces severe environmental friction in ephemeral sandboxed agent worktrees, while relying solely on Tree-sitter limits context to syntactic boundaries. Meta's Glean fact-relational architecture provides the conceptual bridge: by capturing code entities and relational facts in SQLite, Synlynk achieves compiler-grade query flexibility, sub-millisecond AST agility, and strict token economy—advancing Synlynk toward autonomous multi-agent engineering maturity.
