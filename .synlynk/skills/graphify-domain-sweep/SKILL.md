---
name: graphify-domain-sweep
description: Execute multi-modal deep extractions on reference standards, external RFCs, and API specifications to synthesize evidence-backed PRDs and domain models.
---

# Graphify Domain Sweep

## Charter Mandate & Overview
- **Primary Role:** `pm`
- **Supported Harnesses:** Claude
- **Mission:** Anchor product specifications, PRDs, and domain ontologies in verifiable reference standards (e.g. LOINC, HL7, OpenAPI, RFCs, regulatory frameworks) using multi-modal deep AST and text knowledge graphs.

Product requirements must not rely on hand-waving or hallucinated external standard requirements. The PM harness utilizes Graphify's deep multi-modal extraction mode to transform reference documentation into structured knowledge graphs, producing specifications with chapter-and-verse evidentiary citations.

---

## Available Tools & CLI Commands

### MCP Tools (`graphify-mcp`)
- `query_graph(question: str)`: Formulates natural-language queries against the domain knowledge graph, returning semantic entities, citation anchors, and structural relationship triples.
- `get_community(id: str | int)`: Clusters domain concepts into thematic modules, revealing requirement overlaps and cross-standard mappings.

### CLI & External Tool Commands
- `graphify extract <dir> --mode deep`: Executes multi-modal deep extraction across Markdown, PDFs, OpenAPI YAML/JSON, and schemas, synthesizing a semantic knowledge graph.
- `synlynk pm sweep`: Conducts autonomous product management and competitive sweeps across project backlog and target domain references.

---

## Execution Protocol

### Step 1: Reference Corpus Provisioning
1. Collect reference documents, technical standards, or regulatory specifications into an isolated research directory or documentation worktree (e.g. `docs/references/`).
2. Verify that input formats are supported (Markdown, OpenAPI specs, schema files, structured text).

### Step 2: Deep Extraction Execution
1. Trigger the deep multi-modal extraction:
   ```bash
   graphify extract docs/references/ --mode deep --out .synlynk/domain-graph-out/
   ```
2. **Cost Awareness Gate:** Confirm that deep extraction is invoked intentionally for reference corpora, keeping standard repository code discovery under the zero-cost `--code-only` default.

### Step 3: Evidentiary Querying & Ontology Mapping
1. Query the extracted domain graph to resolve specific domain relationships:
   - Example query: `"What are the mandatory fields for Observation resource in HL7 FHIR v4?"`
2. Extract verified node citations:
   - Source document, chapter, section, or line reference.
   - Identified entities and relationship triples.

### Step 4: PRD & Spec Authoring
1. Author the design specification or PRD in `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`:
   - Cite extracted standards nodes and ontology IDs directly in requirement acceptance criteria.
   - Map external schema requirements to internal Synlynk data models (`state.db`, JSON schemas).
2. Present spec for architectural and human sign-off before triggering implementation plans.

---

## Safety & Governance Guardrails
1. **Manual Invocation Gate:** `--mode deep` involves external multi-modal processing and token spend. It must NEVER be run in automated background daemon loops or CI pipelines without explicit human or PM authorization.
2. **Context Budgeting:** Use targeted queries through `query_graph(question)` rather than inlining large documentation extracts into active prompt contexts.
3. **Brainstorm-First Compliance:** All PRDs and specs produced via domain sweep must complete the brainstorming and review protocol before implementation tasks are dispatched.
