<!-- generated - source of truth is state.db -->
---
decision_id: dec-6d438fd0
topic: "Defer the Graphify document sidecar to its own calibration goal"
date: 2026-10-27
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Defer the Graphify document sidecar to its own calibration goal

## Panel Inputs

### claude
The user-facing gap is real and narrow: when an agent (or Claude at Turn-1) picks up a dispatch, it has to chase a spec/goal/story by hand to find the acceptance line that governs a given code path. The code graph knows symbols; it has no node for "spec §3.2 commits to this behavior" or "story-X governs file Y." That's a navigation gap, not a research gap — it doesn't require LLM calls, images, or turning off `--code-only`.

**Strategies, ranked:**

1. **Second deterministic bucket, same invariant.** Run the existing markdown parser (page/heading nodes, links, inline-code-mention resolution) over `docs/`, `project-docs/`, GOVERNS rows — a `--docs-only` sibling to `--code-only`, same local/zero-token guarantee. Link doc nodes to code nodes only through the parser's existing inline-code-mention resolution (a spec line that says `bin/synlynk.py:exec_command` resolves like any other mention). No new LLM pass, no merge block — two separate extracts a caller can load together.

2. **Index-only metadata, no graph node.** Add a lightweight `GOVERNS`/spec-line → file-path lookup table (generated from front matter or a convention like `Governs: path/to/file`) that `synlynk dispatch` injects into context alongside the code graph, without touching Graphify's node model at all. Cheapest to ship, but it's a workaround, not graph extension — doesn't generalize to review/PM sweeps the way a real graph traversal would.

3. **Full non-code node types with LLM classification.** Rejected outright — explicitly excluded by the prompt and by dec-17f044f8; don't revisit.

**Decision: Strategy 1** — extend Graphify with a second deterministic, zero-token markdown bucket that mirrors `--code-only`'s invariant exactly, linked to the code graph only via existing mention-resolution, not a new merge layer.

**Before implementing anything**, measure: (a) how often a dispatched job's first wrong turn traces to a missing spec/goal link — pull from `capability_ratings`/`pr_review_cycles` on jobs with rework tagged "scope" or "misread spec"; (b) whether `synlynk pr check`'s GOVERNS-link enforcement already surfaces this gap cheaply without a graph at all. If GOVERNS metadata alone closes most of the gap, strategy 2 wins on cost and strategy 1 isn't worth building.

This is advisory only — not a go-ahead to build; v0.26.5 remains unsigned.

### agy
**Last completed task:** `chore(release): sync website/docs-bundle collateral for v0.26.4 (#2637)`  
**Next task from `todo.md`:** `Reconcile project-docs drift stranded in PR #2571 review worktree (PR #2572) [backend]`

---

### Advisory Panel Assessment: Graphify Scope Extension

**User-Facing Gap:**  
In Turn-1 agent dispatches, reviews, and PM sweeps, prompt context cites specification acceptance lines, GOVERNS goals, decisions, or charters that possess no graph edge to the concrete AST symbols they govern. Agents are forced into speculative exploratory grep turns or hallucinated symbol referencing because the knowledge graph stops abruptly at the file boundary.

### Proposed Strategies & Ranking

1. **Rank 1 — Selective Deterministic Markdown Ingestion (Targeted Governance Bridge):**  
   Leverage Graphify’s existing zero-LLM deterministic markdown parser (page/heading nodes and inline code mentions resolved to symbols) strictly scoped to structured operational paths (`docs/superpowers/`, `project-docs/`, charters). Leave images, papers, HTML/YAML, and the semantic LLM chunking/community pass disabled. This connects spec acceptance criteria directly to code AST symbols without violating `dec-17f044f8` (offline, zero extract-time tokens) and without diluting the graph with unstructured prose.

2. **Rank 2 — Dispatch-Time Sidecar Linker (Zero Graph Mutation):**  
   Retain the pure `--code-only` graph unaltered. Build an offline packaging step that parses `state.db` ledgers and markdown headers at dispatch time, regex-resolving declared symbols against the pre-extracted AST index. This prevents any graph dilution, but it sacrifices multi-hop graph queries (e.g., tracing a spec line through governing interfaces to impacted callers during release integrity checks).

3. **Rank 3 — Dual Federated Subgraphs (Code Graph + Doc Graph):**  
   Extract a dedicated `graph.docs.json` alongside `graph.code.json` using deterministic markdown parsing, querying across both via an in-memory bipartite join. While guaranteeing zero AST index contamination, it doubles disk serialization, introduces cross-index drift, and adds unnecessary graph query overhead.

### Measurement Prior to Implementation

Before any implementation, measure:
1. **Extraction Latency Delta:** Wall-clock overhead of running deterministic markdown parsing over governance paths versus the baseline `--code-only` run.
2. **Turn-1 Retrieval Precision & Token Burden:** The reduction in agent discovery turns versus token payload increase when dispatching with spec-to-AST edges.
3. **Graph Density & Centrality Drift:** Degree distribution and PageRank drift on AST symbols to verify documentation nodes do not degrade code-navigation queries.

Decision: Strategy 1 (Selective Deterministic Markdown Ingestion) is recommended because it bridges the governance-to-code gap deterministically while strictly preserving the offline, zero-token invariant.

### codex
The user-facing gap is not “more modalities”; it is missing Turn-1 connective tissue. Agents can see AST symbols, but not reliably connect a governing spec acceptance line, roadmap row, decision, goal, RCA, skill, or charter to the code it constrains. That weakens dispatch context, review reasoning, PM sweeps, and release-integrity checks.

Ranked strategies:

1. **Add a deterministic document sidecar graph, kept separate from the code graph.** Extend the existing markdown parser to emit page/heading nodes, links, inline-code-to-symbol references, and ledger-row identifiers, then relate those nodes to code symbols only through explicit references and path conventions. Keep `--code-only` as the default scan/watch/daemon behavior; provide a separately invoked local document indexing step. This adds useful context without semantic guessing or extract-time tokens, and preserves a clear boundary between authoritative code structure and human intent.

2. **Build a query-time context join, not a unified graph.** Leave Graphify’s code graph unchanged and have Synlynk resolve selected markdown references when assembling dispatch, review, PM, or release context. This minimizes graph dilution and operational risk, but duplicates reference-resolution logic and makes cross-cutting queries less consistent.

3. **Run full Graphify extraction for an opt-in research/indexing mode.** This could capture richer document relationships, but it invokes semantic LLM processing, introduces provider/token variance, and conflicts with the standing offline, zero-cloud, zero extract-time-token invariant. It should remain an experiment, not a product path.

Before implementation, measure a representative corpus: percentage of specs/goals/decisions/stories with explicit code links; Turn-1 tasks requiring manual document lookup; time to identify governing acceptance criteria; review findings attributable to missing document context; PM sweep false positives/negatives; and release-integrity cases where intent-to-code linkage is absent. Also measure sidecar build time, determinism, storage growth, and zero-network compliance.

Decision: Recommend Strategy 1, the deterministic document sidecar graph, pending evidence that it materially reduces context misses without changing the default `--code-only` invariant.

### grok
The gap is Turn-1 context. Dispatch, review, PM sweeps, and release checks already name specs, plans, decisions, roadmap rows, GOVERNS goals and stories, RCAs, skills, and charters. Those are markdown files and ledger rows. Every Synlynk extract is `graphify extract <repo> --code-only --out .synlynk/graphify-out`, which drops the document bucket before Graphify's deterministic markdown parser (page and heading nodes, links, inline code mentions resolved to symbols). An agent can cite an acceptance line or a goal and still have no edge to the code that line governs. Decision dec-17f044f8 (2026-09-14) still holds: no multi-modal sweep until a concrete gap is named, and offline, zero-cloud, zero extract-time tokens stays the invariant. This gap is that concrete case. Images, PDFs, OCR, Docs export, LLM community labels, and a merge block stay out. The default scan, watch, and daemon loop keeps `--code-only`.

1. **Curated markdown join (recommended).** A second local pass over an allowlist only: specs, plans, decisions, RCAs, skills, charters, and roadmap markdown. Use the deterministic parser Graphify already ships. No tree-sitter, no LLM, no `--mode deep`. Write those nodes into the same graph and attach them to existing symbols. Goals and stories stay Synlynk edges keyed by story id, because they are ledger rows, not files Graphify classifies.

2. **Sidecar, read at context-pack time.** Parse the same allowlist in Synlynk and store doc-to-symbol edges beside `graph.json`. Dilution risk is lowest. Cost is a second parser and a second store reviewers must trust.

3. **Full document bucket, still no LLM.** Index every `.md`, `.mdx`, `.txt`, `.rst`, `.html`, `.yaml`, and `.yml` file. Config, HTML, and incidental prose would sit in the same neighborhoods as code and weaken the graph agents already query. Leave this unbuilt.

Before any implementation, dry-run strategy 1 without changing scan, watch, or the daemon. Measure extract wall time and token count against the code-only baseline (tokens must stay zero), node and edge growth, the share of Turn-1 citations that gain at least one resolved code edge, the wrong-symbol rate on inline mentions, and how often a PM sweep can list governed files for a story. Proceed only if the citation hit rate moves and the wrong-symbol rate stays low.

Decision: Adopt strategy 1, a curated deterministic markdown join, with the `--code-only` loop unchanged.

## Synthesis
All four panelists named the same user-facing gap: Turn-1 dispatch, review, PM sweep, and release checks cite specs, plans, decisions, goals, stories, RCAs, skills, and charters, while the code graph has no edge from those lines to the symbols they govern. Every seat kept the default scan, watch, and daemon loop on `graphify extract --code-only`, rejected images, PDFs, OCR, and LLM community labels, and asked for a measurement pass before any build.

They differed on storage. Claude recommended a second deterministic bucket loaded beside the code graph. Agy ranked selective ingestion into the graph first and a dispatch-time sidecar second. Codex recommended a separate document sidecar invoked on its own. Grok recommended a curated join into the same graph, with a sidecar store as the second choice. The synthesizer merged these as a curated sidecar, stored separately from the code graph, linked only by Graphify's existing inline-code mention resolution.

Conductor amendment, recorded because Nikhil asked to document the decision and to hold the evaluation as its own goal: the candidate is accepted as a future calibration, not as v0.26.5 scope. Dropping `--code-only` is not the way to reach the local markdown parser. That flag is what keeps the semantic LLM pass off. The calibration must call the local parser directly.

This record approves the deferral and the calibration goal. It does not approve implementation of the sidecar.

## Decision
Decision: Record the curated deterministic markdown sidecar as the candidate strategy and defer it. Do not implement it in v0.26.5. Evaluate it later with a calibration run under goal-34c225e1 and story-bae335b6. Keep scan, watch, and the daemon on --code-only. Call Graphify's local markdown parser directly over the allowlist (docs/superpowers specs and plans, project-docs, RCAs, skills, and charters). Store doc nodes separately from the code graph and link them only through inline code mentions. Adopt the sidecar only if that calibration shows a citation-hit gain, a low wrong-symbol rate, zero extract-time tokens, and a gap that synlynk pr check's GOVERNS link does not already close.

> Signatures: see 2026-10-27-defer-the-graphify-document-sidecar-to-i.json
