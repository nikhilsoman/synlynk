# Curated Markdown Sidecar Calibration

**Date:** 2026-11-25

**Goal:** `goal-34c225e1`

**Tracked decision:** [gh:#4937](https://github.com/nikhilsoman/synlynk/issues/4937)

**Calibration commit:** `6fa11f52`
**Graphify:** 0.9.67

## Decision

Adopt the curated deterministic Markdown sidecar, kept separate from the code
graph. The calibration meets the decision gate recorded in `dec-6d438fd0`:

- spec/goal citation coverage moves materially;
- the measured wrong-symbol rate is low, with a clear guardrail for the two
  observed false matches;
- extraction is local and uses zero model tokens;
- the core scan remains `graphify extract --code-only`; and
- `synlynk pr check`'s GOVERNS linkage does not provide document-to-symbol
  edges, so it does not close this retrieval gap.

This decision adopts the architecture, not the current implementation without
qualification. The shipped `synlynk/docgraph.py` walks all Markdown and indexes
file references with Synlynk's own parser. The calibrated path instead invokes
Graphify's `extract_markdown()` and `resolve_markdown_mentions()` directly over
the approved allowlist. Aligning the shipped implementation with this decision
is follow-up implementation work and is not part of this calibration task.

## Method

The code baseline was a fresh local extraction:

```text
graphify extract . --code-only --no-cluster --out <temporary-directory>
```

Graphify reported 1,129 code files, 15,644 nodes, and 38,290 edges. It skipped
1,637 non-code files and made no semantic extraction call. The sidecar dry-run
then called Graphify's local Markdown parser directly for these paths:

- `docs/superpowers/specs/**/*.md`
- `docs/superpowers/plans/**/*.md`
- `project-docs/decisions/**/*.md`
- `docs/rca/**/*.md`
- `.synlynk/skills/**/SKILL.md`
- `.synlynk/charters/**/*.md`

The run used the fresh code-only graph solely as the symbol-resolution corpus.
It did not merge document nodes into that graph or change scan, watch, or daemon
extraction flags.

## Results

| Measure | Result |
|---|---:|
| Allowlisted documents | 778 |
| Code-only wall time | 30.88 s |
| Markdown parse time | 1.10 s |
| Cross-graph resolution time | 0.21 s |
| Total sidecar overhead | 1.31 s (4.23%) |
| Extract-time model tokens | 0 |
| Document nodes | 9,928 |
| Document-only edges before code resolution | 9,188 |
| Inline symbol citations | 25,985 |
| Resolved code edges | 7,247 (27.89%) |
| Spec/goal-bearing citations | 14,769 |
| Spec/goal-bearing citations resolved | 3,193 (21.62%) |
| Path-qualified resolved edges | 49 |
| Unique-name inferred edges | 7,198 |

Two consecutive sidecar runs produced identical counts and the same structural
SHA-256:

```text
c2390ce479800b8bd6d46cf427e2cdf21cc73f293b89e418efcac7e5d6dd3db5
```

### Wrong-symbol audit

A deterministic SHA-256-ordered sample of 100 resolved edges was inspected
against the source line and resolved target. Two were false matches, for a 2%
observed wrong-symbol rate:

1. Bare `driver` in a statement about a configuration marker resolved to
   `synlynk/runners/manager.py:.driver()`.
2. Bare `migrate` naming a CLI command resolved to
   `tests/test_db.py:migrate()`.

All 49 path-qualified edges were structurally constrained to the cited file.
The false matches were both generic bare words. Therefore automatic Turn-1
injection must prefer path-qualified references and function/type-shaped unique
mentions. Generic bare-word inferred edges may remain queryable, but must not be
injected as authoritative context without corroborating file or ownership
evidence.

## GOVERNS comparison

The existing PR checks answer different questions:

- the GOVERNS warning checks whether a PR-attributed story has a linked goal;
- the roadmap drift gate checks decisions against roadmap state; and
- neither reads a document graph or resolves a specification citation to a code
  symbol.

Those checks establish ownership and lifecycle integrity, but they cannot supply
the 3,193 spec/goal-to-code edges found in this calibration. The sidecar closes
a distinct Turn-1 retrieval gap.

## Adoption constraints

- Keep `.synlynk/graphify-out/graph.json` code-only.
- Persist the Markdown result as a separate sidecar.
- Restrict ingestion to the calibrated allowlist.
- Use Graphify's local Markdown parser and resolver; do not add an LLM or
  network pass.
- Treat path-qualified edges as authoritative. Gate generic bare-word inferred
  edges from automatic context injection unless corroborated.
- Preserve the strict overall context-token budget when a consumer mounts the
  sidecar.
