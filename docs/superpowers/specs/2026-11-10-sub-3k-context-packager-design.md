# Graph-Backed Context Packager for Sub-3k Token Agent Task Dispatch and Impact Analysis

**Date:** 2026-11-10  
**Status:** Proposed (Brainstorm Design)  
**Authors:** Agy (Gemini) with Nikhil Soman  
**Target Release:** `v0.32.0` (Context Packager & Sub-3k Token Agent Dispatch)  
**Parent Story:** `story-5ce5a997`  
**Parent Goal:** `goal-eacab0dc` (Universal GOVERNS Enforcement & Context Layer)

---

## 1. Executive Summary & Problem Statement

In Synlynk's multi-agent fleet operations (Claude, Agy, Codex, Grok), task dispatches currently synthesize full repository context, role charters, verbose file trees, and unpruned AST summaries into the initial prompt. 

On typical bounded tasks (e.g. bug fixes, minor schema updates, single-function implementations), prompts routinely balloon to **12,000–30,000 tokens**. This causes:
1. **Severe Token Cost Inefficiency**: Dispatches burn 5x–10x more tokens than necessary, rapidly consuming quota reserves and triggering sentinel burn-rate warnings.
2. **Context Dilution & Hallucination**: Overloaded prompts inject irrelevant files and distant AST definitions, distracting LLM attention mechanisms and degrading surgical code accuracy.
3. **Latency Drag**: High prompt token volumes significantly increase Time-to-First-Token (TTFT) across API providers.

### The Contract of Record
This specification formalizes **Sub-3k Token Agent Dispatch**:
- **Default Behavior**: Every standard task dispatch prompt is bounded to **strictly $\le$ 3,000 tokens**.
- **Information Density**: Instead of naive text truncation, context is synthesized using **Graph Slicing + Strict Budget Allocation** backed by Graphify's AST knowledge graph and blast radius impact analysis.
- **Escape Hatch**: An explicit `--full-context` CLI flag is provided for epics, migrations, and broad architectural refactors that genuinely require broad context.

---

## 2. Architecture & 4-Stage Slicing Pipeline

The sub-3k context packager runs deterministic, offline graph operations in `synlynk/pack.py`, `synlynk/impact.py`, and `synlynk/dispatch.py`:

```
┌────────────────────────────────────────────────────────────────────────┐
│                     SUB-3K CONTEXT PACKAGER PIPELINE                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 1: Seed & Intent Extraction                                      │
│ • Resolve Story ID / Task prompt query tokens                          │
│ • Query stories table in state.db for title & scope                    │
│ • Filter stopwords and extract domain entity keywords                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 2: 1-Hop AST Graph Slicing & Blast Radius Analysis               │
│ • Match seed AST nodes in .synlynk/graphify-out/graph.json             │
│ • Slice 1-hop inbound callers (who calls this?)                        │
│ • Slice 1-hop outbound dependencies (what does this call?)             │
│ • Identify associated test targets from test/ and tests/ nodes         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 3: Adaptive AST Compaction                                       │
│ • Strip AST function bodies and internal implementation blocks         │
│ • Retain def/class signature with full type annotations                │
│ • Condense multi-line docstrings to 1-line functional summary (<120 ch)│
│ • Format callers and callees as compact relative references            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 4: Strict Budget Allocator & Envelope Assembly                   │
│ • Section A: Directives, Receipts & Story Ref (~500 tokens)            │
│ • Section B: Task Criteria & Scoped File Paths (~400 tokens)           │
│ • Section C: AST Context Pack (Signatures & Interfaces) (~1,200 tokens)│
│ • Section D: Blast Radius & Impact Warnings (~400 tokens)              │
│ • Section E: Suggested Test Verification Targets (~400 tokens)         │
│ • Invariant: Total Prompt Budget <= 3,000 tokens                       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Strict Token Budget Allocation (3,000 Token Envelope)

When compiling prompts in `synlynk/dispatch.py:_format_prompt_for_agent`, tokens are allocated into partitioned envelopes. If any section exceeds its ceiling, section-specific compression rules are applied before prompt concatenation:

| Section | Target Ceiling | Overflow / Compaction Strategy |
|:---|:---|:---|
| **A. Task Receipts, Directives & Role Charter** | **500 tokens** | Condense role charter to enforced boundaries only; exclude guidance advice. |
| **B. Task Intent & Story Criteria** | **400 tokens** | Format task requirements into bullet points; limit task criteria to top 5 points. |
| **C. AST Signatures & Primary Subsystems** | **1,200 tokens** | Max 6 top symbols; compact 1-line signatures `def func(...) -> Type`; exclude method bodies. |
| **D. Blast Radius & Dependent Risks** | **400 tokens** | List top 5 direct upstream callers and affected files; summarize downstream modules. |
| **E. Verification Test Targets & Command** | **400 tokens** | Provide exact `pytest <test_file>::<test_name>` commands for affected code. |
| **Headroom Buffer** | **100 tokens** | Reserve for markdown formatting tokens, headers, and separators. |
| **TOTAL PROMPT** | **3,000 tokens** | **Hard Floor Guarantee** ($\le$ 3,000 tokens). |

---

## 4. AST Graph Slicing & Blast Radius Engine

### 4.1 Seed Matching
Seeds are identified by scoring AST nodes from `.synlynk/graphify-out/graph.json` against task tokens:
- Exact symbol name match: score +5
- File path match: score +3
- Docstring/summary match: score +1

Top $K \le 6$ scored nodes form the **seed set**.

### 4.2 1-Hop Slicing Contract
Rather than traversing deep multi-hop dependency graphs (which explode prompt sizes), the Sub-3k engine restricts traversal to **1-hop directed edges**:
1. **Inbound Edges ($A \rightarrow Seed$)**: Direct callers that invoke the target symbol. (Helps the agent understand expected call contracts).
2. **Outbound Edges ($Seed \rightarrow B$)**: Direct dependencies invoked by the target symbol. (Prevents interface mismatches with internal utilities).
3. **Test Edges**: Test functions or files that reference the seed symbol or its module.

### 4.3 Adaptive AST Compactor
When extracting definition signatures from source files (`_get_ast_signature`):
```python
# Raw Source File:
def execute_dispatch(job_id: str, harness: str, timeout: int = 300) -> DispatchResult:
    """Execute a task dispatch against an isolated agent worktree.
    
    This function handles lock management, worktree provisioning,
    execution piping, and verification receipt collection.
    
    Parameters:
        job_id: Unique dispatch identifier.
        ...
    """
    ... 60 lines of implementation ...

# Compacted AST Output (sub-3k format):
- `execute_dispatch(job_id: str, harness: str, timeout: int = 300) -> DispatchResult` [synlynk/dispatch.py:L2850]
  *Execute a task dispatch against an isolated agent worktree.*
  - Inbound Callers: `cmd_dispatch` [synlynk/cli.py:L1420]
  - Dependencies: `_provision_worktree` [synlynk/worktree.py:L104]
```

### 4.4 Knowledge Graph Freshness & Zero-Drift Invariant

The Sub-3k Context Packager depends fundamentally on the AST Knowledge Graph reflecting the true current state of the workspace. Previously, `_GRAPH_STALE_COMMIT_THRESHOLD = 25` allowed up to 25 commits of drift before auto-refreshing, leading to stale AST signatures and Vizor warnings (`⚠️ Graph Stale`).

This design establishes a **Zero-Drift Graph Currency Contract**:
1. **Zero-Drift Threshold (`_GRAPH_STALE_COMMIT_THRESHOLD = 0`)**:
   In `synlynk/dispatch.py`, if `built_at_commit != git rev-parse HEAD`, the graph is treated as immediately stale.
2. **Pre-Dispatch Just-In-Time Refresh**:
   Before `synthesize_context_pack` executes, `dispatch.py` compares `built_at_commit` with HEAD. If mismatched, it triggers an incremental `_run_graphify_extract(repo_root)` (taking ~1–3s via Graphify's file-hash cache) so that dispatches **never** receive outdated signatures.
3. **Dual Commit Stamping**:
   `_run_graphify_extract` updates `built_at_commit` atomically in both `.synlynk/graphify-out/manifest.json` and `.synlynk/graphify-out/graph.json`, ensuring Vizor, packager, and discovery always agree on the current HEAD SHA.
4. **Post-Merge & Watch Auto-Sweep**:
   When PRs are merged via `synlynk pr merge` or when the background daemon (`synlynk watch`) detects HEAD movement, a non-blocking background graph extract is fired automatically.

---

## 5. CLI & Runtime Flag Semantics

### 5.1 Default vs. Full Context Mode
In `synlynk/dispatch.py` and `synlynk/cli.py`:

```bash
# Default dispatch: Automatically compiles sub-3k context pack
synlynk dispatch --as-agent dev --story story-1234abcd

# Full context override: Bypasses 3k token ceiling for large architectural tasks
synlynk dispatch --full-context --as-agent architect --story story-5678ef01
```

### 5.2 Standalone Inspection Command
Developers and conductors can inspect the generated context pack and token count directly:

```bash
# Generate and display sub-3k pack for a story or prompt
synlynk pack --budget 3000 story-5ce5a997

# Output token count and section breakdown
synlynk pack --budget 3000 --inspect story-5ce5a997
```

Sample `--inspect` output:
```text
=== Sub-3k Task Context Pack Inspection ===
Target Story: story-5ce5a997 (Graph-backed context packager...)
Total Estimated Tokens: 2,410 / 3,000 (PASSED)

Section Breakdown:
  [A] Directives & Charter:   420 tokens
  [B] Task Criteria:          310 tokens
  [C] AST Interfaces (5):     980 tokens
  [D] Blast Radius & Risks:   380 tokens
  [E] Test Targets (3):       320 tokens
```

### 5.3 Sentinel Monitoring
If an uncompressed standard dispatch prompt exceeds 3,000 tokens, `synlynk sentinel` emits a `CONTEXT_BUDGET_EXCEEDED` warning event to ensure continuous budget compliance and prevent regression.

---

## 6. Implementation Plan & File Touch Surface

| Module | Primary Modifications |
|:---|:---|
| [`synlynk/pack.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/pack.py) | Implement `synthesize_sub3k_context_pack()`, adaptive AST compaction with 1-line docstring truncation, and partitioned section assembly. |
| [`synlynk/impact.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/impact.py) | Add `slice_1hop_impact(seed_nodes)` to return compact caller/callee/test tuples bounded by count limits. |
| [`synlynk/dispatch.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/dispatch.py) | Wire `--full-context` flag into `dispatch` parser; default `_format_prompt_for_agent` to sub-3k budget; add `CONTEXT_BUDGET_EXCEEDED` sentinel trigger. |
| [`synlynk/cli.py`](file:///Users/nikhilsoman/dev/synlynk/synlynk/cli.py) | Add `--full-context` flag to `dispatch` parser and `--inspect` flag to `pack` command. |
| [`tests/test_context_packager_sub3k.py`](file:///Users/nikhilsoman/dev/synlynk/tests/test_context_packager_sub3k.py) | Unit tests verifying: 1) Strict $\le$ 3,000 token ceiling on benchmark stories, 2) Complete signature retention, 3) 1-hop caller/callee linkage, 4) `--full-context` passthrough. |

---

## 7. Verification Invariants & Acceptance Criteria

1. **Token Ceiling Invariant**: For all standard task dispatches (without `--full-context`), `len(prompt) // 4` (or exact tiktoken / cl100k estimate) MUST NOT exceed 3,000 tokens.
2. **Signature Integrity Invariant**: No function definition signature or type annotation is truncated mid-identifier. Signatures must remain valid AST strings.
3. **Zero External Network Dependencies**: Graph slicing, AST compaction, and impact extraction operate 100% locally on `.synlynk/graphify-out/graph.json` and Python source files.
4. **Deterministic Output**: Given the same git commit and story ID, the generated context pack produces identical character output across all harnesses.

---

## 8. Future Horizon: Curated Document Sidecar Graph (`goal-34c225e1`)

To prevent non-code artifacts from bloating the core code AST graph while still granting agents semantic access to specifications and architectural history, this design establishes the roadmap bridge for the **Curated Markdown Document Sidecar Graph**:

### 8.1 Scope & Architecture
- **Curated Ingestion Allowlist**: Rather than parsing arbitrary text, the sidecar deterministically indexes structured markdown artifacts: `docs/superpowers/specs/`, `docs/superpowers/plans/`, `project-docs/decisions/`, `docs/rfcs/`, role charters, and `.agents/` profiles.
- **Dual-Graph Separation**: The core AST graph stays strictly `--code-only` (`.synlynk/graphify-out/graph.json`) to preserve sub-second code slicing speeds. The document sidecar resides at `.synlynk/graphify-out/doc_graph.json`.
- **Cross-Graph Edges**: Document nodes link to code symbols via explicit backticks or markdown links (`[ClassName](file:///...)`), allowing the packager to traverse from a spec requirement directly to the implementing code function.

### 8.2 Trigger & Activation Criteria
The sidecar graph is triggered and merged into context packs under the following deterministic conditions:
1. **Role / Discipline Trigger**: Dispatches assigning `architect`, `pm`, `strategist`, `director`, or `docs` roles automatically mount the document sidecar.
2. **Path / Domain Trigger**: Tasks touching files in `docs/`, `project-docs/`, or specs (`engg_domain in ('docs', 'architecture', 'strategy')`).
3. **Budget Partitioning**: In document-enabled mode, the AST budget envelope dynamically partitions into 600 tokens for code AST + 600 tokens for spec/decision excerpts, preserving the strict 3,000-token total ceiling.
4. **Goal Alignment**: Formally tracked under active goal [`goal-34c225e1`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md) (*"Decide whether a curated deterministic markdown sidecar should join specs, plans, decisions, RCAs, skills, and charters to code symbols"*) and governed by [`goal-eacab0dc`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md).

